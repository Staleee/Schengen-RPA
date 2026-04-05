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

**§24 / §25 (Turkey travel history):** `{24y}` `{24n}` — visited Turkey before yes/no; `{25y}` `{25n}` — deported/refused from Turkey yes/no.
JSON (preferred): `maid_traveled_to_turkey_before`, `maid_deported_from_turkey_before` (`yes`/`no` or bool). Legacy: `traveled_turkey_before`, `deported_from_turkey_before`.

**Client email typo in Word:** `{client)email}` maps to the same value as `client_email`.

**Visa duration:** If `arrival_date` and `departure_date` parse, `visa_duration` is set to inclusive day count (e.g. `14 days`) unless you already send a non-empty `visa_duration`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def _truthy_tristate(v: Any) -> Optional[bool]:
    """True/False or None if unknown / empty."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("", "unknown", "n/a", "na", "null"):
        return None
    if s in ("y", "yes", "true", "1", "on"):
        return True
    if s in ("n", "no", "false", "0", "off"):
        return False
    return None


def turkey_history_checkboxes(flat: Dict[str, Any]) -> Dict[str, str]:
    """§24 visited Turkey before → {24y}/{24n}; §25 deported/refused → {25y}/{25n}."""
    visited = _truthy_tristate(
        flat.get("maid_traveled_to_turkey_before")
        or flat.get("traveled_turkey_before")
        or flat.get("been_to_turkey_before")
        or flat.get("turkey_visited_before")
    )
    if visited is True:
        y24, n24 = "☑", "☐"
    elif visited is False:
        y24, n24 = "☐", "☑"
    else:
        y24, n24 = "☐", "☐"

    deported = _truthy_tristate(
        flat.get("maid_deported_from_turkey_before")
        or flat.get("maid_deported_from_tueky_before")
        or flat.get("deported_from_turkey_before")
        or flat.get("deported_from_turkey")
        or flat.get("turkey_deported_before")
    )
    if deported is True:
        y25, n25 = "☑", "☐"
    elif deported is False:
        y25, n25 = "☐", "☑"
    else:
        y25, n25 = "☐", "☐"

    return {"24y": y24, "24n": n24, "25y": y25, "25n": n25}


_DATE_FORMATS = (
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d %B %Y",
    "%d %b %Y",
)


def _parse_flexible_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def compute_inclusive_stay_days(flat: Dict[str, Any]) -> Optional[int]:
    """Days from arrival through departure inclusive (trip length)."""
    arr = _parse_flexible_date(flat.get("arrival_date"))
    dep = _parse_flexible_date(flat.get("departure_date"))
    if arr is None or dep is None:
        return None
    if dep < arr:
        return None
    return (dep - arr).days + 1


def build_replacements(flat: Dict[str, Any]) -> Dict[str, str]:
    cb = checkbox_placeholders(flat.get("sex"), flat.get("marital_status"))
    hist = turkey_history_checkboxes(flat)
    days = compute_inclusive_stay_days(flat)

    values: Dict[str, str] = {}
    for k, v in flat.items():
        nk = normalize_key(str(k)) if k is not None else ""
        if not nk:
            continue
        sval = _sanitize_for_word(str(v))
        values[nk] = sval

    if days is not None:
        existing = str(flat.get("visa_duration") or "").strip()
        if not existing:
            values["visa_duration"] = f"{days} days"

    for ck, cv in cb.items():
        values[ck] = cv
    for hk, hv in hist.items():
        values[hk] = hv

    # Word typo `{client)email}` → normalize_key gives `clientemail`, not `client_email`
    if "client_email" in values:
        values["clientemail"] = values["client_email"]

    return values


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


def _resolve_soffice_path() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    if os.name == "nt":
        for guess in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if Path(guess).is_file():
                return guess
    env = os.environ.get("LIBREOFFICE_PATH", "").strip()
    if env and Path(env).is_file():
        return env
    return None


def _convert_docx_bytes_to_pdf_soffice(docx_bytes: bytes) -> Optional[bytes]:
    soffice = _resolve_soffice_path()
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        docx_path = td / "turkey_fill.docx"
        docx_path.write_bytes(docx_bytes)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(td), str(docx_path)],
                check=True,
                timeout=120,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None
        pdf_path = td / "turkey_fill.pdf"
        if pdf_path.is_file():
            return pdf_path.read_bytes()
    return None


def _convert_docx_bytes_to_pdf_word_windows(docx_bytes: bytes) -> Optional[bytes]:
    """
    Convert using Microsoft Word via COM (Windows only). Requires Word installed.
    Optional: pip install pywin32
    """
    if os.name != "nt":
        return None
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        docx_path = (td / "turkey_fill.docx").resolve()
        pdf_path = (td / "turkey_fill.pdf").resolve()
        docx_path.write_bytes(docx_bytes)
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            try:
                word.DisplayAlerts = 0
            except Exception:
                pass
            doc = word.Documents.Open(str(docx_path), ReadOnly=True)
            try:
                doc.SaveAs(str(pdf_path), FileFormat=17)
            finally:
                doc.Close(SaveChanges=False)
        except Exception:
            return None
        finally:
            if word is not None:
                try:
                    word.Quit(SaveChanges=False)
                except Exception:
                    pass
        if pdf_path.is_file():
            return pdf_path.read_bytes()
    return None


def convert_docx_bytes_to_pdf(docx_bytes: bytes) -> Optional[bytes]:
    """
    Convert filled .docx to .pdf: tries LibreOffice (soffice) first, then on Windows
    Microsoft Word (COM). Returns None if neither is available or conversion fails.
    """
    pdf = _convert_docx_bytes_to_pdf_soffice(docx_bytes)
    if pdf:
        return pdf
    return _convert_docx_bytes_to_pdf_word_windows(docx_bytes)


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
