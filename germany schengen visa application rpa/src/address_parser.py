"""
Parse a full address string into parts (street, house_number, postal_code, city, country).

1. Rule-based parser (no API key): runs always, handles common formats (e.g. "Street 123, 10115 Berlin, Germany").
2. Optional LLM: set OPENAI_API_KEY to use GPT for trickier addresses; otherwise only the rule-based parser is used.
"""

import json
import os
import re
from typing import Dict, Optional

# UAE cities: treat as city, set country = UAE (not "Dubai" as country)
_UAE_CITIES = frozenset({
    "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah", "fujairah",
    "umm al quwain", "al ain",
})
# Other country names/codes for when last part is country
_COUNTRIES = frozenset({
    "germany", "deutschland", "de", "uae", "united arab emirates",
    "philippines", "ph", "india", "in", "pakistan", "pk", "egypt", "eg", "uk", "united kingdom",
    "france", "fr", "spain", "es", "italy", "it", "netherlands", "nl", "austria", "at",
    "saudi arabia", "sa", "oman", "om", "qatar", "qa", "bahrain", "bh", "kuwait", "kw",
})


# Normalize common short / alpha-2 country tokens to the labels VIDEX expects.
_COUNTRY_NORMALIZE = {
    "uae": "United Arab Emirates",
    "ae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "ksa": "Saudi Arabia",
    "sa": "Saudi Arabia",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "united kingdom": "United Kingdom",
    "de": "Germany",
    "deutschland": "Germany",
    "germany": "Germany",
    "ph": "Philippines",
    "philippines": "Philippines",
    "in": "India",
    "india": "India",
    "pk": "Pakistan",
    "pakistan": "Pakistan",
    "eg": "Egypt",
    "egypt": "Egypt",
    "fr": "France",
    "france": "France",
    "es": "Spain",
    "spain": "Spain",
    "it": "Italy",
    "italy": "Italy",
    "nl": "Netherlands",
    "netherlands": "Netherlands",
    "at": "Austria",
    "austria": "Austria",
    "om": "Oman",
    "oman": "Oman",
    "qa": "Qatar",
    "qatar": "Qatar",
    "bh": "Bahrain",
    "bahrain": "Bahrain",
    "kw": "Kuwait",
    "kuwait": "Kuwait",
}


def _normalize_country(value: str) -> str:
    """Map short codes or lowercase names to the label VIDEX dropdowns use."""
    if not value:
        return value
    return _COUNTRY_NORMALIZE.get(value.strip().lower(), value)


def _parse_heuristic(full_address: str) -> Dict[str, str]:
    """
    Rule-based split. No API key. Handles:
    - "2604 Tiara United Towers West, Business Bay, Dubai" (UAE: unit, building, area, city)
    - "Street Name 42, 10115 Berlin, Germany"
    - "123 Main St, Dubai, UAE"
    """
    out = {"street": "", "house_number": "", "postal_code": "", "city": "", "country": ""}
    s = str(full_address).strip()
    if not s:
        return out
    s = re.sub(r"[\n\t]+", ", ", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = [p.strip() for p in re.split(r",\s*", s) if p.strip()]
    if not parts:
        out["street"] = s
        return out

    # UAE style: last part is city (Dubai, Abu Dhabi) -> city + country
    # Emit the full VIDEX-friendly label "United Arab Emirates" rather than the
    # short "UAE" so the German country dropdown can match it.
    if parts[-1].lower() in _UAE_CITIES:
        out["city"] = parts[-1]
        out["country"] = "United Arab Emirates"
        parts = parts[:-1]
    # Else: last part is country
    elif parts[-1].lower() in _COUNTRIES or len(parts[-1]) <= 3:
        out["country"] = _normalize_country(parts[-1])
        parts = parts[:-1]
    if not parts:
        return out

    # Second-to-last: city or "postal_code city" (e.g. "10115 Berlin")
    last = parts[-1]
    postcity = re.match(r"^(\d{4,6})\s+(.+)$", last) or re.match(r"^(.+?)\s+(\d{4,6})$", last)
    if postcity:
        g = postcity.groups()
        if g[0].isdigit():
            out["postal_code"], out["city"] = g[0], g[1]
        else:
            out["city"], out["postal_code"] = g[0], g[1]
        parts = parts[:-1]
    elif not out["city"] and not re.match(r"^\d+$", last):
        out["city"] = last
        parts = parts[:-1]
    if not parts:
        return out

    # Remaining: first part = "2604 Tiara United Towers West", rest = "Business Bay" (area)
    first = parts[0]
    rest = parts[1:]  # area(s) in UAE e.g. Business Bay
    # Unit/building number at start: "2604 Tiara United Towers West"
    m = re.match(r"^(\d+[A-Za-z]?)\s+(.+)$", first)
    if m:
        out["house_number"] = m.group(1)
        street_rest = m.group(2).strip()
        if rest:
            out["street"] = street_rest + ", " + ", ".join(rest)
        else:
            out["street"] = street_rest
    else:
        m = re.match(r"^(.+?)\s+(\d+[A-Za-z]?)\s*$", first)
        if m:
            out["street"] = (m.group(1).strip() + (", " + ", ".join(rest) if rest else "")).strip(", ")
            out["house_number"] = m.group(2)
        else:
            out["street"] = first + (", " + ", ".join(rest) if rest else "")
    return out


def parse_address(full_address: str) -> Optional[Dict[str, str]]:
    """
    Split a single address string into: street, house_number, postal_code, city, country.
    Uses rule-based parsing (no API key). If OPENAI_API_KEY is set, can optionally use LLM for harder cases.
    """
    if not full_address or not str(full_address).strip():
        return None

    # Always try heuristic first (no key needed)
    result = _parse_heuristic(full_address)
    if any(result.values()):
        return result

    # Optional: try LLM when key is set (for messy or non-standard addresses)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return result  # return whatever heuristic gave (may be partial)

    try:
        import openai
    except ImportError:
        return result

    prompt = """You are an address parser. Given a single line or multi-line address, return a JSON object with exactly these keys (use empty string if not found):
- street (street name only, no number)
- house_number (building/house number)
- postal_code (ZIP/postal code)
- city (city or town)
- country (country name or code)

Address to parse:
"""
    prompt += str(full_address).strip()
    prompt += "\n\nReturn only valid JSON, no markdown. Example: {\"street\":\"Main Street\",\"house_number\":\"42\",\"postal_code\":\"10115\",\"city\":\"Berlin\",\"country\":\"Germany\"}"

    try:
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        out = json.loads(text)
        if isinstance(out, dict):
            return {
                "street": str(out.get("street", "") or "").strip(),
                "house_number": str(out.get("house_number", "") or "").strip(),
                "postal_code": str(out.get("postal_code", "") or "").strip(),
                "city": str(out.get("city", "") or "").strip(),
                "country": str(out.get("country", "") or "").strip(),
            }
    except Exception:
        pass
    return result
