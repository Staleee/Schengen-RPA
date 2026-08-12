"""
GCC issuing affidavit – fill {{placeholder}} values inside the flat AFFIDAVIT-template.pdf.

Unlike the letter templates (.docx), the affidavit ships as a flat Canva PDF: no
AcroForm fields, placeholders are baked into the page content. Filling = locate
each text line that still holds a {{placeholder}}, redact that line, and re-write
it at the same baseline with the values substituted. Base-14 Helvetica /
Helvetica-Bold stand in for the template's embedded HelveticaWorld subset
(same metrics), and substituted values render bold — the same convention
doc_utils.fill_document applies to the .docx letters.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf

from doc_utils import normalize_key

_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")

REGULAR_FONT = "helv"   # Helvetica (base-14)
BOLD_FONT = "hebo"      # Helvetica-Bold (base-14)

# Substituted values render bold (same house style as the .docx letters).
BOLD_VALUES = True

# Shrink-to-fit floor: never render below this fraction of the original size.
_MIN_FONT_SCALE = 0.55
_FONT_STEP = 0.25

# Control chars break PDF text operators; strip them from substituted values.
_INVALID_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    return _INVALID_CHARS_RE.sub("", str(value)).strip()


def _color_int_to_rgb(color: int) -> Tuple[float, float, float]:
    return (
        ((color >> 16) & 0xFF) / 255.0,
        ((color >> 8) & 0xFF) / 255.0,
        (color & 0xFF) / 255.0,
    )


def _segment_width(text: str, bold: bool, size: float) -> float:
    font = BOLD_FONT if (bold and BOLD_VALUES) else REGULAR_FONT
    return pymupdf.get_text_length(text, fontname=font, fontsize=size)


def _line_jobs(page: "pymupdf.Page", substitutions: Dict[str, str]) -> List[Dict[str, Any]]:
    """One job per text line containing a mapped {{placeholder}}."""
    jobs: List[Dict[str, Any]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text")]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans)
            if "{{" not in text:
                continue
            matches = list(_PLACEHOLDER_RE.finditer(text))
            if not matches:
                continue
            segments: List[Tuple[str, bool]] = []
            pos = 0
            replaced_any = False
            for m in matches:
                if m.start() > pos:
                    segments.append((text[pos : m.start()], False))
                placeholder = m.group(0)
                if placeholder in substitutions:
                    segments.append((_sanitize(substitutions[placeholder]), True))
                    replaced_any = True
                else:
                    # Unmapped placeholder: leave untouched ("no guessing" rule).
                    segments.append((placeholder, False))
                pos = m.end()
            if not replaced_any:
                continue
            if pos < len(text):
                segments.append((text[pos:], False))
            jobs.append(
                {
                    "bbox": pymupdf.Rect(line["bbox"]),
                    "origin": pymupdf.Point(spans[0]["origin"]),
                    "size": max(s["size"] for s in spans),
                    "color": _color_int_to_rgb(spans[0]["color"]),
                    "segments": segments,
                }
            )
    return jobs


def _right_edge(page: "pymupdf.Page") -> float:
    """Right edge of the body text block (the template is justified, so the
    widest line marks where substituted lines may extend to)."""
    edges = [
        pymupdf.Rect(line["bbox"]).x1
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        if line.get("spans")
    ]
    return max(edges) if edges else page.rect.width * 0.9


def _insert_job(page: "pymupdf.Page", job: Dict[str, Any], right_limit: float) -> None:
    size = job["size"]
    origin = job["origin"]
    segments = job["segments"]

    # Shrink only when the substituted line would run past the body block's
    # right edge (long names/passport numbers stay on one line like the original).
    available = right_limit - origin.x
    while size > job["size"] * _MIN_FONT_SCALE:
        total = sum(_segment_width(t, b, size) for t, b in segments if t)
        if total <= available:
            break
        size -= _FONT_STEP

    x = origin.x
    for text, is_value in segments:
        if not text:
            continue
        font = BOLD_FONT if (is_value and BOLD_VALUES) else REGULAR_FONT
        page.insert_text(
            (x, origin.y),
            text,
            fontname=font,
            fontsize=size,
            color=job["color"],
        )
        x += pymupdf.get_text_length(text, fontname=font, fontsize=size)


def fill_affidavit_pdf(template_path: Path, substitutions: Dict[str, str]) -> bytes:
    """
    Replace placeholders in the affidavit PDF and return the filled PDF bytes.

    ``substitutions`` maps the literal template placeholder (e.g. "{{maid-name}}")
    to the value to render. Placeholders not present in the mapping are left
    as-is; mapped keys with no value render as empty text (same as the .docx flow).
    """
    doc = pymupdf.open(template_path)
    try:
        for page in doc:
            jobs = _line_jobs(page, substitutions)
            if not jobs:
                continue
            right_limit = _right_edge(page)
            for job in jobs:
                page.add_redact_annot(job["bbox"] + (-1, -1, 1, 1))
            # Redaction (not white-painting) so the placeholder text is gone
            # from the text layer too — this is a signed legal document.
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            for job in jobs:
                _insert_job(page, job, right_limit)
        return doc.tobytes(deflate=True, garbage=3)
    finally:
        doc.close()


def list_affidavit_placeholders(template_path: Path) -> List[str]:
    """Normalized placeholder names found in the PDF (counterpart of doc_utils.list_placeholder_variables)."""
    found: List[str] = []
    try:
        doc = pymupdf.open(template_path)
    except Exception:
        return found
    with doc:
        for page in doc:
            for m in _PLACEHOLDER_RE.finditer(page.get_text()):
                name = normalize_key(m.group(1).strip())
                if name and name not in found:
                    found.append(name)
    return sorted(found)
