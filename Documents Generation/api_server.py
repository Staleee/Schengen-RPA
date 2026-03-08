"""
Documents Generation API – Schengen invitation letter, sponsor letter, cover letter.
One request body for all documents; bold text in .docx templates = variables (normalized to snake_case).
"""

import io
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

from doc_utils import fill_document, list_bold_variables, normalize_key

app = FastAPI(
    title="Documents Generation API",
    description="Fill invitation letter, sponsor letter, cover letter from one request body (for Schengen applications).",
    version="1.0.0",
)

# Folder containing the .docx templates (same folder as this file)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = {
    "invitation": BASE_DIR / "Invitation Letter (Schengen Visa – Domestic Worker_Housemaid).docx",
    "sponsor": BASE_DIR / "Sponsor_letter.docx",
    "cover": BASE_DIR / "Cover_Letter.docx",
}


# One request body for all documents: flat key-value. Keys = normalized bold text from templates (e.g. client_name).
# Zoho field names map to these keys (see REQUEST_BODY.md).


@app.get("/")
async def root():
    return {"status": "ok", "service": "documents-generation", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "documents-generation", "version": "1.0.0"}


@app.get("/variables")
async def get_variables(document_type: Optional[str] = None):
    """
    List bold placeholders (variables) in the templates.
    document_type: invitation | sponsor | cover | (omit = all).
    Returns {"invitation": [...], "sponsor": [...], "cover": [...]} with {raw, key} per variable.
    """
    result: Dict[str, list] = {}
    for name, path in TEMPLATES.items():
        if document_type and name != document_type:
            continue
        if not path.exists():
            result[name] = [{"error": f"Template not found: {path.name}"}]
            continue
        result[name] = list_bold_variables(path)
    return result


@app.post("/generate")
async def generate_one(
    document_type: str,
    body: Dict[str, Any],
):
    """
    Generate one document. document_type = invitation | sponsor | cover.
    Body: flat key-value; keys = normalized bold names (e.g. client_name, applicant_name). Returns the .docx file.
    """
    if document_type not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"document_type must be one of: {list(TEMPLATES.keys())}")
    path = TEMPLATES[document_type]
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Template not found: {path.name}")

    variables = {normalize_key(k): str(v) for k, v in body.items() if v is not None and str(v).strip()}
    output = BASE_DIR / "output" / f"filled_{document_type}.docx"
    output.parent.mkdir(parents=True, exist_ok=True)
    filled = fill_document(path, variables, output)
    return StreamingResponse(
        io.BytesIO(output.read_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={document_type}_letter.docx"},
    )


@app.post("/generate-all")
async def generate_all(body: Dict[str, Any]):
    """
    Generate all three documents from one request body. Returns a ZIP with invitation_letter.docx, sponsor_letter.docx, cover_letter.docx.
    """
    variables = {normalize_key(k): str(v) for k, v in body.items() if v is not None and str(v).strip()}
    out_dir = BASE_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in TEMPLATES.items():
            if not path.exists():
                continue
            output = out_dir / f"filled_{name}.docx"
            fill_document(path, variables, output)
            zf.write(output, f"{name}_letter.docx")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=schengen_documents.zip"},
    )


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    print("\nDocuments Generation API – /variables, POST /generate, POST /generate-all\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
