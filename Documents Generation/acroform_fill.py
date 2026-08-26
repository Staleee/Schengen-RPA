"""
Fill an AcroForm (fillable) PDF by field name, then flatten it to static content.

Used by the Schengen maid NOC (``Travel_NOC_Fillable.pdf``), a genuine two-page
English + Arabic AcroForm where every blank is a real form field (unlike the flat
{{placeholder}} affidavit / client-noc PDFs handled by ``affidavit_fill.py``).

The template is a flat letter with form fields laid over the gaps, so a value cannot
reflow the sentence around it — it gets only the gap the template author left. Filling
therefore works in three steps per value, cheapest first, so the result reads as part of
the letter instead of as shrunken form input:

1. Typeset at the letter's own body size (``_BODY_FONTSIZE``), not the 9pt the template
   stores on its widgets.
2. If the value is wider than its gap, grow the field into adjacent whitespace and push
   the rest of that line right, as far as the right margin allows. English page only:
   the Arabic page runs right-to-left, its static text is stored as shaped glyph runs
   that cannot be re-drawn, and its Arabic span boxes are too tall to tell reliably
   which side of a field is free — widening there lands values on top of the text.
3. Only if it still overflows, shrink the text — never clip it, since losing characters
   is worse than small text. ``fill_acroform_pdf_with_report`` names the fields that had
   to go below ``_MIN_FONTSIZE``: their gap in the template is too narrow for real data.

Fields with no value are deleted rather than left blank — an unfilled widget bakes its
grey border into the output as an empty box.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

# Control chars break PDF text; strip them from substituted values.
_INVALID_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# The template's body text is Times-Roman 11pt — fill at the same size so values blend
# into the sentence. (The widgets carry a 9pt default, which is why every value used to
# print visibly smaller than the text around it.)
_BODY_FONTSIZE = 11.0
# Readable floor: below this a value is reported as not fitting its gap. Shrinking still
# continues past it, because clipping the value would lose characters outright.
_MIN_FONTSIZE = 8.0
_ABS_MIN_FONTSIZE = 4.0

# The template body is Times New Roman; fill fields in Times-Roman (the Base-14 twin)
# so values blend in instead of standing out as sans-serif Helvetica.
_FIELD_FONT = "TiRo"
_FIELD_FONT_METRICS = "tiro"

# Text column of the letter (both pages share it).
_LEFT_MARGIN = 71.5
_RIGHT_MARGIN = 543.0
# Keep a filled value this far clear of the static text beside it.
_EDGE_PAD = 1.0
# Widgets/spans whose vertical centres are this close sit on the same line.
_LINE_TOL = 5.0
# Static text below this size is the page footer, never part of a filled line.
_BODY_MIN_SIZE = 10.0

# The Schengen NOC is a fixed two-page English + Arabic form. Two fields on the Arabic
# page are constants whose correct rendering is authored static Arabic text
# (employment_basis, trip_purpose) — pymupdf cannot shape Arabic inside a form-field
# appearance, so those widgets are dropped and the static text underneath shows through
# (see scripts/patch_noc_schengen_template.py).
_ENGLISH_PAGE_INDEX = 0
_ARABIC_PAGE_INDEX = 1
_ARABIC_STATIC_FIELDS = ("employment_basis", "trip_purpose")

# Static spans get re-drawn when a line is pushed right; map the template's embedded font
# names onto the Base-14 equivalents pymupdf can write with.
_BASE14 = {
    "Times-Roman": "tiro",
    "Times-Bold": "tibo",
    "Times-Italic": "tiit",
    "Times-BoldItalic": "tibi",
    "TimesNewRomanPSMT": "tiro",
    "TimesNewRomanPS-BoldMT": "tibo",
    "TimesNewRomanPS-ItalicMT": "tiit",
    "Helvetica": "helv",
    "Helvetica-Bold": "hebo",
}

# One entry of a laid-out line: (widget index or -1 for static, rect, field name, span).
_LineItem = Tuple[int, pymupdf.Rect, Optional[str], Optional[dict]]


def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    return _INVALID_CHARS_RE.sub("", str(value)).strip()


def _text_width(text: str, size: float) -> float:
    return pymupdf.get_text_length(text, fontname=_FIELD_FONT_METRICS, fontsize=size)


def _fit_fontsize(text: str, avail: float) -> float:
    """Largest size <= the body size that keeps ``text`` inside ``avail`` points."""
    size = _BODY_FONTSIZE
    while size > _ABS_MIN_FONTSIZE and _text_width(text, size) > avail:
        size -= 0.25
    return round(size, 2)


def _needed_width(text: str) -> float:
    return _text_width(text, _BODY_FONTSIZE) + 2 * _EDGE_PAD


def _body_spans(page: pymupdf.Page) -> List[dict]:
    """Static letter-body text spans (the small-print footer excluded)."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip() and span["size"] >= _BODY_MIN_SIZE:
                    spans.append(span)
    return spans


def _same_line(a: pymupdf.Rect, b: pymupdf.Rect) -> bool:
    return abs((a.y0 + a.y1) / 2 - (b.y0 + b.y1) / 2) <= _LINE_TOL


def _group_lines(items: List[_LineItem]) -> List[List[_LineItem]]:
    lines: List[List[_LineItem]] = []
    for item in sorted(items, key=lambda e: ((e[1].y0 + e[1].y1) / 2, e[1].x0)):
        if lines and _same_line(lines[-1][0][1], item[1]):
            lines[-1].append(item)
        else:
            lines.append([item])
    for line in lines:
        line.sort(key=lambda e: e[1].x0)
    return lines


def _grow_into_whitespace(
    rect: pymupdf.Rect, needed: float, neighbours: List[pymupdf.Rect]
) -> pymupdf.Rect:
    """Widen ``rect`` toward whichever side is free, stopping short of ``neighbours``."""
    grown = pymupdf.Rect(rect)
    short = needed - grown.width
    if short <= 0:
        return grown

    right, left = _RIGHT_MARGIN, _LEFT_MARGIN
    for other in neighbours:
        if not _same_line(rect, other):
            continue
        if other.x0 >= rect.x1 - 1:
            right = min(right, other.x0)
        if other.x1 <= rect.x0 + 1:
            left = max(left, other.x1)

    take = min(short, max(0.0, (right - _EDGE_PAD) - grown.x1))
    grown.x1 += take
    short -= take
    if short > 0:
        take = min(short, max(0.0, grown.x0 - (left + _EDGE_PAD)))
        grown.x0 -= take
    return grown


def _plan_line(
    line: List[_LineItem], values: Dict[str, str]
) -> Optional[Tuple[Dict[int, pymupdf.Rect], List[Tuple[dict, float]]]]:
    """Re-lay one left-to-right line at body size by pushing its tail right.

    Returns the widget rects (keyed by widget index) and the static spans to shift, or
    None when the extra width would run past the right margin.
    """
    slack = _RIGHT_MARGIN - max(rect.x1 for _, rect, _, _ in line)
    if slack <= 0:
        return None

    shift = 0.0
    rects: Dict[int, pymupdf.Rect] = {}
    moved: List[Tuple[dict, float]] = []
    for index, rect, field_name, span in line:
        if index < 0:
            if shift > 0 and span is not None:
                moved.append((span, shift))
            continue
        placed = pymupdf.Rect(rect.x0 + shift, rect.y0, rect.x1 + shift, rect.y1)
        needed = _needed_width(values.get(field_name or "", ""))
        if needed > placed.width:
            shift += needed - placed.width
            placed.x1 = placed.x0 + needed
        rects[index] = placed

    if shift > slack:
        return None
    return rects, moved


def _shift_static_text(page: pymupdf.Page, moved: List[Tuple[dict, float]]) -> None:
    """Redact each span and re-draw it ``dx`` points right, same font, size and colour."""
    if not moved:
        return
    for span, _dx in moved:
        box = pymupdf.Rect(span["bbox"])
        page.add_redact_annot(
            pymupdf.Rect(box.x0 - 0.5, box.y0 - 0.5, box.x1 + 0.5, box.y1 + 0.5)
        )
    # Keep the letterhead artwork; only the letter's text is being re-laid out.
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    for span, dx in moved:
        origin_x, origin_y = span["origin"]
        colour = span.get("color", 0)
        page.insert_text(
            (origin_x + dx, origin_y),
            span["text"],
            fontname=_BASE14.get(span["font"], _FIELD_FONT_METRICS),
            fontsize=span["size"],
            color=(
                (colour >> 16 & 255) / 255,
                (colour >> 8 & 255) / 255,
                (colour & 255) / 255,
            ),
        )


def fill_acroform_pdf(template_path: Path, values: Dict[str, str]) -> bytes:
    """Fill fields named in ``values`` (field_name -> text), flatten, return PDF bytes.

    The same field name may appear on several widgets/pages (e.g. ``worker_name``); every
    widget with that name is filled. Fields with no value are removed, so the flattened
    output carries no empty boxes.
    """
    content, _ = fill_acroform_pdf_with_report(template_path, values)
    return content


def fill_acroform_pdf_with_report(
    template_path: Path, values: Dict[str, str]
) -> Tuple[bytes, Dict[str, float]]:
    """As ``fill_acroform_pdf``, plus ``{field_name: fontsize}`` for the values that had
    to print below ``_MIN_FONTSIZE`` because their gap in the template is too narrow."""
    doc = pymupdf.open(template_path)
    shrunk: Dict[str, float] = {}
    try:
        clean = {name: _sanitize(text) for name, text in values.items()}
        for page in doc:
            _fill_page(page, clean, shrunk)
        # Flatten form fields into page content (removes widgets + field borders).
        doc.bake(widgets=True)
        return doc.tobytes(deflate=True, garbage=3), shrunk
    finally:
        doc.close()


def _drop_empty_widgets(page: pymupdf.Page, values: Dict[str, str]) -> None:
    """Delete every widget with nothing to print, so no empty box is baked in.

    That includes the two Arabic constants, whose correct value is the static Arabic text
    the box was sitting on top of and hiding.
    """
    for widget in list(page.widgets() or []):
        is_arabic_static = (
            page.number == _ARABIC_PAGE_INDEX and widget.field_name in _ARABIC_STATIC_FIELDS
        )
        if is_arabic_static or not values.get(widget.field_name, ""):
            page.delete_widget(widget)


def _fill_page(page: pymupdf.Page, values: Dict[str, str], shrunk: Dict[str, float]) -> None:
    _drop_empty_widgets(page, values)
    widgets = list(page.widgets() or [])
    if not widgets:
        return

    spans = _body_spans(page)
    placed: Dict[int, pymupdf.Rect] = {}
    if page.number == _ENGLISH_PAGE_INDEX:
        items: List[_LineItem] = [
            (i, pymupdf.Rect(w.rect), w.field_name, None) for i, w in enumerate(widgets)
        ] + [(-1, pymupdf.Rect(s["bbox"]), None, s) for s in spans]
        moved: List[Tuple[dict, float]] = []
        for line in _group_lines(items):
            if not any(index >= 0 for index, _, _, _ in line):
                continue
            plan = _plan_line(line, values)
            if plan is None:
                continue
            line_rects, line_moved = plan
            placed.update(line_rects)
            moved.extend(line_moved)
        # Re-drawing text rewrites the page's annotations, so re-read the widgets after.
        _shift_static_text(page, moved)
        widgets = list(page.widgets() or [])

    span_rects = [pymupdf.Rect(s["bbox"]) for s in spans]
    widget_rects = [pymupdf.Rect(w.rect) for w in widgets]
    for index, widget in enumerate(widgets):
        name = widget.field_name
        text = values[name]
        rect = placed.get(index)
        if rect is None and page.number == _ENGLISH_PAGE_INDEX:
            neighbours = [r for i, r in enumerate(widget_rects) if i != index] + span_rects
            rect = _grow_into_whitespace(
                pymupdf.Rect(widget.rect), _needed_width(text), neighbours
            )
        if rect is None:
            rect = pymupdf.Rect(widget.rect)
        size = _fit_fontsize(text, rect.width - 2 * _EDGE_PAD)
        if size < _MIN_FONTSIZE:
            shrunk[name] = min(size, shrunk.get(name, size))
        widget.rect = rect
        widget.field_value = text
        widget.text_font = _FIELD_FONT
        widget.text_fontsize = size
        # Drop the input-box border so the flattened output reads like a letter, not a
        # form (matches the .docx-derived NOCs).
        try:
            widget.border_width = 0
            widget.border_color = None
        except (ValueError, RuntimeError):
            pass
        widget.update()
