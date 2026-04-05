# Spain Schengen PDF – Request body (`POST /fill-pdf`)

The UAE BLS form is a **fillable PDF** (AcroForm), not a website. Values are written into named fields. Full list: **`PDF_FIELD_CATALOG.json`**.

**Official PDF (download / compare versions):**  
https://uae.blsspainvisa.com/assets/pdf/schengen_visa_application_form_english.pdf  

Bundled copy: **`assets/schengen_visa_application_form_english.pdf`**

**Primary mapping (maid / client / companion, defaults):** **`FIELDS_TO_FILL.md`**

The API accepts **any extra JSON keys** (`model_config.extra = "allow"`) so Zoho can POST a wide payload; known keys are merged in **`spain_merge.py`** and written in **`pdf_fill.py`**.

---

## 1. Controls

| Key | Description |
|-----|-------------|
| `use_business_merge` | Default `true`: apply defaults + client/companion routing. Set `false` for raw `pdf_fields` only. |
| `pdf_fields` | Exact AcroForm name → value; applied last (overrides). |

### Inspecting what Zoho (or any client) sent

Set on the server (e.g. Railway variables):

| Variable | Effect |
|----------|--------|
| `SPAIN_LOG_REQUEST_BODY=1` | Logs one line per request: `spain_fill_pdf_request_body` + full JSON on **stdout** (view in platform logs). Contains PII — use only in trusted environments. |
| `SPAIN_SAVE_REQUEST_BODY_DIR=/path/to/dir` | Also writes a timestamped `.json` file per request (pretty-printed). Use a persistent volume if you need files to survive restarts. |

Both can be enabled together. The logged object is the **full** parsed body (including `pdf_fields` and `use_business_merge`).

## 2. Common payload keys (after merge)

| Area | Example keys |
|------|----------------|
| Maid identity | `maid_surname`, `maid_surname_at_birth`, `maid_first_names`, `maid_date_of_birth`, `maid_place_of_birth`, **`country_of_birth`** (ignored when **`nationality`** is sent — §6 / `Texto3` is always filled from nationality: demonym→country e.g. *Filipino*→*Philippines*), `nationality`, `maid_gender` |
| Passport | `passport_number`, `passport_issue_date`, `passport_expiry_date`, `passport_issuing_country` |
| Maid contact | `maid_address`, `maid_email`, `maid_phone` |
| UAE residence (§20) | `maid_uae_resident`, `uae_residence_visa_number`, `uae_residence_visa_expiry` |
| Trip | `arrival_date`, `departure_date`, `number_of_entries`, `schengen_visa_before` |
| Client/companion | `client_is_travel_companion`, `client_name`, `client_hotel_address`, `client_email`, `client_phone`, `companion_*`, `sponsor_client_*`, `client_erp_address` |

Full table: **`FIELDS_TO_FILL.md`**. Low-level PDF names: **`pdf_fill.py`** (`STRUCTURED_FIELD_MAP`, `TEXTO_FIELD_MAP`, `CHECKBOX_ALIASES`).

---

## 3. Raw PDF fields (`pdf_fields`)

Any AcroForm name → string value. **Merged after** structured keys; same name **overrides**.

Use this for:

- **`Texto1` … `Texto32`** and other generic boxes (dates, passport number, place of birth, etc.) once you align them visually with the PDF.
- Checkboxes: value **`/On`** or **`/Off`** (some viewers also accept `Yes`/`Off`; pypdf uses `/On`/`/Off` for this template).

Example:

```json
{
  "maid_surname": "García",
  "maid_first_names": "María",
  "sex_female": true,
  "travel_doc_ordinary_passport": true,
  "purpose_tourism": true,
  "entries_one": true,
  "pdf_fields": {
    "Texto5": "P1234567",
    "Texto6": "15/03/1990"
  }
}
```

---

## 4. Example minimal `POST /fill-pdf`

```http
POST /fill-pdf
Content-Type: application/json
```

```json
{
  "maid_surname": "Santos",
  "maid_first_names": "Maria",
  "nationality": "Philippines",
  "maid_phone": "+971501234567",
  "maid_gender": "female",
  "passport_number": "P1234567",
  "passport_issue_date": "01/01/2020",
  "passport_expiry_date": "01/01/2030",
  "passport_issuing_country": "Philippines",
  "client_is_travel_companion": true,
  "client_name": "Ahmed Example",
  "client_email": "client@example.ae",
  "client_phone": "+971500000000"
}
```

Response: **PDF** binary (`application/pdf`).

---

## 5. Inspecting fields

- **`GET /template-info`** – page count, field count, path to catalog.
- Open the PDF in **Adobe Acrobat** → Prepare Form → see each field name.
- Regenerate catalog if BLS updates the PDF: run from repo (with pypdf):

```python
from pypdf import PdfReader
import json
r = PdfReader("assets/schengen_visa_application_form_english.pdf", strict=False)
rows = [{"name": str(k), "ft": str(v.get("/FT", ""))} for k, v in (r.get_fields() or {}).items()]
```

---

## 6. Legal

For authorized use only. Comply with BLS Spain UAE and Schengen application rules.
