# Spain Schengen PDF – Field mapping (verified)

Bundled PDF uses **exact AcroForm names** from `PDF_FIELD_CATALOG.json`. If your downloaded PDF uses different names, use **`my_pdf_mapping.json`**.

---

## Numbered items → JSON keys → PDF field name

| # | Data | Request keys | PDF field (bundled template) |
|---|------|--------------|------------------------------|
| 1 | Last name | `maid_surname`, `last_name` | `1 ApellidosSumames` |
| 2 | Last name at birth | `maid_surname_at_birth` | `2 Apellidos de nacimiento apellidos anterioresSuma` |
| 3 | First name | `maid_first_names`, `first_name` | `3 NombresFirst names Given names` |
| 4 | Maid DOB | `maid_date_of_birth` | `Texto1` |
| 5 | Place of birth | `maid_place_of_birth` | `Texto2` |
| 6 | Country of birth | `country_of_birth` | `Texto3` |
| 7 | Nationality (two lines) | `nationality` (+ optional `nationality_line_top`, `nationality_line_bottom`) | `Texto4`, `Texto5` |
| 8 | Gender | `maid_gender` or `sex_male` / `sex_female` | `VarónMale`, `MujerFemale` |
| 9 | Marital | `marital_status_single` or `marital_status: "single"` | `ChkBox` |
| | | `marital_status_married` or `marital_status: "married"` | `ChkBox-0` |
| 12 | Ordinary passport | default on | `Pasaporte ordinarioOrdinary Passport` |
| 13 | Passport no. | `passport_number` | `Texto10` |
| 14 | Issue date | `passport_issue_date` | `Texto11` |
| 15 | Expiry | `passport_expiry_date` | `Texto12` |
| 16 | Issuing country | `passport_issuing_country` | `Texto13` |
| 19 | Maid address + email | `maid_address`, `maid_email` (combined with newline) | `Texto18` |
| | Maid phone | `maid_phone` | `Números de teléfonoTelephone numbers` |
| 20 | Resident outside nationality + visa | `maid_uae_resident`, `uae_residence_visa_number`, `uae_residence_visa_expiry` | `20 Residente…`, `nnumber`, `válido hasta el valid until` |
| 21 | Occupation | `occupation` (default Domestic Worker) | `21 Profesión actual Current occupation` |
| 22 | Employer (Maids CC) | `employer_sponsor_address` or `employer_block_text` | `Texto19` |
| 23 | Tourism | `purpose_tourism` (default true) | `TurismoTourism` |
| 24 | Purpose text | `purpose_additional_info` | `24 Información adicional sobre el motivo de la est` |
| 25 | Spain | `destination_member_state_line` | `Texto21` |
| 26 | Spain (first entry MS) | `first_entry_member_state` | `26 Estado miembro de primera entradaMember State o` |
| 27 | Entries | `number_of_entries` / `entries_one` / `entries_two` / `entries_multiple` | `UnaOne entry`, `DosTwo entries`, `MúltiplesMultiple entries` |
| 28 | Arrival / departure | `arrival_date`, `departure_date` | `Texto22`, `Texto23` |
| 29 | Schengen before | `schengen_visa_before` | `NOno` / `SÍyes` |
| 31 | Host name / email / hotel / phone | `client_*` or `companion_*` (see below) | `Texto25`, `Texto26`, `Texto27`, `Números de teléfonoTelephone numbers-0` |
| 33 | All expenses | default on | `Todos los gastos de estancia están cubiertosAll ex` |
| 34 | Sponsor name / contact / phone | ERP `client_*` or `sponsor_client_*` | `Texto31`, `Texto32`, `Número de teléfono  Phone number` |
| — | Place & date | `place_and_date` (default UAE + today) | `Lugar y fechaPlace and date` |

Footer mirror (page 1): `ApellidosSumamefamily name`, `NombresFirst names Given names` ← same as 1 & 3 unless `skip_footer_name_mirror`.

---

## §31 / §34 client vs companion

- **`client_is_travel_companion`: true** → §31 uses `client_name`, `client_hotel_address` / `client_address`, `client_email`, `client_phone`.
- **false** → §31 uses `companion_*` fields.

§34 sponsor block always prefers **`sponsor_client_*`**, then **`client_*`** (name → `Texto31`; email + ERP address → `Texto32`; phone → `Número de teléfono  Phone number`).

---

## Overrides

**`my_pdf_mapping.json`** — see `HOW_I_FIX_THE_MAPPING.md`.  
**`pdf_fields`** in POST body — wins for any exact PDF name.
