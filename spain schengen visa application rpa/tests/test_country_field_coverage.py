"""Cross-country field-coverage guard for the multi-country Schengen filler.

Every registered country (AcroForm or overlay) must bind the priority logical fields the
pro-backend sends, so a newly onboarded country cannot silently ship with the gaps that the
Tourist Visa issues sheet catalogued (§11 leaking the residence number, §19 phone missing, §20
residence permit missing, §26 first entry missing, §29 previous-visa missing, §30/31 host phone
missing, §33/34 sponsor block missing, combined travel dates, missing place/date).

Each concept lists the acceptable logical keys — a country passes when it maps at least one of
them (forms differ: Switzerland splits arrival/departure into two widgets while others use a
single "intended_dates"; Italy has only the "No" previous-visa box; overlays carry place+date in
one "place_and_date" box while Italy uses separate place/application_date widgets).

Run directly:  python tests/test_country_field_coverage.py   (exit code = failures)
Or via pytest: pytest tests/test_country_field_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

import countries  # noqa: F401,E402  (import registers every country config)
from multi_country_fill import COUNTRY_CONFIGS  # noqa: E402

# concept label -> acceptable logical keys (at least one must be mapped).
REQUIRED_CONCEPTS: list[tuple[str, set[str]]] = [
    ("§7 nationality", {"nationality"}),
    ("§19 applicant address+email", {"applicant_address_email"}),
    ("§19 applicant phone", {"maid_phone"}),
    ("§20 residence permit number", {"residence_number"}),
    ("§20 residence permit valid-until", {"residence_valid_until"}),
    ("§26 first entry", {"first_entry_member_state"}),
    ("§29 previous Schengen visa", {"schengen_before_yes", "schengen_before_no"}),
    ("arrival date", {"arrival_date", "intended_dates"}),
    ("departure date", {"departure_date", "intended_dates"}),
    ("§30/31 host phone", {"partner_phone"}),
    ("§33/34 person-filling name", {"person_filling_form_name"}),
    ("§33/34 person-filling address+email", {"person_filling_form_address_email"}),
    ("§33/34 person-filling phone", {"person_filling_form_phone"}),
    ("signature place + date", {"place_and_date", "place", "application_date"}),
]


def mapped_keys(config) -> set[str]:
    keys: set[str] = set()
    for attr in ("text_map", "checkbox_map", "mark_map", "radio_map", "overlay_map"):
        mapping = getattr(config, attr, None)
        if mapping:
            keys |= set(mapping.keys())
    return keys


def coverage_gaps() -> dict[str, list[str]]:
    """country -> list of concept labels it fails to cover."""
    gaps: dict[str, list[str]] = {}
    for country, config in sorted(COUNTRY_CONFIGS.items()):
        keys = mapped_keys(config)
        missing = [label for label, acceptable in REQUIRED_CONCEPTS if not (acceptable & keys)]
        if missing:
            gaps[country] = missing
    return gaps


def test_every_country_covers_priority_fields() -> None:
    assert COUNTRY_CONFIGS, "no country configs registered"
    gaps = coverage_gaps()
    assert not gaps, "priority field-coverage gaps: " + "; ".join(
        f"{c}: {', '.join(m)}" for c, m in gaps.items()
    )


def main() -> int:
    if not COUNTRY_CONFIGS:
        print("FAIL no country configs registered")
        return 1
    gaps = coverage_gaps()
    for country in sorted(COUNTRY_CONFIGS):
        missing = gaps.get(country, [])
        status = "ok  " if not missing else "FAIL"
        print(f"  {status} {country:12} {'covers all priority fields' if not missing else ', '.join(missing)}")
    return sum(len(v) for v in gaps.values())


if __name__ == "__main__":
    raise SystemExit(main())
