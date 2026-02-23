# How to test the Germany VIDEX RPA

Two ways to verify the form filling works: **CLI** (browser + local JSON file) or **API** (POST JSON, get PDF back).

---

## Prerequisites

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\germany schengen visa application rpa"
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

---

## Option 1: CLI test (see the browser fill the form)

Uses the example JSON file. Good for watching the form get filled step by step.

```powershell
# From project root (germany schengen visa application rpa)
python -m src.main fill --data output/mandatory_fields_example.json
```

- **With visible browser** (default): you’ll see Chromium open and the VIDEX form being filled.
- **Save PDF**: PDF is written to `output/` (e.g. `output/videx_application_..._timestamp.pdf`).
- **Headless**: add `--headless` to run without a visible window.
- **Fill only, no PDF**: add `--no-pdf` to stop after filling (no PDF download step).

**Note:** The CLI loads data from the file only. It does **not** run the API’s extra logic (e.g. building `employer` from client name + phone, or copying `client_*` into address fields). So for a test that matches production, use Option 2 (API).

---

## Option 2: API test (full flow: request body → PDF)

Starts the API server and sends a POST request with JSON. This is the same path your app will use.

**Terminal 1 – start the API:**

```powershell
python -m src.api
```

You should see something like: `Uvicorn running on http://0.0.0.0:8000`.

**Terminal 2 – send a test request:**

```powershell
# PowerShell (save PDF to current directory)
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/fill" -ContentType "application/json" -InFile "output/mandatory_fields_example.json" -OutFile "test_output.pdf"
```

Or with **curl** (if installed):

```powershell
curl -X POST http://localhost:8000/fill -H "Content-Type: application/json" -d "@output/mandatory_fields_example.json" -o test_output.pdf
```

If the request succeeds, `test_output.pdf` will contain the filled VIDEX form. If it fails, the API returns JSON with an error message.

---

## Option 3: Run the test script (API + POST + save PDF)

A small script starts the API, waits for it to be ready, POSTs the example JSON, and saves the PDF.

```powershell
python scripts/run_test.py
```

This script is intended to be run from the **project root** (`germany schengen visa application rpa`). It will:

1. Start the API in a subprocess.
2. Wait for `GET /health` to respond.
3. POST `output/mandatory_fields_example.json` to `/fill`.
4. Save the response as `test_output.pdf` in the project root.
5. Stop the API.

---

## Quick checklist

- [ ] `output/defaults.json` exists (defaults for occupation, residence, reference type, costs).
- [ ] `output/fields_schema.json` exists (form field mappings; from a previous scrape).
- [ ] `output/mandatory_fields_example.json` has all required keys (see REQUEST_BODY.md).
- [ ] For API test: `client_birth_place` (or `inviter_birth_place`) is set when using reference type “Inviting person”, or the API returns 400 with a hint.

---

## If something fails

- **“Field not found” / fields left empty:** Check `output/fields_schema.json` and that the VIDEX form hasn’t changed (IDs/labels). Re-scrape if needed: `python -m src.main scrape`.
- **400 “Reference Place of birth is required”:** Add `client_birth_place` (or `inviter_birth_place`) to your JSON.
- **500 / PDF generation failed:** Check the API response body for `detail`; run the CLI with `--no-headless` to see where the browser flow fails.
- **Browser doesn’t open / Playwright errors:** Run `playwright install chromium` and ensure Chromium is installed.
