# France Schengen RPA – Developer Handover Guide

This document is a handover guide for developers rebuilding the France Schengen visa application RPA from scratch. It describes the workflow, the fields to fill on the France-Visas form, hardcoded values, and the request body the RPA receives (e.g. from Zoho or your API).

---

## 1. What the RPA Does

- Opens the **official France-Visas application form**:  
  **https://application-form.france-visas.gouv.fr/fv-fo-dde**
- Waits for **manual login** (or uses a saved session), then fills **5 wizard pages + final step** (Next, declaration, submit/download).
- Accepts a **JSON request body** (same idea as the Germany Schengen RPA: one DB/API can feed both where keys align).

**Reference files in this repo:** `README.md`, `FIELDS_TO_FILL.md`, `REQUEST_BODY_REFERENCE.md`, `SAMPLE_REQUEST_BODY.json`, `JIRA_DESCRIPTION_FRANCE_SChengen_RPA.md`, and `api_server.py` (see `FranceFillRequest`).

---

## 2. How to Proceed (Step-by-Step for Developers)

| Step | Action |
|------|--------|
| **A** | Confirm the **live form** still matches the field IDs in `FIELDS_TO_FILL.md` (France-Visas can change the site and break selectors). |
| **B** | Implement **browser automation** (e.g. Playwright): open URL, optional wait for login, then fill page-by-page using the IDs/selectors from `FIELDS_TO_FILL.md`. |
| **C** | Map **request JSON → form**: use the **`FranceFillRequest`** shape for **`POST /fill-application/full`** (see §4 below). |
| **D** | Implement **hardcoded choices** exactly as in `FIELDS_TO_FILL.md` (passport type, tourism, employer country UAE, “live outside nationality” Yes, host type, funding, etc.). |
| **E** | Handle **dropdowns** with **exact option text** as on the site (`sex`, `marital_status`, `visa_type`, `number_of_entries`, `sector`, etc.). |
| **F** | **Nationality:** the first-page field uses a **label** (e.g. `Filipino`), not always the country name (`Philippines`); the API can map country → label (see `COUNTRY_TO_NATIONALITY_LABEL` in `api_server.py`). |
| **G** | **Dates:** use **`dd/mm/yyyy`** everywhere in the payload and when typing into date fields. |
| **H** | **Page 3:** if “Schengen in last 59 months?” = yes, fill visa from/to and fingerprints; if no, skip those sub-fields. |
| **I** | **Final step:** Continue → tick declaration → handle popup → Next/download; define success (screenshot, PDF path, or error). |
| **J** | Expose a **small HTTP API** (e.g. FastAPI) and document it; consider **async + callback** if Zoho times out (same pattern as Germany’s `RAILWAY_ASYNC.md`). |
| **K** | Optional: support **`POST /fill-application`** for partial/raw `fields` map + structured keys (see `REQUEST_BODY_REFERENCE.md` §1–3). |

---

## 3. Fields to Fill in the Application

These are the **data-driven** fields the RPA must fill from the request body. Exact **form field IDs** are in **`FIELDS_TO_FILL.md`**.

### 3.1 Control

| Key | Description |
|-----|-------------|
| `wait_for_manual_login_seconds` | Seconds to wait for the user to log in in the opened browser (e.g. `60`). |

### 3.2 Page 1 – Your Plans

| Key | Description |
|-----|-------------|
| `current_nationality` | **Nationality label** (e.g. `Filipino`) or country name that you map to a label. |
| `place_of_submission_country` | e.g. `United Arab Emirates`. |
| `visa_type` | One of: `Short stay`, `Long stay`, `Transit`. |
| `main_destination` | e.g. `France`. |
| `issuing_authority_travel_document` | Issuing authority (as on the form). |
| `travel_document_number` | Passport number. |
| `passport_date_of_issue` | `dd/mm/yyyy`. |
| `passport_expiry_date` | `dd/mm/yyyy`. |

**Hardcoded on Page 1 (not in request body):** Travel document = **Ordinary passport**; Your plans = **Tourism**; Main purpose = **Tourism / Private Visit**. City of submission is filled by the site when place of submission is set (capital).

### 3.3 Page 2 – Your Information (Applicant)

| Key | Description |
|-----|-------------|
| `sex` | Exact option text from the form. |
| `marital_status` | Exact option text from the form. |
| `last_name` | Applicant surname. |
| `first_name` | Applicant first name(s). |
| `place_of_birth` | Place of birth. |
| `date_of_birth` | `dd/mm/yyyy` (split to day/month/year on the form). |
| `country_of_birth` | Country/territory of birth. |
| `address` | Street address. |
| `city` | City. |
| `country` | Country or territory of residence. |
| `phone` | Telephone number. |
| `email` | Email address. |
| `sector` | Business segment (e.g. `Other`). |

**Hardcoded on Page 2:** “Do you live in a country other than your nationality?” = **Yes**; Current job = **Manual worker**; Employer = **client** (name, address, city, country, phone, email); Employer country = **United Arab Emirates**.

### 3.4 Client (Employer on Page 2 + Host on Page 5)

| Key | Used for |
|-----|----------|
| `client_surname` | Employer name + host surname. |
| `client_first_name` | Employer first name + host first name. |
| `client_street` | Employer address + host address. |
| `client_city` | Employer city + host city. |
| `client_country` | Employer country + host country. |
| `client_phone` | Employer phone + host phone. |
| `client_email` | Employer email + host email. |

### 3.5 Page 3 – Your Last Visa

| Key | Description |
|-----|-------------|
| `schengen_last_59_months` | `true` = Yes, `false` = No. |
| `valid_visa_start` | If yes – valid from (`dd/mm/yyyy`). |
| `valid_visa_end` | If yes – valid to (`dd/mm/yyyy`). |
| `fingerprints_taken_before` | If yes – fingerprints taken before (`true`/`false`). |

### 3.6 Page 4 – Your Stay

| Key | Description |
|-----|-------------|
| `arrival_date` | Planned date of arrival in Schengen (`dd/mm/yyyy`). |
| `departure_date` | Planned date of departure (`dd/mm/yyyy`). |
| `number_of_entries` | e.g. `Single entry` – must match form options. |
| `number_of_stays` | Number of stays in France (e.g. `"1"`). |

**Hardcoded on Page 4:** “Travel in other member states?” = **No**.

### 3.7 Page 5 – Your Contacts (Host)

All host fields are filled from **client** data (see §3.4).  
**Hardcoded:** Host = **A person will be accommodating me**; Funding = **By the person hosting me**; Means of subsistence = **All expenses covered during stay**.

### 3.8 Final Page

- Click **Continue**; tick **Declare that the info is correct and complete**; handle popup; click **Next** → download/confirmation.

---

## 4. Request Body from Zoho / API

There is no separate “Zoho-only” payload documented in this repo for France. **Zoho Flow / Creator / Deluge** (or your middleware) should **map CRM/ERP fields** into the JSON below. The **target contract** for the full fill is **`FranceFillRequest`** (same shape as `SAMPLE_REQUEST_BODY.json`), with optional Page 3 fields when applicable.

### 4.1 Full Example (POST /fill-application/full)

```json
{
  "wait_for_manual_login_seconds": 60,

  "current_nationality": "Filipino",
  "place_of_submission_country": "United Arab Emirates",
  "visa_type": "Short stay",
  "main_destination": "France",
  "issuing_authority_travel_document": "Philippines",
  "travel_document_number": "P12345678",
  "passport_date_of_issue": "15/06/2020",
  "passport_expiry_date": "14/06/2030",

  "sex": "Female",
  "marital_status": "Single",
  "last_name": "Santos",
  "first_name": "Maria",
  "place_of_birth": "Manila",
  "date_of_birth": "22/05/1990",
  "country_of_birth": "Philippines",
  "address": "Villa 12, Palm Residence, Jumeirah",
  "city": "Dubai",
  "country": "United Arab Emirates",
  "phone": "971501234567",
  "email": "maria.santos@example.com",
  "sector": "Other",

  "client_surname": "Al Maktoum",
  "client_first_name": "Ahmed",
  "client_street": "Sheikh Zayed Road, Building 100",
  "client_city": "Dubai",
  "client_country": "United Arab Emirates",
  "client_phone": "971501234568",
  "client_email": "ahmed.almaktoum@example.ae",

  "schengen_last_59_months": false,
  "valid_visa_start": null,
  "valid_visa_end": null,
  "fingerprints_taken_before": null,

  "arrival_date": "20/03/2026",
  "departure_date": "05/04/2026",
  "number_of_entries": "Single entry",
  "number_of_stays": "1"
}
```

When `schengen_last_59_months` is **true**, set `valid_visa_start`, `valid_visa_end`, and `fingerprints_taken_before` as appropriate; when **false**, they can be omitted or null.

### 4.2 Key Conventions

- **`current_nationality`** = nationality **label** (e.g. **Filipino**, **Lebanese**), not always country name. The API can map country → label (e.g. Philippines → Filipino).
- **`visa_type`** = one of: **Short stay**, **Long stay**, **Transit** (normalize from request if needed).
- **Dates:** always **dd/mm/yyyy**.
- **Dropdowns:** option text must match the **exact** text on the France-Visas form.

### 4.3 Partial Fill (POST /fill-application)

For a simpler flow, **`POST /fill-application`** accepts:

- **`fields`** – raw key/value where key = form label, input `name`, or `id`; value = string to fill.
- **Structured keys** – e.g. `last_name`, `first_name`, `date_of_birth`, `email`, `passport_number`, etc. (see `REQUEST_BODY_REFERENCE.md` §3).

`fields` takes precedence over structured keys. This is useful for testing or when only a subset of fields is needed.

---

## 5. Other Endpoints (If Rebuilding the Full Service)

From `README.md`:

- **POST /register-and-verify** – Full flow: register → verify email (IMAP) → login. Requires email/IMAP settings in the body.
- **POST /login** – Login only (verified account).
- **POST /fill-application** – Fill form fields (manual login + raw/structured fields).
- **POST /fill-application/full** – Full France Schengen form (Pages 1–5 + final).

CAPTCHA handling for registration is in `captcha_solver.py`.

---

## 6. Summary for Developers

- **What Zoho sends** = whatever you configure in Zoho; **what the RPA must accept** = the **`FranceFillRequest`** JSON above. Add a **mapping layer** (Zoho webhook → this JSON) if field names differ.
- **Exact form IDs** and hardcoded values: **`FIELDS_TO_FILL.md`**.
- **Request body shape and examples:** **`REQUEST_BODY_REFERENCE.md`** and **`SAMPLE_REQUEST_BODY.json`**.
- If Zoho or the caller times out, use an **async job + callback** pattern (see Germany’s **`RAILWAY_ASYNC.md`** in the Germany RPA folder).
