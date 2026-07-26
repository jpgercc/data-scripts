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
from dataclasses import dataclass
from pathlib import Path

from .config import settings
from .models import Curriculum

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayoutPreset:
    name: str
    title: str


LAYOUT_PRESETS: tuple[LayoutPreset, ...] = (
    LayoutPreset(name="balanced", title="balanced"),
    LayoutPreset(name="compact-1", title="compact-1"),
    LayoutPreset(name="compact-2", title="compact-2"),
    LayoutPreset(name="compact-3", title="compact-3"),
)


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


def _find_pdfinfo() -> str:
    """
    Localiza o executável `pdfinfo` no PATH.
    Levanta FileNotFoundError se não encontrado.
    """
    binary = shutil.which("pdfinfo")
    if not binary:
        raise FileNotFoundError(
            "Binário `pdfinfo` não encontrado no PATH.\n"
            "Instale o pacote Poppler para validar a quantidade de páginas."
        )
    return binary


def _page_count(pdf_path: Path) -> int:
    """
    Lê a contagem de páginas do PDF gerado.
    """
    pdfinfo_bin = _find_pdfinfo()
    result = subprocess.run(
        [pdfinfo_bin, str(pdf_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"pdfinfo falhou (código {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())

    raise RuntimeError(f"Não foi possível identificar a quantidade de páginas em {pdf_path}.")


def _render_payload(curriculum: Curriculum, layout_preset: str) -> dict:
    payload = curriculum.model_dump()
    payload["layout"] = {"preset": layout_preset}
    return payload


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

        # Copia o template para o mesmo diretório (necessário para json() funcionar)
        template_dest = workdir_path / "curriculo.typ"
        shutil.copy2(settings.template_path, template_dest)
        pdf_in_workdir = workdir_path / output_filename
        last_page_count = None
        last_error = None

        for preset in LAYOUT_PRESETS:
            data_file = workdir_path / "dados_curriculo.json"
            data_file.write_text(
                json.dumps(
                    _render_payload(curriculum, preset.name),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            cmd = [
                typst_bin,
                "compile",
                str(template_dest),
                str(pdf_in_workdir),
                "--font-path",
                str(workdir_path),  # sem fontes extras; usa built-ins
            ]

            logger.info("Compilando PDF [%s]: %s", preset.title, " ".join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=workdir,
            )

            if result.returncode != 0:
                last_error = (
                    f"Typst falhou no preset {preset.title} (código {result.returncode}):\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )
                continue

            last_page_count = _page_count(pdf_in_workdir)
            logger.info("PDF gerado no preset %s com %s página(s).", preset.title, last_page_count)

            if last_page_count == 1:
                shutil.move(str(pdf_in_workdir), str(output_pdf))
                break

            last_error = (
                f"O preset {preset.title} produziu {last_page_count} páginas."
            )
        else:
            raise RuntimeError(
                "Não foi possível reduzir o currículo para 1 página.\n"
                f"Último resultado: {last_error}\n"
                "Ajuste manualmente o conteúdo do currículo de origem para caber em uma página."
            )

        if last_page_count != 1:
            raise RuntimeError(
                "Falha inesperada ao validar o PDF final."
            )

    logger.info("PDF gerado: %s", output_pdf.resolve())
    return output_pdf.resolve()
