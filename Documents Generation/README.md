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
| POST | `/generate?document_type=cover` | Cover letter; body = cover variables. Returns .docx. Add `&format=json` for JSON with base64 file + filename (recommended for Zoho upload/preview). |
| POST | `/generate?document_type=sponsor` | Sponsor letter; same, use `?format=json` for Zoho. |
| POST | `/generate?document_type=invitation` | Invitation letter; same, use `?format=json` for Zoho. |
| POST | `/generate-all` | Body = union of all variables → ZIP. Add `?format=json` for Zoho. |

---

## Request body (per document)

Each document has its own set of keys. See **REQUEST_BODY.md** for the full list and Zoho mapping. Examples in **samples/**.

- **Cover:** `maid_full_name`, `maid_passport_number`, `schengen_country`, `departure_date`, `return_date`, `client_name`, `client_passport_number`, `employment_start_date`
- **Sponsor:** `client_name`, `passport_number`, `full_address_uae`, `maid_full_name`, `maid_passport_number`, `employment_start_date`, `salary_in_letters`, `schengen_country`, `departure_date`, `return_date`, `phone_number`, `email`
- **Invitation:** `destination`, `client_name`, `address_in_uae`, `maid_name`, `contract_start_date`, `arrival_date_to_departure_date`, `cities`, `hotel_address`, `phone_number`, `email_address`

---

## Zoho mapping and upload

- **Request body → document fields:** see **REQUEST_BODY.md** and **document_mapping.json**.
- **Saving the generated file to a Zoho upload field and getting preview to work:** see **ZOHO.md**. Use `?format=json`, then decode the base64 and upload with the returned filename so the file type is correct and Zoho can preview it.

---

## Railway

- Build: Dockerfile in this folder.
- Health check: `/health`.
- No browser or heavy deps; lightweight Python image.
