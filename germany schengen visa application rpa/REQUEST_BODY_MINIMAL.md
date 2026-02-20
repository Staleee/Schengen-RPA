# Minimal request body – what you actually send

- **maid_*** = applicant (the maid).
- **client_*** = inviting person (the client). We reuse client for applicant address, employer, and reference.

We **hardcode** the rest (occupation, reference type, purpose, residence, rvisa type, costs, etc.). No repetition.

---

## Do NOT send (we fill these for you)

- `occupation` → always Blue-collar worker  
- `reference_type` → always Inviting person  
- `purpose_of_visit` → always Tourism  
- `has_residence_permit` → always true  
- `rvisa_type` → always re-entry visa (REGISTRATION VISA)  
- `passport_type` → always Ordinary passport (unless "Official duty passport")  
- `number_of_entries` → always Single entry  
- `third_party_pays`, `inviter_pays`, `all_expenses_covered` → always true  

Send **client_*** once; we use it for applicant address, employer (name + phone), and reference.

---

## Send only this (minimal body)

### Maid (applicant)

| Key | Example |
|-----|--------|
| `maid_surname` | Santos |
| `maid_first_name` | Maria |
| `maid_date_of_birth` | 22.05.1990 (dd.mm.yyyy) |
| `maid_place_of_birth` | Manila |
| `maid_country_of_birth` | Philippines |
| `maid_sex` | Female |
| `maid_marital_status` | Single |
| `maid_nationality` | Philippines |

### Client (inviting person – we reuse for address, employer, reference)

| Key | Example |
|-----|--------|
| `client_surname` | Muller |
| `client_first_name` | Hans |
| `client_gender` | Male |
| `client_date_of_birth` | 10.08.1975 |
| `client_birth_place` | Munich |
| `client_nationality` | Germany |
| `client_street` | Hauptstrasse |
| `client_house_number` | 42 |
| `client_postal_code` | 10115 |
| `client_city` | Berlin |
| `client_country` | Germany |
| `client_email` | host@example.de |
| `client_phone` | 49 30 12345678 (no +) |

### Passport (applicant’s)

| Key | Example |
|-----|--------|
| `passport_number` | P1234567 |
| `passport_issue_date` | 01.06.2020 |
| `passport_expiry_date` | 01.06.2030 |
| `passport_issuing_country` | Philippines |

### Rvisa (we set checkbox and type)

| Key | Example |
|-----|--------|
| `rvisa_number` | RV-2024-001234 |
| `rvisa_expiration_date` | 31.12.2025 |

### Travel

| Key | Example |
|-----|--------|
| `first_entry_country` | Germany |
| `main_destination` | Germany |
| `visa_start_date` | 15.03.2026 |
| `visa_end_date` | 30.03.2026 |

---

## Optional

- `fingerprints_collected` (true/false), `fingerprint_date` (if known)  
- `passport_type`: only if "Official duty passport"  
- `number_of_entries`: only if not Single entry  

---

## Example

See **`output/request_body_minimal.json`**. Use **maid_*** for the applicant and **client_*** for the inviting person.
