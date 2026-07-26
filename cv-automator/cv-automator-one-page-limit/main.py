"""
main.py — Orquestrador do Perfect CV.

Fluxo completo:
  [Perfil Mestre JSON] + [Descrição da Vaga]
  → Limpeza
  → LLM
  → Validação Pydantic
  → Geração Typst
  → Compilação PDF
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from src.config import settings
from src.ia_client import generate_curriculum
from src.models import Curriculum
from src.compiler import compile_pdf

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────
# Helpers de I/O
# ─────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Arquivo não encontrado: %s", path)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error("JSON inválido em %s: %s", path, exc)
        sys.exit(1)


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("Arquivo de vaga não encontrado: %s", path)
        sys.exit(1)


def _safe_slug(text: str) -> str:
    """Converte texto em slug seguro para nome de arquivo."""
    import re
    return re.sub(r"[^\w]+", "_", text.lower()).strip("_")


# ─────────────────────────────────────────────────────────────
# Fluxo principal
# ─────────────────────────────────────────────────────────────

def run(vaga_path: Path, output_name: str | None = None) -> Path:
    """
    Executa o fluxo completo para uma vaga.

    Args:
        vaga_path: Caminho para o arquivo .txt com a descrição da vaga.
        output_name: Nome do PDF de saída. Se None, gerado automaticamente.

    Returns:
        Path para o PDF gerado.
    """
    # 1. Validar configuração
    settings.validate_provider_key()

    # 2. Carregar perfil mestre
    logger.info("Carregando perfil mestre: %s", settings.perfil_path)
    perfil = _load_json(settings.perfil_path)

    # 3. Carregar descrição da vaga
    logger.info("Carregando vaga: %s", vaga_path)
    vaga_raw = _load_text(vaga_path)

    # 4. Chamar IA
    logger.info("Gerando currículo via IA (%s / %s)...", settings.ai_provider, settings.effective_model)
    raw_result = generate_curriculum(perfil, vaga_raw)

    # 5. Validar com Pydantic
    logger.info("Validando resposta da IA...")
    try:
        curriculum = Curriculum.model_validate(raw_result)
    except ValidationError as exc:
        logger.error("Resposta da IA inválida:\n%s", exc)
        sys.exit(1)

    # 6. Definir nome do PDF
    if not output_name:
        nome_slug = _safe_slug(curriculum.nome)
        titulo_slug = _safe_slug(curriculum.titulo)
        output_name = f"CV_{nome_slug}_{titulo_slug}.pdf"

    # 7. Compilar PDF
    logger.info("Compilando PDF: %s", output_name)
    pdf_path = compile_pdf(curriculum, output_name)

    logger.info("✅ Currículo gerado com sucesso: %s", pdf_path)
    return pdf_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perfect-cv",
        description="Gera currículos ATS-friendly a partir de um perfil JSON e uma vaga.",
    )
    parser.add_argument(
        "vaga",
        type=Path,
        help="Caminho para o arquivo .txt com a descrição da vaga.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Nome do arquivo PDF de saída (ex: CV_Joao_DevOps.pdf).",
    )
    parser.add_argument(
        "--perfil",
        type=Path,
        default=None,
        help="Caminho para o perfil mestre JSON (sobrescreve DATA_DIR/perfil_mestre.json).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Sobrescreve perfil se fornecido via CLI
    if args.perfil:
        settings.data_dir = args.perfil.parent
        # Redefinir perfil_path dinamicamente não é necessário pois
        # a property já computa a partir de data_dir; basta copiar:
        import shutil
        target = settings.data_dir / "perfil_mestre.json"
        if args.perfil != target:
            shutil.copy2(args.perfil, target)

    run(vaga_path=args.vaga, output_name=args.output)


if __name__ == "__main__":
    main()
