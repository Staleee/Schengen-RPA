"""
Turkey Schengen – fill a Word template using single-brace placeholders {name}.

Checkbox sections (6 Sex, 8 Marital status): put tokens **in the box or just before the label**
(same line is fine). The API fills them from `sex` and `marital_status` in the JSON.

**Short (minimal text in Word):**
  {6m} {6f}  — male / female
  {8s} {8m}  — single / married (mnemonic letters)
  {8a} {8b} {8c} {8d} {8e} {8f}  — same order: single → other (if you prefer letters a–f)

**Long (same behaviour):**
  {sex_check_male} {sex_check_female}
  {marital_check_single} … {marital_check_other}

Other fields use any {placeholder_name}; values come from the same flat JSON (snake_case keys).
"""

from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from docx import Document

_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffe\uffff]")
_SINGLE_BRACE_RE = re.compile(r"\{([^{}]+)\}")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PACKAGE_DIR = Path(__file__).resolve().parent


def normalize_key(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^\w\-]", "", t)
    return t


def _sanitize_for_word(value: str) -> str:
    if not value:
        return ""
    return _INVALID_XML_RE.sub("", value)


def resolve_word_template() -> Path:
    env = os.environ.get("TURKEY_WORD_TEMPLATE")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    preferred_names = ("tvisaform.docx", "visaform.docx", "turkey_application.docx")
    search_roots = (ASSETS_DIR, PACKAGE_DIR)
    for root in search_roots:
        for name in preferred_names:
            p = root / name
            if p.is_file():
                return p
    for root in search_roots:
        for p in sorted(root.glob("*.docx")):
            if p.name.startswith("~$"):
                continue
            return p
    return ASSETS_DIR / "tvisaform.docx"


def _normalize_marital(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "_")
    aliases = {
        "divorce": "divorced",
        "widow": "widowed",
        "widower": "widowed",
        "spouse": "married",
    }
    return aliases.get(s, s)


def checkbox_placeholders(sex: Any, marital_status: Any) -> Dict[str, str]:
    """☑ / ☐ for Word next to each option (sections 6 and 8)."""
    s = str(sex or "").strip().lower()
    if s in ("m", "male", "man", "1"):
        male, female = "☑", "☐"
    elif s in ("f", "female", "woman", "2"):
        male, female = "☐", "☑"
    else:
        male, female = "☐", "☐"

    m = _normalize_marital(str(marital_status or ""))
    opts = ("single", "married", "separated", "divorced", "widowed", "other")
    out = {
        "sex_check_male": male,
        "sex_check_female": female,
    }
    for opt in opts:
        out[f"marital_check_{opt}"] = "☑" if m == opt else "☐"
    # Compact §6 / §8 tokens (same values as long names; easier on layout)
    out["6m"] = out["sex_check_male"]
    out["6f"] = out["sex_check_female"]
    short_marital = ("8a", "8b", "8c", "8d", "8e", "8f")
    for letter, opt in zip(short_marital, opts):
        out[letter] = out[f"marital_check_{opt}"]
    # Mnemonic single / married (common on short forms)
    out["8s"] = out["marital_check_single"]
    out["8m"] = out["marital_check_married"]
    return out


def flatten_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    fields = body.get("fields")
    if isinstance(fields, dict):
        out.update(fields)
    for k, v in body.items():
        if k == "fields" or v is None:
            continue
        out[k] = v
    return out


def build_replacements(flat: Dict[str, Any]) -> Dict[str, str]:
    cb = checkbox_placeholders(flat.get("sex"), flat.get("marital_status"))
    values: Dict[str, str] = {}
    for k, v in flat.items():
        nk = normalize_key(str(k)) if k is not None else ""
        if nk:
            values[nk] = _sanitize_for_word(str(v))
    for ck, cv in cb.items():
        values[ck] = cv
    return values


def _process_paragraph(paragraph, values: Dict[str, str]) -> None:
    full_text = "".join(run.text for run in paragraph.runs)
    if "{" not in full_text:
        return

    def repl(m: re.Match) -> str:
        key = normalize_key(m.group(1).strip())
        if key in values:
            return values[key]
        return m.group(0)

    segments: List[Tuple[str, bool]] = []
    pos = 0
    for m in _SINGLE_BRACE_RE.finditer(full_text):
        segments.append((full_text[pos : m.start()], False))
        key = normalize_key(m.group(1).strip())
        segments.append((repl(m), bool(key in values)))
        pos = m.end()
    segments.append((full_text[pos:], False))

    for run in list(paragraph.runs):
        run._r.getparent().remove(run._r)
    for text, is_bold in segments:
        if not text:
            continue
        r = paragraph.add_run(text)
        r.bold = is_bold


def _process_block(paragraphs, tables, values: Dict[str, str]) -> None:
    for p in paragraphs:
        _process_paragraph(p, values)
    if tables:
        for table in tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        _process_paragraph(p, values)


def fill_turkey_docx_bytes(template_path: Path, flat: Dict[str, Any]) -> bytes:
    if not template_path.is_file():
        raise FileNotFoundError(f"Word template not found: {template_path}")

    values = build_replacements(flat)
    doc = Document(str(template_path))

    _process_block(doc.paragraphs, doc.tables, values)
    for section in doc.sections:
        for block in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
            getattr(section, "even_page_header", None),
            getattr(section, "even_page_footer", None),
        ):
            if block is not None:
                _process_block(block.paragraphs, getattr(block, "tables", []) or [], values)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def list_single_brace_placeholders(doc_path: Path) -> List[str]:
    found: List[str] = []
    try:
        doc = Document(str(doc_path))
    except Exception:
        return found

    def scan_paragraphs(paragraphs) -> None:
        for paragraph in paragraphs:
            full_text = "".join(run.text for run in paragraph.runs)
            for m in _SINGLE_BRACE_RE.finditer(full_text):
                var_name = normalize_key(m.group(1).strip())
                if var_name and var_name not in found:
                    found.append(var_name)

    scan_paragraphs(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                scan_paragraphs(cell.paragraphs)
    for section in doc.sections:
        for block in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
            getattr(section, "even_page_header", None),
            getattr(section, "even_page_footer", None),
        ):
            if block is not None:
                scan_paragraphs(block.paragraphs)
                for table in getattr(block, "tables", []) or []:
                    for row in table.rows:
                        for cell in row.cells:
                            scan_paragraphs(cell.paragraphs)

    return sorted(found)
