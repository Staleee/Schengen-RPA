"""Generate review copies of the maid NOC (all country variants) + Turkey client NOC.

All NOCs are Word-based and written as filled .docx (production converts them to PDF via
LibreOffice, which isn't installed locally).

Run from the Documents Generation directory:
    python generate_review_samples.py
"""

from __future__ import annotations

from pathlib import Path

from doc_utils import fill_document
from doc_utils import normalize_key
import json

BASE = Path(__file__).resolve().parent
OUT = (BASE.parent / "REVIEW_SAMPLES").resolve()
OUT.mkdir(parents=True, exist_ok=True)

NOC_TEMPLATE = BASE / "noc-travel.docx"
CLIENT_NOC_TEMPLATE = BASE / "client-noc.docx"

MAID = {
    "maid_name": "Maria Santos Reyes",
    "maid_passport_number": "P0150695D",
    "maid_nationality": "Filipino",
    "maid_eid_number": "784-1990-1234567-1",
    "maid_profession": "Domestic Worker",
}
COMPANION = {
    "companion_salutation_name": "Mr.",
    "companion_name": "Ahmed Al Maktoum",
    "companion_nationality": "Emirati",
    "companion_passport_number": "A12345678",
}

NOC_SCENARIOS = {
    "NOC_Egypt_SingleEntry_LongStay": {
        "destination_country": "Egypt", "visa_type": "Single",
        "family_suffix": ", or their family.", "stay_line": "they will be staying for 2 months",
        "addressee": "",
    },
    "NOC_Egypt_MultipleEntry": {
        "destination_country": "Egypt", "visa_type": "Multiple",
        "family_suffix": ", or their family.", "stay_line": "",
        "addressee": "",
    },
    "NOC_Saudi": {
        "destination_country": "Saudi Arabia", "visa_type": "Single",
        "family_suffix": ".", "stay_line": "",
        "addressee": "To: The Saudi Consulate",
    },
    "NOC_Lebanon": {
        "destination_country": "Lebanon", "visa_type": "Single",
        "family_suffix": ".", "stay_line": "",
        "addressee": "",
    },
    "NOC_Schengen_Spain": {
        "destination_country": "Spain", "visa_type": "Schengen",
        "family_suffix": ".", "stay_line": "",
        "addressee": "",
    },
}


def gen_nocs() -> None:
    for name, params in NOC_SCENARIOS.items():
        variables = {**MAID, **COMPANION, **params}
        out = OUT / f"{name}.docx"
        fill_document(NOC_TEMPLATE, variables, out)
        print(f"  wrote {out.name}")


def gen_client_noc() -> None:
    mapping = json.load(open(BASE / "document_mapping.json", encoding="utf-8"))["client-noc"]
    vals = {
        "client_name": "Ahmed Al Maktoum",
        "client_nationality": "Emirati",
        "client_passport_number": "A12345678",
        "client_contact_number": "971501234567",
        "maid_name": "Maria Santos Reyes",
        "maid_nationality": "Filipino",
        "maid_passport_number": "P0150695D",
    }
    variables = {normalize_key(rk): vals.get(normalize_key(rk), "") for rk in mapping}
    out = OUT / "ClientNOC_Turkey.docx"
    fill_document(CLIENT_NOC_TEMPLATE, variables, out)
    print(f"  wrote {out.name}")


if __name__ == "__main__":
    print("Generating maid NOC review samples (.docx) + Turkey client NOC (.docx)...")
    gen_nocs()
    gen_client_noc()
    print(f"Done -> {OUT}")
