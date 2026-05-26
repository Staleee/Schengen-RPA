"""
Documents Generation API – Schengen invitation letter, sponsor letter, cover letter.
Templates use {{variable_name}} placeholders. Each document has its own request body; Zoho calls each endpoint separately.
What gets replaced for which document is defined only in document_mapping.json (no guessing).
"""

import base64
import io
import json
import traceback
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image
from pypdf import PdfReader, PdfWriter
import uvicorn

from doc_utils import fill_document, list_placeholder_variables, normalize_key
from pdf_convert import docx_to_pdf
from variable_enrichment import enrich_variables

PDF_MEDIA = "application/pdf"
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(
    title="Documents Generation API",
    description="Fill invitation, sponsor, cover letters from {{variable}} placeholders. Each document has its own request body; Zoho calls each endpoint by document_type. Mapping: document_mapping.json.",
    version="2.0.0",
)

# Folder containing the .docx templates (same folder as this file)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = {
    "invitation": BASE_DIR / "Invitation Letter (Schengen Visa – Domestic Worker_Housemaid).docx",
    "sponsor": BASE_DIR / "Sponsor_letter.docx",
    "cover": BASE_DIR / "Cover_Letter.docx",
}

# Single source of truth: for each document type, request_body_key -> template placeholder string.
# Only these keys are used for each document; no inference, no guessing.
MAPPING_PATH = BASE_DIR / "document_mapping.json"

# .docx and .zip both start with ZIP magic bytes; if we send anything else, clients get XML/garbage.
ZIP_MAGIC = b"PK"


def _ensure_zip_content(content: bytes, label: str = "file") -> None:
    """Raise 500 if content is not a valid ZIP (docx/zip), so we never return XML or garbage."""
    if not content or not content.startswith(ZIP_MAGIC):
        start = content[:20] if len(content) >= 20 else content
        raise HTTPException(
            status_code=500,
            detail=f"Generated {label} is not a valid docx/zip (starts with {start!r}). Check template and server.",
        )


def _build_one_document(
    document_type: str, body: Dict[str, Any], want_pdf: bool
) -> tuple[bytes, str, str, Dict[str, str]]:
    """
    Fill template; return (bytes, filename, media_type, extra_headers).
    want_pdf=True: convert to PDF (LibreOffice). If conversion fails, returns .docx with X-Pdf-Unavailable.
    """
    path = TEMPLATES[document_type]
    variables = enrich_variables(
        document_type, _variables_for_document(body, document_type), body
    )
    out_docx = BASE_DIR / "output" / f"filled_{document_type}.docx"
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    fill_document(path, variables, out_docx)
    docx_bytes = out_docx.read_bytes()
    _ensure_zip_content(docx_bytes, "docx")
    extra: Dict[str, str] = {}
    if not want_pdf:
        return docx_bytes, f"{document_type}_letter.docx", DOCX_MEDIA, extra
    pdf_out = BASE_DIR / "output" / f"filled_{document_type}.pdf"
    pdf_path = docx_to_pdf(out_docx, pdf_out)
    if pdf_path and pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
        if pdf_bytes.startswith(b"%PDF"):
            return pdf_bytes, f"{document_type}_letter.pdf", PDF_MEDIA, extra
    extra["X-Pdf-Unavailable"] = "true"
    extra["X-Document-Format"] = "docx"
    return docx_bytes, f"{document_type}_letter.docx", DOCX_MEDIA, extra


def _load_mapping() -> Dict[str, Dict[str, str]]:
    if not MAPPING_PATH.exists():
        return {}
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _variables_for_document(body: Dict[str, Any], document_type: str) -> Dict[str, str]:
    """Map document keys to values; body lookup is normalized so Zoho camelCase/spaces still match."""
    mapping = _load_mapping()
    doc_map = mapping.get(document_type, {})
    body_by_nk: Dict[str, Any] = {}
    for k, v in body.items():
        nk = normalize_key(str(k))
        if nk and nk not in body_by_nk:
            body_by_nk[nk] = v
    out = {}
    for request_key in doc_map.keys():
        nk = normalize_key(request_key)
        val = body.get(request_key)
        if val is None and nk:
            val = body_by_nk.get(nk)
        out[nk] = (str(val) if val is not None else "").strip()
    return out


def get_expected_keys(document_type: Optional[str] = None) -> Dict[str, List[str]]:
    """Expected request body keys per document (from document_mapping.json)."""
    mapping = _load_mapping()
    result = {}
    for name in TEMPLATES:
        if document_type and name != document_type:
            continue
        result[name] = list(mapping.get(name, {}).keys())
    return result


@app.get("/")
async def root():
    return {"status": "ok", "service": "documents-generation", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "documents-generation", "version": "1.0.0"}


@app.get("/mapping")
async def get_mapping(document_type: Optional[str] = None):
    """
    Exact exchange: for each document, request_body_key -> template placeholder.
    Single source of truth from document_mapping.json. No guessing.
    """
    mapping = _load_mapping()
    if document_type:
        if document_type not in mapping:
            raise HTTPException(status_code=400, detail=f"document_type must be one of: {list(mapping.keys())}")
        return {document_type: mapping[document_type]}
    return mapping


@app.get("/variables")
async def get_variables(document_type: Optional[str] = None):
    """
    List expected request keys and placeholders per document (from document_mapping.json).
    Optional ?document_type=invitation|sponsor|cover.
    """
    expected = get_expected_keys(document_type)
    result: Dict[str, Any] = {}
    for name, path in TEMPLATES.items():
        if name not in expected:
            continue
        result[name] = {
            "expected_keys": expected[name],
            "placeholders_in_file": list_placeholder_variables(path) if path.exists() else [],
        }
    return result


@app.post("/generate")
async def generate_one(
    body: Dict[str, Any],
    document_type: Optional[str] = None,
    format: Optional[str] = None,
    output: Optional[str] = Query(None, description="pdf (default) or docx"),
):
    """
    Generate one document. Default file is **PDF**; use ?output=docx for Word.
    Sponsor: trip_duration recomputed from departure_date + return_date when both parse (overrides Zoho).
    If departure_date is empty in the mapped body, arrival_date (or trip_start_date) from the raw JSON is used as start.
    Zoho dates: year/month/day (YYYY/MM/DD or YY/MM/DD). camelCase keys are normalized. Inclusive day count.
    salary_in_letters: plain numbers (e.g. 1500) become words only (AED in template).
    """
    dt = document_type or body.pop("document_type", None)
    if not dt:
        raise HTTPException(
            status_code=422,
            detail="document_type is required. Add to URL: ?document_type=invitation (or sponsor or cover). Or put in body: \"document_type\": \"invitation\".",
        )
    if dt not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"document_type must be one of: {list(TEMPLATES.keys())}")
    path = TEMPLATES[dt]
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Template not found: {path.name}")
    # Ensure template is a real .docx (zip), not XML or corrupt
    try:
        with zipfile.ZipFile(path, "r") as z:
            if "word/document.xml" not in z.namelist():
                raise HTTPException(status_code=500, detail=f"Template {path.name} is not a valid .docx (missing word/document.xml).")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=500, detail=f"Template {path.name} is not a valid .docx (not a ZIP file). Re-upload a real Word document.")

    want_pdf = (output or "").lower().strip() != "docx"
    content, filename, media_type, extra_headers = _build_one_document(dt, body, want_pdf)

    if format and format.lower() == "json":
        return {
            "filename": filename,
            "content_type": media_type,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }

    hdrs = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(content)),
        "Cache-Control": "no-transform",
    }
    hdrs.update(extra_headers)
    return Response(content=content, media_type=media_type, headers=hdrs)


@app.post("/generate-all")
async def generate_all(
    body: Dict[str, Any],
    format: Optional[str] = None,
    output: Optional[str] = Query(None, description="pdf (default) or docx"),
):
    """
    Generate all three documents from one request body. Default: each file as **PDF** inside the ZIP
    (invitation_letter.pdf, sponsor_letter.pdf, cover_letter.pdf). Use ?output=docx for Word files in the ZIP.
    """
    want_pdf = (output or "").lower().strip() != "docx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in TEMPLATES.items():
            if not path.exists():
                continue
            try:
                with zipfile.ZipFile(path, "r") as z:
                    if "word/document.xml" not in z.namelist():
                        continue
            except zipfile.BadZipFile:
                continue
            doc_bytes, arc_name, _media, _extra = _build_one_document(name, body, want_pdf)
            zf.writestr(arc_name, doc_bytes)
    buf.seek(0)
    content = buf.getvalue()
    _ensure_zip_content(content, "zip")
    filename = "schengen_documents.zip"

    if format and format.lower() == "json":
        return {
            "filename": filename,
            "content_type": "application/zip",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
            "Cache-Control": "no-transform",
        },
    )


# ZERP-127 — Turkey application PDF merge.
# Single endpoint that converts each incoming attachment (PDF / image / DOCX)
# to PDF and concatenates them in the order the caller supplied. Keeping all
# PDF assembly server-side avoids shipping pdf-lib + sharp into the Next.js
# bundle and reuses the LibreOffice install we already pay for.

PDF_MAGIC = b"%PDF"
# Pillow handles JPEG / PNG / WebP / GIF / BMP / TIFF natively; HEIC requires
# `pillow-heif` and is not installed yet. If iPhone HEIC uploads start showing
# up in production, add the dep and reuse the same branch.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
DOCX_EXTS = {".docx", ".doc"}
MERGE_MAX_BYTES = 50 * 1024 * 1024  # 50 MB guardrail against Railway OOMs


def _to_pdf_bytes(filename: str, data: bytes) -> bytes:
    """Convert one attachment to PDF bytes.

    Order of detection: PDF magic > extension. The PDF magic-byte check covers
    files that arrived from Supabase Storage without a useful filename
    extension (the storage path is opaque `{ts}_{label}.pdf` so usually fine,
    but defensive).
    """
    if data.startswith(PDF_MAGIC):
        return data
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        # Filename says PDF but magic bytes are wrong — surface clearly so the
        # operator can re-upload, instead of producing a corrupt merged PDF.
        raise HTTPException(status_code=415, detail=f"{filename} is not a valid PDF")
    if suffix in IMAGE_EXTS:
        try:
            img = Image.open(io.BytesIO(data))
            # PDF doesn't support alpha; flatten to RGB on a white background
            # to avoid black blocks where the alpha channel was.
            if img.mode in ("RGBA", "LA", "P"):
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                rgb.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
                img = rgb
            else:
                img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="PDF", resolution=150.0)
            return out.getvalue()
        except Exception as exc:
            raise HTTPException(status_code=415, detail=f"Could not render image {filename}: {exc}")
    if suffix in DOCX_EXTS:
        tmp_in = BASE_DIR / "output" / f"merge_{uuid4().hex}{suffix}"
        tmp_in.parent.mkdir(parents=True, exist_ok=True)
        tmp_in.write_bytes(data)
        tmp_out = tmp_in.with_suffix(".pdf")
        pdf_path = docx_to_pdf(tmp_in, tmp_out)
        if not pdf_path or not pdf_path.exists():
            raise HTTPException(status_code=500, detail=f"LibreOffice failed to convert {filename}")
        try:
            return pdf_path.read_bytes()
        finally:
            for tmp in (tmp_in, tmp_out):
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
    raise HTTPException(status_code=415, detail=f"Unsupported file type: {filename}")


@app.post("/merge-application")
async def merge_application(request: Request):
    """Merge an ordered list of attachments into a single PDF.

    Multipart fields:
      - `file_00`, `file_01`, ... — attachments in the order they should
        appear in the output. The numeric suffix is what defines order, not
        the filename; the caller picks names like `file_07` to enforce a
        deterministic position.
      - `meta` — JSON string with `applicationId`, `maid_name`, `country`.
        Only `maid_name` is used today (for the output filename); the rest
        is logged so we can correlate Railway logs with the ERP record.

    Returns: `application/pdf` bytes. Errors are 4xx/5xx with a `detail`
    message that the Next.js caller forwards to the operator's toast.
    """
    form = await request.form()
    meta_raw = form.get("meta")
    try:
        meta: Dict[str, Any] = json.loads(meta_raw) if isinstance(meta_raw, str) and meta_raw else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="`meta` is not valid JSON")

    # Duck-type the upload values instead of isinstance(UploadFile): in some
    # Starlette / python-multipart combos the file class doesn't pass the
    # check even though the value behaves like an UploadFile. Whatever it is,
    # we just need `.read()` to get bytes and `.filename` for type detection.
    items_iter = form.multi_items() if hasattr(form, "multi_items") else form.items()
    file_entries: List[tuple[str, Any]] = []
    debug_keys: List[tuple[str, str]] = []
    for key, value in items_iter:
        debug_keys.append((key, type(value).__name__))
        if not key.startswith("file_"):
            continue
        if hasattr(value, "read") and hasattr(value, "filename"):
            file_entries.append((key, value))
    if not file_entries:
        # Surface what we actually received so the operator can diagnose
        # multipart issues without redeploying.
        raise HTTPException(
            status_code=400,
            detail=f"No files provided (expected file_00, file_01, ...). Received: {debug_keys}",
        )
    file_entries.sort(key=lambda kv: kv[0])

    log_id = f"merge:{meta.get('applicationId', '?')}:{len(file_entries)}"
    print(f"[merge-application] -> {log_id} country={meta.get('country')!r} files={[name for name, _ in file_entries]}")

    total_bytes = 0
    writer = PdfWriter()
    for key, upload in file_entries:
        # ZERP-70 — every step of per-file processing is wrapped so a bad
        # source file produces an actionable detail in the response instead
        # of bubbling up to Starlette as a generic "Internal Server Error".
        # The most common offenders we've seen so far:
        #   - password-protected/encrypted PDFs (iOS "Adobe Scan" output,
        #     some banks' bank-statement PDFs) → pypdf raises
        #     FileNotDecryptedError when iterating `reader.pages`, NOT at
        #     PdfReader construction time.
        #   - Corrupt xrefs from re-saved PDFs → PdfReadError mid-iteration.
        #   - DOCX uploads where LibreOffice silently dies on Railway.
        # Without the wrapper these all show up as opaque 500s in the
        # operator's toast and we can't tell which file is the bad one.
        filename = upload.filename or key
        try:
            data = await upload.read()
            total_bytes += len(data)
            if total_bytes > MERGE_MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Combined input exceeds {MERGE_MAX_BYTES // (1024 * 1024)} MB",
                )
            pdf_bytes = _to_pdf_bytes(filename, data)
            try:
                reader = PdfReader(io.BytesIO(pdf_bytes))
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not read PDF produced from {filename}: {exc}",
                )
            # Encrypted PDFs only complain when we actually touch a page.
            # Attempt a no-password decrypt first; many "secured" PDFs
            # (airline tickets, bank statements, scanner output) are readable
            # without a prompt but still contain a PDF /Encrypt dictionary.
            # pypdf's `is_encrypted` remains true after successful decrypt, so
            # the decrypt return value is the source of truth here.
            if getattr(reader, "is_encrypted", False):
                try:
                    decrypt_result = reader.decrypt("")
                except Exception as exc:
                    raise HTTPException(
                        status_code=415,
                        detail=(
                            f"{filename} is encrypted and could not be opened "
                            f"without a password: {exc}"
                        ),
                    )
                if not decrypt_result:
                    raise HTTPException(
                        status_code=415,
                        detail=(
                            f"{filename} is password-protected; please re-upload "
                            "an un-encrypted copy and merge again."
                        ),
                    )
            for page in reader.pages:
                writer.add_page(page)
        except HTTPException:
            raise
        except Exception as exc:
            # Surface the Python traceback in Railway logs so we can
            # diagnose new failure modes without redeploying. The response
            # only carries the short message — full traceback stays
            # server-side.
            print(f"[merge-application] !! file={filename!r} crashed: {exc}")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Could not process {filename}: {exc.__class__.__name__}: {exc}",
            )

    out = io.BytesIO()
    writer.write(out)
    merged = out.getvalue()

    maid = str(meta.get("maid_name") or "applicant").strip().replace(" ", "_") or "applicant"
    country = str(meta.get("country") or "Turkey").strip().replace(" ", "_") or "Turkey"
    filename = f"{maid}_{country}_Application_Package.pdf"

    print(f"[merge-application] <- {log_id} merged_bytes={len(merged)} filename={filename}")

    return Response(
        content=merged,
        media_type=PDF_MEDIA,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(merged)),
            "Cache-Control": "no-transform",
        },
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    print("\nDocuments Generation API – /variables, POST /generate, POST /generate-all, POST /merge-application\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
