# Germany VIDEX – Request body (single source of truth)

All sections are on one page. Send one JSON body; the API fills the form. No duplicate keys: reuse the same keys for Contact data and Reference when they are the same (client info).

---

## 1. Personal Details – Applicant's personal data (maid)

| Request key | Form label | Notes |
|-------------|------------|--------|
| `surname` or `family_name` | Family name | Maid |
| `first_name` | First name(s) | Maid |
| `date_of_birth` | Date of birth (dd.mm.yyyy) | Maid, format dd.mm.yyyy |
| `place_of_birth` | Place of birth | Maid |
| `country_of_birth` | Country of birth | Maid |
| `sex` or `gender` | Sex | Maid |
| `marital_status` | Marital status | Maid |
| `nationality` or `current_nationality` | Current nationality | Maid |

---

## 2. Personal Details – Occupation

| Request key | Form label | Notes |
|-------------|------------|--------|
| `occupation` or `current_occupation` | Current occupation | **Always "Blue-collar worker"** (or "Blue Collar Worker" – API normalizes). Default in `defaults.json`. |
| `employer` | Company name and telephone number | **Client name + client phone**. API builds from `client_first_name` + `client_surname` + `client_phone` if `employer` empty. |
| `employer_street` | Street | Client address (where maid works). |
| `employer_house_number` | House number | Client. |
| `employer_postal_code` | Postal code | Client. |
| `employer_city` | Town/city | Client. |
| `employer_country` | Country | Client. |

---

## 3. Contact data – Applicant's address (client = applicant address)

Same as client; no need to duplicate. Use these keys; API copies from `client_*` when these are missing.

| Request key | Form label | Notes |
|-------------|------------|--------|
| `street` | Street | Client. |
| `house_number` | House number | Client. |
| `postal_code` | Postal code | Client. |
| `city` | Town/city | Client. |
| `country` | Country | Client. |
| `email` | Email | **Client email.** |
| `phone` | Telephone/mobile number | **Client number.** |

---

## 4. Residence in other country (always yes)

| Request key | Form label | Notes |
|-------------|------------|--------|
| `has_residence_permit` or `residence_in_other_country` | Is your residence in a country other than that of your current nationality? | **Always true.** Default in `defaults.json`. |

When **yes**, the following subsection appears:

### Details on the applicant's right to reside in place of residence

| Request key | Form label | Notes |
|-------------|------------|--------|
| `rvisa_type` or `authorisation_type` | Type of authorisation to return/residence permit | **Always "REGISTRATION VISA"** (API maps to form option "re-entry visa"). Default in `defaults.json`. |
| `rvisa_number` or `residence_permit_number` | Number of authorisation to return/residence permit | Rvisa number. |
| `rvisa_expiration_date` or `residence_permit_valid_until` | Valid until (dd.mm.yyyy) | Rvisa expiry, dd.mm.yyyy. |

---

## 5. Documents – Identification papers and travel documents

| Request key | Form label | Notes |
|-------------|------------|--------|
| `passport_type` | Type of travel document | **"Ordinary passport"** or **"Official duty passport"** (API accepts "Passport"/"Official Passport"). Default: Ordinary passport. |
| `passport_number` | Travel document number | Passport number. |
| `passport_issue_date` or `date_of_issue` | Date of issue (dd.mm.yyyy) | Passport date of issue. |
| `passport_expiry_date` or `valid_until` | Valid until (dd.mm.yyyy) | Passport expiry. |
| `passport_issuing_country` or `issuing_state` | Issuing state | Passport issuing country. |

---

## 6. Biometric data

| Request key | Form label | Notes |
|-------------|------------|--------|
| `fingerprints_collected` or `has_fingerprints` | Have your fingerprints been collected previously for the purpose of applying for a Schengen visa? | true/false. |
| `fingerprint_date` or `fingerprints_date` | Date if known | Optional; dd.mm.yyyy. |

---

## 7. Travel data

| Request key | Form label | Notes |
|-------------|------------|--------|
| `purpose_of_visit` | Purpose(s) of the journey | **Always "Tourism".** Default in `defaults.json`. |
| `purpose_description` | Other (please specify) | Optional. |
| `additional_info` | Further information on the purpose of the stay | Optional. |
| `first_entry_country` | Member State of first entry | e.g. Germany. |
| `main_destination` | Main travel destination(s) | e.g. Germany. |
| `number_of_entries` | Number of entries requested | e.g. "Single entry". Default in `defaults.json`. |
| `visa_start_date` or `travel_start_date` | Intended date of arrival for the first intended stay in the Schengen area | dd.mm.yyyy. |
| `visa_end_date` or `travel_end_date` | Intended date of departure from the Schengen area after the first intended stay | dd.mm.yyyy. |

---

## 8. Reference – Householder

| Request key | Form label | Notes |
|-------------|------------|--------|
| `reference_type` | Type of reference | **Always "Inviting person".** Default in `defaults.json`. |
| `client_surname` | Family name | Client (same as above; no duplicate key). |
| `client_first_name` | First name(s) | Client. |
| `client_gender` or `sex` | Sex | Client. |
| `client_date_of_birth` | Date of birth (dd.mm.yyyy) | Client. |
| `client_birth_place` | Place of birth | Client. |
| `client_nationality` | Nationality | Client. |
| `client_street` | Street | Client. |
| `client_house_number` | House number | Client. |
| `client_postal_code` | Postal code | Client. |
| `client_city` | Town/city | Client. |
| `client_country` | Country | Client. |
| `client_phone` | Telephone/mobile number | Client. |
| `client_email` | Email | Client. |

**Address of traveling country (hotel):** same fields – `client_street`, `client_house_number`, `client_postal_code`, `client_city`, `client_email`, `client_phone` (no separate keys).

---

## 9. Assumption of costs

| Request key | Form label | Notes |
|-------------|------------|--------|
| `third_party_pays` | Travel and living costs | **true** = a third party (host, company, organisation). Default in `defaults.json`. |
| `inviter_pays` | + the inviting person, see details provided above | **true.** Default in `defaults.json`. |
| `all_expenses_covered` | Means of support | **true** = Assumption of all expenses during the stay / All costs during the stay will be covered. Default in `defaults.json`. |

---

## Summary

- **Maid (applicant):** `surname`, `first_name`, `date_of_birth`, `place_of_birth`, `country_of_birth`, `sex`, `marital_status`, `nationality`.
- **Occupation:** `occupation` = Blue-collar worker; employer = client name + phone; address = client address (`employer_street`, `employer_house_number`, etc.).
- **Contact (applicant's address):** same client – `street`, `house_number`, `postal_code`, `city`, `country`, `email`, `phone` (API copies from `client_*` if missing).
- **Residence:** `has_residence_permit` = true; then `rvisa_type` = REGISTRATION VISA (→ re-entry visa), `rvisa_number`, `rvisa_expiration_date`.
- **Passport:** `passport_type` (Ordinary or Official duty passport), `passport_number`, `passport_issue_date`, `passport_expiry_date`, `passport_issuing_country`.
- **Biometric:** `fingerprints_collected`, optional `fingerprint_date`.
- **Travel:** `purpose_of_visit` = Tourism, `first_entry_country`, `main_destination`, `number_of_entries`, `visa_start_date`, `visa_end_date`.
- **Reference (Householder):** `reference_type` = Inviting person; client fields (`client_surname`, `client_first_name`, …) – same as above, no duplicates.
- **Costs:** `third_party_pays`, `inviter_pays`, `all_expenses_covered` = true.

See `output/defaults.json` for default values; override any with the same key in the request body. See `output/mandatory_fields_example.json` for a full example.
