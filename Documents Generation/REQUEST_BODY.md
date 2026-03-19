# Documents Generation – Request body per document & Zoho mapping

**Exact exchange (no guessing):** see **`document_mapping.json`** and **MAPPING.md** for the single source of truth: which request key replaces which placeholder in each document. The API uses only those keys per document.

Templates use **{{variable_name}}** placeholders. Each document has **its own request body**; Zoho calls each endpoint separately (`?document_type=invitation`, `sponsor`, or `cover`).

### Response format (PDF default)

- **`POST /generate`** – Returns **PDF** by default (`Content-Type: application/pdf`, filename `*_letter.pdf`). Use **`?output=docx`** for Word.
- **`POST /generate-all`** – ZIP of three **PDFs** by default; use **`?output=docx`** for `.docx` files in the ZIP.
- **`?format=json`** – Same as above, but JSON with `content_base64` + `filename` + `content_type`.
- PDF conversion uses **LibreOffice** (`soffice`) on the server. If it is missing, the API falls back to **.docx** and sets response headers **`X-Pdf-Unavailable: true`** and **`X-Document-Format: docx`**.

### Sponsor letter – auto-filled fields

- **`trip_duration`** – If you send **`departure_date`** and **`return_date`**, the service overwrites `trip_duration` with the **inclusive** calendar day count (e.g. 15 Mar–30 Mar → `16 days`). You can still send `trip_duration`; it will be replaced when both dates parse successfully.
- **`salary_in_letters`** – You may send a **number** (e.g. `1500` or `"1500"`). It is converted to English words and suffixed with **“UAE Dirhams”** (e.g. *One thousand five hundred UAE Dirhams*). If you send full text already, it is left as-is.

---

## 1. Cover letter

**POST /generate?document_type=cover**

| Request key | Zoho / source |
|-------------|----------------|
| `maid_full_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `schengen_country` | Germany / France (Schengen country from Zoho) |
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
| `salary_in_letters` | Salary in letters (or numeric → auto words + UAE Dirhams) |
| `schengen_country` | Germany / France (Schengen country from Zoho) |
| `trip_duration` | Optional; auto from `departure_date` + `return_date` when both set |
| `departure_date` | Departure date |
| `return_date` | Return date |
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

## Template format

In the .docx templates, variables are written as **{{variable_name}}** (e.g. `{{maid_full_name}}`, `{{schengen_country}}`). The API replaces each with the value from the request body for that document.

**Note:** Word sometimes splits placeholders across runs; the API still finds and replaces them (we match `{{...}}` even when XML tags appear between the braces). Run `python scripts/check_placeholders.py` to verify templates match the expected variables (see **CONSISTENCY.md**).

---

## Output

Letters are generated from **.docx** templates; the API returns **PDF** by default (LibreOffice conversion). Use **`?output=docx`** when you need editable Word files.
