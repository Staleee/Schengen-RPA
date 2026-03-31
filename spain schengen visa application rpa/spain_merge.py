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


def _today_dd_mm_yyyy() -> str:
    return date.today().strftime("%d/%m/%Y")


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


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

    # §19: address + email in one field (Texto18)
    addr, em = b.get("maid_address"), b.get("maid_email")
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
    if "employer_block_text" in b:
        out["employer_block_text"] = b["employer_block_text"]
    elif "employer_sponsor_address" in b:
        out["employer_block_text"] = b["employer_sponsor_address"]
    else:
        out.setdefault("employer_block_text", DEFAULT_EMPLOYER_BLOCK)
    if "purpose_additional_info" not in out:
        out["purpose_additional_info"] = DEFAULT_PURPOSE_24
    if "first_entry_member_state" not in out:
        out["first_entry_member_state"] = "Spain"
    if "destination_member_state_line" not in out:
        out["destination_member_state_line"] = "Spain"

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
    if tp["name"]:
        out["host_travel_name"] = tp["name"]
    if tp["address"]:
        out["host_travel_address"] = tp["address"]
    if tp["email"]:
        out["host_travel_email"] = tp["email"]
    if tp["phone"]:
        out["host_travel_phone"] = tp["phone"]

    s_name = b.get("sponsor_client_name") or b.get("client_name")
    if s_name:
        out.setdefault("sponsor_display_name", s_name)

    s_email = b.get("sponsor_client_email") or b.get("client_email")
    s_addr = b.get("sponsor_client_address") or b.get("client_erp_address") or b.get("client_address")
    if s_email or s_addr:
        out["sponsor_email_address_block"] = "\n".join(x for x in (s_email, s_addr) if x)

    s_phone = b.get("sponsor_client_phone") or b.get("client_phone")
    if s_phone:
        out["sponsor_client_phone_line"] = s_phone

    if "all_expenses_covered_during_stay" not in out:
        out["all_expenses_covered_during_stay"] = True
    if "costs_paid_by_sponsor_host" not in out:
        out["costs_paid_by_sponsor_host"] = True

    if not out.get("place_and_date"):
        out["place_and_date"] = f"{DEFAULT_PLACE_COUNTRY}, {_today_dd_mm_yyyy()}"

    if not _truthy(b.get("skip_footer_name_mirror")):
        if out.get("surname_line_1"):
            out.setdefault("footer_surname", out["surname_line_1"])
        if out.get("given_names_line_3"):
            out.setdefault("footer_given_names", out["given_names_line_3"])

    # §9 Marital: Single = ChkBox, Married = ChkBox-0
    if _truthy(b.get("marital_status_single")) or str(b.get("marital_status", "")).lower() == "single":
        out["marital_status_single"] = True
        out["marital_status_married"] = False
    if _truthy(b.get("marital_status_married")) or str(b.get("marital_status", "")).lower() == "married":
        out["marital_status_married"] = True
        out["marital_status_single"] = False

    return out
