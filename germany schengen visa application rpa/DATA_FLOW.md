# Germany VIDEX RPA – Where data comes from and why a field can be skipped

## 1. Request body → PDF: the full path

```
Your JSON (Postman/curl/frontend)
        ↓
   src/api.py  (POST /fill)
        ↓
   FieldTranslator.translate_data(body)   ← merges with output/defaults.json
        ↓
   translated_data  (German field IDs, e.g. referenz.ansprechpartner.geburtsort)
        ↓
   VidexFormFiller(applicant_data=translated_data)
        ↓
   form_filler.py  only fills keys that exist in self.data
        ↓
   PDF returned
```

**If a key is missing from the final `translated_data`, that field is never filled.**  
So if the request body (and defaults) don’t include the **reference Place of birth**, it will always be skipped.

---

## 2. Files that decide “what gets filled”

| File | Role |
|------|------|
| **Request body (your JSON)** | You must send every value you want filled. The API does not invent data. |
| **`output/defaults.json`** | Default values. Loaded first; then your request body overrides them. If a field is only in defaults with `""`, it exists in data but with empty value, so the filler skips it (see below). |
| **`src/api.py`** | Receives `data: dict` (request body), calls `FieldTranslator(DEFAULTS_PATH).translate_data(data)`, passes result to `VidexFormFiller(applicant_data=translated_data)`. |
| **`src/automation/field_translator.py`** | Maps English keys → VIDEX IDs (e.g. `client_birth_place` → `referenz.ansprechpartner.geburtsort`). Builds `translated_data` = defaults + your body (body wins). |
| **`src/automation/form_filler.py`** | Uses only `self.data` (the `translated_data`). Loops over `self.data.keys()`; for each key gets `value = self.data.get(field_id)` and **only fills when `value is not None and value != ""`**. So if a key is missing, or present with empty string, that field is skipped. |

So:

- **Reference Place of birth is skipped** when:
  1. You don’t send **any** of: `client_birth_place`, `inviter_birth_place`, `householder_place_of_birth` in the **request body**, and
  2. There is no non-empty value in **defaults** for that field (defaults don’t set it, or set it to `""`).

Then `referenz.ansprechpartner.geburtsort` is either missing from `translated_data` or has value `""`, so the form filler never fills it.

---

## 3. What you must send for Reference (Householder)

For the **Householder** (reference) block to be filled, the **request body** must include at least:

- `reference_type`: e.g. `"Householder"`
- `client_birth_place` (or `inviter_birth_place` or `householder_place_of_birth`) ← **this is the one that maps to “Place of birth” in the reference section**

Example:

```json
{
  "reference_type": "Householder",
  "client_surname": "Doe",
  "client_first_name": "Jane",
  "client_gender": "Female",
  "client_date_of_birth": "14.02.1980",
  "client_birth_place": "Berlin",
  "client_nationality": "Germany",
  "client_street": "Main St",
  "client_house_number": "1",
  "client_postal_code": "10115",
  "client_city": "Berlin",
  "client_country": "Germany"
}
```

If `client_birth_place` (or the other aliases) is **missing or empty** in the request, the reference “Place of birth” will **always** be skipped, no matter how the form filler is implemented.

---

## 4. Technology used (no OCR in this RPA)

This project is **browser automation**, not OCR:

| Layer | Technology |
|-------|------------|
| **API** | FastAPI (Python) |
| **Form filling** | Playwright (Python) – opens the real VIDEX page in Chromium and fills inputs/clicks dropdowns. |
| **Field mapping** | Custom `field_translator.py` (English names → VIDEX internal IDs). |
| **Defaults** | JSON file `output/defaults.json`. |
| **Schema** | `output/fields_schema.json` (field IDs, types, selectors) – used by the form filler for selectors and types. |
| **Data loading (CLI)** | `data_loader.py` – loads JSON from disk, merges with defaults, translates; API uses the same translation path with the request body as input. |

There is **no OCR** in the Germany VIDEX RPA. Text is not read from images; we send your JSON into the live form via Playwright.  
(Other RPAs in the repo, e.g. France, may use different stacks.)

---

## 5. Quick checklist when “Reference Place of birth” is empty

1. **Request body** – Do you send `client_birth_place` (or `inviter_birth_place` or `householder_place_of_birth`) with a non-empty string?
2. **Key name** – Exact names that work: `client_birth_place`, `inviter_birth_place`, `householder_place_of_birth` (see `field_translator.py`).
3. **Defaults** – They can add the key with `""` so it exists; they don’t replace a missing value from the body. You still must send the value from the client/frontend.

If you’re sure the body includes `client_birth_place` and it’s still empty on the form, the next place to check is the form filler (selectors/visibility) in `form_filler.py`; the flow above confirms that if the value is in `translated_data`, the filler will at least attempt to fill it.
