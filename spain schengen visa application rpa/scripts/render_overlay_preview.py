"""Fill a country template with a sample payload and render each page to PNG for eyeballing.

    python scripts/render_overlay_preview.py italy
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from multi_country_fill import fill_country_pdf  # noqa: E402

_GENERIC = {
    "maid_surname": "BALABAG",
    "maid_surname_at_birth": "BALABAG",
    "maid_first_names": "EVELYN",
    "maid_gender": "Female",
    "marital_status": "Single",
    "maid_place_of_birth": "Manila",
    "maid_date_of_birth": "01.01.1990",
    "nationality": "Filipino",
    "country_of_birth": "Philippines",
    "passport_number": "P0150695D",
    "passport_issue_date": "01.01.2020",
    "passport_expiry_date": "01.01.2030",
    "passport_issuing_country": "Philippines",
    "maid_address": "Al Barsha 2, Dubai",
    "maid_email": "maid@example.com",
    "maid_phone": "+971501112233",
    "uae_residence_visa_number": "201/2024/1234567",
    "uae_residence_visa_expiry": "01.01.2027",
    "occupation": "Domestic Worker",
    "employer_sponsor_address": "Maids CC Domestic Workers Services - Al Barsha, Dubai",
    "purpose_additional_info": "I will be accompanying my employer and will return with them.",
    "number_of_entries": "Multiple",
    "arrival_date": "10.09.2026",
    "departure_date": "20.09.2026",
    "client_is_travel_companion": True,
    "client_name": "Ahmed Al Maktoum",
    "client_hotel_address": "1 Main Street, 1000 City",
    "client_email": "ahmed@example.com",
    "client_phone": "+971501234567",
    "all_expenses_covered_during_stay": True,
}

SAMPLES = {
    "portugal": {**_GENERIC, "country": "Portugal", "main_destination": "Portugal", "first_entry_member_state": "Portugal"},
    "greece": {**_GENERIC, "country": "Greece", "main_destination": "Greece", "first_entry_member_state": "Greece"},
    "bulgaria": {**_GENERIC, "country": "Bulgaria", "main_destination": "Bulgaria", "first_entry_member_state": "Bulgaria"},
    "italy": {
        "country": "Italy",
        "maid_surname": "BALABAG",
        "maid_surname_at_birth": "BALABAG",
        "maid_first_names": "EVELYN",
        "maid_gender": "Female",
        "marital_status": "Single",
        "maid_place_of_birth": "LAGONGLONG MISOR",
        "maid_date_of_birth": "04-01-1976",
        "nationality": "Filipino",
        "country_of_birth": "Philippines",
        "current_nationality": "Filipino",
        "passport_number": "P0150695D",
        "passport_issue_date": "01-01-2020",
        "passport_expiry_date": "01-01-2030",
        "passport_issuing_country": "Philippines",
        "maid_address": "Al Barsha 2, Dubai, UAE",
        "maid_email": "maid@example.com",
        "maid_phone": "+971501112233",
        "uae_residence_visa_number": "201/2024/1234567",
        "uae_residence_visa_expiry": "01-01-2027",
        "occupation": "Domestic Worker",
        "employer_sponsor_address": "Maids CC Domestic Workers Services - Al Barsha, Dubai",
        "purpose_additional_info": "I will be accompanying my employer and will return with them.",
        "main_destination": "Italy",
        "first_entry_member_state": "Italy",
        "number_of_entries": "Multiple",
        "arrival_date": "10-09-2026",
        "departure_date": "20-09-2026",
        "client_is_travel_companion": True,
        "client_name": "Ahmed Al Maktoum",
        "client_hotel_address": "Via Roma 1, 20121 Milano",
        "client_email": "ahmed@example.com",
        "client_phone": "+971501234567",
        "all_expenses_covered_during_stay": True,
    },
}


def main() -> None:
    country = sys.argv[1] if len(sys.argv) > 1 else "italy"
    sample = SAMPLES.get(country)
    if sample is None:
        print(f"no sample for {country}; add one in SAMPLES")
        return
    pdf = fill_country_pdf(country, sample, None)
    outdir = BASE_DIR / "output"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{country}_filled.pdf").write_bytes(pdf)
    doc = fitz.open(stream=pdf, filetype="pdf")
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(dpi=110)
        pix.save(str(outdir / f"{country}_page{i+1}.png"))
    print(f"wrote {len(doc)} page PNGs + {country}_filled.pdf to output/")
    doc.close()


if __name__ == "__main__":
    main()
