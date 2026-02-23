# VIDEX Form Automation API

Automate the German VIDEX Schengen visa application form. Deploy as an API or run locally.

## 🚀 API Usage (Deployed)

Send a POST request with applicant data in JSON, receive the filled form as PDF:

```bash
curl -X POST https://your-railway-url.railway.app/fill \
  -H "Content-Type: application/json" \
  -d '{
    "surname": "Smith",
    "first_name": "John",
    "date_of_birth": "15.03.1985",
    "place_of_birth": "New York",
    "country_of_birth": "United States",
    "gender": "Male",
    "nationality": "United States",
    "passport_number": "AB1234567",
    "visa_start_date": "01.06.2026",
    "visa_end_date": "15.06.2026"
  }' \
  --output videx_Smith_John.pdf
```

## 📋 Available Fields

All fields use English-friendly names:

| Category | Fields |
|----------|--------|
| Personal | `surname`, `first_name`, `birth_name`, `date_of_birth`, `place_of_birth`, `country_of_birth`, `gender`, `marital_status`, `nationality`, `nationality_at_birth` |
| Occupation | `occupation`, `employer`, `employer_street`, `employer_house_number`, `employer_postal_code`, `employer_city`, `employer_country` |
| Address | `street`, `house_number`, `apartment`, `postal_code`, `city`, `country`, `phone`, `email` |
| Passport | `passport_type`, `passport_number`, `national_id`, `passport_issue_date`, `passport_expiry_date`, `passport_issuing_country`, `passport_issued_by`, `passport_issue_place` |
| Travel | `purpose_of_visit`, `first_entry_country`, `main_destination`, `number_of_entries`, `visa_start_date`, `visa_end_date` |
| Reference (Householder/Inviter) | `reference_type`, `client_surname`, `client_first_name`, `client_gender`, `client_date_of_birth`, `client_birth_place`, `client_nationality`, `client_street`, `client_house_number`, `client_postal_code`, `client_city` (aliases: `inviter_*`, `householder_place_of_birth`) |
| Assumption of costs | `applicant_pays`, `third_party_pays`, `cash`, `all_expenses_covered`, etc. |

See **[FIELDS_TO_FILL.md](FIELDS_TO_FILL.md)** for the full dissected form (every section, client/zoho/hard-coded). See `output/mandatory_fields_example.json` for a full request-body example.

**Why is a field left empty?** Only fields present in your **request body** (or in defaults) get filled. If you don’t send e.g. `client_birth_place`, the reference “Place of birth” is skipped. See [DATA_FLOW.md](DATA_FLOW.md) for the full path from request → PDF and the tech stack (this RPA uses Playwright, not OCR).

### Mandatory fields (all must be filled for PDF to generate)

| Section | JSON keys |
|--------|-----------|
| **Personal** | `surname`, `first_name`, `date_of_birth`, `place_of_birth`, `country_of_birth`, `gender`, `marital_status`, `nationality`. Set `freedom_of_movement: true` to skip occupation/financial. |
| **Contact** | `street`, `house_number`, `postal_code`, `city`, `country` |
| **Documents** | `passport_type`, `passport_number`, `passport_issue_date`, `passport_expiry_date`, `passport_issuing_country` (or `date_of_issue`, `valid_until`, `issuing_state`) |
| **Travel** | `purpose_of_visit`, `first_entry_country`, `main_destination`, `number_of_entries`, `visa_start_date`, `visa_end_date` |
| **Reference (Householder)** | `reference_type` (e.g. `"Householder"`), `client_surname`, `client_first_name`, `client_gender`, `client_date_of_birth`, **`client_birth_place`** (or `inviter_birth_place` / `householder_place_of_birth`), `client_nationality`, `client_street`, `client_house_number`, `client_postal_code`, `client_city` |
| **Assumption of costs** | e.g. `applicant_pays: true`, `cash: true` (or third party / other means as needed) |

## ⚙️ Default Values

These fields have default values (override by including in your JSON):

- `passport_type`: "Ordinary passport"
- `number_of_entries`: "Single entry"
- `freedom_of_movement`: true (so occupation/financial can be skipped)
- `reference_type`: "Inviting person"
- Cost coverage: Applicant pays (`applicant_pays: true`), means of support: Cash (`cash: true`)

## 🛠 Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run API locally
python -m src.api
# API available at http://localhost:8000

# Or run CLI
python -m src.main fill --data output/sample_english.json
```

## 🚂 Deploy to Railway

1. Push to GitHub
2. Connect repo to Railway
3. Railway will auto-detect the Dockerfile
4. Set environment variables if needed
5. Deploy!

The API will be available at your Railway URL.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/fill` | Submit JSON, get PDF |

## 📁 Project Structure

```
videx/
├── Dockerfile            # Railway deployment
├── railway.json          # Railway config
├── requirements.txt
├── output/
│   ├── defaults.json         # Default field values
│   ├── fields_schema.json    # Form field schema
│   ├── complete_template.json # All available fields
│   └── sample_english.json   # Example input
├── src/
│   ├── api.py               # FastAPI server
│   ├── main.py              # CLI entry point
│   ├── automation/
│   │   ├── form_filler.py   # Form automation
│   │   ├── field_translator.py # English→German field mapping
│   │   └── data_loader.py
│   └── scraper/
│       ├── form_scraper.py
│       └── schema_generator.py
└── README.md
```
