#!/usr/bin/env python3
"""
Export every AcroForm widget: field NAME (the PDF "ID") + PAGE + bounding box.

Run from repo folder:
  python scripts/export_pdf_field_positions.py

Outputs (next to assets/):
  FIELD_POSITIONS.json   — machine-readable
  FIELD_POSITIONS.md     — human: sorted by page, top-to-bottom, left-to-right

Use this to match ambiguous names (e.g. Texto5) to the printed Schengen labels.
Coordinates are PyMuPDF space: origin top-left of page, y increases downward, units = points (1/72 inch).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "assets" / "schengen_visa_application_form_english.pdf"
OUT_JSON = ROOT / "FIELD_POSITIONS.json"
OUT_MD = ROOT / "FIELD_POSITIONS.md"


def main() -> int:
    try:
        import fitz
    except ImportError:
        print("Install PyMuPDF: pip install pymupdf", file=sys.stderr)
        return 1

    if not PDF_PATH.exists():
        print(f"Missing template: {PDF_PATH}", file=sys.stderr)
        return 1

    doc = fitz.open(PDF_PATH)
    rows: list[dict] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        for w in page.widgets() or []:
            r = w.rect
            x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
            rows.append(
                {
                    "name": w.field_name or "",
                    "page": page_no,
                    "field_type": w.field_type_string,
                    "x0": round(x0, 2),
                    "y0": round(y0, 2),
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "width": round(x1 - x0, 2),
                    "height": round(y1 - y0, 2),
                    "center_x": round((x0 + x1) / 2, 2),
                    "center_y": round((y0 + y1) / 2, 2),
                }
            )

    doc.close()

    rows.sort(key=lambda r: (r["page"], r["center_y"], r["center_x"]))

    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Spain Schengen PDF – Field positions (name = AcroForm ID)",
        "",
        f"Generated from `{PDF_PATH.name}`. **Use `name` as the field ID** in `pdf_fields` or in `pdf_fill.py`.",
        "",
        "Coordinates: **top-left origin**, **y down**, **points** (72 pt = 1 inch).",
        "",
        "| Page | y (center) | x (center) | width × height | Type | Field name |",
        "|------|------------|------------|------------------|------|------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['page']} | {r['center_y']} | {r['center_x']} | {r['width']}×{r['height']} | {r['field_type']} | `{r['name']}` |"
        )
    lines.extend(
        [
            "",
            "## How to use",
            "",
            "1. Open the PDF in a viewer **next to** this table (or print the form).",
            "2. Find the printed label (e.g. “Date of birth”) and see which row’s **position** matches that box.",
            "3. Note the **Field name** — that is the exact string for `pdf_fields` or for `TEXTO_FIELD_MAP` in `pdf_fill.py`.",
            "4. Re-run this script after replacing `assets/schengen_visa_application_form_english.pdf` if BLS updates the file.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {len(rows)} fields to {OUT_JSON.name} and {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
