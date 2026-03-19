"""
Enrich template variables: trip duration from dates, salary number -> words.
"""

import re
from datetime import date, datetime
from typing import Dict, Optional

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None  # type: ignore

try:
    from num2words import num2words
except ImportError:
    num2words = None  # type: ignore


def _parse_date(s: str) -> Optional[date]:
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    if date_parser:
        try:
            dt = date_parser.parse(s, dayfirst=True)
            return dt.date()
        except (ValueError, TypeError, OverflowError):
            pass
    # Fallback: YYYY-MM-DD
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
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
    If value is a plain number (e.g. 1500, 1,500.00), return English words + Dirhams.
    Otherwise return None (caller keeps original text).
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
    return " ".join(parts) + " UAE Dirhams"


def enrich_variables(document_type: str, variables: Dict[str, str]) -> Dict[str, str]:
    """Return a copy with trip_duration and/or salary_in_letters filled when derivable."""
    out = dict(variables)

    # Salary: numeric -> words (sponsor mapping uses salary_in_letters)
    sal_key = "salary_in_letters"
    if sal_key in out:
        converted = salary_numeric_to_words(out.get(sal_key, ""))
        if converted is not None:
            out[sal_key] = converted

    # Sponsor: trip length from departure + return (inclusive days)
    if document_type == "sponsor":
        dep = out.get("departure_date", "")
        ret = out.get("return_date", "")
        days = compute_trip_duration_days(dep, ret)
        if days is not None:
            out["trip_duration"] = f"{days} days"

    return out
