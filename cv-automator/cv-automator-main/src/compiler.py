"""
compiler.py — Geração do arquivo Typst e compilação para PDF.

Responsabilidades:
- Escrever dados_curriculo.json no diretório de trabalho do Typst.
- Copiar o template .typ para o diretório de saída.
- Executar o binário `typst compile` para produzir o PDF.
- Garantir fontes incorporadas (padrão do Typst).
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import settings
from .models import Curriculum

logger = logging.getLogger(__name__)


def _find_typst() -> str:
    """
    Localiza o executável `typst` no PATH.
    Levanta FileNotFoundError se não encontrado.
    """
    binary = shutil.which("typst")
    if not binary:
        raise FileNotFoundError(
            "Binário `typst` não encontrado no PATH.\n"
            "Instale via: https://github.com/typst/typst/releases"
        )
    return binary


def compile_pdf(curriculum: Curriculum, output_filename: str) -> Path:
    """
    Gera o PDF a partir do currículo validado.

    Args:
        curriculum: Instância validada pelo Pydantic.
        output_filename: Nome do arquivo PDF de saída (sem caminho).

    Returns:
        Path absoluto para o PDF gerado.
    """
    typst_bin = _find_typst()
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    output_pdf = settings.output_dir / output_filename

    # Usa diretório temporário para isolar os arquivos de trabalho do Typst
    with tempfile.TemporaryDirectory(prefix="perfect_cv_") as workdir:
        workdir_path = Path(workdir)

        # 1. Escreve os dados como JSON (lido pelo template via json())
        data_file = workdir_path / "dados_curriculo.json"
        data_file.write_text(
            json.dumps(curriculum.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 2. Copia o template para o mesmo diretório (necessário para json() funcionar)
        template_dest = workdir_path / "curriculo.typ"
        shutil.copy2(settings.template_path, template_dest)

        # 3. Compila com Typst
        pdf_in_workdir = workdir_path / output_filename
        cmd = [
            typst_bin,
            "compile",
            str(template_dest),
            str(pdf_in_workdir),
            "--font-path", str(workdir_path),  # sem fontes extras; usa built-ins
        ]

        logger.info("Compilando PDF: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=workdir,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Typst falhou (código {result.returncode}):\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

        # 4. Move PDF para o diretório de saída definitivo
        shutil.move(str(pdf_in_workdir), str(output_pdf))

    logger.info("PDF gerado: %s", output_pdf.resolve())
    return output_pdf.resolve()
