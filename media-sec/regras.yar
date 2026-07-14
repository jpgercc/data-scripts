/*
    Regras usadas pelo verificador de arquivos para auditar conteúdo de
    texto/scripts. Mantidas em arquivo separado (versionável) em vez de
    embutidas no código, para que possam ser curadas/atualizadas sem tocar
    em main.py.

    Requer: pip install yara-python (e a lib nativa libyara instalada).
*/

rule ComandoPerigosoOfuscadoOuNao
{
    meta:
        descricao = "Comandos de shell/eval perigosos, com ou sem tentativa simples de ofuscação"
        severidade = "media"

    strings:
        $rm       = "rm -rf"
        $chmodx   = "chmod +x"
        $curl     = "curl "
        $wget     = "wget "
        $eval_py  = "eval("
        $exec_py  = "exec("
        $b64_hint = /[A-Za-z0-9+\/]{80,}={0,2}/  // possível blob base64 grande

    condition:
        any of them
}

rule ReverseShellComum
{
    meta:
        descricao = "Padrões comuns de reverse shell em bash/python/nc"
        severidade = "alta"

    strings:
        $sh1 = "/bin/sh -i"
        $sh2 = "/bin/bash -i"
        $nc1 = "nc -e"
        $py1 = "socket.SOCK_STREAM"
        $py2 = "subprocess.call([\"/bin/sh\""

    condition:
        any of them
}

rule OfuscacaoComCaracteresInvisiveis
{
    meta:
        descricao = "Presença de caracteres Unicode de formatação/controle invisíveis, frequentemente usados para esconder código"
        severidade = "alta"

    strings:
        $zw1 = { E2 80 8B } // ZERO WIDTH SPACE (U+200B)
        $zw2 = { E2 80 8C } // ZERO WIDTH NON-JOINER (U+200C)
        $zw3 = { E2 80 8D } // ZERO WIDTH JOINER (U+200D)
        $rtl = { E2 80 AE } // RIGHT-TO-LEFT OVERRIDE (U+202E)
        $bom = { EF BB BF } // BOM no meio do arquivo (fora do início) é suspeito

    condition:
        any of them
}