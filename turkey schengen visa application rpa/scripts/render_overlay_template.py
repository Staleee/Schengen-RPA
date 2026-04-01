#!/usr/bin/env python3
"""
Render the template PDF pages to PNG for manual coordinate mapping.

Writes:
  debug_screenshots/page_1.png, page_2.png, ...

After that you can open the PNG, pick x/y coordinates (use a viewer) and fill mapping.json.
If you want an interactive click-to-capture tool, ask and we’ll add it.
"""

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "assets" / "turkey_schengen_form.pdf"
OUT = ROOT / "debug_screenshots"


def main() -> None:
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF} (put the real Turkey PDF there)")
    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(PDF))
    try:
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            out = OUT / f"page_{i+1}.png"
            pix.save(out.as_posix())
            print("wrote", out)
    finally:
        doc.close()


if __name__ == "__main__":
    main()

