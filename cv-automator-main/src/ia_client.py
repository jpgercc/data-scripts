"""
ia_client.py — Limpeza de vaga, construção de prompts e comunicação com IA.

Suporta Groq e Google Gemini.
Implementa retry com backoff exponencial para HTTP 429.
Chaves nunca aparecem em logs.
"""

import json
import logging
import re
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .config import settings

logger = logging.getLogger(__name__)

# ── Constantes de retry ───────────────────────────────────────
_MAX_ATTEMPTS = 4
_WAIT_MIN = 2   # segundos
_WAIT_MAX = 30  # segundos


# ─────────────────────────────────────────────────────────────
# Limpeza da vaga
# ─────────────────────────────────────────────────────────────

def _remove_urls(text: str) -> str:
    return re.sub(r"https?://\S+|www\.\S+", "", text)


def _remove_repeated_lines(text: str) -> str:
    seen: set[str] = set()
    lines = []
    for line in text.splitlines():
        normalized = line.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            lines.append(line)
    return "\n".join(lines)

# MELHORAR A REMOCAO DE RUIDO
def _remove_benefits_noise(text: str) -> str:
    """Remove padroes comuns de beneficios e ruido irrelevante."""
    noise_patterns = [
        r"(?i)(vale[\s-]?(refeição|alimentação|transporte|cultura|academia)[\s\S]{0,120})",
        r"(?i)(plano[\s-]?(de saúde|odontológico|médico)[\s\S]{0,120})",
        r"(?i)(seguro[\s-]?de vida[\s\S]{0,80})",
        r"(?i)(bônus|participação nos lucros|pli|ppr)[\s\S]{0,120}",
        r"(?i)(gympass|wellhub|totalpass)[\s\S]{0,80}",
        r"(?i)(política de diversidade[\s\S]{0,200})",
        r"(?i)(somos uma empresa[\s\S]{0,300})",
        r"(?i)(vaga afirmativa[\s\S]{0,200})",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text)
    return text


def clean_job_description(raw: str) -> str:
    """
    Limpa a descricao da vaga preservando apenas requisitos tecnicos
    e responsabilidades relevantes para o currculo.
    """
    text = _remove_urls(raw)
    text = _remove_benefits_noise(text)
    text = _remove_repeated_lines(text)
    # Colapsa múltiplas linhas em branco
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# 
# Construcao do prompt
# 

_SYSTEM_PROMPT = """\
Você é um especialista em currículos ATS (Applicant Tracking System).
Sua tarefa é adaptar um Perfil Mestre para uma vaga específica.

REGRAS OBRIGATÓRIAS:
1. Retorne EXCLUSIVAMENTE JSON válido, sem markdown, sem explicações.
2. Mantenha 100% de veracidade — não invente informações.
3. Priorize experiências e habilidades mais relevantes para a vaga.
4. O resumo deve ter entre 3 e 5 frases focadas nos requisitos da vaga.
5. Selecione no máximo 3 experiências mais relevantes.
6. Mantenha as responsabilidades como bullet points concisos e quantificados.
7. Em "habilidades", use um dict onde a chave é a categoria e o valor é uma lista de strings.

SCHEMA JSON ESPERADO:
{
  "nome": "string",
  "titulo": "string adaptado para a vaga",
  "email": "string",
  "telefone": "string",
  "linkedin": "string",
  "github": "string",
  "localizacao": "string",
  "resumo": "string de 3-5 frases",
  "experiencias": [
    {
      "empresa": "string",
      "cargo": "string",
      "periodo": "string",
      "responsabilidades": ["string", ...]
    }
  ],
  "habilidades": {
    "categoria": ["item1", "item2"]
  },
  "formacao": [
    {
      "instituicao": "string",
      "curso": "string",
      "periodo": "string"
    }
  ],
  "certificacoes": ["string"],
  "idiomas": [
    {"idioma": "string", "nivel": "string"}
  ]
}
"""


def build_prompt(perfil: dict[str, Any], vaga_limpa: str) -> str:
    perfil_json = json.dumps(perfil, ensure_ascii=False, indent=2)
    return (
        f"PERFIL MESTRE:\n{perfil_json}\n\n"
        f"DESCRIÇÃO DA VAGA:\n{vaga_limpa}\n\n"
        "Gere o JSON do currículo adaptado para esta vaga."
    )


# 
# Clientes de IA
# 

class RateLimitError(Exception):
    """Levantado quando a API retorna HTTP 429."""


def _parse_json_from_response(text: str) -> dict[str, Any]:
    """
    Extrai e parseia JSON de uma resposta de texto.
    Remove possíveis blocos de markdown residuais.
    """
    # Remove cercas de markdown caso a IA as inclua apesar da instrução
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    return json.loads(cleaned)


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=_WAIT_MIN, max=_WAIT_MAX),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_groq(prompt: str) -> dict[str, Any]:
    from groq import Groq, RateLimitError as GroqRateLimitError

    client = Groq(api_key=settings.groq_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.effective_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
    except GroqRateLimitError as exc:
        raise RateLimitError("Groq rate limit atingido.") from exc

    content = response.choices[0].message.content or ""
    return _parse_json_from_response(content)


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=_WAIT_MIN, max=_WAIT_MAX),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_gemini(prompt: str) -> dict[str, Any]:
    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.effective_model,
        system_instruction=_SYSTEM_PROMPT,
    )
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 4096},
        )
    except ResourceExhausted as exc:
        raise RateLimitError("Gemini rate limit atingido.") from exc

    return _parse_json_from_response(response.text)


# 
# Interface pública
# 

def generate_curriculum(perfil: dict[str, Any], vaga_raw: str) -> dict[str, Any]:
    """
    Ponto de entrada principal.

    1. Limpa a vaga.
    2. Constrói o prompt.
    3. Chama o provedor de IA configurado.
    4. Retorna o dict bruto para validação com Pydantic.
    """
    vaga_limpa = clean_job_description(vaga_raw)
    logger.debug("Vaga limpa (%d chars).", len(vaga_limpa))

    prompt = build_prompt(perfil, vaga_limpa)

    provider = settings.ai_provider.lower()
    if provider == "groq":
        return _call_groq(prompt)
    if provider == "gemini":
        return _call_gemini(prompt)

    raise ValueError(f"Provedor de IA desconhecido: '{provider}'. Use 'groq' ou 'gemini'.")
