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
- **Applicant address** = copied from client address (see below)
- **Occupation address** = same as client address
- **Name at birth** = same as `maid_surname` when `birth_name` / `maiden_name` not sent
- **Client address parts** = if you send only `client_address` (one string), we split it into street, house_number, postal_code, city, country (no API key needed)

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

**Address:** You can send **either** one full address **or** the split parts.

| Key | Type | Format / notes | Example |
|-----|------|----------------|--------|
| `client_surname` | string | Family name | `"Muller"` |
| `client_first_name` | string | First name | `"Hans"` |
| `client_gender` | string | Male / Female | `"Male"` |
| `client_date_of_birth` | string | DD.MM.YYYY | `"10.08.1975"` |
| `client_birth_place` | string | **Required.** Place of birth | `"Munich"` |
| `client_nationality` | string | Nationality | `"Germany"` |
| **`client_address`** | string | **Preferred.** Full address in one string (e.g. from DB). We split it into street, house_number, postal_code, city, country. UAE format supported (e.g. `2604 Tiara United Towers West, Business Bay, Dubai`). | `"2604 Tiara United Towers West, Business Bay, Dubai"` |
| `client_street` | string | *(Optional if you send `client_address`.)* Street / building name | Filled from `client_address` if missing |
| `client_house_number` | string | *(Optional if you send `client_address`.)* Unit / house number | Filled from `client_address` if missing |
| `client_postal_code` | string | *(Optional.)* Postal code | Filled from `client_address` if missing |
| `client_city` | string | *(Optional if you send `client_address`.)* City | Filled from `client_address` if missing |
| `client_country` | string | *(Optional if you send `client_address`.)* Country | Filled from `client_address` if missing |
| `client_email` | string | Email | `"host@example.de"` |
| `client_phone` | string | Phone, no leading + | `"49 30 12345678"` |

**Where this address is used on the form:** The client (inviting person) address is **not** an address “in the Schengen country”. It is the **inviter’s address** (usually in UAE, where the client lives and where the maid works). The API puts it in three places on the VIDEX form: (1) **Reference – Inviting person** (address of the host), (2) **Contact data** (applicant’s address = where the maid lives), (3) **Occupation** (employer’s address = where the maid works). There is no separate “address in Germany” field – only travel **destination** (country name, e.g. `main_destination`: `"Germany"`), not a street address in the Schengen country.

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

Use this key set when building the request from the DB. Only include keys you have; optional can be omitted. **For address:** send either `client_address` (one string) or the split fields (`client_street`, `client_house_number`, etc.); if you send only `client_address`, we fill the rest.

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
  "client_address": "",
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
