# Documents Generation – Request body per document & Zoho mapping

**Exact exchange (no guessing):** see **`document_mapping.json`** and **MAPPING.md** for the single source of truth: which request key replaces which placeholder in each document. The API uses only those keys per document.

Templates use **{{variable_name}}** placeholders. Each document has **its own request body**; Zoho calls each endpoint separately (`?document_type=invitation`, `sponsor`, or `cover`).

### Response format (PDF default)

- **`POST /generate`** – Returns **PDF** by default (`Content-Type: application/pdf`, filename `*_letter.pdf`). Use **`?output=docx`** for Word.
- **`POST /generate-all`** – ZIP of three **PDFs** by default; use **`?output=docx`** for `.docx` files in the ZIP.
- **`?format=json`** – Same as above, but JSON with `content_base64` + `filename` + `content_type`.
- PDF conversion uses **LibreOffice** (`soffice`) on the server. If it is missing, the API falls back to **.docx** and sets response headers **`X-Pdf-Unavailable: true`** and **`X-Document-Format: docx`**.

### Zoho date format (recommended)

Send **`departure_date`** and **`return_date`** as **year / month / day** (not day/month/year):

- **`YYYY/MM/DD`** or **`YYYY-MM-DD`** — e.g. `2026/6/3`, `2026/06/03`, `2026-8-30`
- **`YY/MM/DD`** — two-digit year is interpreted as **20YY** (e.g. `26/6/3` → 3 June 2026)

Slashes or hyphens are fine between parts. This avoids mixing up June 3 vs 3 June when parsing.

### Sponsor letter – auto-filled fields

- **`trip_duration`** — **Always recalculated** from **`departure_date`** and **`return_date`** when both parse successfully. Any `trip_duration` sent by Zoho is **ignored** in that case. Formula: **inclusive** calendar days (first and last day both count), e.g. `2026/6/3`–`2026/8/30` → `89 days`.
- **`salary_in_letters`** – You may send a **number** (e.g. `1500` or `"1500"`). It is converted to English words only (e.g. *One thousand five hundred*). AED is already in the letter template. If you send full text already, it is left as-is.

---

## 1. Cover letter

**POST /generate?document_type=cover**

| Request key | Zoho / source |
|-------------|----------------|
| `maid_full_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `schengen_country` | Germany / France (Schengen country from Zoho) |
| `destinations` | All trip destinations joined for the travel sentence, e.g. `Spain and France` (falls back to `schengen_country` when empty) |
| `departure_date` | Departure date |
| `return_date` | Return date |
| `client_name` | Client name |
| `client_passport_number` | Client passport number |
| `employment_start_date` | Contract start date from ERP |

---

## 2. Sponsor letter

**POST /generate?document_type=sponsor**

| Request key | Zoho / source |
|-------------|----------------|
| `client_name` | Client name |
| `client_passport_number` | Client passport number |
| `client_address_in_uae` | Full address, UAE |
| `maid_full_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `contract_start_date` | Contract / employment start date |
| `salary_in_letters` | Salary in letters (or numeric → auto words; AED is in template) |
| `schengen_country` | Germany / France (Schengen country from Zoho) |
| `destinations` | All trip destinations joined for the travel sentence, e.g. `Spain and France` (falls back to `schengen_country` when empty) |
| `trip_duration` | Ignored when both dates parse; server sets from `departure_date` + `return_date` (inclusive days) |
| `departure_date` | Departure date — use **YYYY/MM/DD** from Zoho (year first) |
| `return_date` | Return date — same format |
| `client_phone_number` | Client phone number |
| `client_email_address` | Client email |

---

## 3. Invitation letter

**POST /generate?document_type=invitation**

| Request key | Zoho / source |
|-------------|----------------|
| `schengen_country` | Schengen country from Zoho |
| `client_name` | Client name |
| `client_passport_number` | Client passport number |
| `client_address_in_uae` | Address in UAE |
| `maid_full_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `contract_start_date` | Contract start date |
| `arrival_date` | Arrival date |
| `departure_date` | Departure date |
| `city` | City |
| `hotel_address` | Hotel / address |
| `client_phone_number` | Phone number |
| `client_email_address` | Email address |

---

## 4. GCC issuing affidavit

**POST /generate-affidavit** — always returns **PDF** (`Content-Type: application/pdf`, filename `gcc_issuing_affidavit.pdf`); `?format=json` works like the other endpoints. There is no `?output=docx` — the template (`AFFIDAVIT-template.pdf`) is already a PDF and is filled in place.

| Request key | Zoho / source |
|-------------|----------------|
| `maid_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `maid_nic_number` | Maid NIC number |

---

## Template format

In the .docx templates, variables are written as **{{variable_name}}** (e.g. `{{maid_full_name}}`, `{{schengen_country}}`). The API replaces each with the value from the request body for that document.

**Note:** Word sometimes splits placeholders across runs; the API still finds and replaces them (we match `{{...}}` even when XML tags appear between the braces). Run `python scripts/check_placeholders.py` to verify templates match the expected variables (see **CONSISTENCY.md**).

---

## Output

Letters are generated from **.docx** templates; the API returns **PDF** by default (LibreOffice conversion). Use **`?output=docx`** when you need editable Word files.
