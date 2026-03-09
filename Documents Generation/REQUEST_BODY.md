# Documents Generation – Request body per document & Zoho mapping

**Exact exchange (no guessing):** see **`document_mapping.json`** and **MAPPING.md** for the single source of truth: which request key replaces which placeholder in each document. The API uses only those keys per document.

Templates use **{{variable_name}}** placeholders. Each document has **its own request body**; Zoho calls each endpoint separately (`?document_type=invitation`, `sponsor`, or `cover`).

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
| `passport_number` | Client passport number |
| `full_address_uae` | Full address, UAE |
| `maid_full_name` | Maid full name |
| `maid_passport_number` | Maid passport number |
| `employment_start_date` | Employment start date |
| `salary_in_letters` | Salary in letters |
| `schengen_country` | Germany / France (Schengen country from Zoho) |
| `departure_date` | Departure date |
| `return_date` | Return date |
| `phone_number` | Client phone number from Zoho |
| `email` | Client email from Zoho |

---

## 3. Invitation letter

**POST /generate?document_type=invitation**

| Request key | Zoho / source |
|-------------|----------------|
| `destination` | Schengen country from Zoho |
| `client_name` | Client name |
| `address_in_uae` | Address in UAE |
| `maid_name` | Maid name |
| `contract_start_date` | Contract start date |
| `arrival_date_to_departure_date` | Arrival date to departure date |
| `cities` | Cities |
| `hotel_address` | Hotel/Address |
| `phone_number` | Phone number |
| `email_address` | Email address |

---

## Template format

In the .docx templates, variables are written as **{{variable_name}}** (e.g. `{{maid_full_name}}`, `{{schengen_country}}`). The API replaces each with the value from the request body for that document.

**Note:** Word sometimes splits placeholders across runs; the API still finds and replaces them (we match `{{...}}` even when XML tags appear between the braces). Run `python scripts/check_placeholders.py` to verify templates match the expected variables (see **CONSISTENCY.md**).

---

## LaTeX

Output is **.docx** only for now. LaTeX/PDF can be added later as an option if you want neater typesetting; the same request bodies and variables would apply.
