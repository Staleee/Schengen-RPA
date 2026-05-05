"""
VIDEX Form Automation API
Accepts JSON POST requests and returns generated PDF
"""

import os
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from prepare_fill import build_translated_data
from form_runner import run_form_filler

from jobs import enqueue_job, get_job, is_redis_available

app = FastAPI(
    title="VIDEX Form Automation API",
    description="Automate German Schengen visa application form filling. Use POST /submit + callback to avoid Zoho timeout.",
    version="1.0.0"
)

# Paths (form_runner has SCHEMA_PATH)
BASE_DIR = Path(__file__).parent.parent

# Thread pool for running playwright (sync) in async context
executor = ThreadPoolExecutor(max_workers=2)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "VIDEX Form Automation API",
        "usage": "POST /submit with callback_url (async, no timeout) or POST /fill (sync, may timeout)",
        "async": "POST /submit with body + callback_url + optional record_id; we POST result to callback when done.",
    }


@app.get("/health")
async def health():
    """Health check for Railway"""
    return {"status": "healthy", "redis": is_redis_available()}


@app.post("/submit")
async def submit_job(data: dict[str, Any]):
    """
    Queue a VIDEX job and return immediately (no timeout). Worker will run the form and POST the result to your callback_url.
    Body: same as POST /fill. Extra keys:
    - callback_url (required if Redis is configured): we POST JSON here when done: { job_id, record_id, status: "completed"|"failed", pdf_base64?, filename?, error? }.
    - record_id (optional): your record ID, echoed in callback.
    """
    callback_url = (data.pop("callback_url", None) or "").strip()
    record_id = (data.pop("record_id", None) or "").strip()
    if not is_redis_available():
        raise HTTPException(
            status_code=503,
            detail="Async queue unavailable (REDIS_URL not set). Use POST /fill for sync request, or add Redis.",
        )
    if not callback_url:
        raise HTTPException(
            status_code=400,
            detail="callback_url is required. When the PDF is ready we POST to this URL (e.g. Zoho Flow webhook).",
        )
    try:
        build_translated_data(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = enqueue_job(data, callback_url, record_id)
    if not job_id:
        raise HTTPException(status_code=503, detail="Failed to enqueue job.")
    return {"job_id": job_id, "status": "queued", "message": "Worker will POST result to your callback_url when done."}


@app.get("/job/{job_id}")
async def job_status(job_id: str):
    """Get job status (queued, processing, completed, failed). Optional: use if you don't rely only on callback."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    out = {"job_id": job_id, "status": job.get("status", "unknown")}
    if job.get("error"):
        out["error"] = job["error"]
    return out


@app.post("/fill")
async def fill_form(data: dict[str, Any]):
    """
    Fill VIDEX form synchronously and return PDF. May timeout on slow runs; for Zoho use POST /submit + callback_url instead.
    """
    try:
        translated_data, full_name = build_translated_data(data)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            run_form_filler,
            translated_data,
            full_name,
        )
        if result.get("pdf_content"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"videx_{full_name}_{timestamp}.pdf"
            return Response(
                content=result["pdf_content"],
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        # Read the keys actually returned by VidexFormFiller.fill_form()
        # (success_count / fail_count / fields), with a fallback to the older
        # form_runner exception path (successful / failed).
        success_count = result.get("success_count", result.get("successful", 0))
        fail_count = result.get("fail_count", result.get("failed", 0))
        fields_map = result.get("fields") or {}
        failed_fields = sorted([fid for fid, ok in fields_map.items() if not ok])
        validation_error = result.get("validation_error")
        # Pick the most specific stage we can.
        if validation_error:
            stage = "videx_validation_error"
            error_msg = f"VIDEX rejected the form: {validation_error}"
        elif result.get("error"):
            stage = "form_filler_exception"
            error_msg = result["error"]
        else:
            # _save_pdf() returned None and there is no validation modal text —
            # the Continue → Download PDF popup just never appeared.
            stage = "save_pdf_returned_none"
            error_msg = "PDF generation failed (Continue → Download PDF popup not captured)"
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "stage": stage,
                "fields_filled": success_count,
                "fields_failed": fail_count,
                "failed_fields": failed_fields[:50],
                "validation_error": validation_error,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
