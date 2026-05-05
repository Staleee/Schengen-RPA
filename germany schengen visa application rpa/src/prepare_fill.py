"""
Shared logic to build merged + translated_data from request body.
Used by both the API (sync /fill and async /submit) and the worker.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

# Add parent for imports when run as script
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from automation.field_translator import FieldTranslator
from address_parser import parse_address

HARDCODED_DEFAULTS = {
    "occupation": "Blue-collar worker",
    "reference_type": "Inviting person",
    "purpose_of_visit": "Tourism",
    "has_residence_permit": True,
    "residence_in_other_country": True,
    "rvisa_type": "Registration Visa",
    "passport_type": "Passport",
    "third_party_pays": True,
    "inviter_pays": True,
    "all_expenses_covered": True,
    "applicant_pays": False,
    "freedom_of_movement": False,
}


def build_translated_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    From raw request body, build merged dict, translate to VIDEX field IDs, validate.
    Returns (translated_data, full_name) for the form filler.
    Raises ValueError with message if validation fails (e.g. missing client_birth_place).
    """
    merged = {**HARDCODED_DEFAULTS, **data}

    full_addr = (
        merged.get("client_address")
        or merged.get("full_address")
        or merged.get("client_full_address")
        or merged.get("inviter_address")
    )
    addr_parts = ("client_street", "client_house_number", "client_postal_code", "client_city", "client_country")
    need_parts = any(not merged.get(k) or not str(merged.get(k, "")).strip() for k in addr_parts)
    if full_addr and need_parts:
        parsed = parse_address(str(full_addr).strip())
        if parsed:
            key_map = {
                "street": "client_street",
                "house_number": "client_house_number",
                "postal_code": "client_postal_code",
                "city": "client_city",
                "country": "client_country",
            }
            for part_key, client_key in key_map.items():
                if not merged.get(client_key) or not str(merged.get(client_key, "")).strip():
                    val = parsed.get(part_key, "") or ""
                    if val:
                        merged[client_key] = val

    pt = (merged.get("passport_type") or "").strip()
    if pt and "official" in pt.lower():
        merged["passport_type"] = "Official passport"

    if not merged.get("employer") or not str(merged.get("employer", "")).strip():
        fn = merged.get("client_first_name") or ""
        sn = merged.get("client_surname") or ""
        client_name = f"{fn} {sn}".strip()
        phone = merged.get("client_phone") or merged.get("phone") or ""
        if phone and str(phone).strip().startswith("+"):
            phone = str(phone).strip()[1:].strip()
        if client_name or phone:
            merged["employer"] = f"{client_name}, {phone}".strip(", ").strip()

    for addr_key, client_key in [
        ("street", "client_street"), ("house_number", "client_house_number"),
        ("postal_code", "client_postal_code"), ("city", "client_city"), ("country", "client_country"),
        ("email", "client_email"), ("phone", "client_phone"),
    ]:
        if (not merged.get(addr_key) or not str(merged.get(addr_key, "")).strip()) and merged.get(client_key):
            val = merged.get(client_key)
            if addr_key == "phone" and val and str(val).strip().startswith("+"):
                val = str(val).strip()[1:].strip()
            merged[addr_key] = val

    for emp_key, client_key in [
        ("employer_street", "client_street"), ("employer_house_number", "client_house_number"),
        ("employer_postal_code", "client_postal_code"), ("employer_city", "client_city"),
        ("employer_country", "client_country"),
    ]:
        if (not merged.get(emp_key) or not str(merged.get(emp_key, "")).strip()) and merged.get(client_key):
            merged[emp_key] = merged[client_key]

    family_name = merged.get("maid_surname") or merged.get("surname") or merged.get("family_name")
    if family_name and (not merged.get("birth_name") and not merged.get("maiden_name")):
        merged["birth_name"] = family_name

    # GCC fallbacks: VIDEX requires a postal code on the Contact + Reference
    # address blocks even though Gulf countries don't really use them. Fill an
    # all-zero placeholder so the field passes Angular's `required` check.
    _GCC_NO_POSTAL = {
        "united arab emirates", "uae",
        "saudi arabia", "ksa",
        "qatar", "bahrain", "oman", "kuwait",
    }
    def _country_is_gcc(value: object) -> bool:
        return bool(value) and str(value).strip().lower() in _GCC_NO_POSTAL

    for postal_key, country_key in [
        ("client_postal_code", "client_country"),
        ("postal_code", "client_country"),
        ("employer_postal_code", "employer_country"),
        ("inviter_postal_code", "client_country"),
    ]:
        if not str(merged.get(postal_key, "") or "").strip():
            if _country_is_gcc(merged.get(country_key)):
                merged[postal_key] = "00000"

    # VIDEX requires "Issued by" on the passport block (separate from "Issuing
    # state"). Fall back to the issuing country / authority if the caller did
    # not provide a specific issuing office.
    if not str(merged.get("passport_issued_by", "") or "").strip():
        merged["passport_issued_by"] = (
            merged.get("passport_issuing_authority")
            or merged.get("passport_issuing_country")
            or ""
        )

    # VIDEX flags "Original nationality" (Nationality at birth) as required
    # even though the label says "if different". Default it to the current
    # nationality so the validator passes without spurious extra data entry.
    if not str(merged.get("nationality_at_birth", "") or "").strip():
        merged["nationality_at_birth"] = (
            merged.get("birth_nationality")
            or merged.get("maid_nationality_at_birth")
            or merged.get("maid_nationality")
            or ""
        )

    translator = FieldTranslator(defaults_path=None)
    translated_data = translator.translate_data(merged)

    ref_place = (
        merged.get("client_birth_place") or merged.get("inviter_birth_place")
        or translated_data.get("referenz.ansprechpartner.geburtsort")
    )
    if not ref_place or not str(ref_place).strip():
        raise ValueError("client_birth_place (or inviter_birth_place) is required for the reference section.")

    first_name = merged.get("maid_first_name") or merged.get("first_name") or merged.get("vorname", "applicant")
    surname = merged.get("maid_surname") or merged.get("surname") or merged.get("familienname", "")
    full_name = f"{first_name}_{surname}".strip("_").replace(" ", "_")

    return translated_data, full_name
