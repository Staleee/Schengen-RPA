# Germany RPA – Request body vs hardcoded

## Standard request body (everything that is NOT hardcoded)

Send this shape in `POST /fill`. All fields below are either required or optional as noted; nothing in this list is hardcoded in the API.

| Field | Description | Example |
|-------|-------------|---------|
| **Applicant (maid_*)** | | |
| `maid_surname` | Family name | `"Santos"` |
| `maid_first_name` | First name(s) | `"Maria"` |
| `maid_date_of_birth` | DD.MM.YYYY | `"22.05.1990"` |
| `maid_place_of_birth` | Place of birth | `"Manila"` |
| `maid_country_of_birth` | Country of birth | `"Philippines"` |
| `maid_sex` | Sex | `"Female"` or `"Male"` |
| `maid_marital_status` | Marital status | `"Single"`, `"Married"`, etc. |
| `maid_nationality` | Nationality | `"Philippines"` |
| **Client (inviting person)** | | |
| `client_surname` | Client family name | `"Muller"` |
| `client_first_name` | Client first name | `"Hans"` |
| `client_gender` | Client sex | `"Male"` |
| `client_date_of_birth` | DD.MM.YYYY | `"10.08.1975"` |
| `client_birth_place` | **Required.** Place of birth (reference section) | `"Munich"` |
| `client_nationality` | Client nationality | `"Germany"` |
| `client_street` | Client street (also used for applicant address & occupation) | `"Hauptstrasse"` |
| `client_house_number` | House number | `"42"` |
| `client_postal_code` | Postal code | `"10115"` |
| `client_city` | City | `"Berlin"` |
| `client_country` | Country | `"Germany"` |
| `client_email` | Email | `"host@example.de"` |
| `client_phone` | Phone (no leading +) | `"49 30 12345678"` |
| **Passport** | | |
| `passport_type` | `"Passport"` or `"Official passport"` | `"Passport"` |
| `passport_number` | Passport number | `"P1234567"` |
| `passport_issue_date` | DD.MM.YYYY | `"01.06.2020"` |
| `passport_expiry_date` | DD.MM.YYYY | `"01.06.2030"` |
| `passport_issuing_country` | Issuing country | `"Philippines"` |
| **Residence (re-entry / registration visa)** | | |
| `rvisa_number` | Registration/re-entry visa document number | `"RV-2024-001234"` |
| `rvisa_expiration_date` | Valid until DD.MM.YYYY | `"31.12.2025"` |
| **Travel** | | |
| `number_of_entries` | Single / Two / Multiple entry | `"Single entry"` |
| `first_entry_country` | First country of entry | `"Germany"` |
| `main_destination` | Main destination | `"Germany"` |
| `arrival_date` | Arrival date DD.MM.YYYY | `"15.03.2026"` |
| `departure_date` | Departure date DD.MM.YYYY | `"30.03.2026"` |
| **Biometrics** | | |
| `fingerprints_taken_before` | Have your fingerprints been taken before? (boolean) | `true` or `false` |

**Optional in body (filled in code if missing):**

- `birth_name` / `maiden_name` – if omitted, set to the same value as `maid_surname` (Name at birth = Family name).
- `visa_start_date` / `visa_end_date` – accepted as aliases for `arrival_date` / `departure_date`.

---

## Hardcoded (do NOT send; we set them in code)

These are the same for every application unless we change the code. You do not need to send them in the request body.

| Field | Value |
|-------|--------|
| `occupation` | `"Blue-collar worker"` |
| `reference_type` | `"Inviting person"` |
| `purpose_of_visit` | `"Tourism"` |
| `has_residence_permit` | `true` – “Do you have a residence permit / residence in another country?” (so we show and fill the re-entry/registration visa section) |
| `residence_in_other_country` | `true` – same as above (VIDEX uses this for the residence block) |
| `rvisa_type` | `"Registration Visa"` |
| `passport_type` | `"Passport"` (default). If the **request body** sends a value containing `"official"`, we use `"Official passport"`. Only these two options. |
| `third_party_pays` | `true` |
| `inviter_pays` | `true` |
| `all_expenses_covered` | `true` |
| `applicant_pays` | `false` |
| `freedom_of_movement` | `false` |

**Derived in code (not sent as such in body):**

- **Employer** = `client_first_name` + `client_surname` + `client_phone` (one string).
- **Applicant address** (Contact Data) = copied from `client_street`, `client_house_number`, `client_postal_code`, `client_city`, `client_country`, `client_email`, `client_phone` when those fields are not sent as `street`, `house_number`, etc.
- **Occupation address** = same client address fields copied to `employer_street`, `employer_house_number`, etc.
- **Name at birth** (`antragsteller.geburtsname`) = same as family name (`maid_surname`) when `birth_name` / `maiden_name` are not sent.

---

## Example: full standard request body (copy for Postman)

See **`output/request_body_standard.json`** for a ready-to-paste JSON with all non-hardcoded fields filled with example values.
