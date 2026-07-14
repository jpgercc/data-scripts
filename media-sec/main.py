#!/usr/bin/env python3
"""
Verificador de arquivos — uso local (Ubuntu, linha de comando).

Este script é pensado para rodar na SUA máquina, de forma síncrona e via
CLI — não como parte de um serviço web multi-usuário. Por isso, os pontos
de um diagnóstico anterior sobre "loop de eventos assíncrono" e
"vazamento de FD entre threads/requisições de usuários diferentes" NÃO se
aplicam aqui: não há framework assíncrono, não há múltiplas requisições
concorrentes, e cada execução do script é um processo isolado.

Dito isso, os bugs REAIS apontados nesse diagnóstico (independente do
ambiente) foram corrigidos:

  - `escanear_virus` não bloqueia mais silenciosamente quando o antivírus
    falha ao rodar (fail-open corrigido para fail-closed, configurável).
  - O retorno de `_analisar_texto_com_yara` não é mais descartado: uma
    regra YARA disparada agora RESULTA em bloqueio/aviso propagado até o
    resultado final, e não apenas um print perdido no console.
  - `file` via subprocess foi substituído por `python-magic` (bindings
    nativos de libmagic, sem spawnar processo), com fallback documentado
    para subprocess caso a lib não esteja instalada.
  - `abrir_com_seguranca` virou um context manager (`ArquivoSeguro`),
    então o fechamento do file descriptor é garantido por construção
    (`__exit__`) mesmo se o código for refatorado/chamado isoladamente no
    futuro — não depende mais de o chamador lembrar de um `finally`.

Novidades pedidas:

  1. Análise de arquivos .py contra injeção de código E de caracteres
     ocultos, via módulo `ast` nativo + varredura de codepoints Unicode de
     formatação/controle (zero-width, RTL override, etc).
  2. Todas as variáveis de segurança/observabilidade (assinaturas, listas
     de comandos perigosos, timeouts, limites...) vivem em `config.json`,
     carregado relativo à localização do próprio script — não ao diretório
     de onde ele é chamado.
  3. Pode ser executado de qualquer diretório, apontando para qualquer
     caminho de arquivo (relativo ou absoluto), sem precisar mover o
     script para perto do alvo.
  4. Pode receber uma PASTA como alvo e analisa todos os arquivos
     regulares possíveis dentro dela (recursivo por padrão).

Dependências opcionais (instale para os caminhos "corretos"; sem elas o
script usa fallbacks mais fracos, sempre avisando no console):
    pip install python-magic yara-python python-clamd --break-system-packages
    sudo apt install libmagic1 clamav-daemon clamav-freshclam
"""

import argparse
import ast
import datetime
import json
import os
import stat
import subprocess
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Localização do script (para que config.json e regras.yar sejam sempre
# encontrados, não importa de onde o script seja chamado ou para onde
# aponte o arquivo/pasta alvo).
# ---------------------------------------------------------------------------

DIR_SCRIPT = Path(__file__).resolve().parent
CONFIG_PADRAO_PATH = DIR_SCRIPT / "config.json"


class ErroVerificacao(Exception):
    """Erro operacional (ferramenta ausente, timeout, config inválida...),
    distinto de "arquivo malicioso". Sempre tratado como fail-closed."""


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def carregar_config(caminho_config: Path) -> dict:
    if not caminho_config.exists():
        raise ErroVerificacao(
            f"Arquivo de configuração não encontrado: {caminho_config}\n"
            "Copie o config.json de exemplo para junto do script, ou aponte "
            "--config para um arquivo válido."
        )
    try:
        with open(caminho_config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ErroVerificacao(f"config.json inválido: {e}")

    # Resolve caminhos relativos ao script, não ao cwd.
    yara_rel = cfg.get("yara", {}).get("arquivo_regras")
    if yara_rel:
        cfg["yara"]["_arquivo_regras_abs"] = str((DIR_SCRIPT / yara_rel).resolve())

    return cfg


def expandir_usuario(caminho_str: str) -> Path:
    return Path(os.path.expanduser(caminho_str)).resolve()


# ---------------------------------------------------------------------------
# Abertura segura de arquivo (mitigação de TOCTOU) como context manager
# ---------------------------------------------------------------------------

class ArquivoSeguro:
    """
    Abre o arquivo uma única vez (O_NOFOLLOW) e expõe:
      - self.fd         : descritor aberto
      - self.proc_path  : "/proc/self/fd/<fd>", para usar em vez de reabrir
                           o caminho original por nome
      - self.tamanho    : tamanho em bytes (via fstat, sobre o mesmo fd)

    Sendo um context manager, o fechamento do fd é garantido no __exit__,
    mesmo que uma exceção ocorra no meio da análise — isso fecha o ponto
    levantado no diagnóstico sobre possível vazamento de FD em
    refatorações futuras que não passem pelo `finally` original.
    """

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.fd = None
        self.proc_path = None
        self.tamanho = None

    def __enter__(self):
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            self.fd = os.open(str(self.caminho), flags)
        except OSError as e:
            raise ErroVerificacao(f"Não foi possível abrir o arquivo com segurança: {e}")

        try:
            st = os.fstat(self.fd)
            if not stat.S_ISREG(st.st_mode):
                raise ErroVerificacao("Recusado: caminho não aponta para um arquivo regular.")
            self.tamanho = st.st_size
            self.proc_path = f"/proc/self/fd/{self.fd}"
        except Exception:
            self._fechar()
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._fechar()
        return False  # não suprime exceções

    def _fechar(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


def rodar_subprocesso(cmd, timeout, fd_a_herdar=None, **kwargs):
    """
    Wrapper único para subprocess.run: garante timeout e captura
    TimeoutExpired/FileNotFoundError de forma consistente.

    `fd_a_herdar`, quando informado, repassa esse fd via `pass_fds` — sem
    isso, um caminho "/proc/self/fd/<n>" no comando não funcionaria no
    processo filho, já que o Python marca fds como non-inheritable por
    padrão (PEP 446).
    """
    if fd_a_herdar is not None:
        kwargs["pass_fds"] = (fd_a_herdar,)
    try:
        return subprocess.run(cmd, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        raise ErroVerificacao(
            f"Comando '{cmd[0]}' excedeu o timeout de {timeout}s "
            "(possível tentativa de esgotar recursos / DoS)."
        )
    except FileNotFoundError:
        raise ErroVerificacao(f"Ferramenta '{cmd[0]}' não está instalada.")


# ---------------------------------------------------------------------------
# Identificação de tipo (MIME)
# ---------------------------------------------------------------------------

def obter_tipo_mime(arq: ArquivoSeguro, cfg: dict) -> str:
    """
    Prioriza python-magic (bindings nativos de libmagic, sem subprocess).
    Cai para `file -L` via subprocess apenas se a lib não estiver
    instalada. Nunca retorna uma string de erro como se fosse MIME —
    qualquer falha vira ErroVerificacao (fail-closed).
    """
    try:
        import magic  # pip install python-magic
        mime = magic.from_file(arq.proc_path, mime=True)
        if not mime:
            raise ErroVerificacao("python-magic não retornou um MIME type.")
        return mime
    except ImportError:
        pass

    print("Aviso: python-magic não instalado, usando 'file' via subprocess (mais lento).")
    resultado = rodar_subprocesso(
        ["file", "-L", "--mime-type", "-b", arq.proc_path],
        timeout=cfg["timeouts_segundos"]["file_cmd_fallback"],
        fd_a_herdar=arq.fd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if resultado.returncode != 0:
        raise ErroVerificacao(f"Comando 'file' retornou erro: {resultado.stderr.strip()}")
    mime = resultado.stdout.strip()
    if not mime:
        raise ErroVerificacao("Comando 'file' não retornou um MIME type.")
    return mime


def checar_poliglota_basico(arq: ArquivoSeguro, cfg: dict):
    """
    Heurística best-effort: procura assinaturas de mais de um formato
    incompatível (ex: binário + dado) nos primeiros N bytes. Não é uma
    solução formal contra poliglotas, apenas reduz o ponto cego de
    depender só do MIME.
    """
    n = cfg["limites"]["bytes_lidos_para_poliglota"]
    os.lseek(arq.fd, 0, os.SEEK_SET)
    cabecalho = os.read(arq.fd, n)
    os.lseek(arq.fd, 0, os.SEEK_SET)

    encontrados = []
    for item in cfg["assinaturas_poliglota"]["itens"]:
        magia = bytes.fromhex(item["hex"])
        if magia in cabecalho:
            encontrados.append(item)

    categorias = {item["categoria"] for item in encontrados}
    eh_poliglota = "binario" in categorias and "dado" in categorias
    return eh_poliglota, [i["nome"] for i in encontrados]


# ---------------------------------------------------------------------------
# Antivírus
# ---------------------------------------------------------------------------

def escanear_virus(arq: ArquivoSeguro, cfg: dict):
    """
    Retorna (status_str, bloqueado: bool).

    Tenta clamd (daemon, via socket) primeiro. Se indisponível, cai para
    `clamscan` CLI (se permitido na config). Se AMBOS falharem
    operacionalmente, o arquivo é tratado como "não verificado" — e, com
    `modo_fail_closed=true` (padrão), isso agora BLOQUEIA o arquivo em vez
    de deixá-lo passar silenciosamente, corrigindo o fail-open apontado no
    diagnóstico.
    """
    print("[*] Rodando verificação de vírus...")
    socket_path = cfg["clamd"]["socket_path"]

    try:
        import clamd  # pip install python-clamd
        cd = clamd.ClamdUnixSocket(path=socket_path)
        with open(arq.proc_path, "rb") as f:
            resposta = cd.instream(f)
        status, assinatura = resposta.get("stream", ("ERROR", "sem resposta"))
        if status == "OK":
            return "✓ Limpo (clamd)", False
        elif status == "FOUND":
            return f"❌ PERIGO: malware detectado pelo clamd ({assinatura})", True
        else:
            raise ErroVerificacao(f"clamd retornou status inesperado: {status}")
    except ImportError:
        pass
    except Exception:
        pass  # daemon indisponível — segue para o fallback

    if not cfg["seguranca"]["permitir_fallback_clamscan_cli"]:
        motivo = "clamd indisponível e fallback clamscan CLI desabilitado na config."
        bloqueado = cfg["seguranca"]["modo_fail_closed"]
        return f"Aviso: {motivo} (bloqueado={bloqueado})", bloqueado

    print(
        "Aviso: clamd indisponível, usando 'clamscan' via CLI (mais lento, "
        "carrega toda a base de assinaturas a cada execução)."
    )
    try:
        resultado = rodar_subprocesso(
            ["clamscan", "--no-summary", "--infected", arq.proc_path],
            timeout=cfg["timeouts_segundos"]["clamscan"],
            fd_a_herdar=arq.fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except ErroVerificacao as e:
        # Fail-closed real: se o antivírus não pôde rodar, o arquivo não foi
        # verificado — não presumimos que está limpo.
        bloqueado = cfg["seguranca"]["modo_fail_closed"]
        return f"Aviso: ClamAV não pôde ser executado ({e}). Tratado como não verificado.", bloqueado

    if resultado.returncode == 0:
        return "✓ Limpo (clamscan)", False
    elif resultado.returncode == 1:
        return f"❌ PERIGO: assinatura maliciosa encontrada!\n{resultado.stdout.strip()}", True
    else:
        bloqueado = cfg["seguranca"]["modo_fail_closed"]
        return (
            f"Aviso: clamscan retornou código inesperado ({resultado.returncode}). "
            f"Tratado como não verificado.",
            bloqueado,
        )


# ---------------------------------------------------------------------------
# Análise de texto genérico (YARA / fallback)
# ---------------------------------------------------------------------------

def _analisar_texto_com_yara(arq: ArquivoSeguro, cfg: dict):
    import yara  # pip install yara-python
    caminho_regras = cfg["yara"].get("_arquivo_regras_abs")
    if not caminho_regras or not os.path.exists(caminho_regras):
        raise ErroVerificacao(f"Arquivo de regras YARA não encontrado: {caminho_regras}")

    regras = yara.compile(filepath=caminho_regras)
    matches = regras.match(arq.proc_path, timeout=cfg["timeouts_segundos"]["yara"])

    if matches:
        detalhes = [
            {"regra": m.rule, "strings": [s.identifier for s in m.strings]}
            for m in matches
        ]
        return True, detalhes
    return False, []


def _analisar_texto_fallback(arq: ArquivoSeguro, cfg: dict):
    """
    Fallback frágil, mantido apenas para quando yara-python não está
    instalado. Sabidamente gera falsos positivos e é burlável por
    ofuscação simples.
    """
    print(
        "Aviso: yara-python não instalado — usando busca de substrings "
        "(fraca contra ofuscação e propensa a falsos positivos)."
    )
    comandos_perigosos = cfg["comandos_perigosos_texto_fallback"]
    max_linhas = cfg["limites"]["max_linhas_fallback_texto"]
    detalhes = []

    with open(arq.proc_path, "r", errors="ignore") as f:
        for i, linha in enumerate(f, 1):
            if i > max_linhas:
                print("Aviso: limite de linhas atingido, interrompendo auditoria de texto.")
                break
            for cmd in comandos_perigosos:
                if cmd in linha:
                    print(f"Linha {i}: encontrado termo suspeito '{cmd}'")
                    detalhes.append({"linha": i, "termo": cmd})

    if not detalhes:
        print("✓ Nenhum comando ou script suspeito encontrado no texto (heurística fraca).")

    return (len(detalhes) > 0), detalhes


def analisar_texto_generico(arq: ArquivoSeguro, cfg: dict):
    """
    Retorna (suspeito: bool, detalhes: list). O retorno agora É USADO pelo
    chamador — corrigindo o bug em que uma regra YARA disparada apenas
    imprimia no console e o arquivo seguia sendo tratado como limpo.
    """
    try:
        suspeito, detalhes = _analisar_texto_com_yara(arq, cfg)
        if suspeito:
            for d in detalhes:
                print(f"Regra YARA disparada: {d['regra']} (strings: {d['strings']})")
        else:
            print("✓ Nenhuma regra YARA disparada.")
        return suspeito, detalhes
    except ImportError:
        return _analisar_texto_fallback(arq, cfg)


# ---------------------------------------------------------------------------
# Análise de arquivos .py via AST + caracteres ocultos
# ---------------------------------------------------------------------------

def _nome_chamada(node: ast.Call):
    """Reconstrói o nome pontilhado de uma chamada (ex: 'os.system',
    'subprocess.run') a partir do AST, para comparar com a lista de
    chamadas perigosas da config."""
    func = node.func
    partes = []
    while isinstance(func, ast.Attribute):
        partes.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        partes.append(func.id)
    return ".".join(reversed(partes))


def _codepoints_ocultos_no_texto(texto: str, codepoints_suspeitos: set):
    """Varre o texto por codepoints Unicode de formatação/controle
    conhecidos por servirem para ofuscar código (zero-width, overrides de
    direção de texto, BOM embutido, etc). Retorna lista de ocorrências com
    linha e codepoint."""
    ocorrencias = []
    for num_linha, linha in enumerate(texto.splitlines(), 1):
        for ch in linha:
            cp = ord(ch)
            if cp in codepoints_suspeitos:
                ocorrencias.append(
                    {"linha": num_linha, "codepoint": f"U+{cp:04X}", "categoria": unicodedata.category(ch)}
                )
    return ocorrencias


def analisar_python(arq: ArquivoSeguro, cfg: dict):
    """
    Analisa um arquivo .py usando o módulo nativo `ast` (estrutura lógica
    real, não regex) combinado com varredura de caracteres ocultos.

    Retorna (suspeito: bool, detalhes: dict).
    """
    print("\n--- Auditoria de Código Python (AST) ---")
    detalhes = {"chamadas_perigosas": [], "imports_suspeitos": [], "caracteres_ocultos": [], "erro_sintaxe": None}
    suspeito = False

    with open(arq.proc_path, "rb") as f:
        bruto = f.read()

    texto = bruto.decode("utf-8", errors="surrogateescape")

    # 1) Caracteres ocultos/formatação — independem de o arquivo parsear como
    #    Python válido, então rodamos isso mesmo se o ast.parse falhar.
    codepoints_suspeitos = {
        int(h, 16) for h in cfg["caracteres_ocultos"]["codepoints_hex"]
    }
    ocorrencias = _codepoints_ocultos_no_texto(texto, codepoints_suspeitos)
    if ocorrencias:
        suspeito = True
        detalhes["caracteres_ocultos"] = ocorrencias
        for o in ocorrencias[:20]:
            print(f"Linha {o['linha']}: caractere oculto/formatação suspeito {o['codepoint']}")

    # 2) Estrutura lógica via AST.
    try:
        arvore = ast.parse(texto, filename=str(arq.caminho))
    except SyntaxError as e:
        detalhes["erro_sintaxe"] = str(e)
        print(
            f"Aviso: arquivo .py não é um Python sintaticamente válido ({e}). "
            "Isso por si só é suspeito para um .py legítimo."
        )
        # Sem AST não dá pra checar chamadas/imports, mas o arquivo já é
        # marcado como suspeito por causa disso.
        return True, detalhes

    chamadas_perigosas_cfg = set(cfg["python_ast"]["chamadas_perigosas"])
    modulos_suspeitos_cfg = set(cfg["python_ast"]["modulos_suspeitos"])

    tem_base64_import = False
    tem_exec_ou_eval = False

    for node in ast.walk(arvore):
        if isinstance(node, ast.Call):
            nome = _nome_chamada(node)
            if nome in chamadas_perigosas_cfg or nome.split(".")[-1] in chamadas_perigosas_cfg:
                suspeito = True
                detalhes["chamadas_perigosas"].append({"linha": node.lineno, "chamada": nome})
                print(f"Linha {node.lineno}: chamada potencialmente perigosa '{nome}'")
                if nome.split(".")[-1] in ("exec", "eval"):
                    tem_exec_ou_eval = True

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in modulos_suspeitos_cfg:
                    suspeito = True
                    detalhes["imports_suspeitos"].append({"linha": node.lineno, "modulo": alias.name})
                    print(f"Linha {node.lineno}: import suspeito '{alias.name}'")
                if alias.name == "base64":
                    tem_base64_import = True

        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in modulos_suspeitos_cfg:
                suspeito = True
                detalhes["imports_suspeitos"].append({"linha": node.lineno, "modulo": node.module})
                print(f"Linha {node.lineno}: import suspeito 'from {node.module}'")
            if node.module == "base64":
                tem_base64_import = True

    # Padrão clássico de ofuscação: importar base64 e usar exec/eval no mesmo
    # arquivo (ex: exec(base64.b64decode(...))).
    if cfg["python_ast"].get("combinacao_suspeita_base64_exec") and tem_base64_import and tem_exec_ou_eval:
        suspeito = True
        detalhes.setdefault("padroes", []).append("import base64 combinado com exec/eval no mesmo arquivo")
        print("Padrão suspeito: import de base64 combinado com exec/eval no mesmo arquivo.")

    if not suspeito:
        print("✓ Nenhuma chamada perigosa, import suspeito ou caractere oculto encontrado.")

    return suspeito, detalhes


# ---------------------------------------------------------------------------
# Análise de conteúdo (roteador por tipo)
# ---------------------------------------------------------------------------

def analisar_conteudo(arq: ArquivoSeguro, mime: str, caminho: Path, cfg: dict):
    """Retorna (suspeito: bool, detalhes: dict)."""
    print(f"[*] Analisando estrutura interna para tipo: {mime}")

    if caminho.suffix == ".py":
        return analisar_python(arq, cfg)

    if mime.startswith("text/") or mime == "application/json":
        print("\n--- Auditoria de Texto ---")
        if arq.tamanho > cfg["limites"]["max_text_size_bytes"]:
            msg = (
                f"arquivo de texto com {arq.tamanho} bytes excede o limite de "
                f"{cfg['limites']['max_text_size_bytes']} bytes para auditoria em memória."
            )
            print(f"BLOQUEADO: {msg}")
            return True, {"motivo": msg}
        suspeito, detalhes = analisar_texto_generico(arq, cfg)
        return suspeito, {"achados": detalhes}

    elif mime.startswith("video/"):
        print("\n--- Auditoria de Vídeo ---")
        try:
            resultado = rodar_subprocesso(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1",
                    arq.proc_path,
                ],
                timeout=cfg["timeouts_segundos"]["ffprobe"],
                fd_a_herdar=arq.fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if resultado.stderr:
                print("Avisos de estrutura/erros no container de vídeo:")
                print(resultado.stderr)
                return True, {"stderr_ffprobe": resultado.stderr}
            print("✓ Estrutura do container de vídeo válida e íntegra.")
            return False, {}
        except ErroVerificacao as e:
            print(f"Aviso: {e}")
            return cfg["seguranca"]["modo_fail_closed"], {"erro": str(e)}
    else:
        print("Tipo de arquivo não possui parser específico configurado.")
        return False, {}


# ---------------------------------------------------------------------------
# Orquestração — um único arquivo
# ---------------------------------------------------------------------------

def verificar_um_arquivo(caminho: Path, cfg: dict) -> dict:
    """Executa o pipeline completo em um único arquivo e retorna um dict
    estruturado com o resultado (usado tanto para print quanto para o log
    JSON de observabilidade)."""
    resultado = {
        "arquivo": str(caminho),
        "timestamp": datetime.datetime.now().isoformat(),
        "status": None,
        "motivo": None,
        "mime": None,
        "antivirus": None,
        "conteudo_suspeito": None,
        "detalhes_conteudo": None,
        "poliglota": None,
    }

    print("=" * 60)
    print(f"ANALISANDO: {caminho.name}")
    print("=" * 60)

    try:
        with ArquivoSeguro(caminho) as arq:
            if arq.tamanho > cfg["limites"]["max_file_size_bytes"]:
                msg = (
                    f"arquivo tem {arq.tamanho} bytes, acima do limite de "
                    f"{cfg['limites']['max_file_size_bytes']} bytes."
                )
                print(f"BLOQUEADO: {msg}")
                resultado.update(status="BLOQUEADO", motivo=msg)
                return resultado

            try:
                mime = obter_tipo_mime(arq, cfg)
            except ErroVerificacao as e:
                print(f"BLOQUEADO: não foi possível determinar o tipo real do arquivo ({e}).")
                resultado.update(status="BLOQUEADO", motivo=str(e))
                return resultado

            resultado["mime"] = mime
            print(f"[+] Tipo Real Detectado (MIME): {mime}")

            if any(assin in mime for assin in cfg["assinaturas_executaveis_mime"]):
                print("BLOQUEADO: Este arquivo finge ser dados, mas é um EXECUTÁVEL nativo!")
                resultado.update(status="BLOQUEADO", motivo="MIME de executável nativo")
                return resultado

            eh_poliglota, formatos = checar_poliglota_basico(arq, cfg)
            resultado["poliglota"] = formatos
            if eh_poliglota:
                print(
                    f"BLOQUEADO: assinaturas de múltiplos formatos incompatíveis "
                    f"detectadas no mesmo arquivo ({', '.join(formatos)})."
                )
                resultado.update(status="BLOQUEADO", motivo="Possível poliglota")
                return resultado

            status_virus, virus_bloqueia = escanear_virus(arq, cfg)
            resultado["antivirus"] = status_virus
            print(f"[+] Resultado Antivírus: {status_virus}")
            if virus_bloqueia:
                resultado.update(status="BLOQUEADO", motivo="Antivírus: infectado ou não verificado (fail-closed)")
                return resultado

            suspeito, detalhes_conteudo = analisar_conteudo(arq, mime, caminho, cfg)
            resultado["conteudo_suspeito"] = suspeito
            resultado["detalhes_conteudo"] = detalhes_conteudo

            if suspeito:
                resultado.update(status="SUSPEITO", motivo="Conteúdo sinalizado na auditoria")
            else:
                resultado.update(status="LIMPO", motivo=None)

    except ErroVerificacao as e:
        print(f"BLOQUEADO: {e}")
        resultado.update(status="BLOQUEADO", motivo=str(e))

    print("=" * 60 + "\n")
    return resultado


def _mover_para_quarentena(caminho: Path, cfg: dict):
    import shutil
    pasta = expandir_usuario(cfg["seguranca"]["pasta_quarentena"])
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / caminho.name
    try:
        shutil.move(str(caminho), str(destino))
        print(f"[!] Movido para quarentena: {destino}")
    except OSError as e:
        print(f"Aviso: falha ao mover para quarentena ({e}).")


def salvar_log_observabilidade(resultados: list, cfg: dict):
    if not cfg["observabilidade"]["salvar_json_por_arquivo"]:
        return None
    pasta_logs = expandir_usuario(cfg["observabilidade"]["pasta_logs"])
    pasta_logs.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_log = pasta_logs / f"relatorio_{ts}.json"
    with open(caminho_log, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    return caminho_log


# ---------------------------------------------------------------------------
# Orquestração — arquivo único ou pasta inteira
# ---------------------------------------------------------------------------

def coletar_arquivos(alvo: Path, recursivo: bool):
    if alvo.is_file():
        yield alvo
        return

    if alvo.is_dir():
        if recursivo:
            for raiz, _dirs, arquivos in os.walk(alvo):
                for nome in arquivos:
                    caminho = Path(raiz) / nome
                    if caminho.is_symlink():
                        continue  # symlinks são pulados por segurança (evita escapar da pasta alvo)
                    if caminho.is_file():
                        yield caminho
        else:
            for item in sorted(alvo.iterdir()):
                if item.is_symlink():
                    continue
                if item.is_file():
                    yield item


def processar_alvo(caminho_alvo: str, cfg: dict, recursivo: bool):
    alvo = expandir_usuario(caminho_alvo)
    if not alvo.exists():
        print(f"Erro: caminho não encontrado: {alvo}")
        return

    resultados = []
    for caminho in coletar_arquivos(alvo, recursivo):
        resultado = verificar_um_arquivo(caminho, cfg)
        resultados.append(resultado)
        if resultado["status"] == "BLOQUEADO" and cfg["seguranca"]["mover_para_quarentena"]:
            _mover_para_quarentena(caminho, cfg)

    if not resultados:
        print(f"Nenhum arquivo regular encontrado em: {alvo}")
        return

    limpos = sum(1 for r in resultados if r["status"] == "LIMPO")
    suspeitos = sum(1 for r in resultados if r["status"] == "SUSPEITO")
    bloqueados = sum(1 for r in resultados if r["status"] == "BLOQUEADO")

    print("#" * 60)
    print(f"RESUMO: {len(resultados)} arquivo(s) analisado(s)")
    print(f"  ✓ Limpos:     {limpos}")
    print(f"  ⚠ Suspeitos:  {suspeitos}")
    print(f"  ❌ Bloqueados: {bloqueados}")
    print("#" * 60)

    caminho_log = salvar_log_observabilidade(resultados, cfg)
    if caminho_log:
        print(f"Relatório detalhado salvo em: {caminho_log}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verificador de arquivos (MIME real, antivírus, YARA, AST para .py, poliglotas)."
    )
    parser.add_argument("caminho", help="Arquivo ou pasta a analisar (caminho absoluto ou relativo ao seu diretório atual).")
    parser.add_argument(
        "--config", default=str(CONFIG_PADRAO_PATH),
        help=f"Caminho para config.json (padrão: junto do script, {CONFIG_PADRAO_PATH})."
    )
    parser.add_argument(
        "--recursivo", action=argparse.BooleanOptionalAction, default=True,
        help="Se o alvo for uma pasta, entra em subpastas (padrão: sim). Use --no-recursivo para só o nível superior."
    )
    args = parser.parse_args()

    try:
        cfg = carregar_config(Path(args.config))
    except ErroVerificacao as e:
        print(f"Erro de configuração: {e}")
        sys.exit(1)

    processar_alvo(args.caminho, cfg, recursivo=args.recursivo)


if __name__ == "__main__":
    main()