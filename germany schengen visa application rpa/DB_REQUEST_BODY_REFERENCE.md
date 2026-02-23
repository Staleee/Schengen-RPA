# Germany RPA – DB reference: hardcoded vs request body

Use this to know what to store in the DB (request body) and what is fixed in code (hardcoded). **Get only the request-body fields from the DB** when calling `POST /fill`.

---

## 1. HARDCODED (do NOT get from DB – we set in code)

| Key | Value |
|-----|--------|
| `occupation` | `"Blue-collar worker"` |
| `reference_type` | `"Inviting person"` |
| `purpose_of_visit` | `"Tourism"` |
| `has_residence_permit` | `true` |
| `residence_in_other_country` | `true` |
| `rvisa_type` | `"Registration Visa"` |
| `passport_type` | `"Passport"` (or `"Official passport"` if body has "official") |
| `third_party_pays` | `true` |
| `inviter_pays` | `true` |
| `all_expenses_covered` | `true` |
| `applicant_pays` | `false` |
| `freedom_of_movement` | `false` |

**Also derived in code (do not send from DB):**

- **Employer** = `client_first_name` + `client_surname` + `client_phone`
- **Applicant address** = copied from `client_street`, `client_house_number`, `client_postal_code`, `client_city`, `client_country`, `client_email`, `client_phone`
- **Occupation address** = same as client address
- **Name at birth** = same as `maid_surname` when `birth_name` / `maiden_name` not sent

---

## 2. REQUEST BODY (get these from DB and send in POST /fill)

Every key you need to read from the DB and put into the JSON body. Types and formats are below.

### Applicant (maid_*)

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `maid_surname` | string | Family name | `"Santos"` |
| `maid_first_name` | string | First name(s) | `"Maria"` |
| `maid_date_of_birth` | string | DD.MM.YYYY | `"22.05.1990"` |
| `maid_place_of_birth` | string | Place of birth | `"Manila"` |
| `maid_country_of_birth` | string | Country of birth | `"Philippines"` |
| `maid_sex` | string | Male / Female | `"Female"` |
| `maid_marital_status` | string | Single, Married, etc. | `"Single"` |
| `maid_nationality` | string | Nationality | `"Philippines"` |

### Client (inviting person)

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `client_surname` | string | Family name | `"Muller"` |
| `client_first_name` | string | First name | `"Hans"` |
| `client_gender` | string | Male / Female | `"Male"` |
| `client_date_of_birth` | string | DD.MM.YYYY | `"10.08.1975"` |
| `client_birth_place` | string | **Required.** Place of birth | `"Munich"` |
| `client_nationality` | string | Nationality | `"Germany"` |
| `client_street` | string | Street (also used for applicant & occupation address) | `"Hauptstrasse"` |
| `client_house_number` | string | House number | `"42"` |
| `client_postal_code` | string | Postal code | `"10115"` |
| `client_city` | string | City | `"Berlin"` |
| `client_country` | string | Country | `"Germany"` |
| `client_email` | string | Email | `"host@example.de"` |
| `client_phone` | string | Phone, no leading + | `"49 30 12345678"` |

### Passport

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `passport_type` | string | `"Passport"` or `"Official passport"` | `"Passport"` |
| `passport_number` | string | Passport number | `"P1234567"` |
| `passport_issue_date` | string | DD.MM.YYYY | `"01.06.2020"` |
| `passport_expiry_date` | string | DD.MM.YYYY | `"01.06.2030"` |
| `passport_issuing_country` | string | Issuing country | `"Philippines"` |

### Residence (registration visa)

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `rvisa_number` | string | Registration visa document number | `"RV-2024-001234"` |
| `rvisa_expiration_date` | string | Valid until DD.MM.YYYY | `"31.12.2025"` |

### Travel

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `number_of_entries` | string | Single entry / Two entries / Multiple entries | `"Single entry"` |
| `first_entry_country` | string | First country of entry | `"Germany"` |
| `main_destination` | string | Main destination | `"Germany"` |
| `arrival_date` | string | DD.MM.YYYY | `"15.03.2026"` |
| `departure_date` | string | DD.MM.YYYY | `"30.03.2026"` |

### Biometrics

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `fingerprints_taken_before` | boolean | Have fingerprints been taken before? | `true` or `false` |

### Optional (can come from DB or be omitted)

| Key | Type | Notes |
|-----|------|--------|
| `birth_name` | string | Name at birth. If omitted, we use `maid_surname`. |
| `maiden_name` | string | Same as birth_name (alias). |
| `visa_start_date` | string | Alias for `arrival_date` (DD.MM.YYYY). |
| `visa_end_date` | string | Alias for `departure_date` (DD.MM.YYYY). |

---

## 3. Full request body JSON (copy for DB → API)

Use this exact key set when building the request from the DB. Only include keys you have; optional can be omitted.

```json
{
  "maid_surname": "",
  "maid_first_name": "",
  "maid_date_of_birth": "",
  "maid_place_of_birth": "",
  "maid_country_of_birth": "",
  "maid_sex": "",
  "maid_marital_status": "",
  "maid_nationality": "",
  "client_surname": "",
  "client_first_name": "",
  "client_gender": "",
  "client_date_of_birth": "",
  "client_birth_place": "",
  "client_nationality": "",
  "client_street": "",
  "client_house_number": "",
  "client_postal_code": "",
  "client_city": "",
  "client_country": "",
  "client_email": "",
  "client_phone": "",
  "passport_type": "Passport",
  "passport_number": "",
  "passport_issue_date": "",
  "passport_expiry_date": "",
  "passport_issuing_country": "",
  "rvisa_number": "",
  "rvisa_expiration_date": "",
  "number_of_entries": "",
  "first_entry_country": "",
  "main_destination": "",
  "arrival_date": "",
  "departure_date": "",
  "fingerprints_taken_before": true
}
```

---

## 4. Example with sample values (for testing)

Also in `output/request_body_standard.json`.

```json
{
  "maid_surname": "Santos",
  "maid_first_name": "Maria",
  "maid_date_of_birth": "22.05.1990",
  "maid_place_of_birth": "Manila",
  "maid_country_of_birth": "Philippines",
  "maid_sex": "Female",
  "maid_marital_status": "Single",
  "maid_nationality": "Philippines",
  "client_surname": "Muller",
  "client_first_name": "Hans",
  "client_gender": "Male",
  "client_date_of_birth": "10.08.1975",
  "client_birth_place": "Munich",
  "client_nationality": "Germany",
  "client_street": "Hauptstrasse",
  "client_house_number": "42",
  "client_postal_code": "10115",
  "client_city": "Berlin",
  "client_country": "Germany",
  "client_email": "host@example.de",
  "client_phone": "49 30 12345678",
  "passport_type": "Passport",
  "passport_number": "P1234567",
  "passport_issue_date": "01.06.2020",
  "passport_expiry_date": "01.06.2030",
  "passport_issuing_country": "Philippines",
  "rvisa_number": "RV-2024-001234",
  "rvisa_expiration_date": "31.12.2025",
  "number_of_entries": "Single entry",
  "first_entry_country": "Germany",
  "main_destination": "Germany",
  "arrival_date": "15.03.2026",
  "departure_date": "30.03.2026",
  "fingerprints_taken_before": true
}
```

---

**Summary:** Get from DB only the keys in section 2 (request body). Do not send or store for this API the keys in section 1 (hardcoded); they are fixed in code.
