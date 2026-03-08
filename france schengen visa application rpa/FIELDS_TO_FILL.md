# France Schengen – Fields to Fill

Exact form field IDs for the France-Visas application. Request body keys are in **REQUEST_BODY_REFERENCE.md** (what to send); hardcoded values are not in the request body.

---

## Page 1: Your Plans

| Form label | Field ID | Source |
|------------|----------|--------|
| Your situation – Current nationality | `formStep1:visas-selected-nationality_label` | Request body: **nationality label** (e.g. Filipino, Lebanese), not country; API maps country → label |
| Place of submission of application | `formStep1:Visas-selected-deposit-country_label` | Request body |
| Visa type requested | `formStep1:Visas-selected-stayDuration_label` | Request body: **Short stay**, **Long stay**, or **Transit** |
| Main Destination of the stay | `formStep1:Visas-selected-destination_label` | Request body |
| City of submission of application | `formStep1:Visas-selected-deposit-town_label` | Filled by site when place of submission is set (capital) |
| Issuing authority of travel document | `formStep1:Visas-selected-authority_label` | Request body |
| Travel document | `formStep1:Visas-dde-travel-document_label` | **Hardcoded: Ordinary passport** |
| Travel document number | `formStep1:Visas-dde-travel-document-number` | Request body |
| Date of Issue | `formStep1:Visas-dde-release_date_real_input` | Request body |
| Expiry Date | `formStep1:Visas-dde-expiration_date_input` | Request body |
| Your plans | `formStep1:Visas-selected-purposeCategory_label` | **Hardcoded: Tourism** |
| Main purpose of stay | `formStep1:Visas-selected-purpose_label` | **Hardcoded: Tourism / Private Visit** |

**Button:** Verify and then Next

---

## Page 2: Your Information

| Form label | Field ID | Source |
|------------|----------|--------|
| Sex | `formStep2:DDE002_102_label` | Request body |
| Marital Status | `formStep2:DDE002_104_label` | Request body |
| Last name | `formStep2:visas-input-applicant-surname` | Request body |
| First name(s) | `formStep2:visas-input-applicant-firstnames` | Request body |
| Place of birth | `formStep2:visas-input-applicant-placeOfBirth` | Request body |
| Date of birth (dd/mm/yyyy) | `formStep2:visas-input-applicant-dayOfBirth` + `monthOfBirth` + `yearOfBirth` | Request body |
| Country/Territory of birth | `formStep2:visas-selected-countryOfBirth_label` | Request body |
| Address | `formStep2:visas-input-applicant-street` | Request body |
| City | `formStep2:visas-input-applicant-place` | Request body |
| Country or territory | `formStep2:visas-selected-applicant-country_label` | Request body |
| Telephone number | `formStep2:visas-input-applicant-phoneNumber` | Request body |
| Email address | `formStep2:visas-input-applicant-email` | Request body |
| Do you live in a country other than your nationality? | — | **Yes** |
| Current job | `formStep2:visas-input-applicant-activity-occupation_label` | **Hardcoded: Manual worker** |
| Sector | `formStep2:visas-input-applicant-activity-businessSegment_label` | Request body |
| Name of employer | `formStep2:visas-input-applicant-employer-name` | **Client name** |
| Address (employer) | `formStep2:visas-input-applicant-employer-street` | **Client address** |
| City (employer) | `formStep2:visas-input-applicant-employer-place` | **Client city** |
| Country (employer) | `formStep2:visas-selected-applicant-employer-country_label` | **Hardcoded: United Arab Emirates** |
| Telephone (employer) | `formStep2:visas-input-phoneNumber-employer` | **Client phone** |
| Email (employer) | `formStep2:visas-input-email-employer` | **Client email** |

**Button:** Next

---

## Page 3: Your last Visa

| Form label | Field / selector | Source |
|------------|------------------|--------|
| Have you received a Schengen within the last 59 months? | **Yes:** `ui-radiobutton-icon.ui-icon-bullet` / **No:** `ui-radiobutton-icon.ui-icon-blank` | Request body (yes/no) |
| If yes – Valid from | `formStep3:valid-visa-start_input` | Request body |
| If yes – To | `formStep3:valid-visa-end_input` | Request body |
| If yes – Fingerprints taken before? | (formStep3 field) | Request body (yes/no) |

**Button:** Next

---

## Page 4: Your Stay

| Form label | Field ID | Source |
|------------|----------|--------|
| Travel in other member states? | — | **Hardcoded: No** (default) |
| Planned date of arrival in Schengen area | `formStep4:date-of-arrival_input` | Request body |
| Planned date of departure | `formStep4:date-of-departure_input` | Request body |
| Number of entries requested | (formStep4 – confirm ID when testing; may be `visas-selected-*` dropdown) | Request body |
| Number of stays in France (coming year) | `formStep4:visas-input-applicant-numberOfStays_input` | Request body |

**Button:** Next

---

## Page 5: Your contacts

| Form label | Field ID | Source |
|------------|----------|--------|
| Host person or organization | **Hardcoded: A person will be accommodating me** – `ui-chkbox-box` (host person) | Not in request body |
| Name (host) | `formStep5:visas-input-applicant-hostPerson-surname` | **Client** |
| First name (host) | `formStep5:visas-input-applicant-hostPerson-firstnames` | **Client** |
| Address (host) | `formStep5:visas-input-applicant-hostPerson-address` | **Client** |
| City (host) | `formStep5:visas-input-applicant-hostPerson-place` | **Client** |
| Country (host) | `formStep5:visas-selected-hostPerson-country` | **Client** |
| Telephone (host) | `formStep5:visas-input-applicant-hostPerson-phoneNumber` | **Client** |
| Email (host) | `formStep5:visas-input-applicant-hostPerson-email` | **Client** |
| Funding of Travel Costs | **Hardcoded: By the person hosting me** – `ui-chkbox-icon.ui-icon-check` | Not in request body |
| Means of subsistence | **Hardcoded: All expenses covered during stay** | Not in request body |

**Button:** Next

---

## Last page

- **Continue:** `ui-button-text.ui-c` (or button with text "Continue")
- **Declare that the info is correct and complete:** `ui-chkbox-box` (declare checkbox)
- Popup → Continue
- **Next** → download
