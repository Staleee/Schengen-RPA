"""
Documents Generation – replace {{variable}} placeholders in .docx templates.
Uses python-docx so the output is always a valid .docx that Word opens without errors.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from docx import Document

# XML 1.0 invalid control chars (only \t \n \r are allowed in content)
_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffe\uffff]")

# Placeholder in document text: {{variable_name}}
_PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")

# Per-document variables (snake_case). Zoho will call each endpoint with its own body.
COVER_LETTER_VARIABLES = [
    "maid_full_name",
    "maid_passport_number",
    "schengen_country",  # Germany / France from Zoho
    "departure_date",
    "return_date",
    "client_name",
    "client_passport_number",
    "employment_start_date",  # contract start date from ERP
]

SPONSOR_LETTER_VARIABLES = [
    "client_name",
    "passport_number",
    "full_address_uae",
    "maid_full_name",
    "maid_passport_number",
    "employment_start_date",
    "salary_in_letters",
    "schengen_country",
    "departure_date",
    "return_date",
    "phone_number",  # client phone from Zoho
    "email",  # client email from Zoho
]

INVITATION_LETTER_VARIABLES = [
    "destination",  # Schengen country from Zoho
    "client_name",
    "address_in_uae",
    "maid_name",
    "contract_start_date",
    "arrival_date_to_departure_date",
    "cities",
    "hotel_address",
    "phone_number",
    "email_address",
]

DOCUMENT_VARIABLES = {
    "cover": COVER_LETTER_VARIABLES,
    "sponsor": SPONSOR_LETTER_VARIABLES,
    "invitation": INVITATION_LETTER_VARIABLES,
}


def normalize_key(text: str) -> str:
    """Normalize to snake_case: strip, lowercase, spaces -> underscores."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^\w\-]", "", t)
    return t


def _sanitize_for_word(value: str) -> str:
    """Strip characters that break Word (control chars, invalid Unicode)."""
    if not value:
        return ""
    return _INVALID_XML_RE.sub("", value)


def fill_document(doc_path: Path, variables: Dict[str, str], output_path: Path) -> List[str]:
    """
    Replace {{variable_name}} placeholders using python-docx. Output is always a valid
    .docx that Word opens without "unspecified error". Handles placeholders split across runs.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not variables:
        import shutil
        shutil.copy2(doc_path, output_path)
        return []

    normalized = {normalize_key(k): _sanitize_for_word((str(v) if v is not None else "").strip()) for k, v in variables.items()}
    filled: List[str] = []

    def repl(match: re.Match) -> str:
        var_name = normalize_key(match.group(1).strip())
        if var_name == "date":
            # {{date}} = current date when the document is generated (not from request body)
            filled.append("date")
            n = datetime.now()
            return f"{n.month}/{n.day}/{n.year}"  # e.g. 3/10/2026
        if var_name in normalized:
            filled.append(var_name)
            return normalized[var_name]
        return match.group(0)

    def process_paragraph(paragraph):
        """Replace placeholders in a paragraph and make substituted text bold."""
        full_text = "".join(run.text for run in paragraph.runs)
        if "{{" not in full_text:
            return
        new_text = _PLACEHOLDER_RE.sub(repl, full_text)
        if paragraph.runs:
            for i, run in enumerate(paragraph.runs):
                run.text = new_text if i == 0 else ""
                if i == 0 and new_text:
                    run.bold = True
        else:
            r = paragraph.add_run(new_text)
            r.bold = True

    def process_block(paragraphs, tables=None):
        for p in paragraphs:
            process_paragraph(p)
        if tables:
            for table in tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            process_paragraph(p)

    doc = Document(doc_path)

    # Body: paragraphs and tables
    process_block(doc.paragraphs, doc.tables)

    # Headers and footers (where maid_full_name at bottom/signature often lives)
    for section in doc.sections:
        for block in (section.header, section.footer, section.first_page_header, section.first_page_footer, getattr(section, "even_page_header", None), getattr(section, "even_page_footer", None)):
            if block is not None:
                process_block(block.paragraphs, getattr(block, "tables", []))

    doc.save(str(output_path))
    return filled


def list_placeholder_variables(doc_path: Path) -> List[str]:
    """List {{variable}} placeholders in the document (paragraphs and table cells)."""
    found: List[str] = []
    try:
        doc = Document(doc_path)
    except Exception:
        return found
    for paragraph in doc.paragraphs:
        full_text = "".join(run.text for run in paragraph.runs)
        for m in _PLACEHOLDER_RE.finditer(full_text):
            var_name = normalize_key(m.group(1).strip())
            if var_name and var_name not in found:
                found.append(var_name)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    full_text = "".join(run.text for run in paragraph.runs)
                    for m in _PLACEHOLDER_RE.finditer(full_text):
                        var_name = normalize_key(m.group(1).strip())
                        if var_name and var_name not in found:
                            found.append(var_name)
    return sorted(found)
