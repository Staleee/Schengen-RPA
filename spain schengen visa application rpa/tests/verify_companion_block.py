"""Companion identity in the host (§30/§31) and person-filling (§33/§34) blocks.

These two blocks name the one person travelling with the maid, so the name, address, email and
phone in them must all describe that same person. Three defects made them describe two:

  * the merges re-derived the travelling party from ``client_is_travel_companion`` and read only
    that side's keys, so one blank ERP column (the client's email is frequently unset) emptied
    the block even though the workflow's mandatory companion field held the value;
  * the host block printed the trip's accommodation address beside the companion's name;
  * Spain's §34 preferred the raw ``client_name`` over the resolved ``sponsor_client_name``, so
    §31 named the companion while §34 named the employer.

Unlike the other files here this one needs no service and no Docker: the merges are pure
functions, so it calls them in-process.

    python tests/verify_companion_block.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import countries  # noqa: F401  (registers the country configs)
from multi_country_fill import merge_schengen_common_body
from spain_merge import merge_spain_schengen_body

COMPANION_UAE_ADDRESS = "Villa 12, Al Barsha 2, Dubai, United Arab Emirates"
HOTEL_ADDRESS = "Bahnhofstrasse 1, 8001 Zurich, Switzerland"

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:
    if actual == expected:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         expected: {expected!r}\n         actual:   {actual!r}")
        failures.append(label)


def contains(label: str, haystack: object, needle: str) -> None:
    if needle and needle in str(haystack or ""):
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         {needle!r} not found in {haystack!r}")
        failures.append(label)


def base_body(**overrides: object) -> dict:
    """An external companion travels (the common case that exposed all three defects)."""
    body = {
        "country": "Greece",
        "client_is_travel_companion": "No",
        "companion_name": "Test Companion",
        "companion_email": "companion@example.ae",
        "companion_phone": "+971500000001",
        "companion_home_address": COMPANION_UAE_ADDRESS,
        "companion_address": COMPANION_UAE_ADDRESS,
        "companion_hotel_address": HOTEL_ADDRESS,
        "hotel_address": HOTEL_ADDRESS,
        "client_name": "Dalia Baddar",
        "client_email": "",
        "client_phone": "+971500000002",
        "client_erp_address": "Client ERP Address, Dubai",
        "sponsor_client_name": "Test Companion",
        "sponsor_client_email": "companion@example.ae",
        "sponsor_client_phone": "+971500000001",
    }
    body.update(overrides)
    return body


print("external companion — shared merge (Greece / Switzerland / Italy / Bulgaria / Portugal)")
m = merge_schengen_common_body(base_body())
check("§30 name is the companion", m.get("partner_name"), "Test Companion")
contains("§30 block carries the companion email", m.get("partner_address_email"), "companion@example.ae")
# §30/§31 states where the applicant will stay in the Member State, so it is the destination
# accommodation — the companion's UAE home belongs in §33/§34 and must NOT appear here.
contains("§30 block carries the destination accommodation", m.get("partner_address_email"), HOTEL_ADDRESS)
check("§30 block omits the UAE home address",
      COMPANION_UAE_ADDRESS in str(m.get("partner_address_email")), False)
check("§30 phone is the companion's", m.get("partner_phone"), "+971500000001")
check("§33 name is the companion", m.get("person_filling_form_name"), "Test Companion")
contains("§33 block carries the companion UAE address", m.get("person_filling_form_address_email"), COMPANION_UAE_ADDRESS)
contains("§33 block carries the companion email", m.get("person_filling_form_address_email"), "companion@example.ae")

print("\nclient is the companion and the agent corrected the ERP-seeded name — shared merge")
# S2 seeds companion_* from the ERP client but leaves them editable, so a correction lives there.
# Preferring client_* reprinted the stale ERP spelling on every document.
m = merge_schengen_common_body(base_body(
    client_is_travel_companion="Yes",
    client_name="testt",
    client_email="",
    companion_name="test",
    companion_email="dalia@example.ae",
))
check("§30 name is the corrected value, not the ERP one", m.get("partner_name"), "test")
contains("§30 email falls back to the companion column", m.get("partner_address_email"), "dalia@example.ae")

print("\nclient is the companion with no snapshot — the live ERP client is still the fallback")
m = merge_schengen_common_body(base_body(
    client_is_travel_companion="Yes", companion_name="", companion_email="", companion_phone=""))
check("§30 name falls back to the ERP client", m.get("partner_name"), "Dalia Baddar")

print("\nexternal companion — Spain merge")
m = merge_spain_schengen_body(base_body(country="Spain"))
contains("§31 upper names the companion", m.get("host_upper_name_hotel_stacked"), "Test Companion")
contains("§31 upper carries the destination accommodation", m.get("host_upper_name_hotel_stacked"), HOTEL_ADDRESS)
contains("§31 lower carries the companion email", m.get("host_lower_email_hotel_stacked"), "companion@example.ae")
check("§31 phone is the companion's", m.get("host_travel_phone"), "+971500000001")
check("§34 names the companion, not the employer", m.get("sponsor_section_client_name"), "Test Companion")
contains("§34 carries the companion UAE address", m.get("sponsor_section_address_email_stacked"), COMPANION_UAE_ADDRESS)
contains("§34 carries the companion email", m.get("sponsor_section_address_email_stacked"), "companion@example.ae")

print("\nSpain, client is the companion and the agent corrected the ERP-seeded name")
m = merge_spain_schengen_body(base_body(
    country="Spain",
    client_is_travel_companion="Yes",
    client_name="testt",
    client_email="",
    companion_name="test",
    companion_email="dalia@example.ae",
    sponsor_client_name="test",
    sponsor_client_email="dalia@example.ae",
))
contains("§31 upper uses the corrected name", m.get("host_upper_name_hotel_stacked"), "test")
check("§31 upper omits the stale ERP name",
      "testt" in str(m.get("host_upper_name_hotel_stacked")), False)
contains("§31 lower falls back to the companion email", m.get("host_lower_email_hotel_stacked"), "dalia@example.ae")
check("§34 uses the corrected name", m.get("sponsor_section_client_name"), "test")

print("\nexternal companion with a blank companion column — never borrows the client")
m = merge_spain_schengen_body(base_body(
    country="Spain", companion_name="", companion_email="", companion_phone=""))
check("§31 never names the employer when someone else travels",
      "Dalia Baddar" in str(m.get("host_upper_name_hotel_stacked") or ""), False)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("All companion-block checks passed.")
