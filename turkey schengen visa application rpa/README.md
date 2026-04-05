# Turkey Schengen RPA 🇹🇷

## Word template (primary)

1. Save the application as **`.docx`** (Word; not legacy `.doc`) in **`assets/`** (e.g. `tvisaform.docx`) **or** in this folder’s root with the same names — or set env **`TURKEY_WORD_TEMPLATE`** to the full path.
2. Use **`{placeholder}`** (single braces) for fields you want the API to fill.
3. For **section 6 (sex)** and **section 8 (marital status)**, put tiny tokens in or beside each box (they become ☑ or ☐). **Short:** `{6m}` `{6f}`; for marital use `{8s}` / `{8m}` (single / married) and/or `{8a}` … `{8f}` for all six in form order. Long names like `{sex_check_male}` still work.
4. **§24 / §25 (Turkey history):** `{24y}` `{24n}` (visited Turkey before), `{25y}` `{25n}` (deported/refused before). JSON (preferred): `maid_traveled_to_turkey_before`, `maid_deported_from_turkey_before` (`yes`/`no` or bool). Legacy keys `traveled_turkey_before`, `deported_from_turkey_before` still work. You can also use `{maid_traveled_to_turkey_before}` / `{maid_deported_from_turkey_before}` as plain text placeholders in Word.
5. **`client_email`:** Use JSON key `client_email`. If the Word token is misspelled as `{client)email}`, it is filled from the same value.
6. **`{port}`:** Send `port` in the JSON body.
7. **`visa_duration`:** If `arrival_date` and `departure_date` parse and `visa_duration` is empty, it is set automatically to **inclusive day count** (e.g. `15 days`). Dates: `dd/mm/yyyy`, `dd.mm.yyyy`, or `yyyy-mm-dd`.
8. **POST** `http://127.0.0.1:8092/fill-docx` with JSON (see `REQUEST_BODY_TEMPLATE_TURKEY.json`). **`POST /fill-docx-pdf`** returns a PDF after filling: conversion tries **LibreOffice** (`soffice`) first, then on **Windows** **Microsoft Word** via COM if **`pywin32`** is installed (`pip install pywin32`) and Word is on the machine.
9. **GET** `/word-template-info` lists `{placeholders}` found in the template.

## Optional: coordinate PDF

If the PDF has **no** AcroForm fields, you can overlay text at coordinates (`mapping.json`). If the PDF **has** fields, use the Spain-style field fill instead.

### PDF scaffold status

- Preview: `debug_screenshots/turkey_page1_preview.png`.
- Place a real PDF at `assets/turkey_schengen_form.pdf` if you use **`POST /fill-pdf`**.

## Run locally

```powershell
cd "turkey schengen visa application rpa"
.\setup_env.ps1
.\.venv\Scripts\python api_server.py
```

Default URL: `http://127.0.0.1:8092`

## Generate overlay PNGs (after adding the PDF)

```powershell
.\.venv\Scripts\python scripts\render_overlay_template.py
```

Then copy `mapping.EXAMPLE.json` → `mapping.json` and replace x/y coordinates.

