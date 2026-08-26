"""One-time import: install the business-provided Turkey client NOC Word template.

Source: ``turkey/NOC (1).docx`` (provided by operations). It uses the old @token@
style; this converts the tokens to the house {{placeholder}} style with the standard
request-key names and writes ``client-noc.docx`` next to the other letter templates.

Token mapping:
  @client_name@               → {{client_name}}
  @client_nationality@        → {{client_nationality}}
  @Client_passport_number@    → {{client_passport_number}}
  @Housemaid_name@            → {{maid_name}}
  @Housemaid_nationality@     → {{maid_nationality}}
  @Housemaid_passport_number@ → {{maid_passport_number}}
  @Client_phone_number@       → {{client_phone_number}}

Idempotent: re-running regenerates client-noc.docx from the same source.

    python scripts/import_client_noc_docx.py
"""

from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE = BASE_DIR / "turkey" / "NOC (1).docx"
TARGET = BASE_DIR / "client-noc.docx"

# Tokens land on the REQUEST key names — the docx fill matches placeholders by request key.
TOKEN_MAP = {
    "client_name": "client_name",
    "client_nationality": "client_nationality",
    "Client_passport_number": "client_passport_number",
    "Housemaid_name": "maid_name",
    "Housemaid_nationality": "maid_nationality",
    "Housemaid_passport_number": "maid_passport_number",
    "Client_phone_number": "client_contact_number",
}


def _convert_text(text: str) -> str:
    for token, placeholder in TOKEN_MAP.items():
        text = text.replace(f"@{token}@", "{{" + placeholder + "}}")
    return text


def _convert_paragraph(para) -> int:
    """Convert @tokens@ in a paragraph. Run-level first (preserves formatting); if a token
    is split across runs, rebuild the paragraph text into the first run (these paragraphs
    are uniformly styled, so nothing is lost)."""
    changed = 0
    for run in para.runs:
        new = _convert_text(run.text)
        if new != run.text:
            run.text = new
            changed += 1
    joined = "".join(r.text for r in para.runs)
    if "@" in joined:
        converted = _convert_text(joined)
        if converted != joined and para.runs:
            para.runs[0].text = converted
            for run in para.runs[1:]:
                run.text = ""
            changed += 1
    return changed


def main() -> None:
    if not SOURCE.exists():
        print(f"  ERROR: source not found: {SOURCE}")
        return

    doc = Document(str(SOURCE))
    converted = 0
    for para in doc.paragraphs:
        converted += _convert_paragraph(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    converted += _convert_paragraph(para)

    doc.save(str(TARGET))
    print(f"  converted {converted} run(s)/paragraph(s); wrote {TARGET.name}")


if __name__ == "__main__":
    main()
