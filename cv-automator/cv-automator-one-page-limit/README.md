# Perfect CV

```
[Dados Base: JSON] ➔ [Orquestrador: Python] ➔ [IA: LLM API] ➔ [Validação: Pydantic] ➔ [Renderizador: Typst] ➔ [PDF Perfeito para ATS]
```

Geração automática de currículos ATS-friendly a partir de um Perfil Mestre em JSON e uma descrição de vaga.

---

## Pré-requisitos

- **Python 3.12+**
- **Typst** — [Instalar](https://github.com/typst/typst/releases)
- **Chave de API Groq** — [Obter gratuitamente](https://console.groq.com)

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
# Edite .env e adicione sua GROQ_API_KEY
```

---

## Configuração

Edite o arquivo `.env`:

```env
# Obrigatório
GROQ_API_KEY=gsk_...

# Opcional — padrão: groq
AI_PROVIDER=groq

# Opcional — padrão: llama-3.1-8b-instant (groq) | gemini-1.5-flash (gemini)
AI_MODEL=llama-3.1-8b-instant
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

### Groq (padrão)
```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
AI_MODEL=llama-3.1-8b-instant
# Alternativa mais capaz:
# AI_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
```

### Google Gemini
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=AI...
AI_MODEL=gemini-1.5-flash
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

Os dados do perfil são enviados apenas para o provedor configurado.
Tanto a Groq quanto o Google AI Studio oferecem opções de uso sem treinamento de modelos públicos.
Consulte os termos do provedor escolhido.
