"""
Documents Generation – read bold placeholders from .docx and fill them from a request body.
Bold text in the template = variable name (we normalize to snake_case for the API).
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

from docx import Document


def normalize_key(text: str) -> str:
    """Normalize placeholder to request-body key: strip, lowercase, spaces -> underscores."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^\w\-]", "", t)  # keep letters, digits, underscore, hyphen
    return t


def fill_document(doc_path: Path, variables: Dict[str, str], output_path: Path) -> List[str]:
    """
    Open docx, replace each bold run whose normalized text matches a key in variables with the value.
    variables: dict of normalized_key -> value (e.g. {"client_name": "John Doe"}).
    Returns list of keys that were filled.
    """
    doc = Document(str(doc_path))
    filled: List[str] = []
    # Build list of (para, run_index, normalized_key) for each bold run
    to_fill: List[Tuple[object, int, str]] = []
    for para in doc.paragraphs:
        for i, run in enumerate(para.runs):
            if run.bold and run.text.strip():
                key = normalize_key(run.text)
                if key and key in variables:
                    to_fill.append((para, i, key))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for i, run in enumerate(para.runs):
                        if run.bold and run.text.strip():
                            key = normalize_key(run.text)
                            if key and key in variables:
                                to_fill.append((para, i, key))

    for para, run_index, key in to_fill:
        run = para.runs[run_index]
        run.text = str(variables[key])
        filled.append(key)

    doc.save(str(output_path))
    return filled


def list_bold_variables(doc_path: Path) -> List[Dict[str, str]]:
    """
    List all bold run texts (placeholders) in the document.
    Returns list of {"raw": "Client Name", "key": "client_name"}.
    """
    doc = Document(str(doc_path))
    seen = set()
    out: List[Dict[str, str]] = []
    for para in doc.paragraphs:
        for run in para.runs:
            if run.bold and run.text.strip():
                raw = run.text.strip()
                key = normalize_key(raw)
                if key and key not in seen:
                    seen.add(key)
                    out.append({"raw": raw, "key": key})
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        if run.bold and run.text.strip():
                            raw = run.text.strip()
                            key = normalize_key(raw)
                            if key and key not in seen:
                                seen.add(key)
                                out.append({"raw": raw, "key": key})
    return out
