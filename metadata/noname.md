#

- usar exiftool

Fluxo:

``` txt
    Entrada: Receber caminho do arquivo.

    Verificação de Ambiente:

        Detectar Sistema Operacional (Windows/Linux).

        Verificar disponibilidade das ferramentas necessárias (exiftool, strings ou binários equivalentes).

    Análise de Metadados e Estrutura:

        Obter metadados brutos do arquivo.

        Identificar assinatura real do arquivo (independente de extensão).

        Registrar tamanho em bytes.

    Extração de Conteúdo:

        Processar o binário para extração de caracteres legíveis (strings).

    Relatório:

        Agrupar resultados: [Tamanho + Identificação Técnica + Metadados + Strings].

        Apresentar na tela.

    Saída de Dados:

        Solicitar comando do usuário para persistência (salvar em arquivo).
```

Modo de uso:

```
lookin.py arquivo.exemplo
``` 