# Perfect CV

```
[Dados Base: JSON] ➔ [Orquestrador: Python] ➔ [IA: LLM API] ➔ [Validação: Pydantic] ➔ [Renderizador: Typst] ➔ [PDF Perfeito para ATS]
```

Geração automática de currículos ATS-friendly a partir de um Perfil Mestre em JSON e uma descrição de vaga.

---

## Pré-requisitos

- **Python 3.12+**
- **Typst** — [Instalar](https://github.com/typst/typst/releases)
- **9Router em execução** — [instalação e dashboard](https://9router.com/)
- **Chave de API do 9Router** — crie-a no dashboard do seu roteador

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/jpgercc/cv-automator.git
cd cv-automator

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env e adicione sua NINE_ROUTER_API_KEY
```

---

## Configuração

Edite o arquivo `.env`:

```env
# Obrigatório
NINE_ROUTER_API_KEY=sk_...

# Opcional — padrão: 9router
AI_PROVIDER=9router

# Opcional — URL local padrão do 9Router
NINE_ROUTER_BASE_URL=http://127.0.0.1:20128/v1

# Opcional — modelo ou Combo cadastrado no seu 9Router
AI_MODEL=cc/claude-opus-4-7
```

---

## Uso

### 1. Preencha seu Perfil Mestre

Edite `data/perfil_mestre.json` com suas informações reais.

### 2. Prepare a descrição da vaga

Salve o texto da vaga em um arquivo `.txt`, por exemplo: `data/minha_vaga.txt`

### 3. Execute

```bash
python main.py data/minha_vaga.txt
```

O PDF será salvo em `output/`.

### Opções adicionais

```bash
# Nome personalizado para o PDF
python main.py data/minha_vaga.txt --output CV_Joao_Senior_DevOps.pdf

# Perfil alternativo
python main.py data/minha_vaga.txt --perfil data/outro_perfil.json

# Testar com a vaga de exemplo incluída
python main.py data/vaga_exemplo.txt
```

---

## Estrutura do Projeto

```
cv-automator/
├── .env                    # Variáveis de ambiente (não comitar)
├── .env.example            # Exemplo de configuração
├── requirements.txt
├── main.py                 # Ponto de entrada / orquestrador
│
├── data/
│   ├── perfil_mestre.json  # Seu perfil completo
│   └── vaga_exemplo.txt    # Vaga de exemplo para teste
│
├── templates/
│   └── curriculo.typ       # Template Typst ATS-friendly
│
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuração centralizada (pydantic-settings)
│   ├── models.py           # Schemas Pydantic (validação da resposta da IA)
│   ├── ia_client.py        # Limpeza de vaga, prompts, comunicação com IA
│   └── compiler.py         # Geração Typst + compilação PDF
│
└── output/                 # PDFs gerados
```

---

## Provedores de IA

### 9Router (padrão)
```env
AI_PROVIDER=9router
NINE_ROUTER_API_KEY=sk_...
# O padrão atende à instalação local do 9Router.
NINE_ROUTER_BASE_URL=http://127.0.0.1:20128/v1
# Use um modelo ou Combo existente no seu dashboard.
AI_MODEL=cc/claude-opus-4-7
```

---

## Garantias ATS

- ✅ Texto 100% selecionável e pesquisável
- ✅ Sem rasterização (nenhum conteúdo como imagem)
- ✅ Ordem de leitura linear
- ✅ Fontes incorporadas no PDF
- ✅ Compatível com conversores PDF → TXT
- ✅ Caracteres especiais preservados
- ✅ PDF ajustado automaticamente para caber em 1 página; se não couber, a geração falha explicitamente

---

## Confiabilidade

- Retry automático com backoff exponencial (até 4 tentativas)
- Tratamento de HTTP 429 (rate limit)
- Validação Pydantic antes de qualquer geração
- Chaves de API nunca aparecem em logs

---

## Privacidade

Os dados do perfil são enviados ao 9Router e, por ele, ao modelo/Combo configurado.
Consulte os termos do 9Router e do provedor final selecionado.

## Problemas

- JSON não é fonte da verdade, o schema é baseado no ptyhon e não no JSON, ou seja o JSON precisa seguir um mock-pré fixado.<br>
    Atualmente:
    ```txtx
    `models.py` --> `compiler.py` tysp CV
    ```
    
    Sujestão:
    ```txt
    JSON --> `models.py` prepare data --> ia_client.py --> `compiler.py` tysp CV
    ```

- O prompt fica no python inves de ficar em um JSON.

**Ai sim o código começaria a fazer mais sentido inves de ser puro slop.**
