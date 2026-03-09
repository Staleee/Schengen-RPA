# Zoho: saving the response to an upload field and preview

If you call the API and **save the raw response** straight into a Zoho file/upload field, the file often **won’t preview** in Zoho (and can look like XML or “no type”). That’s because:

- The response is **binary** (.docx or .zip).
- Connectors can treat it as text or change encoding, so the stored file is corrupted or has no proper type/filename.

**Use JSON + base64 so Zoho gets a proper file and can preview it.**

---

## 1. Call the API with `?format=json`

- Single document:  
  `POST /generate?document_type=cover&format=json`  
  (or `sponsor` / `invitation`)

- All documents (ZIP):  
  `POST /generate-all?format=json`

You’ll get a **200** response with JSON like:

```json
{
  "filename": "cover_letter.docx",
  "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "content_base64": "UEsDBBQABgAI..."
}
```

---

## 2. In Zoho, use the JSON to upload to the file field

Do **not** upload the raw Invoke-URL response body. Instead:

1. Parse the JSON from the response.
2. Take `content_base64` and **decode it to file content** (binary/base64 decode, depending what your Zoho action expects).
3. Upload that decoded content to the upload field, and set the **filename** from `response.filename` (e.g. `cover_letter.docx`).

When the upload step receives **decoded file bytes + correct filename** (and content type if the action allows it), Zoho can store it as a real .docx (or .zip) and **preview will work**.

---

## 3. Summary

| Step | What to do |
|------|------------|
| Call API | Use `?format=json` so you always get JSON, not binary. |
| Response | Use `filename`, `content_type`, and `content_base64`. |
| Upload in Zoho | Decode `content_base64` → file bytes, then upload those bytes with `filename` to the file field. |

If you skip `format=json` and send the raw binary response straight to the upload field, the file is often corrupted or typeless and Zoho can’t preview it.
