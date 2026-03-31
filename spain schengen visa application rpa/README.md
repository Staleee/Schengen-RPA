# Spain Schengen visa application (UAE BLS) – PDF RPA 🇪🇸

Fills the **official English Schengen application PDF** used by BLS Spain in the UAE. The form is a **fillable PDF** (same interaction model as typing in Adobe Reader), implemented with **pypdf** instead of Playwright.

**Official PDF URL:** https://uae.blsspainvisa.com/assets/pdf/schengen_visa_application_form_english.pdf  

Bundled template: **`assets/schengen_visa_application_form_english.pdf`** (refresh this file if BLS updates the form).

## Setup

From **`spain schengen visa application rpa`**:

- **PowerShell:** `.\setup_env.ps1`
- **CMD:** `setup_env.bat`

Run API:

```text
.\.venv\Scripts\python api_server.py
```

Default **http://0.0.0.0:8090** (change in `api_server.py` if needed).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info + source PDF link |
| GET | `/health` | Health check |
| GET | `/template-info` | Page count, AcroForm field count |
| POST | `/fill-pdf` | JSON body → filled PDF download |

## Documentation

- **`FIELDS_TO_FILL.md`** – Your business spec (maid / client / companion) → JSON keys → PDF fields.
- **`FIELD_MAPPING_GUIDE.md`** – Field **IDs** vs **coordinates**; run `scripts/export_pdf_field_positions.py` and optional overlay PNGs.
- **`HOW_I_FIX_THE_MAPPING.md`** – If values land in wrong boxes: edit **`my_pdf_mapping.json`** (no Python).
- **`REQUEST_BODY_REFERENCE.md`** – Structured keys, `pdf_fields`, examples.
- **`PDF_FIELD_CATALOG.json`** – All 129 AcroForm names and types (`/Tx` text, `/Btn` button/checkbox, `/Sig` signature).
- **`pdf_fill.py`** – `STRUCTURED_FIELD_MAP` and `CHECKBOX_ALIASES` (extend as you map more of the form).

## Compared to France / Germany RPAs

| | France / Germany | Spain (this folder) |
|--|------------------|---------------------|
| Target | HTML web form | Single PDF |
| Stack | Playwright (+ optional CAPTCHA/email) | FastAPI + pypdf |
| Field IDs | CSS / DOM | AcroForm names (`pdf_fields` or mapped keys) |

Many Schengen data points on this PDF use **`Texto1`–`Texto32`**; map them to your DB/Zoho in **`pdf_fields`** after checking the live PDF layout.

## Legal

For authorized use only. Comply with BLS and visa application terms.
