# Turkey Schengen RPA 🇹🇷

## Word template (primary)

1. Save the application as **`.docx`** (Word; not legacy `.doc`) in **`assets/`** (e.g. `tvisaform.docx`) **or** in this folder’s root with the same names — or set env **`TURKEY_WORD_TEMPLATE`** to the full path.
2. Use **`{placeholder}`** (single braces) for fields you want the API to fill.
3. For **section 6 (sex)** and **section 8 (marital status)**, put tiny tokens in or beside each box (they become ☑ or ☐). **Short:** `{6m}` `{6f}`; for marital use `{8s}` / `{8m}` (single / married) and/or `{8a}` … `{8f}` for all six in form order. Long names like `{sex_check_male}` still work.
4. **POST** `http://127.0.0.1:8092/fill-docx` with JSON including at least `"sex"` and `"marital_status"` (see `REQUEST_BODY_TEMPLATE_TURKEY.json`).
5. **GET** `/word-template-info` lists `{placeholders}` found in the template.

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

