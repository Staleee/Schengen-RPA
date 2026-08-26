# Consistency check: templates vs code/docs

Run: `python scripts/check_placeholders.py` from the **Documents Generation** folder.

---

## Finding and replacing {{placeholders}} when Word splits them

Word often splits text into multiple **runs**, so in the docx XML you get things like:

- `<w:t>{{</w:t><w:t>maid_full_name</w:t><w:t>}}</w:t>` instead of one `{{maid_full_name}}`.

The code now **handles that**: we match `{{` … anything (including XML tags) … `}}`, then strip the tags to get the variable name. So:

- **list_placeholder_variables()** finds every `{{...}}` even when split across runs.
- **fill_document()** replaces each such placeholder with the value (one run is written back).

You don’t need to re-type placeholders in one go; your existing `{{variable}}` text will be found and replaced even if Word split it.

---

## What to do

1. Re-run `python scripts/check_placeholders.py` – it now finds placeholders even when Word split them across runs.
2. If “In file” and “In code” still differ, add any missing `{{variable_name}}` in the template or add/rename variables in code (doc_utils + REQUEST_BODY.md) to match.
3. **Cover’s {{date}}** – If that is meant to be one of the existing vars (e.g. `employment_start_date` or `return_date`), rename it in the template to that full name. If “date” is a separate field, we can add `date` to the cover variables in code and REQUEST_BODY.md.

---

## Expected variables (reference)

Defined in **doc_utils.py** and **REQUEST_BODY.md**:

| Document   | Expected keys |
|-----------|----------------|
| **cover** | maid_full_name, maid_passport_number, schengen_country, destinations, departure_date, return_date, client_name, client_passport_number, employment_start_date |
| **sponsor** | client_name, passport_number, full_address_uae, maid_full_name, maid_passport_number, employment_start_date, salary_in_letters, schengen_country, destinations, departure_date, return_date, phone_number, email |
| **invitation** | destination, client_name, address_in_uae, maid_name, contract_start_date, arrival_date_to_departure_date, cities, hotel_address, phone_number, email_address |

These must appear **exactly** as `{{key}}` in the corresponding .docx (e.g. `{{maid_full_name}}`, not `{{ maid_full_name }}` and not split across runs).
