# How to find the correct field IDs (so we can fix missing/wrong ones)

We use **German internal IDs** (e.g. `antragsteller.personendaten.staendigeAnschrift.land`) to find each form field. If a field is “missing” or country/phone is wrong, the ID might be different on the live VIDEX form. Here’s how you can get the real IDs and share them.

---

## Option 1: Dump IDs from the live form (easiest)

From the project root:

```powershell
python scripts/dump_form_ids.py
```

This opens VIDEX, switches to English, and collects every `input` and `select` **id**, **name**, **type**, and **label**. It writes:

- **`output/videx_form_ids_dump.json`** – full list (id, name, type, placeholder, label)
- **`output/videx_form_ids_dump.txt`** – tab-separated: `id`, `type`, `label`

**What to do:**

1. Open **`output/videx_form_ids_dump.txt`** in a text editor.
2. Search for the label you care about, e.g.:
   - **Country** → see which `id` is next to it (applicant address, employer, reference, etc. may have different ids).
   - **Telephone** / **phone** / **Telephone/mobile number** → see the exact `id` for each phone field.
3. If the ID in the dump is **different** from what we use, send us:
   - The **form label** (e.g. “Country”, “Telephone/mobile number”).
   - The **exact id** from the dump (e.g. `antragsteller.personendaten.staendigeAnschrift.land`).
   - Which **section** it’s in (e.g. “Applicant’s address”, “Reference/Householder”).

We’ll fix **`src/automation/field_translator.py`** (and schema if needed) so that field is filled correctly.

---

## Option 2: Browser DevTools (manual)

1. Open VIDEX: https://videx.diplo.de/videx/visum-erfassung/videx-kurzfristiger-aufenthalt  
2. Switch language to English.  
3. Right‑click the field that’s wrong or missing (e.g. Country, Telephone).  
4. **Inspect** (or Inspect Element).  
5. In the Elements panel, look at the `<input>` or `<select>`:
   - **id="..."** → that’s the field ID we need.
   - If there’s no `id`, look at **name="..."**.
6. Send us:
   - The **label** of the field (as shown on the form).
   - The **id** (or **name**) you see in the HTML.
   - Which **section** of the form it’s in.

We’ll map that ID in the translator and (if needed) in **`output/fields_schema.json`**.

---

## What we already fixed

- **Phone format:** We no longer send a leading **+**. All telephone values are normalized (leading `+` stripped) before filling, including in the “employer” (company name + telephone) field and when copying client phone to applicant address.
- **Country:** Our schema already has e.g. `antragsteller.personendaten.staendigeAnschrift.land` and `referenz.ansprechpartner.anschrift.land` as **select** fields. If the live form uses different IDs or option labels (e.g. “Germany” vs “Germany (Federal Republic of)”), run the dump or DevTools and send us the exact **id** and, for dropdowns, the **exact option text** so we can match it.

---

## Where we use the IDs

| File | Purpose |
|------|--------|
| **`src/automation/field_translator.py`** | Maps your request keys (e.g. `country`, `phone`, `client_phone`) → German field ID. |
| **`output/fields_schema.json`** | For each ID: selector, field_type (text/select/checkbox), and for selects the option list. |
| **`src/automation/form_filler.py`** | Uses the ID (and schema selector) to find the element and fill it. |

So: once we have the **exact id** (and option label for dropdowns) from the live form, we can fix translator and/or schema and stop missing or mis-filling those fields.
