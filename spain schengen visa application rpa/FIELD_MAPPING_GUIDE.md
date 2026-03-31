# How to know exactly where each value goes (Spain PDF)

## 1. Field **IDs** (what the code uses)

Fillable PDFs use **AcroForm field names** — that is the **ID**. There are no separate HTML-style `id` attributes; the name **is** the identifier.

- Full list: **`PDF_FIELD_CATALOG.json`** (name + `/Tx` text, `/Btn` checkbox, etc.).
- In **Adobe Acrobat**: *Tools → Prepare Form* → click a box → the **name** appears in the field properties.

Anything you send in **`pdf_fields`** must use that **exact** name (e.g. `Texto7`, `Pasaporte ordinarioOrdinary Passport`).

---

## 2. **Coordinates** (to match `Texto*` to the printed form)

Generic names like **`Texto1` … `Texto32`** do not say “passport” on the label — only position on the page does.

We ship a small exporter that lists **every** widget with:

- **page** (1–4)
- **center x, center y** (and width × height)
- **field name** (the ID)

### Generate the tables

From **`spain schengen visa application rpa`**:

```powershell
.\.venv\Scripts\pip install pymupdf
.\.venv\Scripts\python scripts\export_pdf_field_positions.py
```

This writes:

| File | Purpose |
|------|--------|
| **`FIELD_POSITIONS.md`** | Markdown table: sorted **top-to-bottom** on each page — easy to read next to the PDF |
| **`FIELD_POSITIONS.json`** | Same data for scripts / spreadsheets |

Coordinate system: **top-left of page = (0,0)**, **y increases downward**, units **points** (72 pt = 1 inch).

### Workflow

1. Open **`assets/schengen_visa_application_form_english.pdf`** on screen.
2. Open **`FIELD_POSITIONS.md`** (or sort `FIELD_POSITIONS.json` by `page`, `center_y`, `center_x`).
3. For the printed label you care about (e.g. “Date of birth”), find the row whose **position** matches that box.
4. Put that **`name`** into **`pdf_fill.py`** → `TEXTO_FIELD_MAP` (e.g. map `maid_date_of_birth` → the correct `TextoN`), **or** send it in **`pdf_fields`** from Zoho without changing code.

---

## 3. **PNG overlay** (names drawn on the form)

```powershell
.\.venv\Scripts\python scripts\export_pdf_field_overlay_png.py
```

Creates **`debug_screenshots/field_overlay_page_1.png`** (and pages 2–4). Each box is labelled in **red** with its **field name** so you can see exactly which `TextoN` sits on which printed line.

---

## 4. Easiest fix when boxes are wrong (no code)

Follow **`HOW_I_FIX_THE_MAPPING.md`**: edit **`my_pdf_mapping.json`** so each *data key* (e.g. `maid_date_of_birth`) points to the *correct PDF name* you read from the overlay PNGs or Acrobat.

---

## 5. Summary

| You need | Use |
|----------|-----|
| Official ID for API / Zoho | **Field `name`** from catalog or Acrobat |
| Map `Texto5` → “passport number” on paper | **`FIELD_POSITIONS.md`** or **overlay PNGs** |
| Fix mapping without editing Python | **`my_pdf_mapping.json`** |
| Override one-off | **`pdf_fields`: `{ "ExactPdfName": "value" }`** |

The merge layer in **`spain_merge.py`** only knows what **`pdf_fill.py`** maps; **`my_pdf_mapping.json`** overrides those targets.
