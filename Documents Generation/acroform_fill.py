"""
Fill an AcroForm (fillable) PDF by field name, then flatten it to static content.

Used by the Schengen maid NOC (``Travel_NOC_Fillable.pdf``), a genuine two-page
English + Arabic AcroForm where every blank is a real form field (unlike the flat
{{placeholder}} affidavit / client-noc PDFs handled by ``affidavit_fill.py``).

Filling = set each widget's ``field_value`` (shrinking the font when a value would
clip the field's width), regenerate appearances, then ``doc.bake()`` so the result
is flat text with no editable widgets or field borders — the same finished look as
the .docx letters converted to PDF.
"""

import re
from pathlib import Path
from typing import Any, Dict

import pymupdf

# Control chars break PDF text; strip them from substituted values.
_INVALID_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Never shrink an auto-fit field below this (points) — smaller is unreadable.
_MIN_FONTSIZE = 5.0
_DEFAULT_FONTSIZE = 9.0

# The template body is Times New Roman; fill fields in Times-Roman (the Base-14 twin)
# so values blend in instead of standing out as sans-serif Helvetica.
_FIELD_FONT = "TiRo"
_FIELD_FONT_METRICS = "tiro"

# The Schengen NOC is a fixed two-page English + Arabic form. Two fields on the Arabic
# page are constants whose correct rendering is authored static Arabic text
# (employment_basis = أساس طويل الأمد, trip_purpose = السياحة) — pymupdf cannot shape
# Arabic inside a form-field appearance, so those widgets keep the template's static
# text instead of receiving the English value (see scripts/patch_noc_schengen_template.py).
_ARABIC_PAGE_INDEX = 1
_ARABIC_STATIC_FIELDS = ("employment_basis", "trip_purpose")


def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    return _INVALID_CHARS_RE.sub("", str(value)).strip()


def _fit_fontsize(value: str, width: float, base_size: float) -> float:
    """Largest size ≤ base that keeps ``value`` inside ``width`` (Times metrics)."""
    avail = max(width - 4.0, 1.0)
    size = base_size if base_size and base_size > 0 else _DEFAULT_FONTSIZE
    while size > _MIN_FONTSIZE:
        if pymupdf.get_text_length(value, fontname=_FIELD_FONT_METRICS, fontsize=size) <= avail:
            break
        size -= 0.5
    return size


def fill_acroform_pdf(template_path: Path, values: Dict[str, str]) -> bytes:
    """Fill fields named in ``values`` (field_name -> text), flatten, return PDF bytes.

    Fields absent from ``values`` are left blank. The same field name may appear on
    several widgets/pages (e.g. ``worker_name``); every widget with that name is filled.
    """
    doc = pymupdf.open(template_path)
    try:
        for page in doc:
            for w in page.widgets() or []:
                name = w.field_name
                if name not in values:
                    continue
                if page.number == _ARABIC_PAGE_INDEX and name in _ARABIC_STATIC_FIELDS:
                    continue
                text = _sanitize(values[name])
                w.field_value = text
                w.text_font = _FIELD_FONT
                if text and w.rect.width > 0:
                    w.text_fontsize = _fit_fontsize(text, w.rect.width, w.text_fontsize)
                # Drop the input-box border so the flattened output reads like a letter,
                # not a form (matches the .docx-derived NOCs).
                try:
                    w.border_width = 0
                    w.border_color = None
                except (ValueError, RuntimeError):
                    pass
                w.update()
        # Flatten form fields into page content (removes widgets + field borders).
        doc.bake(widgets=True)
        return doc.tobytes(deflate=True, garbage=3)
    finally:
        doc.close()
