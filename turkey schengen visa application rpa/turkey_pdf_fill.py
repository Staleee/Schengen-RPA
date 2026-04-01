"""
Turkey Schengen – PDF filler (coordinate-based).

This is for PDFs that have NO AcroForm fields. We draw text onto the PDF at coordinates.

Workflow:
1) Put the real PDF into assets/turkey_schengen_form.pdf
2) Run scripts/render_overlay_template.py to generate PNGs
3) Create mapping.json with coordinates for each key
4) POST /fill-pdf with the request body; we draw values and return PDF
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import fitz  # PyMuPDF

DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "assets" / "turkey_schengen_form.pdf"
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "mapping.json"


@dataclass(frozen=True)
class FieldPos:
    page: int
    x: float
    y: float
    font_size: float = 9.0


def _load_mapping(path: Path) -> Dict[str, FieldPos]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, FieldPos] = {}
    for key, v in (data.get("fields") or {}).items():
        out[str(key)] = FieldPos(
            page=int(v["page"]),
            x=float(v["x"]),
            y=float(v["y"]),
            font_size=float(v.get("font_size", 9.0)),
        )
    return out


def fill_turkey_pdf(
    payload: Dict[str, Any],
    template_path: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
) -> bytes:
    pdf_path = template_path or DEFAULT_TEMPLATE
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing template PDF: {pdf_path}")

    mpath = mapping_path or DEFAULT_MAPPING_PATH
    if not mpath.exists():
        raise FileNotFoundError(f"Missing mapping file: {mpath} (create it after generating overlays)")

    mapping = _load_mapping(mpath)

    doc = fitz.open(str(pdf_path))
    try:
        for key, pos in mapping.items():
            if key not in payload:
                continue
            val = payload.get(key)
            if val is None:
                continue
            page_index = pos.page - 1
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            page.insert_text(
                fitz.Point(pos.x, pos.y),
                str(val),
                fontsize=pos.font_size,
                color=(0, 0, 0),
            )
        return doc.tobytes()
    finally:
        doc.close()

