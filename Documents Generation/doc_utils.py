"""
Documents Generation – replace {{variable}} placeholders in .docx templates.
Templates use {{variable_name}} so we know exactly what to replace. Works when placeholder is split across runs (we replace in raw XML).
"""

import re
import zipfile
from pathlib import Path
from typing import Dict, List

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


def _strip_xml_tags(s: str) -> str:
    """Remove XML tags from string to get plain text (e.g. "maid" from "<w:t>maid</w:t>")."""
    return re.sub(r"<[^>]+>", "", s)


def _xml_escape(value: str) -> str:
    """Escape value for use inside XML <w:t>."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# Match {{ ... }} where ... can be split by Word into multiple XML runs (tags in between).
# So we match {{, then anything (including <w:t>...</w:t>), then }}. Extract var name by stripping tags.
_PLACEHOLDER_PATTERN = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)


def fill_document(doc_path: Path, variables: Dict[str, str], output_path: Path) -> List[str]:
    """
    Replace {{variable_name}} placeholders in the .docx with values from variables.
    Handles Word splitting placeholders across multiple runs: we match {{...}} even when
    XML tags appear between the braces (e.g. {{<w:t>maid</w:t><w:t>_full_name</w:t>}}).
    Every key in variables is used; missing/empty values become ''.
    """
    if not variables:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(doc_path, output_path)
        return []
    normalized = {normalize_key(k): (str(v) if v is not None else "").strip() for k, v in variables.items()}

    filled: List[str] = []
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(doc_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                data = zin.read(name)
                if name == "word/document.xml":
                    xml = data.decode("utf-8")
                    # Replace each {{...}} (possibly with XML inside) by looking up normalized var name
                    def repl(match):
                        inner = match.group(1)
                        var_name = normalize_key(_strip_xml_tags(inner))
                        if var_name in normalized:
                            filled.append(var_name)
                            return "<w:r><w:t>" + _xml_escape(normalized[var_name]) + "</w:t></w:r>"
                        return match.group(0)

                    xml = _PLACEHOLDER_PATTERN.sub(repl, xml)
                    data = xml.encode("utf-8")
                zout.writestr(name, data)
    return filled


def list_placeholder_variables(doc_path: Path) -> List[str]:
    """
    List {{variable}} placeholders in the document. Handles Word splitting:
    we match {{...}} even when XML tags appear between the braces, then strip tags to get the var name.
    """
    found: List[str] = []
    with zipfile.ZipFile(doc_path, "r") as z:
        if "word/document.xml" not in z.namelist():
            return found
        xml = z.read("word/document.xml").decode("utf-8")
        for m in _PLACEHOLDER_PATTERN.finditer(xml):
            inner = m.group(1)
            var_name = normalize_key(_strip_xml_tags(inner))
            if var_name and var_name not in found:
                found.append(var_name)
    return sorted(found)
