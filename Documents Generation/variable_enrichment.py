"""
Enrich template variables: trip duration from dates, salary number -> words.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None  # type: ignore

try:
    from num2words import num2words
except ImportError:
    num2words = None  # type: ignore


# Every variable that carries an Emirates ID into a template.
_EID_KEYS = ("worker_eid", "companion_eid", "maid_eid_number")

# A UAE Emirates ID is 15 digits beginning 784, conventionally written 784-YYYY-NNNNNNN-C.
_EID_DIGITS = 15
_EID_PREFIX = "784"

# Unicode bidi isolates, for a left-to-right value embedded in an Arabic sentence.
_LTR_ISOLATE = "⁦"  # LEFT-TO-RIGHT ISOLATE
_POP_ISOLATE = "⁩"  # POP DIRECTIONAL ISOLATE


def _isolate_ltr(value: str) -> str:
    return f"{_LTR_ISOLATE}{value}{_POP_ISOLATE}" if value else value


# U+2011 NON-BREAKING HYPHEN, drawn identically to "-" but not a line-break opportunity.
# With ordinary hyphens the ID broke across a line on the NOC's Arabic page and the two halves
# came out in right-to-left order ("784-1988-" then "8-1234567") — an ID number that reads wrong
# on a document a consulate checks. Keeping it one unbreakable token avoids that entirely.
_NB_HYPHEN = "‑"


def format_emirates_id(value: str) -> Optional[str]:
    """``"784199012345671"`` -> ``"784‑1990‑1234567‑1"``; None when it is not an Emirates ID.

    Accepts any punctuation or spacing around the digits, so an already-formatted value is
    re-emitted in the canonical form. Returns None rather than guessing when the digit count is
    wrong — a short value is missing digits and cannot be reconstructed. Separators are
    non-breaking hyphens (see ``_NB_HYPHEN``).
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != _EID_DIGITS or not digits.startswith(_EID_PREFIX):
        return None
    parts = (digits[:3], digits[3:7], digits[7:14], digits[14])
    return _NB_HYPHEN.join(parts)


def _parse_zoho_year_month_day(s: str) -> Optional[date]:
    """
    Zoho sends dates as year/month/day (not day/month/year).
    Accepts: YYYY/MM/DD, YYYY-M-D, YY/MM/DD (2-digit year → 20YY), same with hyphens.
    """
    s = str(s).strip()
    if not s:
        return None
    # Four-digit year first (avoids dayfirst confusion with 2026/6/3 etc.)
    m = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    # Two-digit year: yy/mm/dd → 20yy (e.g. 26/6/3 → 2026-06-03)
    m2 = re.fullmatch(r"(\d{2})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m2:
        yy = int(m2.group(1))
        mo, d = int(m2.group(2)), int(m2.group(3))
        y = 2000 + yy if yy < 100 else yy
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def _parse_date(s: str) -> Optional[date]:
    if not s or not str(s).strip():
        return None
    s = str(s).strip()

    # 1) Zoho / ISO-style year-first (never treat as day-first)
    z = _parse_zoho_year_month_day(s)
    if z is not None:
        return z

    # 2) Plain ISO YYYY-MM-DD (no slashes)
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # 3) EU / Zoho dd.MM.yyyy before dateutil (avoids wrong guesses on dotted dates)
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # 4) dateutil: yearfirst=True (NOT dayfirst) for remaining strings
    if date_parser:
        try:
            dt = date_parser.parse(s, yearfirst=True, dayfirst=False)
            return dt.date()
        except (ValueError, TypeError, OverflowError):
            pass

    return None


def compute_trip_duration_days(departure: str, return_date: str) -> Optional[int]:
    """
    Inclusive calendar days between departure and return (visa-style).
    e.g. 15 Mar 2026 – 30 Mar 2026 -> 16 days.
    """
    d1 = _parse_date(departure)
    d2 = _parse_date(return_date)
    if not d1 or not d2:
        return None
    if d2 < d1:
        return None
    return (d2 - d1).days + 1


def salary_numeric_to_words(value: str) -> Optional[str]:
    """
    If value is a plain number (e.g. 1500, 1,500.00), return English words only.
    AED/currency is already in the letter template. Otherwise return None (caller keeps original text).
    """
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    # Strip currency words / AED if present for detection
    cleaned = re.sub(r"[^\d.,]", "", raw)
    cleaned = cleaned.replace(",", "")
    if not cleaned or not re.fullmatch(r"\d+\.?\d*", cleaned):
        return None
    try:
        n = int(float(cleaned))
    except ValueError:
        return None
    if n < 0 or n > 999_999_999:
        return None
    if not num2words:
        return str(n)
    words = num2words(n, lang="en")
    # Title case first word for letter style
    parts = words.split()
    if parts:
        parts[0] = parts[0].capitalize()
    return " ".join(parts)


def _raw_body_first_string(raw: Dict[str, Any], *candidate_keys: str) -> str:
    """Match Zoho keys by normalized name (camelCase, spaces) when not in document map."""
    from doc_utils import normalize_key as nk_fn

    by_nk: Dict[str, Any] = {}
    for k, v in raw.items():
        nk = nk_fn(str(k))
        if nk and nk not in by_nk:
            by_nk[nk] = v
    for ck in candidate_keys:
        nk = nk_fn(ck)
        if nk in by_nk and by_nk[nk] is not None:
            s = str(by_nk[nk]).strip()
            if s:
                return s
    return ""


_PAYMENT_DATE_KEYS = ("date", "payment_date", "salary_date")
_PAYMENT_AMOUNT_KEYS = ("amount", "amount_aed", "salary")
_SALARY_TABLE_SLOTS = 6


def _format_letter_date(d: date) -> str:
    """Printable date for English letters (e.g. 5 October 2026)."""
    return f"{d.day} {d.strftime('%B %Y')}"


def _payment_field(item: Dict[str, Any], candidate_keys: tuple[str, ...]) -> str:
    from doc_utils import normalize_key as nk_fn

    by_nk: Dict[str, Any] = {}
    for k, v in item.items():
        nk = nk_fn(str(k))
        if nk and nk not in by_nk:
            by_nk[nk] = v
    for ck in candidate_keys:
        nk = nk_fn(ck)
        if nk in by_nk and by_nk[nk] is not None:
            s = str(by_nk[nk]).strip()
            if s:
                return s
    return ""


def _read_salary_payments_list(raw_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    from doc_utils import normalize_key as nk_fn

    by_nk: Dict[str, Any] = {}
    for k, v in raw_body.items():
        nk = nk_fn(str(k))
        if nk and nk not in by_nk:
            by_nk[nk] = v
    val = by_nk.get(nk_fn("salary_payments"))
    if val is None:
        return []
    if isinstance(val, dict):
        return [val]
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    return []


def _expand_salary_payments(raw_body: Dict[str, Any]) -> Dict[str, str]:
    """Map salary_payments[] to last_salary_date_N / last_salary_N (newest first, max 6)."""
    items = _read_salary_payments_list(raw_body)
    if not items:
        return {}

    parsed: List[tuple[Optional[date], str, str]] = []
    for item in items:
        date_raw = _payment_field(item, _PAYMENT_DATE_KEYS)
        amount = _payment_field(item, _PAYMENT_AMOUNT_KEYS)
        parsed.append((_parse_date(date_raw), date_raw, amount))

    parsed.sort(key=lambda t: t[0] or date.min, reverse=True)

    out: Dict[str, str] = {}
    for i, (d, date_raw, amount) in enumerate(parsed[:_SALARY_TABLE_SLOTS], start=1):
        if d is not None:
            out[f"last_salary_date_{i}"] = _format_letter_date(d)
        elif date_raw:
            out[f"last_salary_date_{i}"] = date_raw
        if amount:
            out[f"last_salary_{i}"] = amount
    return out


def enrich_variables(
    document_type: str,
    variables: Dict[str, str],
    raw_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Return a copy with trip_duration and/or salary_in_letters filled when derivable."""
    out = dict(variables)
    raw_body = raw_body or {}

    # Salary: numeric -> words (sponsor mapping uses salary_in_letters)
    sal_key = "salary_in_letters"
    if sal_key in out:
        converted = salary_numeric_to_words(out.get(sal_key, ""))
        if converted is not None:
            out[sal_key] = converted

    # Sponsor: trip_duration from departure_date + return_date; if departure empty, try raw arrival_date.
    if document_type == "sponsor":
        dep = (out.get("departure_date") or "").strip() or _raw_body_first_string(
            raw_body, "arrival_date", "Arrival_Date", "trip_start_date"
        )
        ret = (out.get("return_date") or "").strip() or _raw_body_first_string(
            raw_body, "return_date", "Return_Date", "trip_end_date"
        )
        days = compute_trip_duration_days(dep, ret)
        if days is not None:
            # Template already has a hardcoded " days" word after {{trip_duration}};
            # storing just the number prevents the "X days days" duplication.
            out["trip_duration"] = str(days)

    # Cover/sponsor: {{destinations}} lists every trip country ("Spain and France").
    # Callers that predate the key (or single-destination trips) fall back to the
    # one application country so the travel sentence never renders empty.
    if document_type in ("cover", "sponsor"):
        if not (out.get("destinations") or "").strip():
            out["destinations"] = (out.get("schengen_country") or "").strip()

    # Emirates ID: the ERP stores it as free text, so it arrives unpunctuated, part-punctuated
    # or spaced. Print it in the official 784-YYYY-NNNNNNN-C form wherever the digits allow.
    for eid_key in _EID_KEYS:
        raw = (out.get(eid_key) or "").strip()
        if not raw:
            continue
        formatted = format_emirates_id(raw)
        if formatted:
            out[eid_key] = formatted
        else:
            # Not repairable here — a value like "487627" is missing digits outright. Printed as
            # given rather than invented, and surfaced so the profile can be corrected.
            print(
                f"[{document_type}] !! {eid_key}={raw!r} is not a 15-digit Emirates ID "
                f"(784-YYYY-NNNNNNN-C); printed as given"
            )

    # Maid NOC: the companion's passport number and Emirates ID are optional on the
    # application, so the letter composes that clause instead of printing the labels
    # around empty placeholders ("holder of passport number  , Emirates ID:").
    if document_type in ("noc-schengen", "noc-turkey"):
        passport = (out.get("companion_passport") or "").strip()
        eid = (out.get("companion_eid") or "").strip()
        out["companion_id_clause"] = _join_clauses(
            f"holder of passport number {passport}" if passport else "",
            f"Emirates ID: {eid}" if eid else "",
        )
        # The Arabic clause mixes Arabic with left-to-right values, so doc_utils cannot isolate
        # it wholesale — the passport number and Emirates ID are fenced individually here, or
        # bidi renders them right-to-left inside the Arabic sentence (the ID printed as
        # "8-1234567-1988-784").
        out["companion_id_clause_ar"] = _join_clauses(
            f"حامل جواز السفر {_isolate_ltr(passport)}" if passport else "",
            f"الهوية الإماراتية: {_isolate_ltr(eid)}" if eid else "",
            separator="، ",
        )

    if document_type == "salary-statement":
        if not (out.get("today_date") or "").strip():
            out["today_date"] = _format_letter_date(date.today())
        for key, val in _expand_salary_payments(raw_body).items():
            if not (out.get(key) or "").strip():
                out[key] = val

    if document_type == "noc-syria":
        gender = (out.get("companion_gender") or "").strip()
        if not gender:
            gender = _raw_body_first_string(
                raw_body, "companion_gender", "companionGender", "Companion_Gender"
            )
        title_raw = (out.get("companion_title") or "").strip() or gender
        out["companion_title"] = syria_companion_title_arabic(title_raw)

    return out


_SYRIA_COMPANION_FEMALE = frozenset({"f", "female"})
_SYRIA_COMPANION_MALE = frozenset({"m", "male"})


def syria_companion_title_arabic(raw: str) -> str:
    """Map companion gender codes to Arabic honorific for noc-syria {{companion_title}}."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s in ("السيدة", "السيد"):
        return s
    key = s.lower()
    if key in _SYRIA_COMPANION_FEMALE:
        return "السيدة"
    if key in _SYRIA_COMPANION_MALE:
        return "السيد"
    return s


def _join_clauses(*parts: str, separator: str = ", ") -> str:
    """Join the non-empty parts, or "" when none are set.

    No leading space — ``fill_document`` strips substituted values, so the template
    carries the space before the placeholder instead.
    """
    return separator.join(p for p in parts if p)
