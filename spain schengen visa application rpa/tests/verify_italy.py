"""Check the Italian application against the running service, field by field.

Italy used to be filled by drawing text at coordinates onto a flat PDF. That map covered 33 of
the form's fields and the rest printed blank with nothing to say so — §11, §19's phone, §20
entirely, §29, §31's phone, and the declaration place and date. It now uses the ops-provided
fillable template, so every value can be read back by name and asserted.

Two things about that template shape these checks.

**Every tick box is a one-character text input**, not a checkbox: 8-10pt Text widgets sitting over
a printed ☐, which take a typed mark.

**Some option groups still carry only one option** — Female but not Male, Multiple entries but not
Single or Two, Fingerprints-No but not Yes. A box is only marked when the answer is the one it
states, so the two-entries case below asserts that Multiple_entries stays BLANK and that the
service reports the gap. Marking it anyway would state something untrue on a visa application.

§9 is complete: a box was added per civil status, so the married, divorced and widowed cases below
assert their own box is ticked and that Single is not. The merge used to force single for anything
that was not married, which is exactly what those cases catch.

Run via tests/docker-compose.yml, or against a running service with
RPA_BASE_URL=http://localhost:8090 python tests/verify_italy.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

import pymupdf

BASE_URL = os.environ.get("RPA_BASE_URL", "http://localhost:8090").rstrip("/")
SERVICE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "output"
sys.path.insert(0, str(SERVICE_DIR))

MARK = "X"

# Fields that must carry a value, and the value expected for the payload below.
EXPECTED_TEXT = {
    "Surname": "Youssef",
    "Surname_at_birth": "Youssef",
    "First_names": "Norhaina MasundigNalo",
    "Date_of_birth": "16.07.1985",
    "Place_of_birth": "Isulan S Kudarat",
    # §6 must be a COUNTRY. pro-backend sends the nationality here, so this printed the demonym
    # "Egyptian" until the merge started normalising it.
    "Country_of_birth": "Egypt",
    "Current_nationality": "Egyptian",
    "Travel_doc_number": "P6756869A",
    "Travel_doc_date_of_issue": "12.04.2018",
    "Travel_doc_valid_until": "11.04.2028",
    "Travel_doc_issued_by_country": "Egypt",
    # §20 was not wired at all under the overlay.
    "Residence_permit_number": "301/2024/9988776",
    "Residence_permit_valid_until": "14.02.2029",
    "Current_occupation": "Domestic Worker",
    "Main_destination_member_state": "Italy, Greece",
    "First_entry_member_state": "Italy",
    "Intended_date_of_arrival": "29.08.2026",
    "Intended_date_of_departure": "30.08.2026",
    "Inviting_person_name": "Heba Ragaei Youssef",
    # §31's phone was not wired under the overlay.
    "Inviting_person_telephone": "+971509998877",
    # The declaration block was not wired under the overlay.
    "Declaration_place": "United Arab Emirates",
    # §19 the applicant's own address, email and phone. Force-emptied until ops asked for them.
    "Home_address_and_email": "Villa 12, Al Barsha 2, Dubai\nnorhaina@example.ae",
    "Telephone_number": "+971501112233",
    # §34 the person filling in the application: the client here, since they accompany the maid.
    # Their HOME address, not the hotel address §30 carries.
    "Person_filling_form_name": "Heba Ragaei Youssef",
    "Person_filling_form_address_email": "Apt 903, Marina Gate 1, Dubai\ndev@teljoy.io",
    "Person_filling_form_telephone": "+971509998877",
}

# Fields that must be non-empty but whose exact text is not asserted.
EXPECTED_NONEMPTY = (
    "Employer_name_address_telephone",
    "Additional_information_purpose",
    "Inviting_person_address",
    "Declaration_date",
)

# Ticks expected for this payload.
EXPECTED_MARKS = (
    "Sex_Female",
    "Travel_doc_ordinary_passport",
    "Residence_in_other_country_yes",
    "Purpose_tourism",
    "Fingerprints_no",
    "Cost_paid_by_sponsor",
    "Sponsor_referred_field",
    "Sponsor_means_all_expenses",
)

# Nothing is force-emptied on this form any more; §19 and §34 are asserted above.
EXPECTED_BLANK: tuple[str, ...] = ()

PAYLOAD: Dict[str, object] = {
    "country": "italy",
    "maid_surname": "Youssef",
    "maid_surname_at_birth": "Youssef",
    "maid_first_names": "Norhaina MasundigNalo",
    "maid_date_of_birth": "16.07.1985",
    "maid_place_of_birth": "Isulan S Kudarat",
    "nationality": "Egyptian",
    "maid_gender": "Female",
    "marital_status": "married",
    "passport_number": "P6756869A",
    "passport_issue_date": "12.04.2018",
    "passport_expiry_date": "11.04.2028",
    "passport_issuing_country": "Egypt",
    "maid_uae_resident": True,
    "uae_residence_visa_number": "301/2024/9988776",
    "uae_residence_visa_expiry": "14.02.2029",
    "occupation": "Domestic Worker",
    "purpose_tourism": True,
    "employer_sponsor_address": (
        "Maids CC Domestic Workers Services - Umm Suqeim Street, Al Barsha 2, Dubai"
    ),
    "purpose_additional_info": (
        "I will be accompanying my employer to continue my regular domestic duties."
    ),
    "destination_member_state_line": "Italy",
    "destination_countries": '["Greece"]',
    "first_entry_member_state": "Italy",
    "arrival_date": "29.08.2026",
    "departure_date": "30.08.2026",
    "number_of_entries": "two",
    "client_name": "Heba Ragaei Youssef",
    "client_phone": "+971509998877",
    "client_email": "dev@teljoy.io",
    "client_is_travel_companion": True,
    "client_hotel_address": "Italy: milan",
    "client_erp_address": "Apt 903, Marina Gate 1, Dubai",
    "maid_address": "Villa 12, Al Barsha 2, Dubai",
    "maid_email": "norhaina@example.ae",
    "maid_phone": "+971501112233",
    "schengen_visa_before": "no",
}


def _wait_for_service(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
                if r.status == 200:
                    print(f"service up at {BASE_URL}")
                    return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(1)
    raise SystemExit(f"service never became healthy at {BASE_URL}: {last}")


def _fill(payload: Dict[str, object]) -> bytes:
    request = urllib.request.Request(
        f"{BASE_URL}/fill-pdf",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"/fill-pdf returned {exc.code}: {exc.read().decode('utf-8','replace')}")


def _values(pdf_path: Path) -> Tuple[Dict[str, str], Dict[str, float]]:
    """field name -> value, and field name -> font size (to catch a clipped value)."""
    values: Dict[str, str] = {}
    sizes: Dict[str, float] = {}
    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for w in page.widgets() or []:
                values[w.field_name] = (w.field_value or "").strip()
                sizes[w.field_name] = w.text_fontsize or 0.0
    finally:
        doc.close()
    return values, sizes


def _check(label: str, ok: bool, detail: str = "") -> int:
    print("  %-4s %-44s %s" % ("ok" if ok else "FAIL", label, detail))
    return 0 if ok else 1


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _wait_for_service()
    failures = 0

    pdf = OUT_DIR / "italy-application.pdf"
    pdf.write_bytes(_fill(dict(PAYLOAD)))
    values, sizes = _values(pdf)
    print(f"\nitaly ({pdf.name}) — {len(values)} fields on the form")

    for field, expected in EXPECTED_TEXT.items():
        got = values.get(field, "<absent>")
        failures += _check(field, got == expected, "" if got == expected else f"got {got!r}")

    for field in EXPECTED_NONEMPTY:
        failures += _check(field + " (non-empty)", bool(values.get(field)),
                           "" if values.get(field) else "blank")

    for field in EXPECTED_MARKS:
        failures += _check(field + " (ticked)", values.get(field) == MARK,
                           "" if values.get(field) == MARK else f"got {values.get(field)!r}")

    for field in EXPECTED_BLANK:
        failures += _check(field + " (blank)", not values.get(field),
                           "" if not values.get(field) else f"got {values.get(field)!r}")

    # A value longer than its box is clipped by the form with no indication; §25 held
    # "Italy, Greece" in a 45pt box at 9pt and printed "Italy, Gree".
    failures += _check(
        "§25 shrunk to fit rather than clipped",
        0 < sizes.get("Main_destination_member_state", 0) < 9.0,
        f"fontsize={sizes.get('Main_destination_member_state')}",
    )

    # §9 now carries a box per civil status, so a married applicant ticks Married and only Married.
    failures += _check("Civil_status_Married ticked for a married applicant",
                       values.get("Civil_status_Married") == MARK,
                       f"got {values.get('Civil_status_Married')!r}")
    failures += _check("Civil_status_Single blank for a married applicant",
                       not values.get("Civil_status_Single"),
                       f"got {values.get('Civil_status_Single')!r}")
    failures += _check("Multiple_entries blank when two entries requested",
                       not values.get("Multiple_entries"),
                       f"got {values.get('Multiple_entries')!r}")

    from multi_country_fill import COUNTRY_CONFIGS, merge_schengen_common_body, report_missing_options

    gaps = report_missing_options(COUNTRY_CONFIGS["italy"], merge_schengen_common_body(dict(PAYLOAD)))
    failures += _check("reported: entries=entries_two", "entries=entries_two" in gaps,
                       "" if "entries=entries_two" in gaps else f"report was {list(gaps)}")
    failures += _check("marital status no longer reported as a gap",
                       not any(g.startswith("marital status=") for g in gaps),
                       f"report was {list(gaps)}")

    # The merge used to force single=True for anything that was not "married", so a divorced or
    # widowed applicant had Single ticked — an untrue statement, and one report_missing_options
    # could not see because by then the answer looked like "single".
    for status, box in (("divorced", "Civil_status_Divorced"), ("widow", "Civil_status_Widow")):
        other = OUT_DIR / f"italy-application-{status}.pdf"
        other.write_bytes(_fill(dict(PAYLOAD, marital_status=status)))
        other_values, _ = _values(other)
        failures += _check(f"{box} ticked for a {status} applicant",
                           other_values.get(box) == MARK,
                           f"got {other_values.get(box)!r}")
        failures += _check(f"Civil_status_Single blank for a {status} applicant",
                           not other_values.get("Civil_status_Single"),
                           f"got {other_values.get('Civil_status_Single')!r}")

    # §34 with a companion rather than the client accompanying. pro-backend now sends the
    # companion's own home address as companion_home_address, so both halves print. Neither the
    # hotel address nor the CLIENT's home address may be substituted — §34 asks where this
    # person lives, and either would state something untrue.
    comp = OUT_DIR / "italy-application-companion.pdf"
    comp.write_bytes(_fill(dict(
        PAYLOAD,
        client_is_travel_companion=False,
        companion_name="Karim Ragaei Youssef",
        companion_email="karim@example.ae",
        companion_phone="+971507776655",
        companion_home_address="Flat 4, Al Nahda 2, Sharjah",
    )))
    comp_values, _ = _values(comp)
    failures += _check("§34 name is the companion",
                       comp_values.get("Person_filling_form_name") == "Karim Ragaei Youssef",
                       f"got {comp_values.get('Person_filling_form_name')!r}")
    failures += _check("§34 is the companion's home address and email",
                       comp_values.get("Person_filling_form_address_email")
                       == "Flat 4, Al Nahda 2, Sharjah\nkarim@example.ae",
                       f"got {comp_values.get('Person_filling_form_address_email')!r}")

    # Without a companion_home_address the address half must stay out rather than fall back to
    # the client's — this is the old behaviour, and it is still the correct one.
    comp_noaddr = OUT_DIR / "italy-application-companion-no-address.pdf"
    comp_noaddr.write_bytes(_fill(dict(
        PAYLOAD,
        client_is_travel_companion=False,
        companion_name="Karim Ragaei Youssef",
        companion_email="karim@example.ae",
        companion_phone="+971507776655",
    )))
    comp_noaddr_values, _ = _values(comp_noaddr)
    failures += _check("§34 falls back to the email alone with no companion home address",
                       comp_noaddr_values.get("Person_filling_form_address_email") == "karim@example.ae",
                       f"got {comp_noaddr_values.get('Person_filling_form_address_email')!r}")

    # When the client accompanies, an agent-corrected companion_home_address outranks the address
    # seeded from their ERP record.
    client_edited = OUT_DIR / "italy-application-client-edited-address.pdf"
    client_edited.write_bytes(_fill(dict(
        PAYLOAD,
        companion_home_address="Villa 7, Jumeirah 1, Dubai",
    )))
    client_edited_values, _ = _values(client_edited)
    failures += _check("§34 prefers the edited home address over client_erp_address",
                       client_edited_values.get("Person_filling_form_address_email")
                       == "Villa 7, Jumeirah 1, Dubai\ndev@teljoy.io",
                       f"got {client_edited_values.get('Person_filling_form_address_email')!r}")

    # A single applicant must actually tick Single, or the mark map is wired the wrong way round.
    single = OUT_DIR / "italy-application-single.pdf"
    single.write_bytes(_fill(dict(PAYLOAD, marital_status="single", number_of_entries="multiple")))
    single_values, _ = _values(single)
    failures += _check("Civil_status_Single ticked for a single applicant",
                       single_values.get("Civil_status_Single") == MARK,
                       f"got {single_values.get('Civil_status_Single')!r}")
    failures += _check("Multiple_entries ticked when multiple requested",
                       single_values.get("Multiple_entries") == MARK,
                       f"got {single_values.get('Multiple_entries')!r}")

    doc = pymupdf.open(pdf)
    try:
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=100).save(str(OUT_DIR / f"italy-application-p{i}.png"))
    finally:
        doc.close()

    print(f"\nartifacts in {OUT_DIR}")
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
