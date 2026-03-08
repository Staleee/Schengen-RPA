# France RPA – Request body for fill-application

**POST /fill-application** needs a request body. You can send either raw `fields` (label → value) or structured keys (like the Germany RPA) that we map to the France form.

---

## France visa websites (official)

| Use | URL |
|-----|-----|
| **Application form / login** (where the RPA goes) | **https://application-form.france-visas.gouv.fr/fv-fo-dde** |
| **Info / start** (main portal, English) | **https://france-visas.gouv.fr/en/web/france-visas/** |

The RPA opens the **application form** URL; you log in there, then we fill the form.

---

## 1. Request body shape

You can send **either** (or both):

- **`fields`** – raw key/value: key = form label or input name on France-Visas, value = string to fill.
- **Structured keys** – same names as DB/Germany RPA: `last_name`, `first_name`, `date_of_birth`, `email`, `passport_number`, etc. We map these to France form labels.

**Example (raw `fields` only):**

```json
{
  "wait_for_manual_login_seconds": 60,
  "fields": {
    "Last name": "Santos",
    "First name": "Maria",
    "Email": "maria@example.com"
  }
}
```

**Example (structured keys, DB-style):**

```json
{
  "wait_for_manual_login_seconds": 60,
  "last_name": "Santos",
  "first_name": "Maria",
  "date_of_birth": "22/05/1990",
  "nationality": "Philippines",
  "email": "client@example.com",
  "passport_number": "P1234567"
}
```

| Key | Type | Description |
|-----|------|-------------|
| `wait_for_manual_login_seconds` | number | Seconds to wait for you to log in in the browser (e.g. 60). |
| `fields` | object | Optional. Raw form label/name → value. Takes precedence over structured keys. |
| `last_name`, `first_name`, `date_of_birth`, … | string | Optional. Structured keys; we map to France form labels (see §3). |

**What are the keys in `fields`?** They can be **any** of these (whatever the France website uses):

| Key = … | Meaning |
|--------|--------|
| **Label text** | The text next to the field on the page, e.g. `"Last name"`, `"First name"`. |
| **Input `name`** | The HTML attribute `name="..."`, e.g. `"lastName"`, `"firstName"`. |
| **Input `id`** | The HTML attribute `id="..."`, e.g. `"lastName"`, `"email"`. |
| **Placeholder** | Part of the placeholder text inside the input. |

So **yes – you can use the website’s input `id` or `name`** as the key. Example: if the site has `<input id="nom" name="nom">`, you can send `"fields": { "nom": "Santos" }`. The RPA tries label first, then `name`/`id`, then placeholder.

---

## 2. Example (minimal)

```json
{
  "wait_for_manual_login_seconds": 60,
  "fields": {
    "Last name": "Santos",
    "First name": "Maria",
    "Date of birth": "22/05/1990",
    "Place of birth": "Manila",
    "Nationality": "Philippines",
    "Email": "client@example.com",
    "Passport number": "P1234567"
  }
}
```

Add more keys as you discover the France form labels (e.g. from the page or from `debug_screenshots/`).

---

## 3. Supported structured keys (DB-style)

These request-body keys are mapped to France form labels in code. Same idea as Germany RPA so one DB schema can feed both.

| Request key | Mapped to France form |
|-------------|------------------------|
| `last_name` | Last name |
| `first_name` | First name |
| `date_of_birth` | Date of birth |
| `place_of_birth` | Place of birth |
| `country_of_birth` | Country of birth |
| `nationality` | Nationality |
| `sex` | Sex |
| `marital_status` | Marital status |
| `email` | Email |
| `phone` | Phone |
| `passport_number` | Passport number |
| `passport_expiry_date` | Passport valid until |
| `passport_issue_date` | Passport date of issue |
| `passport_issuing_country` | Passport issuing country |
| `street`, `house_number`, `postal_code`, `city`, `country` | Address fields |

You can mix: use **structured keys** for DB data and **`fields`** for any extra or overriding values (e.g. a label that doesn’t have a structured key yet).

---

## 4. Getting the right keys

- Run the RPA once with a few `fields`, then check **debug_screenshots/fill_step_3_filled.png** to see what’s on the page.
- Use browser DevTools on the France-Visas form to read `name` and `id` of inputs.
- Add those keys to `fields` in the next request.

See **FIELDS_TO_FILL.md** for the exact form field IDs and what is hardcoded.

---

## 5. Full multi-step flow – POST /fill-application/full

For the **full France Schengen form** (all 5 pages + final), use **POST /fill-application/full** with a **FranceFillRequest** body. Hardcoded values (travel document = Ordinary passport, purpose = Tourism, employer country = UAE, etc.) are not in the body – see **FIELDS_TO_FILL.md**.

**Example body:**

```json
{
  "wait_for_manual_login_seconds": 60,
  "current_nationality": "Filipino",
  "place_of_submission_country": "United Arab Emirates",
  "visa_type": "Short stay",
  "main_destination": "France",
  "issuing_authority_travel_document": "Philippines",
  "travel_document_number": "P1234567",
  "passport_date_of_issue": "01/06/2020",
  "passport_expiry_date": "01/06/2030",
  "sex": "Female",
  "marital_status": "Single",
  "last_name": "Santos",
  "first_name": "Maria",
  "place_of_birth": "Manila",
  "date_of_birth": "22/05/1990",
  "country_of_birth": "Philippines",
  "address": "123 Main St",
  "city": "Dubai",
  "country": "United Arab Emirates",
  "phone": "971501234567",
  "email": "maria@example.com",
  "sector": "Other",
  "client_surname": "Al Maktoum",
  "client_first_name": "Ahmed",
  "client_street": "Sheikh Zayed Road",
  "client_city": "Dubai",
  "client_country": "United Arab Emirates",
  "client_phone": "971501234568",
  "client_email": "ahmed@example.ae",
  "schengen_last_59_months": false,
  "arrival_date": "15/03/2026",
  "departure_date": "30/03/2026",
  "number_of_entries": "Single entry",
  "number_of_stays": "1"
}
```

- **`current_nationality`** = **nationality label** (e.g. **Filipino**, **Lebanese**, **Indian**), **not** country name (Philippines, Lebanon). The API maps country names to labels (e.g. Philippines → Filipino) so you can send either.
- **`visa_type`** = one of: **Short stay**, **Long stay**, **Transit** (in request body; we normalize so "short stay" → "Short stay").
- Other dropdowns (`sex`, etc.) must match the **exact option text** on the form.
