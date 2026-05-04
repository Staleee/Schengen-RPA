"""
Patch script kept for backwards compatibility / idempotency.

Earlier versions of this script prepended a `{{addressee}}` paragraph at the top
of each letter template. The runtime fill engine (`doc_utils.fill_document`) now
replaces the existing "Embassy of {{schengen_country}}" + city lines with the
addressee value at fill time, which is much cleaner because:

  * Non-Turkey letters keep their original "Embassy of <country>" / "Abu Dhabi"
    block untouched.
  * Turkey letters get a single addressee line inside the existing To block,
    instead of a duplicate addressee at the very top of the page.

This script is now a no-op except that it strips a legacy top-level
`{{addressee}}` paragraph from any template that was patched by the old version
of this script. That way, repeatedly building the Docker image (or running this
script on a previously patched template) leaves the file in the new, clean
state.

Run during the Docker build:
    RUN python scripts/patch_addressee_placeholder.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = {
    "cover": BASE_DIR / "Cover_Letter.docx",
    "sponsor": BASE_DIR / "Sponsor_letter.docx",
    "invitation": BASE_DIR
    / "Invitation Letter (Schengen Visa \u2013 Domestic Worker_Housemaid).docx",
}

ADDRESSEE_PLACEHOLDER = "{{addressee}}"


def _para_text(para) -> str:
    return "".join(run.text for run in para.runs)


def _remove_paragraph(paragraph) -> None:
    elem = paragraph._element
    parent = elem.getparent()
    if parent is not None:
        parent.remove(elem)


def _strip_legacy_top_addressee(doc) -> bool:
    """If the very first non-empty body paragraph is just `{{addressee}}` (left
    over from an older patch), remove it. Returns True if the file changed."""
    for para in doc.paragraphs[:3]:
        text = _para_text(para).strip()
        if not text:
            continue
        if text == ADDRESSEE_PLACEHOLDER:
            _remove_paragraph(para)
            return True
        return False
    return False


def patch_template(path: Path) -> None:
    if not path.exists():
        print(f"  SKIP (not found): {path.name}")
        return
    doc = Document(str(path))
    if _strip_legacy_top_addressee(doc):
        doc.save(str(path))
        print(f"  CLEANED legacy top {{{{addressee}}}}: {path.name}")
    else:
        print(f"  OK (no legacy patch): {path.name}")


if __name__ == "__main__":
    print("Cleaning legacy {{addressee}} top paragraphs (if any)...")
    for name, path in TEMPLATES.items():
        patch_template(path)
    print("Done.")
