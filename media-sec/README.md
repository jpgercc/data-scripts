# Verificador de Arquivos

Um verificador de arquivos para uso **local** em Linux (Ubuntu), projetado segundo o princípio de **negação por padrão (fail-closed)** e baseado em múltiplas camadas independentes de validação.

O objetivo não é apenas detectar malware conhecido, mas reduzir superfícies de ataque comuns envolvendo arquivos maliciosos, conteúdo ofuscado, poliglotas, scripts perigosos e tentativas de evasão.

# Resumo

O projeto implementa uma estratégia de **defesa em profundidade**, onde múltiplas verificações independentes são executadas antes que um arquivo seja considerado confiável.

A combinação de identificação do tipo real, mitigação de TOCTOU, detecção de poliglotas, antivírus, análise estrutural via AST, inspeção de caracteres Unicode ocultos e regras YARA fornece uma metodologia mais robusta do que depender exclusivamente de assinaturas antivírus ou da extensão do arquivo.

---

# Filosofia

Ao invés de confiar em uma única ferramenta (como um antivírus), este projeto utiliza uma **metodologia em camadas**, onde cada etapa tenta responder uma pergunta específica.

Caso alguma etapa crítica não possa ser executada corretamente, o sistema considera que **não possui informação suficiente para afirmar que o arquivo é seguro**.

Por isso, o comportamento padrão é:

> **Na dúvida, bloquear.**

Esse princípio evita o problema conhecido como **fail-open**, onde falhas internas acabam permitindo que arquivos sejam aceitos sem terem sido realmente verificados.

---

# Metodologia

O fluxo completo é composto pelas etapas abaixo.

```
Arquivo
   │
   ▼
Abertura segura
   │
   ▼
Identificação do MIME real
   │
   ▼
Detecção de poliglotas
   │
   ▼
Antivírus
   │
   ▼
Auditoria de conteúdo
   │
   ▼
Resultado final
```

Cada etapa possui um objetivo específico.

---

# 1. Abertura segura (TOCTOU Mitigation)

Antes de qualquer análise, o arquivo é aberto apenas uma única vez utilizando:

- `O_NOFOLLOW`
- `fstat()`
- `/proc/self/fd/<fd>`

Isso reduz ataques conhecidos de **TOCTOU (Time Of Check, Time Of Use)**.

Ao invés de reabrir o caminho diversas vezes, todas as ferramentas utilizam o mesmo descritor de arquivo.

Isso garante que o arquivo analisado seja exatamente o mesmo durante toda a execução.

Além disso, o descritor é encapsulado em um **Context Manager**, garantindo fechamento automático mesmo em caso de exceções.

---

# 2. Identificação do tipo real

A extensão do arquivo nunca é considerada confiável.

O projeto identifica o tipo utilizando:

- `python-magic`
- `libmagic`

Caso essa biblioteca não esteja disponível, utiliza:

```
file --mime-type
```

como fallback.

Assim, um arquivo chamado:

```
foto.jpg
```

mas contendo um executável ELF será identificado corretamente.

---

# 3. Bloqueio de executáveis disfarçados

Após identificar o MIME real, o sistema verifica se o conteúdo corresponde a tipos executáveis.

Exemplos:

- ELF
- PE (Windows)
- Executáveis nativos

Caso um executável esteja mascarado como documento, imagem ou outro formato, o arquivo é imediatamente bloqueado.

---

# 4. Detecção de arquivos poliglota

Arquivos poliglota possuem duas ou mais estruturas válidas simultaneamente.

Exemplo:

- PNG + ZIP
- PDF + JavaScript
- GIF + Executável

A metodologia faz uma busca por assinaturas mágicas (magic bytes) incompatíveis coexistindo no mesmo arquivo.

Embora seja uma heurística, ela reduz significativamente falsos negativos decorrentes da simples análise de MIME.

---

# 5. Antivírus

A etapa seguinte procura malware conhecido.

Prioridade:

```
python-clamd
        │
        ▼
    clamd daemon
```

Caso indisponível:

```
clamscan
```

Se ambas as opções falharem e o modo **fail-closed** estiver ativo, o arquivo é tratado como:

> Não verificado.

e é bloqueado.

Isso elimina um problema comum onde falhas do antivírus fazem arquivos serem considerados limpos sem terem sido escaneados.

---

# 6. Auditoria de conteúdo

Após verificar a estrutura externa do arquivo, o projeto analisa seu conteúdo.

A estratégia varia conforme o tipo detectado.

---

## Arquivos Python

Arquivos `.py` recebem uma auditoria estrutural utilizando o módulo nativo:

```
ast
```

Ao invés de procurar texto com regex, o código é transformado em uma árvore sintática.

São procurados padrões como:

- exec()
- eval()
- os.system()
- subprocess
- imports suspeitos
- combinações de Base64 + exec/eval

Esse método é muito mais robusto contra pequenas alterações de sintaxe.

---

## Caracteres Unicode ocultos

Além da AST, o projeto procura caracteres Unicode frequentemente utilizados para ofuscação.

Exemplos:

- Zero Width Space
- Right-To-Left Override
- Left-To-Right Override
- BOM embutido
- caracteres invisíveis

Esses caracteres podem alterar visualmente o código sem alterar seu comportamento.

Todos são configuráveis via `config.json`.

---

## Arquivos de texto

Quando disponível:

- YARA

é utilizado para detectar padrões maliciosos.

Na ausência da biblioteca:

```
yara-python
```

o sistema utiliza um fallback simples baseado em busca de substrings configuráveis.

Embora menos robusto, o comportamento continua previsível e documentado.

---

## Vídeos

Arquivos de vídeo são validados utilizando:

```
ffprobe
```

Erros estruturais do container são tratados como indícios de corrupção ou conteúdo suspeito.

---

# Configuração

Toda a lógica operacional é externa ao código.

As decisões ficam centralizadas em:

```
config.json
```

Entre elas:

- timeouts
- assinaturas
- regras YARA
- limites de tamanho
- MIME proibidos
- chamadas AST perigosas
- módulos suspeitos
- quarentena
- logs
- comportamento fail-closed

Isso permite alterar políticas de segurança sem modificar o código-fonte.

---

# Observabilidade

Cada execução pode gerar um relatório JSON contendo:

- arquivo analisado
- timestamp
- MIME identificado
- resultado do antivírus
- indicadores de conteúdo suspeito
- motivo do bloqueio
- detalhes técnicos

Esses relatórios permitem auditoria posterior e integração com outras ferramentas.

---

# Arquitetura

A análise segue o princípio de responsabilidade única.

Cada componente possui uma função específica.

```
CLI
 │
 ▼
Configuração
 │
 ▼
Abertura Segura
 │
 ▼
Identificação MIME
 │
 ▼
Poliglota
 │
 ▼
Antivírus
 │
 ▼
Auditoria de Conteúdo
 │
 ▼
Resultado
 │
 ▼
Log JSON
```

Essa separação facilita manutenção, testes e futuras extensões.

---

# Princípios de segurança adotados

- Fail-Closed
- Defesa em profundidade (Defense in Depth)
- Menor confiança possível na entrada
- Não confiar na extensão do arquivo
- Não reutilizar caminhos após validação
- Configuração desacoplada do código
- Observabilidade completa
- Timeouts para impedir consumo excessivo de recursos
- Uso de múltiplos mecanismos independentes de detecção

---

# Limitações

Nenhum mecanismo de segurança garante detecção absoluta.

Este projeto utiliza:

- heurísticas;
- assinaturas;
- análise estrutural;
- validação de formato;
- AST;
- antivírus.

Ainda assim, novas técnicas de evasão podem surgir.

O objetivo da metodologia é **reduzir significativamente a superfície de ataque**, tornando necessária a superação de múltiplas camadas independentes em vez de apenas uma única verificação.

---

# Requisitos

Python 3.10+

Dependências opcionais:

```bash
pip install python-magic yara-python python-clamd
```

Pacotes do sistema:

```bash
sudo apt install libmagic1 clamav-daemon clamav-freshclam
```

---

# Execução

Analisar um arquivo:

```bash
python verificador.py arquivo.ext
```

Analisar uma pasta inteira:

```bash
python verificador.py /caminho/da/pasta
```

Sem recursão:

```bash
python verificador.py /caminho/da/pasta --no-recursivo
```

Utilizando outro arquivo de configuração:

```bash
python verificador.py arquivo.ext --config minha_config.json
```

---

