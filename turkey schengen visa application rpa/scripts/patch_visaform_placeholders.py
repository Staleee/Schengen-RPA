"""
Diagnostic + patch script for visaform.docx.

1. Lists all {placeholder} tokens found in the template.
2. Checks whether {rvisa_number}, {current_citizenship}, {citizenship_at_birth} are present.
3. If any are missing, scans table cells for the nearest label (e.g. "residence", "visa no",
   "citizenship", "nationality") and inserts the placeholder into the adjacent value cell.
4. Saves the modified template (idempotent: skips cells that already have the placeholder).

Run once locally or during Docker build (python-docx required):
    python scripts/patch_visaform_placeholders.py
"""

import re
import sys
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

PACKAGE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PACKAGE_DIR / "visaform.docx"

_SINGLE_BRACE_RE = re.compile(r"\{([^{}]+)\}")

# Mapping: placeholder we need -> keywords (lowercase) to find in an adjacent label cell.
REQUIRED_PLACEHOLDERS: dict[str, list[str]] = {
    "rvisa_number": ["rvisa", "r visa", "residence permit", "visa no", "visa number", "uae visa"],
    "rvisa_expiry_date": ["rvisa expiry", "r visa expiry", "residence permit expiry", "visa expiry"],
    "current_citizenship": ["current citizenship", "citizenship", "nationality"],
    "citizenship_at_birth": ["citizenship at birth", "birth citizenship", "original citizenship"],
}


def _cell_text(cell) -> str:
    return "".join(p.text for p in cell.paragraphs).strip()


def _find_placeholders(doc: Document) -> set[str]:
    found = set()
    all_text = []
    for para in doc.paragraphs:
        all_text.append("".join(r.text for r in para.runs))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    all_text.append("".join(r.text for r in para.runs))
    for text in all_text:
        for m in _SINGLE_BRACE_RE.finditer(text):
            found.add(m.group(1).strip().lower().replace(" ", "_").replace("-", "_"))
    return found


def _label_matches(label: str, keywords: list[str]) -> bool:
    label_lower = label.lower()
    return any(kw in label_lower for kw in keywords)


def _append_placeholder_to_cell(cell, placeholder: str) -> None:
    """Append {placeholder} text to the last paragraph of a cell."""
    # Use the last paragraph (or add one)
    if cell.paragraphs:
        para = cell.paragraphs[-1]
    else:
        para = cell.add_paragraph()
    run = para.add_run(f"{{{placeholder}}}")
    # Don't apply bold – let fill_turkey_docx_bytes handle it naturally


def _try_add_in_tables(doc: Document, placeholder: str, keywords: list[str]) -> bool:
    """
    Try to find a table row where one cell is a label matching keywords,
    and the next cell either is empty or lacks the placeholder.
    Returns True if the placeholder was inserted.
    """
    for table in doc.tables:
        for row in table.rows:
            cells = row.cells
            for i, cell in enumerate(cells):
                label = _cell_text(cell)
                if not _label_matches(label, keywords):
                    continue
                # Look at the next cell(s) for the value field
                for j in range(i + 1, len(cells)):
                    val_cell = cells[j]
                    val_text = _cell_text(val_cell)
                    if f"{{{placeholder}}}" in val_text:
                        return True  # Already there
                    if not val_text or not _SINGLE_BRACE_RE.search(val_text):
                        _append_placeholder_to_cell(val_cell, placeholder)
                        print(f"    Inserted {{{placeholder}}} in cell after '{label}'")
                        return True
    return False


# `build_replacements` substitutes `{visa_duration}` with values like "15 days" (it
# always appends the unit). Templates that have a hardcoded " days" word right after
# the placeholder render as "15 days days". Strip those duplicate units.
_DUPLICATE_DAYS_RE = re.compile(r"(\{visa_duration\})\s+days\b", re.IGNORECASE)


def _strip_duplicate_days(doc: Document) -> int:
    """Find paragraphs (incl. table cells) where `{visa_duration}` is followed by a
    literal ' days' and remove the redundant word. Returns the number of edits."""
    edits = 0

    def fix_paragraph(paragraph) -> None:
        nonlocal edits
        full_text = "".join(run.text for run in paragraph.runs)
        if "{visa_duration}" not in full_text.lower():
            return
        new_text = _DUPLICATE_DAYS_RE.sub(r"\1", full_text)
        if new_text == full_text:
            return
        for run in list(paragraph.runs):
            run._r.getparent().remove(run._r)
        paragraph.add_run(new_text)
        edits += 1

    for para in doc.paragraphs:
        fix_paragraph(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    fix_paragraph(para)
    return edits


def patch_template(path: Path) -> None:
    if not path.exists():
        print(f"SKIP (not found): {path}")
        sys.exit(1)

    doc = Document(path)
    existing = _find_placeholders(doc)

    print(f"\nTemplate: {path.name}")
    print(f"Existing placeholders ({len(existing)}): {sorted(existing)}")

    changed = False
    for placeholder, keywords in REQUIRED_PLACEHOLDERS.items():
        if placeholder in existing:
            print(f"  OK: {{{placeholder}}}")
        else:
            print(f"  MISSING: {{{placeholder}}} \u2014 searching for label matching {keywords[:2]}...")
            inserted = _try_add_in_tables(doc, placeholder, keywords)
            if inserted:
                changed = True
            else:
                print(f"    WARNING: Could not find a suitable cell. Add {{{placeholder}}} manually.")

    duplicate_edits = _strip_duplicate_days(doc)
    if duplicate_edits:
        print(f"  Removed redundant ' days' word after {{visa_duration}} ({duplicate_edits} edit(s))")
        changed = True

    if changed:
        doc.save(str(path))
        print(f"Saved patched template: {path.name}")
    else:
        print("No changes needed.")


if __name__ == "__main__":
    patch_template(TEMPLATE_PATH)
