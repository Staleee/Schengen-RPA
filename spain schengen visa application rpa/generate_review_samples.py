"""Generate review copies of each Schengen country's visa-application PDF.

Spain uses the production AcroForm path; Switzerland/Italy/Portugal/Greece/Bulgaria go through
the new multi-country filler; Turkey is a Word template (production converts to PDF, written here
as .docx for review).

Run from the spain RPA directory:
    python generate_review_samples.py
"""

from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = (BASE.parent / "REVIEW_SAMPLES").resolve()
OUT.mkdir(parents=True, exist_ok=True)

# A realistic payload shaped like the pro-backend buildBlsVisa body.
BLSCOMMON = {
    "maid_surname": "BALABAG",
    "maid_surname_at_birth": "BALABAG",
    "maid_first_names": "EVELYN BAGUIO",
    "maid_date_of_birth": "04.01.1976",
    "maid_place_of_birth": "Lagonglong Misamis",
    "nationality": "Filipino",
    "maid_gender": "F",
    "marital_status": "single",
    "passport_number": "P0150695D",
    "passport_issue_date": "06.08.2021",
    "passport_expiry_date": "05.08.2031",
    "passport_issuing_country": "Philippines",
    "maid_address": "Al Barsha 2, Dubai",
    "maid_email": "evelyn@example.com",
    "maid_phone": "+971501112233",
    "uae_residence_visa_number": "201/2024/1234567",
    "uae_residence_visa_expiry": "01.01.2027",
    "occupation": "Domestic Worker",
    "employer_sponsor_address": "Maids CC Domestic Workers Services - Umm Suqeim Street, Al Barsha 2, Dubai",
    "purpose_additional_info": "I will be accompanying my employer to continue my regular domestic duties and I will return with them after the trip.",
    "number_of_entries": "Multiple",
    "arrival_date": "10.09.2026",
    "departure_date": "20.09.2026",
    "client_is_travel_companion": True,
    "client_name": "Ahmed Al Maktoum",
    "client_hotel_address": "Bahnhofstrasse 1, 8001 Zurich, Switzerland",
    "client_email": "ahmed@example.com",
    "client_phone": "+971501234567",
    "all_expenses_covered_during_stay": True,
}


def main() -> None:
    from multi_country_fill import fill_country_pdf
    from pdf_fill import fill_spain_schengen_pdf

    countries = {
        "Spain": "Spain",
        "Switzerland": "Switzerland",
        "Italy": "Italy",
        "Portugal": "Portugal",
        "Greece": "Greece",
        "Bulgaria": "Bulgaria",
    }
    for name, country in countries.items():
        body = {**BLSCOMMON, "country": country, "main_destination": country, "first_entry_member_state": country}
        if country == "Spain":
            pdf = fill_spain_schengen_pdf(body, None)
        else:
            pdf = fill_country_pdf(country, body, None)
        out = OUT / f"VisaApp_{name}.pdf"
        out.write_bytes(pdf)
        print(f"  wrote {out.name} ({len(pdf)} bytes)")


if __name__ == "__main__":
    main()
    print(f"Done -> {OUT}")
