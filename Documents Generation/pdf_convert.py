"""
Convert filled .docx to .pdf using LibreOffice headless (soffice).
Falls back to None if converter not installed (local dev without LibreOffice).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def _soffice_cmd() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def docx_to_pdf(docx_path: Path, pdf_path: Optional[Path] = None, timeout: int = 120) -> Optional[Path]:
    """
    Convert docx to pdf. Writes next to docx if pdf_path not given.
    Returns path to PDF or None if conversion failed / soffice missing.
    """
    docx_path = Path(docx_path).resolve()
    if not docx_path.exists():
        return None
    soffice = _soffice_cmd()
    if not soffice:
        return None
    out_dir = docx_path.parent
    if pdf_path:
        out_dir = Path(pdf_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(docx_path),
            ],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    produced = out_dir / (docx_path.stem + ".pdf")
    if not produced.exists():
        return None
    if pdf_path and produced.resolve() != Path(pdf_path).resolve():
        Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced), str(pdf_path))
        return Path(pdf_path)
    return produced
