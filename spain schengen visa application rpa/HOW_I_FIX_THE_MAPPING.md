# Fix wrong boxes — **you only edit one JSON file**

The server fills the PDF with **PyMuPDF** when installed (`pip install pymupdf`), which applies values more reliably than before. **`pdf_field_resolve.py`** also maps **close spellings** of field names (accents, typos like `Nono` → `NOno`, `TurisomoTourism` → `TurismoTourism`) to the real names in the file.

---

The code guesses PDF field names like `Texto2`, `Texto9`. **You** tell it the correct name for each data item by editing **`my_pdf_mapping.json`** (you create it once — copy from the example).

---

## Step 1 — See the real field names on the form

Run:

```powershell
cd "spain schengen visa application rpa"
.\.venv\Scripts\python scripts\export_pdf_field_overlay_png.py
```

Open the images in **`debug_screenshots/`**. Every box has a **red label** — that label is the **exact string** you must use.

*(Or use Adobe Acrobat → Prepare Form → click a field → copy the **Name**.)*

---

## Step 2 — Create `my_pdf_mapping.json`

Copy the example:

```powershell
copy my_pdf_mapping.EXAMPLE.json my_pdf_mapping.json
```

Edit **`my_pdf_mapping.json`** in any text editor. Three sections (only add what you need to **change**):

| Section | Meaning |
|---------|--------|
| **`structured`** | Named PDF fields (not `Texto*`) — keys match **`pdf_fill.py`** → `STRUCTURED_FIELD_MAP` |
| **`texto`** | Generic boxes — keys match **`TEXTO_FIELD_MAP`** (`maid_date_of_birth`, `passport_number`, …) |
| **`checkbox`** | Checkboxes — keys match **`CHECKBOX_ALIASES`** (`sex_female`, `purpose_tourism`, …) |

**Right-hand side** = the **exact** name from the red label / Acrobat (including accents, spaces).

Example: if DOB is wrong and the overlay shows it is really **`Texto3`**, set:

```json
{
  "texto": {
    "maid_date_of_birth": "Texto3"
  }
}
```

Save the file. **Restart is not required** — the next API request reloads the file.

---

## Step 3 — Test again

```powershell
curl.exe -s -X POST "http://127.0.0.1:8090/fill-pdf" -H "Content-Type: application/json" --data-binary "@test_payload.json" -o "output\test_run.pdf"
```

Repeat until each value sits in the right printed box.

---

## Where do internal keys come from?

- **`FIELDS_TO_FILL.md`** — “Request body key” column → that is what `spain_merge` produces (e.g. `maid_date_of_birth`).
- **`pdf_fill.py`** — look at `STRUCTURED_FIELD_MAP`, `TEXTO_FIELD_MAP`, `CHECKBOX_ALIASES` for the **left-hand** keys you can override.

You never need to edit Python if you only fix mappings in **`my_pdf_mapping.json`**.

---

## Optional: send one-off overrides from Zoho

`POST /fill-pdf` body can still include **`pdf_fields`**: `{ "ExactPdfName": "value" }` — wins over everything for that field name.
