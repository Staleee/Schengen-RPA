# Where the RPA gets the fields to search for

The RPA does **not** have one hardcoded list of “fields to fill”. It fills **every key** in the data it receives (request body + defaults), after translating English names to German field IDs. The places you care about for “specifying fields” are below.

---

## 1. Which fields get filled (the “list” of fields)

**Decided by:** Whatever keys end up in the data passed to the form filler.

- **API:** Request body JSON + `output/defaults.json` → merged and translated → that dict is the data.
- **CLI:** JSON file + `output/defaults.json` → same merge + translate → that dict is the data.

So the “fields to search for” are exactly the **keys of that translated data** (German field IDs like `antragsteller.familienname`).

**In code:** The filler iterates over `self.data.keys()` and tries to fill each one. See:

- **`src/automation/form_filler.py`**  
  - Around **715**: `for field_id in self.data.keys()` (which fields to consider).  
  - Around **881–890**: `for field_id in new_fields` → `_fill_field(field_id, value)` (actual fill).

So: **add a key to the data (via translator + request/defaults) and it gets filled; remove it and it won’t.**

---

## 2. Where you map “request key” → “form field ID” (and thus add a new field)

**File:** **`src/automation/field_translator.py`**

**What to edit:** The big dict **`ENGLISH_TO_GERMAN`** at the top (starts around line 11).

- Each key = what you send in the request body (e.g. `"surname"`, `"client_birth_place"`).
- Each value = the VIDEX internal field ID (e.g. `"antragsteller.familienname"`, `"referenz.ansprechpartner.geburtsort"`).

To support a **new** field:

1. Add a line in **`ENGLISH_TO_GERMAN`**, e.g.  
   `"my_request_key": "antragsteller.some.form.id"`.
2. Send that key in the request body (or add it to `output/defaults.json` with a value).

That’s how you “specify” a new field for the RPA to search for and fill.

---

## 3. Where the code gets the selector for each field (how it “searches” for the element)

**File:** **`src/automation/form_filler.py`**

- **`_load_field_mappings()`** (around 64–87): Reads **`output/fields_schema.json`** and builds `self.field_mappings`: for each field it stores **id → { selector, type, options }**.
- **`_get_selector(field_id)`** (around 131–137): Returns the selector for that `field_id` from `field_mappings`, or fallback **`[id="field_id"]`** if the field is not in the schema.

So:

- **Selector for a field** comes from **`output/fields_schema.json`** (per-field `"id"` and `"selector"`), when present.
- If a field is only in the translator (and thus in `self.data`) but **not** in the schema, the filler still tries to find it using **`[id="field_id"]`**.

**File to edit if you need to change how a field is found:** **`output/fields_schema.json`**

- Find the object whose **`"id"`** equals the German field ID (e.g. `antragsteller.familienname`).
- Change **`"selector"`** (and **`"field_type"`** if it’s select/checkbox/radio).

Schema structure (one field):

```json
{
  "id": "antragsteller.familienname",
  "label": "Family name",
  "field_type": "text",
  "selector": "[id=\"antragsteller.familienname\"]",
  ...
}
```

---

## 4. Summary – “I want to manually specify the fields”

| What you want to do | Where to do it |
|---------------------|----------------|
| Add a new field the RPA should fill | **`src/automation/field_translator.py`** → add a line to **`ENGLISH_TO_GERMAN`** (request key → German field ID). Optionally add that field to **`output/fields_schema.json`** with correct `selector` and `field_type`. |
| Change which element is used for an existing field | **`output/fields_schema.json`** → find the field by **`id`** → change **`selector`** (and **`field_type`** if needed). |
| Make a field always filled with a fixed value | **`output/defaults.json`** → add the **English** key and value (e.g. `"occupation": "Blue-collar worker"`). |
| See the exact loop that drives “which fields to search for” | **`src/automation/form_filler.py`** → **`_get_current_page_fields()`** (uses `self.data.keys()`) and the **`fill_form()`** loop that calls **`_fill_field(field_id, value)`** for each key. |

So: **request/defaults + translator** define *which* fields (by ID); **schema** (or fallback) defines *how* each is found (selector). The code that “searches” for them is **`_get_selector(field_id)`** and the locator built from it in the fill methods.
