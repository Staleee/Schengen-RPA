# Document mapping – what we exchange (no guessing)

**Single source of truth:** `document_mapping.json`  
The API replaces **only** the placeholders listed there for each document. Request body keys that are not in the mapping for that document are ignored.

---

## Cover letter (`?document_type=cover`)

| Request body key | Replaced in template |
|------------------|----------------------|
| `maid_full_name` | `{{maid_full_name}}` |
| `maid_passport_number` | `{{maid_passport_number}}` |
| `schengen_country` | `{{schengen_country}}` |
| `departure_date` | `{{departure_date}}` |
| `return_date` | `{{return_date}}` |
| `client_name` | `{{client_name}}` |
| `client_passport_number` | `{{client_passport_number}}` |
| `employment_start_date` | `{{employment_start_date}}` |
| `maid_rvisa_number` | `{{maid_rvisa_number}}` |

---

## Sponsor letter (`?document_type=sponsor`)

| Request body key | Replaced in template |
|------------------|----------------------|
| `client_name` | `{{client_name}}` |
| `client_passport_number` | `{{client_passport_number}}` |
| `client_address_in_uae` | `{{client_address_in_uae}}` |
| `maid_full_name` | `{{maid_full_name}}` |
| `maid_passport_number` | `{{maid_passport_number}}` |
| `contract_start_date` | `{{contract_start_date}}` |
| `salary_in_letters` | `{{salary_in_letters}}` |
| `schengen_country` | `{{schengen_country}}` |
| `trip_duration` | `{{trip_duration}}` |
| `departure_date` | `{{departure_date}}` |
| `return_date` | `{{return_date}}` |
| `client_phone_number` | `{{client_phone_number}}` |
| `client_email_address` | `{{client_email_address}}` |

---

## Invitation letter (`?document_type=invitation`)

| Request body key | Replaced in template |
|------------------|----------------------|
| `schengen_country` | `{{schengen_country}}` |
| `client_name` | `{{client_name}}` |
| `client_passport_number` | `{{client_passport_number}}` |
| `client_address_in_uae` | `{{client_address_in_uae}}` |
| `maid_full_name` | `{{maid_full_name}}` |
| `maid_passport_number` | `{{maid_passport_number}}` |
| `contract_start_date` | `{{contract_start_date}}` |
| `arrival_date` | `{{arrival_date}}` |
| `departure_date` | `{{departure_date}}` |
| `city` | `{{city}}` |
| `hotel_address` | `{{hotel_address}}` |
| `client_phone_number` | `{{client_phone_number}}` |
| `client_email_address` | `{{client_email_address}}` |

---

## GCC issuing affidavit (`POST /generate-affidavit`)

The affidavit is a **flat PDF** template (`AFFIDAVIT-template.pdf`), filled in place
(each line holding a placeholder is redacted and re-written with the values). Output
is always PDF; substituted values render bold like the letters.

| Request body key | Replaced in template |
|------------------|----------------------|
| `maid_name` | `{{maid-name}}` |
| `maid_passport_number` | `{{passport-no}}` |
| `maid_nic_number` | `{{nic-number}}` |

---

## API

- **GET /mapping** – Returns the exact key → placeholder mapping (from `document_mapping.json`). Optional `?document_type=cover|sponsor|invitation|affidavit`.
- **GET /variables** – Expected request keys per document + placeholders found in each template file.
- **POST /generate?document_type=...** – Body is a flat object; only keys present in the mapping for that document are used. Others are ignored.
- **POST /generate-all** – One body; each document is filled using only its own mapping keys.
- **POST /generate-affidavit** – GCC issuing affidavit PDF from the flat PDF template (`AFFIDAVIT-template.pdf`).

To add or change a field: edit `document_mapping.json` (add `"request_key": "{{placeholder}}` under the right document). No code changes needed for new keys that follow the same pattern.
