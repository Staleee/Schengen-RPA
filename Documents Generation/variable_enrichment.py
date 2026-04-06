"""
Enrich template variables: trip duration from dates, salary number -> words.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, Optional

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None  # type: ignore

try:
    from num2words import num2words
except ImportError:
    num2words = None  # type: ignore


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
            out["trip_duration"] = f"{days} days"

    return out
