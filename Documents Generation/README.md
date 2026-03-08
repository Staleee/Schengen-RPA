# Documents Generation – Schengen letters

API to fill **invitation letter**, **sponsor letter**, and **cover letter** from **one request body**. Used for Schengen applications (all countries). Deploy as a separate service on Railway.

- **Bold text** in each .docx template = variable; we normalize to **snake_case** for the API (e.g. `Client Name` → `client_name`).
- One JSON body for all three documents; map your Zoho fields to these keys (see **REQUEST_BODY.md**).

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
| GET | `/variables` | List bold placeholders (variables) per document. Optional `?document_type=invitation\|sponsor\|cover` |
| POST | `/generate?document_type=invitation` | Generate one document; body = flat key-value. Returns .docx |
| POST | `/generate?document_type=sponsor` | Same body → sponsor letter .docx |
| POST | `/generate?document_type=cover` | Same body → cover letter .docx |
| POST | `/generate-all` | Same body → ZIP with all three filled .docx |

---

## Request body

Flat JSON. Keys = normalized bold placeholders (see **GET /variables** or run `python scripts/extract_bold_variables.py`).

Example:

```json
{
  "client_name": "Ahmed Al Maktoum",
  "applicant_name": "Maria Santos",
  "date_of_invitation": "20 March 2026"
}
```

---

## Zoho mapping

See **REQUEST_BODY.md** for the table that maps **request body keys** to **Zoho field names** so you can build the JSON from Zoho and assign values to the correct document fields.

---

## Railway

- Build: Dockerfile in this folder.
- Health check: `/health`.
- No browser or heavy deps; lightweight Python image.
