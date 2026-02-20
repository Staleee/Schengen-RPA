# Germany Schengen VIDEX – Fields to Fill (maids.cc)

All sections are on **one page**. The RPA fills them as instructed. Request body keys are the single source of truth; see **REQUEST_BODY.md** for the full list (no duplicates).

---

## 1. Personal Details – Applicant's personal data (maid)

| Form label | Request key | Source |
|------------|-------------|--------|
| Family name | `surname` or `family_name` | Maid |
| First name(s) | `first_name` | Maid |
| Date of birth (dd.mm.yyyy) | `date_of_birth` | Maid |
| Place of birth | `place_of_birth` | Maid |
| Country of birth | `country_of_birth` | Maid |
| Sex | `sex` or `gender` | Maid |
| Marital status | `marital_status` | Maid |
| Current nationality | `nationality` or `current_nationality` | Maid |

---

## 2. Personal Details – Occupation

| Form label | Request key | Source |
|------------|-------------|--------|
| Current occupation | `occupation` or `current_occupation` | **Always "Blue-collar worker"** (defaults) |
| Company name and telephone number | `employer` | **Client name + client phone** (API builds if empty) |
| Street | `employer_street` | Client (where maid works) |
| House number | `employer_house_number` | Client |
| Postal code | `employer_postal_code` | Client |
| Town/city | `employer_city` | Client |
| Country | `employer_country` | Client |

---

## 3. Contact data – Applicant's address (client)

| Form label | Request key | Source |
|------------|-------------|--------|
| Street | `street` | Client (API copies from `client_street` if missing) |
| House number | `house_number` | Client |
| Postal code | `postal_code` | Client |
| Town/city | `city` | Client |
| Country | `country` | Client |
| Email | `email` | **Client email** |
| Telephone/mobile number | `phone` | **Client number** |

---

## 4. Residence

| Form label | Request key | Source |
|------------|-------------|--------|
| Is your residence in a country other than that of your current nationality? | `has_residence_permit` or `residence_in_other_country` | **Checkbox always yes** (defaults) |

**When yes – Details on the applicant's right to reside in place of residence:**

| Form label | Request key | Source |
|------------|-------------|--------|
| Type of authorisation to return/residence permit | `rvisa_type` or `authorisation_type` | **REGISTRATION VISA** (API maps to form option "re-entry visa"; defaults) |
| Number of authorisation to return/residence permit | `rvisa_number` or `residence_permit_number` | Rvisa number |
| Valid until (dd.mm.yyyy) | `rvisa_expiration_date` or `residence_permit_valid_until` | Rvisa expiry date |

---

## 5. Documents – Identification papers and travel documents

| Form label | Request key | Source |
|------------|-------------|--------|
| Type of travel document | `passport_type` | **Passport or Official Passport** (Ordinary passport / Official duty passport; defaults: Ordinary passport) |
| Travel document number | `passport_number` | Passport number |
| Date of issue (dd.mm.yyyy) | `passport_issue_date` or `date_of_issue` | Passport date of issue |
| Valid until (dd.mm.yyyy) | `passport_expiry_date` or `valid_until` | Passport expiry date |
| Issuing state | `passport_issuing_country` or `issuing_state` | Passport issuing country |

---

## 6. Biometric data

| Form label | Request key | Source |
|------------|-------------|--------|
| Have your fingerprints been collected previously for the purpose of applying for a Schengen visa? | `fingerprints_collected` or `has_fingerprints` | Yes/No |
| Date if known | `fingerprint_date` or `fingerprints_date` | Optional; in request body when known |

---

## 7. Travel data

| Form label | Request key | Source |
|------------|-------------|--------|
| Purpose(s) of the journey | `purpose_of_visit` | **Always Tourism** (defaults) |
| Other (please specify) | `purpose_description` | Optional |
| Further information on the purpose of the stay | `additional_info` | Optional |
| Member State of first entry | `first_entry_country` | e.g. Germany |
| Main travel destination(s) | `main_destination` | e.g. Germany |
| Number of entries requested | `number_of_entries` | e.g. Single entry (defaults) |
| Intended date of arrival for the first intended stay in the Schengen area | `visa_start_date` or `travel_start_date` | dd.mm.yyyy |
| Intended date of departure from the Schengen area after the first intended stay | `visa_end_date` or `travel_end_date` | dd.mm.yyyy |

---

## 8. Reference – Householder

| Form label | Request key | Source |
|------------|-------------|--------|
| Type of reference | `reference_type` | **Always "Inviting person"** (defaults) |
| Family name | `client_surname` | Client |
| First name(s) | `client_first_name` | Client |
| Sex | `client_gender` | Client |
| Date of birth (dd.mm.yyyy) | `client_date_of_birth` | Client |
| Place of birth | `client_birth_place` | Client |
| Nationality | `client_nationality` | Client |
| Street | `client_street` | Client |
| House number | `client_house_number` | Client |
| Postal code | `client_postal_code` | Client |
| Town/city | `client_city` | Client |
| Country | `client_country` | Client |
| Telephone/mobile number | `client_phone` | Client |
| Email | `client_email` | Client |

**Address of traveling country (hotel):** same fields – `client_street`, `client_house_number`, `client_postal_code`, `client_city`, `client_email`, `client_phone` (no separate keys).

---

## 9. Assumption of costs

| Form label | Request key | Source |
|------------|-------------|--------|
| Travel and living costs | `third_party_pays`, `inviter_pays` | **Default: a third party (host, company, organisation) + the inviting person** (defaults) |
| Means of support | `all_expenses_covered` | **Assumption of all expenses during the stay / All costs during the stay will be covered** (defaults) |

---

## Summary

- **Maid:** Personal data + occupation (Blue-collar worker) + employer = client name + phone + client address.
- **Contact (applicant's address):** Client address, email, phone (same as above; API copies from `client_*` if not sent).
- **Residence:** Checkbox yes; type = REGISTRATION VISA (re-entry visa), rvisa number, rvisa expiry.
- **Passport:** Type = Passport or Official Passport, number, issue date, expiry, issuing state.
- **Biometric:** Fingerprints yes/no; optional date if known.
- **Travel:** Purpose = Tourism; first entry, main destination, number of entries, arrival/departure dates.
- **Reference (Householder):** Type = Inviting person; client details (no duplicates in body).
- **Costs:** Third party + inviting person; means = all expenses covered.

See **REQUEST_BODY.md** for the single source of truth (no duplicate keys). See `output/defaults.json` for default values and `output/mandatory_fields_example.json` for a full example.
