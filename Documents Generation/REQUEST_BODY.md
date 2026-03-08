# Documents Generation – Request body & Zoho mapping

One request body is used for **all three documents** (invitation letter, sponsor letter, cover letter). Variables in the templates are the **bold** text in each .docx; we normalize them to **snake_case** keys in the API.

---

## 1. How to get the exact variable list

- **GET /variables** – returns all bold placeholders per document (`raw` = text in doc, `key` = request body key).
- Or run: `python scripts/extract_bold_variables.py` from the `Documents Generation` folder.

Use the returned `key` values in your JSON body. Keys can be sent in any case; we normalize to snake_case (e.g. `Client Name` → `client_name`).

---

## 2. Request body shape

Send a **flat JSON object**. Each key = a placeholder (normalized from bold text); value = string to insert.

**Example:**

```json
{
  "client_name": "Ahmed Al Maktoum",
  "client_address": "Sheikh Zayed Road, Dubai, UAE",
  "applicant_name": "Maria Santos",
  "date_of_invitation": "20 March 2026",
  "purpose_of_visit": "Domestic worker"
}
```

- **POST /generate?document_type=invitation** – body as above → returns `invitation_letter.docx`.
- **POST /generate?document_type=sponsor** – same body → returns `sponsor_letter.docx`.
- **POST /generate?document_type=cover** – same body → returns `cover_letter.docx`.
- **POST /generate-all** – same body → returns ZIP with all three filled documents.

---

## 3. Zoho field mapping

Map your Zoho fields to these request-body keys so you can build the JSON from Zoho data.

| Request body key (snake_case) | Zoho field / source | Used in |
|-------------------------------|---------------------|--------|
| *(fill after running GET /variables or extract_bold_variables.py)* | | |

After you run **GET /variables** or the extraction script, paste the list of `key` values here and assign each to the corresponding Zoho field name. Then one service can accept Zoho payload and fill all three documents.
