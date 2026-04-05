"""
Spain Schengen visa application (UAE BLS) – fill the official PDF form programmatically.

The form is a fillable PDF (AcroForm). Request body: see FIELDS_TO_FILL.md and REQUEST_BODY_REFERENCE.md.

Port: default 8090. If you see "address already in use", stop the other process or set env PORT, e.g.:
  $env:PORT=8091; .\.venv\Scripts\python api_server.py

Debug Zoho / integration payloads (optional):
  SPAIN_LOG_REQUEST_BODY=1          → one JSON line per POST /fill-pdf on stdout (Railway / Docker logs)
  SPAIN_SAVE_REQUEST_BODY_DIR=path  → also write pretty JSON files under that directory (local or mounted volume)
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import uvicorn
from pydantic import BaseModel, ConfigDict, Field

from pdf_fill import DEFAULT_TEMPLATE, fill_spain_schengen_pdf

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "log", "on")


def _record_incoming_fill_pdf_request(payload: Dict[str, Any]) -> None:
    """Log and/or persist the raw POST body when env flags are set (PII — use only in trusted environments)."""
    if not _truthy_env("SPAIN_LOG_REQUEST_BODY") and not os.environ.get("SPAIN_SAVE_REQUEST_BODY_DIR", "").strip():
        return
    try:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except TypeError:
        compact = str(payload)
    if _truthy_env("SPAIN_LOG_REQUEST_BODY"):
        logger.info("spain_fill_pdf_request_body %s", compact)
    save_dir = os.environ.get("SPAIN_SAVE_REQUEST_BODY_DIR", "").strip()
    if save_dir:
        try:
            p = Path(save_dir)
            p.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            fn = p / f"fill_pdf_{stamp}_{uuid.uuid4().hex[:8]}.json"
            fn.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("SPAIN_SAVE_REQUEST_BODY_DIR write failed: %s", e)


app = FastAPI(
    title="Spain Schengen PDF Fill (UAE BLS)",
    description="Fill schengen_visa_application_form_english.pdf. Send maid/client/companion fields per FIELDS_TO_FILL.md; extra keys allowed for Zoho.",
    version="1.1.0",
)


class FillPdfRequest(BaseModel):
    """Core controls plus any payload keys (maid_*, client_*, companion_*, etc.)."""

    model_config = ConfigDict(extra="allow")

    pdf_fields: Optional[Dict[str, str]] = Field(
        default=None,
        description="Exact AcroForm names → values; overrides merged fields where same name.",
    )
    use_business_merge: bool = Field(
        True,
        description="If true, run spain_merge.merge_spain_schengen_body (defaults, client/companion routing).",
    )


def _request_to_dict(body: FillPdfRequest) -> Dict[str, Any]:
    d = body.model_dump(exclude_none=True)
    d.pop("pdf_fields", None)
    d.pop("use_business_merge", None)
    return d


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "spain-schengen-pdf-fill",
        "template": str(DEFAULT_TEMPLATE.name),
        "docs": ["FIELDS_TO_FILL.md", "REQUEST_BODY_REFERENCE.md", "PDF_FIELD_CATALOG.json"],
        "source_pdf_url": "https://uae.blsspainvisa.com/assets/pdf/schengen_visa_application_form_english.pdf",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/template-info")
async def template_info():
    if not DEFAULT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Template PDF missing under assets/")
    from pypdf import PdfReader

    reader = PdfReader(str(DEFAULT_TEMPLATE), strict=False)
    fields = reader.get_fields() or {}
    names = [str(k) for k in fields.keys()]
    return {
        "path": str(DEFAULT_TEMPLATE),
        "page_count": len(reader.pages),
        "field_count": len(names),
        "catalog_file": "PDF_FIELD_CATALOG.json",
    }


@app.post("/fill-pdf")
async def fill_pdf(body: FillPdfRequest):
    if not DEFAULT_TEMPLATE.exists():
        raise HTTPException(
            status_code=500,
            detail="Template PDF missing. Add assets/schengen_visa_application_form_english.pdf",
        )

    full_payload = body.model_dump(exclude_none=True)
    _record_incoming_fill_pdf_request(full_payload)

    structured = _request_to_dict(body)
    try:
        pdf_bytes = fill_spain_schengen_pdf(
            structured,
            body.pdf_fields,
            merge_business_rules=body.use_business_merge,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=500, detail="Output is not valid PDF")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="spain_schengen_application_filled.pdf"'},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
