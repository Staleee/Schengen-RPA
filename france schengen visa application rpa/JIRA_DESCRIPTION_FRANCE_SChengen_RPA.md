# France Schengen Visa Application RPA

**Title:** France Schengen visa application RPA – Automate filling the France-Visas online form

---

## Description (copy into Jira)

**Goal**  
Build an RPA that fills the official France Schengen short-stay visa application on France-Visas ([application-form.france-visas.gouv.fr](https://application-form.france-visas.gouv.fr)). Input: applicant + client (host) data in a JSON body. Output: form filled and submitted and/or PDF/confirmation returned. Same idea as our Germany Schengen RPA in this repo (one DB/API can feed both).

**What to fill**  
- **Page 1 (Plans):** Nationality, place of submission, visa type, destination, travel document = Ordinary passport (hardcoded), passport number + issue/expiry dates, purpose = Tourism (hardcoded).  
- **Page 2 (Applicant):** Sex, marital status, last/first name, place & date & country of birth, address, city, country, phone, email. “Live in country other than nationality?” = Yes (hardcoded). Job = Manual worker (hardcoded). Employer = **client**: name, address, city, country, phone, email.  
- **Page 3 (Last visa):** Schengen in last 59 months? (yes/no), if yes valid from/to, fingerprints before? (yes/no).  
- **Page 4 (Stay):** Arrival and departure dates, number of entries, number of stays in France. “Travel in other member states?” = No (hardcoded).  
- **Page 5 (Host):** Host = “A person” (hardcoded). Host name, first name, address, city, country, phone, email = **client** data. Funding = “By the person hosting me”, subsistence = “All expenses covered” (hardcoded).  
- **Final:** Continue, accept declaration, submit. Capture PDF or confirmation.

**What happens**  
1. API receives POST with JSON (applicant + client fields).  
2. RPA opens browser, goes to France-Visas form (user logged in or wait for manual login).  
3. Fill each page (1→2→3→4→5), click Next; on last step accept declaration and submit.  
4. Return PDF or success/error. On failure, return error + optional screenshot.

**Input (request body)**  
Applicant: `last_name`, `first_name`, `date_of_birth`, `place_of_birth`, `country_of_birth`, `sex`, `marital_status`, `nationality`, `address`, `city`, `country`, `phone`, `email`. Passport: `passport_number`, `passport_issue_date`, `passport_expiry_date`, `passport_issuing_country`. Travel: `arrival_date`, `departure_date`, `number_of_entries`, place/city of submission. Client (host): `client_surname`, `client_first_name`, `client_address`, `client_city`, `client_country`, `client_phone`, `client_email`. Previous Schengen: yes/no, dates if yes, fingerprints yes/no. Use dd/mm/yyyy for dates. Align key names with Germany RPA where possible.

**Acceptance criteria**  
- [ ] RPA fills all pages and submits the form (or reaches final step for download).  
- [ ] Data comes from request body; hardcoded values as above.  
- [ ] On success: return PDF or success payload; on failure: error + optional screenshot.  
- [ ] Request schema documented; same DB can feed Germany and France RPAs.

**Reference**  
Germany Schengen RPA in same repo (`germany schengen visa application rpa/`) for pattern (API, Playwright, field mapping, PDF, optional async). France form URLs and field IDs: confirm on live site; existing `france schengen visa application rpa/FIELDS_TO_FILL.md` and `REQUEST_BODY_REFERENCE.md` in repo for current IDs.
