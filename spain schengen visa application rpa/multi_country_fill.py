"""
Multi-country Schengen visa-application PDF filler.

The Spain service historically filled only the BLS Spain template. The pro-backend routes
*every* non-Germany/Turkey Schengen country to this service's /fill-pdf endpoint, so this
module generalises it: a single /fill-pdf that picks a per-country PDF template + field map
based on the request's country.

Design:
  * Each country registers a CountryConfig (template file + text-field map + checkbox map).
  * A shared generic merge turns the pro-backend payload into logical keys (names, passport,
    dates, nationality, sex/entries checkboxes, residence visa, accommodation parts).
  * The per-country maps translate those logical keys to the country's AcroForm field names.
  * Filling reuses the tested PyMuPDF/pypdf engine + fuzzy field resolver from pdf_fill.py.

Spain stays on the original dedicated path (pdf_fill.fill_spain_schengen_pdf) — this module
is only used for the additional countries so production Spain behaviour is unchanged.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional, Tuple

from pdf_field_resolve import collect_field_names_from_pdf, resolve_updates
from spain_merge import COSTS_DEFAULT_ON_KEYS

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


class CountryConfig(NamedTuple):
    template: str                      # filename under assets/
    text_map: Dict[str, str]           # logical body key -> PDF text field name (AcroForm engine)
    checkbox_map: Dict[str, str]       # logical body key -> PDF checkbox field name (bool -> on/off)
    force_empty: Tuple[str, ...] = ()  # PDF field names always cleared
    # Clear every widget before filling — required because the provided templates are
    # pre-filled sample applications whose stale values must not leak into a new form.
    clear_existing: bool = True
    # "acroform" (fillable fields) or "overlay" (flat PDF, redact+insert at coordinates).
    engine: str = "acroform"
    # overlay engine only: logical body key -> {page, x, y, w, h, font_size, clear}
    overlay_map: Optional[Dict[str, Dict[str, Any]]] = None
    # overlay engine only: baked-in sample strings to redact wherever they appear (for
    # pre-filled templates like the provided Italy form). Clears stale data before writing.
    redact_strings: Tuple[str, ...] = ()
    # acroform engine only: radio-button groups. logical key -> (field name, on-state string).
    # When the logical value is truthy, the group is set to that on-state.
    radio_map: Optional[Dict[str, Tuple[str, str]]] = None


# Country configs are registered by register_country() from countries/*.py modules at import.
COUNTRY_CONFIGS: Dict[str, CountryConfig] = {}


def normalize_country(value: Any) -> str:
    return str(value or "").strip().lower()


def register_country(country: str, config: CountryConfig) -> None:
    COUNTRY_CONFIGS[normalize_country(country)] = config


def has_country(country: Any) -> bool:
    return normalize_country(country) in COUNTRY_CONFIGS


def supported_countries() -> Tuple[str, ...]:
    return tuple(sorted(COUNTRY_CONFIGS.keys()))


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _nonempty(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


_DEMONYM_OR_ALIAS_TO_COUNTRY: Dict[str, str] = {
    "filipino": "Philippines", "filipina": "Philippines", "indian": "India",
    "pakistani": "Pakistan", "bangladeshi": "Bangladesh", "nepali": "Nepal",
    "nepalese": "Nepal", "sri lankan": "Sri Lanka", "indonesian": "Indonesia",
    "ethiopian": "Ethiopia", "ugandan": "Uganda", "kenyan": "Kenya",
    "egyptian": "Egypt", "jordanian": "Jordan", "lebanese": "Lebanon",
    "syrian": "Syria", "sudanese": "Sudan", "vietnamese": "Vietnam",
    "thai": "Thailand", "chinese": "China",
}


def _country_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    return _DEMONYM_OR_ALIAS_TO_COUNTRY.get(raw.lower(), raw)


def _labelled_accommodation_lines(raw: Any) -> list[str]:
    """Parse the ``accommodation_addresses`` JSON array into labelled lines.

    Each entry is ``{country, street, houseNumber, city, postalCode}``; it renders as
    ``"Country: Street House, PostalCode City"`` (country as a label prefix, not repeated).
    Malformed input yields an empty list; blank entries are skipped.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        import json as _json

        parsed = _json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    lines: list[str] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "").strip()
        street = " ".join(
            x for x in (str(item.get("street") or "").strip(), str(item.get("houseNumber") or "").strip()) if x
        )
        cityline = " ".join(
            x for x in (str(item.get("postalCode") or "").strip(), str(item.get("city") or "").strip()) if x
        )
        body = ", ".join(p for p in (street, cityline) if p)
        if country and body:
            lines.append(f"{country}: {body}")
        elif body or country:
            lines.append(body or country)
    return lines


def merge_schengen_common_body(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Generic merge: pass through every body key, then add canonical conveniences shared by
    all countries (sex / entries / schengen-before checkboxes, country-of-birth, composed
    accommodation address from the structured parts)."""
    b = {k: v for k, v in raw.items() if v is not None}
    out: Dict[str, Any] = dict(b)

    # Sex checkboxes
    g = str(b.get("maid_gender", "")).strip().lower()
    if g in ("f", "female", "mujer", "filipina"):
        out["sex_female"], out["sex_male"] = True, False
    elif g in ("m", "male", "varon", "varón"):
        out["sex_male"], out["sex_female"] = True, False
    elif not _truthy(b.get("sex_male")) and not _truthy(b.get("sex_female")):
        # The sex box has to be ticked. Every applicant on this flow is a housemaid and the
        # templates are already written for one, so an unknown gender defaults to female rather
        # than leaving the field blank. An explicit sex_male from the caller still wins.
        out["sex_female"], out["sex_male"] = True, False

    # Country of birth from nationality (demonym -> country)
    nat = _nonempty(b.get("nationality"))
    if nat and "country_of_birth" not in out:
        out["country_of_birth"] = _country_name(nat)

    # Number of entries checkboxes
    n = str(b.get("number_of_entries", "")).lower()
    if "multiple" in n or _truthy(b.get("entries_multiple")):
        out.update(entries_multiple=True, entries_one=False, entries_two=False)
    elif "two" in n or "2" in n or _truthy(b.get("entries_two")):
        out.update(entries_two=True, entries_one=False, entries_multiple=False)
    else:
        out.update(entries_one=True, entries_two=False, entries_multiple=False)

    # Previous Schengen visa
    if "schengen_visa_before" in b or "schengen_before" in b:
        before = _truthy(b.get("schengen_visa_before")) or _truthy(b.get("schengen_before"))
        out["schengen_before_yes"], out["schengen_before_no"] = before, not before

    # UAE residence visa -> resident-outside-country-of-birth checkbox + number/validity
    if _truthy(b.get("maid_uae_resident")) or _nonempty(b.get("uae_residence_visa_number")):
        out["resident_outside_nationality_yes"] = True
    if _nonempty(b.get("uae_residence_visa_number")):
        out["residence_number"] = b["uae_residence_visa_number"]
    if _nonempty(b.get("uae_residence_visa_expiry")):
        out["residence_valid_until"] = b["uae_residence_visa_expiry"]
    out["resident_outside_nationality_no"] = not _truthy(out.get("resident_outside_nationality_yes"))

    # Travel document: ordinary passport unless told otherwise.
    out.setdefault("travel_doc_ordinary_passport", True)

    # §33 costs — same three boxes and the same default-ON rule as the Spain path. These used to
    # be applied only in spain_merge, which this path never reaches, so every non-Spain template
    # left the sponsor boxes blank unless the caller spelled them out.
    for costs_key in COSTS_DEFAULT_ON_KEYS:
        out[costs_key] = _truthy(b[costs_key]) if costs_key in b else True

    # A couple of templates build a tick box as a one-character *text* input instead of a real
    # checkbox (Switzerland's §33 "referred to in field 30 or 31" is the field literally named
    # `undefined`), so the same answer is also exposed as a mark to type into it.
    out["costs_sponsor_referred_mark"] = (
        "X" if out["costs_sponsor_referred_in_field_30_or_31"] else ""
    )

    # Composed accommodation address from the structured parts, when no combined value given.
    if not _nonempty(out.get("hotel_address")):
        street = " ".join(x for x in (_nonempty(b.get("hotel_street")), _nonempty(b.get("hotel_house_number"))) if x)
        cityline = " ".join(x for x in (_nonempty(b.get("hotel_postal_code")), _nonempty(b.get("hotel_city"))) if x)
        parts = [p for p in (street, cityline, _nonempty(b.get("hotel_country"))) if p]
        if parts:
            out["hotel_address"] = ", ".join(parts)

    # §30 accommodation — when the trip has more than one accommodation address, list every one
    # (each on its own line, prefixed with the destination country it belongs to) instead of only
    # the primary. The §30 address widget is multi-line, so the newlines render as separate lines.
    acc_lines = _labelled_accommodation_lines(b.get("accommodation_addresses"))
    if len(acc_lines) > 1:
        block = "\n".join(acc_lines)
        # Update b too: the §30 host/accommodation block below reads client_/companion_hotel_address
        # from the raw body, so the full list must be visible there as well as in out.
        for key in ("hotel_address", "client_hotel_address", "companion_hotel_address"):
            b[key] = block
            out[key] = block

    # Marital status checkboxes
    marital = str(b.get("marital_status", "")).strip().lower()
    if _truthy(b.get("marital_status_married")) or marital == "married":
        out.update(marital_status_married=True, marital_status_single=False)
    else:
        out.update(marital_status_single=True, marital_status_married=False)

    # Convenience aliases used by many country maps
    if _nonempty(b.get("maid_first_names")) and "given_names" not in out:
        out["given_names"] = b["maid_first_names"]
    if _nonempty(b.get("maid_surname")) and "surname" not in out:
        out["surname"] = b["maid_surname"]

    # Combined "place, country" of birth (many forms use a single box for both).
    place = _nonempty(b.get("maid_place_of_birth"))
    cob = _nonempty(out.get("country_of_birth"))
    if place or cob:
        out["place_and_country_of_birth"] = ", ".join(x for x in (place, cob) if x)

    # Applicant home address + email in one block.
    maid_addr = _nonempty(b.get("maid_address"))
    maid_email = _nonempty(b.get("maid_email"))
    if maid_addr or maid_email:
        out["applicant_address_email"] = "\n".join(x for x in (maid_addr, maid_email) if x)

    # Travel partner (client when they accompany, else the companion).
    if _truthy(b.get("client_is_travel_companion")):
        partner_name = _nonempty(b.get("client_name"))
        partner_addr = _nonempty(b.get("client_hotel_address")) or _nonempty(b.get("hotel_address"))
        partner_email = _nonempty(b.get("client_email"))
        partner_phone = _nonempty(b.get("client_phone"))
    else:
        partner_name = _nonempty(b.get("companion_name"))
        partner_addr = _nonempty(b.get("companion_hotel_address")) or _nonempty(b.get("hotel_address"))
        partner_email = _nonempty(b.get("companion_email"))
        partner_phone = _nonempty(b.get("companion_phone"))
    if partner_name:
        out["partner_name"] = partner_name
    if partner_addr or partner_email:
        out["partner_address_email"] = "\n".join(x for x in (partner_addr, partner_email) if x)
    if partner_phone:
        out["partner_phone"] = partner_phone

    # Main destination + any additional destination countries in one line.
    main_dest = _nonempty(b.get("main_destination")) or _nonempty(b.get("destination_member_state_line"))
    extras: list[str] = []
    dc = b.get("destination_countries")
    if isinstance(dc, str) and dc.strip():
        try:
            import json as _json

            parsed = _json.loads(dc)
            if isinstance(parsed, list):
                extras = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            extras = []
    dests = ([main_dest] if main_dest else []) + [e for e in extras if e != main_dest]
    if dests:
        out["destination_member_states_line"] = ", ".join(dests)

    # Intended journey dates in one line ("arrival - departure").
    arr = _nonempty(b.get("arrival_date"))
    dep = _nonempty(b.get("departure_date"))
    if arr or dep:
        out["intended_dates"] = "  —  ".join(x for x in (arr, dep) if x)

    from datetime import date as _date

    today = _date.today().strftime("%d/%m/%Y")
    if not _nonempty(out.get("place_and_date")):
        out["place_and_date"] = f"United Arab Emirates, {today}"
    out.setdefault("place", "United Arab Emirates")
    out.setdefault("application_date", today)

    return out


def _build_updates(config: CountryConfig, merged: Dict[str, Any], pdf_fields: Optional[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, pdf_name in config.text_map.items():
        val = merged.get(key)
        if val is None:
            continue
        out[pdf_name] = str(val).strip()
    for key, pdf_name in config.checkbox_map.items():
        if key not in merged:
            continue
        out[pdf_name] = "/On" if _truthy(merged[key]) else "/Off"
    for fn in config.force_empty:
        out[fn] = ""
    if pdf_fields:
        for k, v in pdf_fields.items():
            if v is None:
                continue
            out[str(k).strip()] = str(v).strip()
    return out


def _fill_template(template: Path, updates: Dict[str, str], clear_existing: bool, radio_map: Optional[Dict[str, Tuple[str, str]]] = None, merged: Optional[Dict[str, Any]] = None) -> bytes:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        warnings.warn("pymupdf not installed; using pypdf fallback", stacklevel=2)
        from pdf_fill import _fill_with_pypdf

        return _fill_with_pypdf(template, updates)

    canonical = collect_field_names_from_pdf(str(template))
    resolved = resolve_updates(updates, canonical)

    # Radio groups: logical key truthy -> set the group field to its on-state value.
    radio_on: Dict[str, str] = {}
    if radio_map and merged is not None:
        for logical, (field_name, on_state) in radio_map.items():
            if _truthy(merged.get(logical)):
                radio_on[field_name] = on_state

    doc = fitz.open(str(template))
    try:
        try:
            doc.need_appearances = True
        except (AttributeError, RuntimeError):
            pass
        cb = fitz.PDF_WIDGET_TYPE_CHECKBOX
        rb = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
        for i in range(len(doc)):
            for w in doc[i].widgets() or []:
                fn = w.field_name
                if not fn:
                    continue
                if clear_existing:
                    # Reset stale template values so a pre-filled sample form never leaks through.
                    # NB: PyMuPDF does not persist an empty-string text value on save — a single
                    # space clears reliably. Checkboxes clear with False.
                    if w.field_type == cb:
                        w.field_value = False
                        w.update()
                    elif w.field_type == rb:
                        # Radio groups are reset once per group below; skip here.
                        pass
                    else:
                        w.field_value = " "
                        w.update()
                if fn in resolved:
                    val = resolved[fn]
                    if w.field_type == cb:
                        w.field_value = str(val).strip() in ("/On", "/Yes", "Yes", "on", "On", "true", "True", "1")
                    elif w.field_type == rb:
                        continue  # handled after the loop
                    else:
                        sval = str(val)
                        # A multi-line value (e.g. several accommodation addresses, one per
                        # destination) only renders as separate lines when the widget's multiline
                        # flag is set; many template text boxes are single-line, so enable it on demand.
                        if "\n" in sval:
                            try:
                                w.field_flags = (w.field_flags or 0) | 4096
                            except Exception:
                                pass
                        w.field_value = sval
                    w.update()
        # Radio groups: select the widget whose on-state matches the desired value.
        # on_state() may carry PDF name encoding (#20 = space, #28/#29 = parens); decode to compare.
        def _decode(s: str) -> str:
            import re as _re
            return _re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s or "")
        for i in range(len(doc)):
            for w in doc[i].widgets() or []:
                if w.field_type != rb:
                    continue
                fn = w.field_name
                if fn in radio_on and _decode(w.on_state()).strip().lower() == _decode(radio_on[fn]).strip().lower():
                    w.field_value = w.on_state()
                    w.update()
        return doc.tobytes()
    finally:
        doc.close()


def fill_country_pdf(
    country: str,
    structured: Dict[str, Any],
    pdf_fields: Optional[Dict[str, str]] = None,
) -> bytes:
    """Fill the given country's Schengen visa PDF. Raises ValueError for unsupported countries
    and FileNotFoundError when the template is not configured yet."""
    key = normalize_country(country)
    config = COUNTRY_CONFIGS.get(key)
    if config is None:
        raise ValueError(
            f"No PDF template registered for country '{country}'. "
            f"Supported: {', '.join(supported_countries()) or '(none)'}."
        )
    template = ASSETS_DIR / config.template
    if not template.exists():
        raise FileNotFoundError(f"PDF template missing for {country}: assets/{config.template}")

    merged = merge_schengen_common_body(structured)
    if config.engine == "overlay":
        from overlay_fill import fill_overlay_pdf

        # Overlay engine: map logical keys to values, then redact+insert at coordinates.
        values: Dict[str, Any] = {}
        for logical in (config.overlay_map or {}).keys():
            if logical in merged and merged[logical] is not None:
                values[logical] = merged[logical]
        # Also allow direct body keys (e.g. number_of_entries) to drive overlay values.
        return fill_overlay_pdf(template, values, config.overlay_map or {}, list(config.redact_strings))

    updates = _build_updates(config, merged, pdf_fields)
    return _fill_template(template, updates, config.clear_existing, config.radio_map, merged)


def list_country_fields(country: str) -> Tuple[str, ...]:
    """Diagnostic: the AcroForm field names present in a country's template."""
    config = COUNTRY_CONFIGS.get(normalize_country(country))
    if config is None:
        return ()
    template = ASSETS_DIR / config.template
    if not template.exists():
        return ()
    return tuple(collect_field_names_from_pdf(str(template)))


# Importing the countries package registers each available country config.
try:
    import countries  # noqa: F401  (side effect: registers configs)
except ImportError:
    pass
