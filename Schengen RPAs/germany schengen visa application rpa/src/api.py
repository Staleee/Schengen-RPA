"""
VIDEX Form Automation API
Accepts JSON POST requests and returns generated PDF
"""

import os
import tempfile
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from automation.field_translator import FieldTranslator
from automation.form_filler import VidexFormFiller

app = FastAPI(
    title="VIDEX Form Automation API",
    description="Automate German Schengen visa application form filling",
    version="1.0.0"
)

# Paths
BASE_DIR = Path(__file__).parent.parent
SCHEMA_PATH = BASE_DIR / "output" / "fields_schema.json"

# Hardcoded defaults – do NOT send these in the request body. We fill them for you.
# marital_status, number_of_entries, passport_type (or arrival/departure) are in the request body.
# has_residence_permit / residence_in_other_country = "Do you have a residence permit in another country?" (e.g. re-entry); we set true so the residence section is filled.
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

# Thread pool for running playwright (sync) in async context
executor = ThreadPoolExecutor(max_workers=2)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "VIDEX Form Automation API",
        "usage": "POST /fill with JSON body containing applicant data",
        "example_fields": [
            "surname", "first_name", "date_of_birth", "nationality",
            "passport_number", "visa_start_date", "visa_end_date"
        ]
    }


@app.get("/health")
async def health():
    """Health check for Railway"""
    return {"status": "healthy"}


@app.post("/fill")
async def fill_form(data: dict[str, Any]):
    """
    Fill VIDEX form with applicant data and return PDF.
    
    Send a JSON body with applicant fields (English names supported).
    Returns the generated PDF file.
    
    Example (maid_* = applicant, client_* = inviting person):
    ```json
    {
        "maid_surname": "Santos",
        "maid_first_name": "Maria",
        "maid_date_of_birth": "22.05.1990",
        "maid_country_of_birth": "Philippines",
        "maid_nationality": "Philippines",
        "client_surname": "Muller",
        "client_first_name": "Hans",
        "client_birth_place": "Munich",
        "client_country": "Germany",
        ...
    }
    ```
    """
    try:
        # Start with hardcoded defaults; body only sends what varies (no occupation, reference_type, costs, etc.)
        merged = {**HARDCODED_DEFAULTS, **data}

        # passport_type: default "Passport"; if body has "official" use "Official passport"
        pt = (merged.get("passport_type") or "").strip()
        if pt and "official" in pt.lower():
            merged["passport_type"] = "Official passport"

        # Employer = client name + client phone (no separate employer in body)
        if not merged.get("employer") or not str(merged.get("employer", "")).strip():
            fn = merged.get("client_first_name") or ""
            sn = merged.get("client_surname") or ""
            client_name = f"{fn} {sn}".strip()
            phone = merged.get("client_phone") or merged.get("phone") or ""
            if phone and str(phone).strip().startswith("+"):
                phone = str(phone).strip()[1:].strip()
            if client_name or phone:
                merged["employer"] = f"{client_name}, {phone}".strip(", ").strip()

        # Applicant address (Contact Data) = client when not provided
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

        # Occupation address = client address (maid works at client's house; same fields, different section)
        for emp_key, client_key in [
            ("employer_street", "client_street"), ("employer_house_number", "client_house_number"),
            ("employer_postal_code", "client_postal_code"), ("employer_city", "client_city"),
            ("employer_country", "client_country"),
        ]:
            if (not merged.get(emp_key) or not str(merged.get(emp_key, "")).strip()) and merged.get(client_key):
                merged[emp_key] = merged[client_key]

        # Name at birth (geburtsname) = same as family name when not provided
        family_name = merged.get("maid_surname") or merged.get("surname") or merged.get("family_name")
        if family_name and (not merged.get("birth_name") and not merged.get("maiden_name")):
            merged["birth_name"] = family_name

        # Translate to German field IDs (no defaults file – we use HARDCODED_DEFAULTS only)
        translator = FieldTranslator(defaults_path=None)
        translated_data = translator.translate_data(merged)
        
        # Reference = Inviting person; need client_birth_place for reference section
        ref_place = (
            merged.get("client_birth_place") or merged.get("inviter_birth_place")
            or translated_data.get("referenz.ansprechpartner.geburtsort")
        )
        if not ref_place or not str(ref_place).strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "client_birth_place (or inviter_birth_place) is required for the reference section.",
                    "example": {"client_birth_place": "Berlin"},
                },
            )

        # Get name for filename (applicant = maid)
        first_name = merged.get("maid_first_name") or merged.get("first_name") or merged.get("vorname", "applicant")
        surname = merged.get("maid_surname") or merged.get("surname") or merged.get("familienname", "")
        full_name = f"{first_name}_{surname}".strip("_").replace(" ", "_")
        
        # Run form filling in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            run_form_filler,
            translated_data,
            full_name
        )
        
        if result.get("pdf_content"):
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"videx_{full_name}_{timestamp}.pdf"
            
            return Response(
                content=result["pdf_content"],
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result.get("error", "PDF generation failed"),
                    "fields_filled": result.get("successful", 0),
                    "fields_failed": result.get("failed", 0)
                }
            )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e)}
        )


def run_form_filler(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Run the form filler synchronously (called from thread pool)"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            screenshot_dir = temp_path / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            
            # Initialize form filler
            headless = os.environ.get("HEADLESS", "true").lower() in ("1", "true", "yes")
            filler = VidexFormFiller(
                applicant_data=data,
                schema_path=SCHEMA_PATH if SCHEMA_PATH.exists() else None,
                headless=headless,
                slow_mo=0,
                screenshot_on_error=True,
                screenshot_dir=screenshot_dir,
                output_dir=temp_path
            )
            
            # Fill the form
            result = filler.fill_form(submit=False, save_pdf=True)
            
            # Read PDF content if available
            pdf_path = result.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                result["pdf_content"] = Path(pdf_path).read_bytes()
            
            return result
            
    except Exception as e:
        return {"error": str(e), "successful": 0, "failed": 0}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
