"""
Map ERP / Zoho style payload → flat PDF field keys for pdf_fill.

Mapping aligned with FIELDS_TO_FILL.md (user-verified vs bundled PDF catalog).
"""

from datetime import date
from typing import Any, Dict, Optional

DEFAULT_EMPLOYER_BLOCK = (
    "Maids CC Domestic Workers Services - Umm Suqeim Street, Al Barsha 2, Dubai"
)
DEFAULT_PURPOSE_24 = (
    "I will be accompanying my employer to continue my regular domestic duties "
    "and I will return with them after the trip."
)
DEFAULT_PLACE_COUNTRY = "United Arab Emirates"

# §33 "Cost of travelling and living during the applicant's stay is covered". In the maids.cc
# flow the client always sponsors the maid's trip and is the host already named in §30/§31, so
# all three boxes default ON; an explicit false in the request still wins. On the harmonised
# form these are "por un patrocinador anfitrión…", "indicado en las casillas 30 o 31" and
# "Todos los gastos de estancia…". multi_country_fill applies the same rule, so every country
# template behaves identically.
COSTS_DEFAULT_ON_KEYS = (
    "all_expenses_covered_during_stay",
    "costs_paid_by_sponsor_host",
    "costs_sponsor_referred_in_field_30_or_31",
)

# §9 marital status: the logical key, and the words that select it. Checked in order, so the
# first match wins and exactly one box is ticked. Covers every HousemaidCivilStatus value in the
# ERP (SINGLE, MARRIED, DIVORCED, WIDOW) plus the other options the form prints.
_MARITAL_OPTIONS = (
    ("single", ("single", "unmarried", "soltero", "soltera")),
    ("married", ("married", "casado", "casada")),
    ("divorced", ("divorced", "divorciado", "divorciada")),
    ("widowed", ("widow", "widowed", "widower", "viudo", "viuda")),
    ("separated", ("separated", "separado", "separada")),
    ("registered_union", ("registered union", "registered_union", "union registrada")),
)


def _today_dd_mm_yyyy() -> str:
    return date.today().strftime("%d/%m/%Y")


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _nonempty_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


# Zoho often sends only `nationality` (demonym). §6 país de nacimiento / Texto3 wants a country name.
_DEMONYM_OR_ALIAS_TO_COUNTRY: Dict[str, str] = {
    "filipino": "Philippines",
    "filipina": "Philippines",
    "indian": "India",
    "pakistani": "Pakistan",
    "bangladeshi": "Bangladesh",
    "nepali": "Nepal",
    "nepalese": "Nepal",
    "sri lankan": "Sri Lanka",
    "indonesian": "Indonesia",
    "ethiopian": "Ethiopia",
    "ugandan": "Uganda",
    "kenyan": "Kenya",
    "ghanaian": "Ghana",
    "nigerian": "Nigeria",
    "egyptian": "Egypt",
    "jordanian": "Jordan",
    "lebanese": "Lebanon",
    "syrian": "Syria",
    "sudanese": "Sudan",
    "vietnamese": "Vietnam",
    "thai": "Thailand",
    "chinese": "China",
    "russian": "Russia",
    "ukrainian": "Ukraine",
    "american": "United States",
    "british": "United Kingdom",
    "brit": "United Kingdom",
}


def _country_name_for_birth_field(nationality_value: str) -> str:
    """Map common nationality strings to country; otherwise return trimmed input (e.g. already 'Philippines')."""
    raw = str(nationality_value).strip()
    if not raw:
        return raw
    key = raw.lower()
    return _DEMONYM_OR_ALIAS_TO_COUNTRY.get(key, raw)


def resolve_travel_partner_contact(b: Dict[str, Any]) -> Dict[str, Optional[str]]:
    if _truthy(b.get("client_is_travel_companion")):
        return {
            "name": b.get("client_name") or b.get("client_full_name"),
            "address": b.get("client_hotel_address") or b.get("client_address"),
            "email": b.get("client_email"),
            "phone": b.get("client_phone"),
        }
    return {
        "name": b.get("companion_name") or b.get("companion_full_name"),
        "address": b.get("companion_hotel_address") or b.get("companion_address"),
        "email": b.get("companion_email"),
        "phone": b.get("companion_phone"),
    }


def merge_spain_schengen_body(raw: Dict[str, Any]) -> Dict[str, Any]:
    b = {k: v for k, v in raw.items() if v is not None}
    out: Dict[str, Any] = dict(b)

    if "maid_surname" in b and "surname_line_1" not in b:
        out["surname_line_1"] = b["maid_surname"]
    if "maid_surname_at_birth" in b and "surname_at_birth" not in b:
        out["surname_at_birth"] = b["maid_surname_at_birth"]
    if "maid_first_names" in b and "given_names_line_3" not in b:
        out["given_names_line_3"] = b["maid_first_names"]
    if "last_name" in b and "surname_line_1" not in out:
        out["surname_line_1"] = b["last_name"]
    if "first_name" in b and "given_names_line_3" not in out:
        out["given_names_line_3"] = b["first_name"]
    if "first_names" in b and "given_names_line_3" not in out:
        out["given_names_line_3"] = b["first_names"]

    for k in (
        "maid_date_of_birth",
        "maid_place_of_birth",
        "maid_address",
        "maid_email",
        "maid_phone",
        "passport_number",
        "passport_issue_date",
        "passport_expiry_date",
        "passport_issuing_country",
        "country_of_birth",
    ):
        if k in b:
            out[k] = b[k]

    # Nationality → Texto4 + Texto5 (not NacionalidadNationality)
    if "nationality" in b:
        out["nationality_line_top"] = b.get("nationality_line_top") or b["nationality"]
        out["nationality_line_bottom"] = b.get("nationality_line_bottom") or b.get("nationality_second_line") or b["nationality"]

    # §6 Country of birth (Texto3): always set from nationality when present (payload often duplicates demonym).
    nat = _nonempty_str(b.get("nationality"))
    if nat:
        out["country_of_birth"] = _country_name_for_birth_field(nat)

    # §19: maid home address + maid email only → Texto18 (no client email here)
    addr = _nonempty_str(
        b.get("maid_address")
        or b.get("maid_full_address")
        or b.get("maid_home_address")
    )
    em = _nonempty_str(b.get("maid_email"))
    if addr or em:
        out["maid_address_email_combined"] = "\n".join(x for x in (addr, em) if x)

    if "maid_gender" in b:
        g = str(b["maid_gender"]).strip().lower()
        if g in ("f", "female", "mujer", "filipina"):
            out["sex_female"] = True
            out["sex_male"] = False
        elif g in ("m", "male", "varón", "varon"):
            out["sex_male"] = True
            out["sex_female"] = False

    if "travel_doc_ordinary_passport" in b:
        out["travel_doc_ordinary_passport"] = _truthy(b["travel_doc_ordinary_passport"])
    else:
        out["travel_doc_ordinary_passport"] = True

    if "purpose_tourism" in b:
        out["purpose_tourism"] = _truthy(b["purpose_tourism"])
    else:
        out["purpose_tourism"] = True

    if "occupation" not in out:
        out["occupation"] = "Domestic Worker"
    eb = _nonempty_str(b.get("employer_block_text"))
    if eb is None:
        eb = _nonempty_str(b.get("employer_sponsor_address"))
    if eb is None:
        eb = DEFAULT_EMPLOYER_BLOCK
    out["employer_block_text"] = eb
    if "purpose_additional_info" not in out:
        out["purpose_additional_info"] = DEFAULT_PURPOSE_24
    if "first_entry_member_state" not in out:
        out["first_entry_member_state"] = "Spain"
    # §25 destination(s): primary + any additional destination countries, so multi-country
    # itineraries are reflected on the Spain form (not just the main destination).
    main_dest = (
        _nonempty_str(b.get("main_destination"))
        or _nonempty_str(b.get("destination_member_state_line"))
        or "Spain"
    )
    extras: list = []
    dc = b.get("destination_countries")
    if isinstance(dc, str) and dc.strip():
        try:
            import json as _json

            parsed = _json.loads(dc)
            if isinstance(parsed, list):
                extras = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            extras = []
    dests = [main_dest] + [e for e in extras if e.lower() != main_dest.lower()]
    out["destination_member_state_line"] = ", ".join(dests)

    # Passport dates/country → Texto11–13 only (not Válido desde / I3astaUntil)
    if b.get("maid_phone"):
        out["phone"] = b["maid_phone"]
    elif b.get("phone"):
        out["phone"] = b["phone"]

    if _truthy(b.get("maid_uae_resident")) or _truthy(b.get("resident_outside_country_of_birth")):
        out["resident_outside_nationality_yes"] = True
    if b.get("uae_residence_visa_number"):
        out["residence_number"] = b["uae_residence_visa_number"]
    if b.get("uae_residence_visa_expiry"):
        out["residence_valid_until"] = b["uae_residence_visa_expiry"]

    if "schengen_visa_before" in b:
        if _truthy(b["schengen_visa_before"]):
            out["schengen_before_yes"] = True
            out["schengen_before_no"] = False
        else:
            out["schengen_before_no"] = True
            out["schengen_before_yes"] = False

    n = str(b.get("number_of_entries", "")).lower()
    if "single" in n or b.get("entries_one"):
        out["entries_one"] = True
        out["entries_two"] = False
        out["entries_multiple"] = False
    elif "two" in n or "2" in n or b.get("entries_two"):
        out["entries_two"] = True
        out["entries_one"] = False
        out["entries_multiple"] = False
    elif "multiple" in n or b.get("entries_multiple"):
        out["entries_multiple"] = True
        out["entries_one"] = False
        out["entries_two"] = False
    else:
        if not any(b.get(k) for k in ("entries_one", "entries_two", "entries_multiple", "number_of_entries")):
            out["entries_one"] = True
            out["entries_two"] = False
            out["entries_multiple"] = False

    if b.get("arrival_date"):
        out["arrival_date"] = b["arrival_date"]
    if b.get("departure_date"):
        out["departure_date"] = b["departure_date"]

    tp = resolve_travel_partner_contact(b)
    n, ad = _nonempty_str(tp["name"]), _nonempty_str(tp["address"])
    em = _nonempty_str(tp["email"])
    # §31 upper (Texto25): client/travel name, then hotel/address
    if n or ad:
        out["host_upper_name_hotel_stacked"] = "\n".join(x for x in (n, ad) if x)
    # §31 lower (Texto26): client email, then hotel/address
    if em or ad:
        out["host_lower_email_hotel_stacked"] = "\n".join(x for x in (em, ad) if x)
    if tp["phone"]:
        out["host_travel_phone"] = tp["phone"]

    # §34: Texto31 = client name; Texto32 = ERP address + client email
    c_name = (
        _nonempty_str(b.get("client_name"))
        or _nonempty_str(b.get("client_full_name"))
        or _nonempty_str(b.get("sponsor_client_name"))
    )
    if c_name:
        out["sponsor_section_client_name"] = c_name
    erp_addr = (
        _nonempty_str(b.get("client_erp_address"))
        or _nonempty_str(b.get("sponsor_client_address"))
        or _nonempty_str(b.get("client_address"))
    )
    c_em = _nonempty_str(b.get("client_email")) or _nonempty_str(b.get("sponsor_client_email"))
    if erp_addr or c_em:
        parts = [x for x in (erp_addr, c_em) if x]
        if len(parts) == 2 and parts[0] == parts[1]:
            parts = [parts[0]]
        out["sponsor_section_address_email_stacked"] = "\n".join(parts)

    s_phone = b.get("sponsor_client_phone") or b.get("client_phone")
    if s_phone:
        out["sponsor_client_phone_line"] = s_phone

    for costs_key in COSTS_DEFAULT_ON_KEYS:
        out[costs_key] = _truthy(b[costs_key]) if costs_key in b else True

    if not out.get("place_and_date"):
        out["place_and_date"] = f"{DEFAULT_PLACE_COUNTRY}, {_today_dd_mm_yyyy()}"

    # §1/§3 footer repeats (`ApellidosSumamefamily name`, `NombresFirst names Given names`):
    # left blank in pdf_fill — do not mirror surname / given names here.

    # §9 Marital status. Only Single and Married used to be handled, so a maid whose ERP civil
    # status is DIVORCED or WIDOW had every box left blank. The form carries a box for each, and
    # exactly one is ticked: the caller's explicit flag wins, otherwise the free-text
    # `marital_status` decides.
    marital = str(b.get("marital_status", "")).strip().lower()
    chosen = None
    for option, words in _MARITAL_OPTIONS:
        if _truthy(b.get(f"marital_status_{option}")) or marital in words:
            chosen = option
            break
    if chosen:
        for option, _ in _MARITAL_OPTIONS:
            out[f"marital_status_{option}"] = option == chosen

    return out
