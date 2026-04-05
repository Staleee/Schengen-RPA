# Turkey Schengen RPA 🇹🇷

## Word template (primary)

1. Save the application as **`.docx`** (Word; not legacy `.doc`) in **`assets/`** (e.g. `tvisaform.docx`) **or** in this folder’s root with the same names — or set env **`TURKEY_WORD_TEMPLATE`** to the full path.
2. Use **`{placeholder}`** (single braces) for fields you want the API to fill.
3. For **section 6 (sex)** and **section 8 (marital status)**, put tiny tokens in or beside each box. **Short:** `{6m}` `{6f}`; marital `{8s}` / `{8m}` and/or `{8a}` … `{8f}`. Replaced tokens use **☑** / **☐** (same styling as your template; we do not resize or switch to ASCII).
4. **§24 / §25 (Turkey history):** `{24y}` `{24n}` (visited Turkey before), `{25y}` `{25n}` (deported/refused before). JSON (preferred): `maid_traveled_to_turkey_before`, `maid_deported_from_turkey_before` (`yes`/`no` or bool). Legacy keys `traveled_turkey_before`, `deported_from_turkey_before` still work. You can also use `{maid_traveled_to_turkey_before}` / `{maid_deported_from_turkey_before}` as plain text placeholders in Word.
5. **`client_email`:** Use JSON key `client_email`. If the Word token is misspelled as `{client)email}`, it is filled from the same value.
6. **`{port}`:** Send **`port`**. **`{means_of_transport}`:** Send **`means_of_transport`** (e.g. `Air`).
7. **`visa_duration`:** When **`arrival_date`** and **`departure_date`** (or camelCase / `date_of_arrival` / `date_of_departure` / `travel_*_date`) parse successfully, **`visa_duration` is always recomputed** (inclusive days) and **overwrites** whatever Zoho sent. **`start_date` / `end_date`** are not used. Spans over **`TURKEY_VISA_MAX_STAY_DAYS`** (default **370**) skip auto-fill. Dates: **`dd.MM.yyyy`** first, then slashes / ISO.
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

## Railway

1. Create a service and set **Root directory** to `turkey schengen visa application rpa` (this folder).
2. **Dockerfile** in this folder installs **LibreOffice** so **`POST /fill-docx-pdf`** returns PDF instead of **503**. Railway usually picks the Dockerfile automatically when it is present.
3. If the build uses **Nixpacks** instead, **`nixpacks.toml`** adds the same APT packages.
4. Ensure your **`.docx` template** is in the image (e.g. under `assets/`) or set **`TURKEY_WORD_TEMPLATE`** to a path inside the container.
5. **`PORT`** is set by Railway; the image uses `$PORT` at runtime.

## Generate overlay PNGs (after adding the PDF)

```powershell
.\.venv\Scripts\python scripts\render_overlay_template.py
```

Then copy `mapping.EXAMPLE.json` → `mapping.json` and replace x/y coordinates.

