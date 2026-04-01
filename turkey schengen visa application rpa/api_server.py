"""
Turkey Schengen RPA – Word (.docx) template fill (primary) and optional coordinate PDF fill.

Default port: 8092 (set env PORT to override).
Word template: assets/*.docx or TURKEY_WORD_TEMPLATE path. Save as .docx (not .doc).
"""

import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import uvicorn
from pydantic import BaseModel, ConfigDict, Field

from turkey_docx_fill import (
    fill_turkey_docx_bytes,
    list_single_brace_placeholders,
    resolve_word_template,
)
from turkey_pdf_fill import DEFAULT_MAPPING_PATH, DEFAULT_TEMPLATE, fill_turkey_pdf

app = FastAPI(
    title="Turkey Schengen Fill",
    description="Fill Word templates with {placeholders}; optional PDF overlay via mapping.json",
    version="0.2.0",
)


class FillPdfRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    # If you want to pass a nested object, put it here; otherwise just pass flat keys.
    fields: Dict[str, Any] = Field(default_factory=dict)


def _merge_fill_body(body: FillPdfRequest) -> Dict[str, Any]:
    payload = dict(body.fields)
    extras = body.model_dump(exclude={"fields"}, exclude_none=True)
    payload.update({k: v for k, v in extras.items() if k != "fields"})
    return payload


@app.get("/")
async def root():
    word = resolve_word_template()
    return {
        "status": "ok",
        "service": "turkey-schengen-fill",
        "word_template": str(word),
        "word_template_exists": word.is_file(),
        "fill_docx": "POST /fill-docx — body: sex, marital_status, plus any {placeholder} keys",
        "pdf_template": str(DEFAULT_TEMPLATE.name),
        "pdf_mapping": str(DEFAULT_MAPPING_PATH.name),
        "fill_pdf": "POST /fill-pdf — requires assets PDF + mapping.json",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/template-info")
async def template_info():
    if not DEFAULT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Template missing: assets/turkey_schengen_form.pdf")
    import fitz

    doc = fitz.open(str(DEFAULT_TEMPLATE))
    try:
        return {"pages": len(doc), "path": str(DEFAULT_TEMPLATE)}
    finally:
        doc.close()


@app.get("/word-template-info")
async def word_template_info():
    path = resolve_word_template()
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No .docx template found. Add assets/tvisaform.docx (or set TURKEY_WORD_TEMPLATE). Expected: {path}",
        )
    return {
        "path": str(path),
        "placeholders": list_single_brace_placeholders(path),
    }


@app.post("/fill-docx")
async def fill_docx(body: FillPdfRequest):
    path = resolve_word_template()
    if not path.is_file():
        raise HTTPException(
            status_code=500,
            detail=f"Word template missing: {path}. Save your form as .docx in assets/ or set TURKEY_WORD_TEMPLATE.",
        )
    payload = _merge_fill_body(body)
    try:
        docx_bytes = fill_turkey_docx_bytes(path, payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Word fill failed: {e}") from e
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="turkey_schengen_filled.docx"'},
    )


@app.post("/fill-pdf")
async def fill_pdf(body: FillPdfRequest):
    if not DEFAULT_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Template missing: assets/turkey_schengen_form.pdf")
    if not DEFAULT_MAPPING_PATH.exists():
        raise HTTPException(status_code=500, detail="Mapping missing: mapping.json (create it after overlay mapping)")

    payload = _merge_fill_body(body)

    pdf_bytes = fill_turkey_pdf(payload)
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=500, detail="Output is not valid PDF")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="turkey_schengen_filled.pdf"'},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8092"))
    uvicorn.run(app, host="0.0.0.0", port=port)

