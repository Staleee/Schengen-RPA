"""Rect-based coordinate-overlay filler for flat (non-AcroForm) Schengen visa templates.

The Italy / Portugal / Greece / Bulgaria templates are flat PDFs (no AcroForm widgets). Rather
than write text at a single baseline point (which overlaps wrapped labels and spills across cell
borders), every value is placed **inside a bounded cell rectangle**:

  * Text is rendered with PyMuPDF ``insert_textbox`` into the rect, so it wraps and stays inside
    the cell. The font auto-shrinks until the text fits the rect (down to ``min_fontsize``).
  * Checkbox marks are drawn as two crisp diagonal strokes inside the detected box rect.

Each country ships a spec map (``countries/<country>_overlay.json`` or an in-code dict). Per
logical key:

    text : {"page": 1, "rect": [x0, y0, x1, y1], "align": "left"|"center",
            "valign": "bottom"|"top"|"center", "fontsize": 9, "min_fontsize": 6,
            "multiline": false}
    check: {"page": 1, "check": true, "box": [x0, y0, x1, y1]}

Rects come from scripts/build_overlay_mapping.py (cell-containment: each value is bounded by the
form's own ruling lines) and must be visually verified against a rendered PNG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

_FONT = "helv"
_ALIGN = {"left": fitz.TEXT_ALIGN_LEFT, "center": fitz.TEXT_ALIGN_CENTER, "right": fitz.TEXT_ALIGN_RIGHT}


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _fit_fontsize(text: str, width: float, base: float, minimum: float) -> float:
    """Largest fontsize (<= base, >= minimum) whose single longest word fits the width."""
    longest = max(text.split(), key=len, default=text)
    size = base
    while size > minimum:
        if fitz.get_text_length(longest, fontname=_FONT, fontsize=size) <= width - 2:
            break
        size -= 0.5
    return size


def _draw_text(page, spec: Dict[str, Any], text: str) -> None:
    x0, y0, x1, y1 = (float(v) for v in spec["rect"])
    rect = fitz.Rect(x0, y0, x1, y1)
    align = _ALIGN.get(str(spec.get("align", "left")), fitz.TEXT_ALIGN_LEFT)
    base = float(spec.get("fontsize", 9.0))
    minimum = float(spec.get("min_fontsize", 6.5))
    multiline = bool(spec.get("multiline", False))

    if multiline:
        # Shrink until the wrapped text fits the box height (insert_textbox returns >=0 on fit).
        size = base
        while size >= minimum:
            rc = page.insert_textbox(rect, text, fontname=_FONT, fontsize=size, align=align,
                                     color=(0, 0, 0), render_mode=0)
            if rc >= 0:
                return
            size -= 0.5
        # Last resort: draw at the minimum size (may clip) so the value is not silently dropped.
        page.insert_textbox(rect, text, fontname=_FONT, fontsize=minimum, align=align, color=(0, 0, 0))
        return

    # Single line: fit to width, then baseline-place by valign inside the rect.
    size = _fit_fontsize(text, rect.width, base, minimum)
    ascent, descent = 0.8 * size, 0.2 * size
    valign = str(spec.get("valign", "bottom"))
    if valign == "top":
        baseline = rect.y0 + ascent
    elif valign == "center":
        baseline = (rect.y0 + rect.y1) / 2 + (ascent - descent) / 2
    else:  # bottom (sits just above the cell's lower rule)
        baseline = rect.y1 - descent
    tw = fitz.get_text_length(text, fontname=_FONT, fontsize=size)
    if align == fitz.TEXT_ALIGN_CENTER:
        x = rect.x0 + max(0.0, (rect.width - tw) / 2)
    elif align == fitz.TEXT_ALIGN_RIGHT:
        x = rect.x1 - tw
    else:
        x = rect.x0
    page.insert_text(fitz.Point(x, baseline), text, fontname=_FONT, fontsize=size, color=(0, 0, 0))


def _draw_check(page, box: List[float]) -> None:
    x0, y0, x1, y1 = (float(v) for v in box)
    r = fitz.Rect(x0, y0, x1, y1)
    inset = min(r.width, r.height) * 0.18
    a = fitz.Point(r.x0 + inset, r.y0 + inset)
    b = fitz.Point(r.x1 - inset, r.y1 - inset)
    c = fitz.Point(r.x0 + inset, r.y1 - inset)
    d = fitz.Point(r.x1 - inset, r.y0 + inset)
    w = max(0.7, min(r.width, r.height) * 0.12)
    page.draw_line(a, b, color=(0, 0, 0), width=w)
    page.draw_line(c, d, color=(0, 0, 0), width=w)


def fill_overlay_pdf(
    template: Path,
    values: Dict[str, Any],
    overlay_map: Dict[str, Dict[str, Any]],
    redact_strings: Optional[list] = None,
) -> bytes:
    if not template.exists():
        raise FileNotFoundError(f"Missing overlay template PDF: {template}")

    doc = fitz.open(str(template))
    try:
        # Optional: clear baked-in sample text (only for pre-filled sample templates).
        for s in (redact_strings or []):
            if not s:
                continue
            for page in doc:
                for r in page.search_for(str(s)):
                    page.add_redact_annot(r, fill=(1, 1, 1))
                page.apply_redactions()

        for key, spec in overlay_map.items():
            page_index = int(spec.get("page", 1)) - 1
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            if spec.get("check"):
                if _truthy(values.get(key)) and spec.get("box"):
                    _draw_check(page, spec["box"])
                continue
            val = values.get(key)
            if key not in values or val in (None, ""):
                continue
            if "rect" not in spec:
                continue
            _draw_text(page, spec, str(val))
        return doc.tobytes()
    finally:
        doc.close()
