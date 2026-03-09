"""
Documents Generation API – Schengen invitation letter, sponsor letter, cover letter.
Templates use {{variable_name}} placeholders. Each document has its own request body; Zoho calls each endpoint separately.
What gets replaced for which document is defined only in document_mapping.json (no guessing).
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

from doc_utils import fill_document, list_placeholder_variables, normalize_key

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


def _load_mapping() -> Dict[str, Dict[str, str]]:
    if not MAPPING_PATH.exists():
        return {}
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _variables_for_document(body: Dict[str, Any], document_type: str) -> Dict[str, str]:
    """Direct exchange: for each key in the mapping for this document, take value from body (or '')."""
    mapping = _load_mapping()
    doc_map = mapping.get(document_type, {})
    out = {}
    for request_key in doc_map.keys():
        val = body.get(request_key)
        out[normalize_key(request_key)] = (str(val) if val is not None else "").strip()
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
):
    """
    Generate one document. Pass document_type in the URL (?document_type=invitation) OR in the body ("document_type": "invitation").
    document_type = invitation | sponsor | cover.
    Body: flat key-value; keys = normalized bold names (e.g. client_name, applicant_name). Returns the .docx file.
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

    variables = _variables_for_document(body, dt)
    output = BASE_DIR / "output" / f"filled_{dt}.docx"
    output.parent.mkdir(parents=True, exist_ok=True)
    filled = fill_document(path, variables, output)
    return StreamingResponse(
        io.BytesIO(output.read_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={dt}_letter.docx"},
    )


@app.post("/generate-all")
async def generate_all(body: Dict[str, Any]):
    """
    Generate all three documents from one request body. Each document uses only the keys
    defined for it in document_mapping.json. Returns a ZIP with invitation_letter.docx, sponsor_letter.docx, cover_letter.docx.
    """
    out_dir = BASE_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in TEMPLATES.items():
            if not path.exists():
                continue
            variables = _variables_for_document(body, name)
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
