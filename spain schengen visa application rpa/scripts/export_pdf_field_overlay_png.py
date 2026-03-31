#!/usr/bin/env python3
"""
Render each PDF page to PNG with field names drawn in red (mapping aid).

  python scripts/export_pdf_field_overlay_png.py

Writes: debug_screenshots/field_overlay_page_1.png, ...
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "assets" / "schengen_visa_application_form_english.pdf"
OUT_DIR = ROOT / "debug_screenshots"


def main() -> int:
    try:
        import fitz
    except ImportError:
        print("pip install pymupdf", file=sys.stderr)
        return 1

    if not PDF_PATH.exists():
        print(f"Missing {PDF_PATH}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(PDF_PATH)
    n = len(doc)
    doc.close()

    for i in range(n):
        doc = fitz.open(PDF_PATH)
        page = doc.load_page(i)
        for w in page.widgets() or []:
            r = w.rect
            label = (w.field_name or "?")[:45]
            # Slightly above top-left of box
            pt = fitz.Point(r.x0, max(r.y0 - 1, 10))
            page.insert_text(pt, label, fontsize=5, color=(1, 0, 0))
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        out = OUT_DIR / f"field_overlay_page_{i + 1}.png"
        pix.save(out.as_posix())
        doc.close()

    print(f"Wrote {n} files under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
