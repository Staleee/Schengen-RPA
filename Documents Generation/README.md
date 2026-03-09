# Documents Generation – Schengen letters

API to fill **invitation letter**, **sponsor letter**, and **cover letter**. Used for Schengen applications (all countries). Deploy as a separate service on Railway.

- Templates use **{{variable_name}}** placeholders (e.g. `{{maid_full_name}}`, `{{schengen_country}}`).
- **Each document has its own request body**; Zoho calls each endpoint separately (`?document_type=invitation`, `sponsor`, or `cover`).
- Exact variables and Zoho mapping: **REQUEST_BODY.md**. Sample bodies: **samples/**.

---

## Setup

```bash
cd "Documents Generation"
pip install -r requirements.txt
```

---

## Run locally

```bash
uvicorn api_server:app --reload --port 8000
```

- Docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/`, `/health` | Health check |
| GET | `/variables` | Expected keys + placeholders in file per document. Optional `?document_type=invitation\|sponsor\|cover` |
| POST | `/generate?document_type=cover` | Cover letter; body = cover variables only. Returns .docx |
| POST | `/generate?document_type=sponsor` | Sponsor letter; body = sponsor variables only. Returns .docx |
| POST | `/generate?document_type=invitation` | Invitation letter; body = invitation variables only. Returns .docx |
| POST | `/generate-all` | Body = union of all variables → ZIP with all three .docx |

---

## Request body (per document)

Each document has its own set of keys. See **REQUEST_BODY.md** for the full list and Zoho mapping. Examples in **samples/**.

- **Cover:** `maid_full_name`, `maid_passport_number`, `schengen_country`, `departure_date`, `return_date`, `client_name`, `client_passport_number`, `employment_start_date`
- **Sponsor:** `client_name`, `passport_number`, `full_address_uae`, `maid_full_name`, `maid_passport_number`, `employment_start_date`, `salary_in_letters`, `schengen_country`, `departure_date`, `return_date`, `phone_number`, `email`
- **Invitation:** `destination`, `client_name`, `address_in_uae`, `maid_name`, `contract_start_date`, `arrival_date_to_departure_date`, `cities`, `hotel_address`, `phone_number`, `email_address`

---

## Zoho mapping

See **REQUEST_BODY.md** for the table that maps **request body keys** to **Zoho field names** so you can build the JSON from Zoho and assign values to the correct document fields.

---

## Railway

- Build: Dockerfile in this folder.
- Health check: `/health`.
- No browser or heavy deps; lightweight Python image.
