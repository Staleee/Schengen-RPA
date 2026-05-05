"""
VIDEX Form Automation API
Accepts JSON POST requests and returns generated PDF
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from prepare_fill import build_translated_data

from jobs import enqueue_job, get_job, is_redis_available

# Path to the stand-alone subprocess runner. Running the form filler in a
# child process avoids the sync_playwright + asyncio event-loop deadlock that
# bites whenever Playwright's sync API is invoked from inside any thread that
# uvicorn/Starlette has touched (anyio attaches loop state to its workers).
SUBPROCESS_RUNNER = Path(__file__).parent / "subprocess_runner.py"

# Hard ceiling for one /fill call. A healthy run finishes in ~85 s; if we
# exceed this, Chromium is genuinely stuck and we'd rather return a clear
# 504 than have the upstream caller time out at 5 minutes.
FILL_TIMEOUT_SECONDS = int(os.environ.get("FILL_TIMEOUT_SECONDS", "180"))

app = FastAPI(
    title="VIDEX Form Automation API",
    description="Automate German Schengen visa application form filling. Use POST /submit + callback to avoid Zoho timeout.",
    version="1.0.0"
)

# Paths (form_runner has SCHEMA_PATH)
BASE_DIR = Path(__file__).parent.parent


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


def _run_filler_subprocess(data: dict[str, Any]) -> dict[str, Any]:
    """
    Spawn `subprocess_runner.py` to drive Playwright in a clean child Python
    process, then read and return the JSON envelope it wrote to a side file.
    Raises HTTPException on transport/timeout failures.
    """
    # Side-channel file: subprocess writes the structured envelope here so it
    # never collides with rich's chatty stdout from form_filler.
    fd, envelope_path_str = tempfile.mkstemp(prefix="videx_envelope_", suffix=".json")
    os.close(fd)
    envelope_path = Path(envelope_path_str)
    try:
        try:
            proc = subprocess.run(
                [sys.executable, str(SUBPROCESS_RUNNER), str(envelope_path)],
                input=json.dumps(data),
                capture_output=True,
                text=True,
                timeout=FILL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail={
                    "error": (
                        f"RPA exceeded {FILL_TIMEOUT_SECONDS}s. The Chromium worker "
                        "is stuck (check container memory, /dev/shm size, and VIDEX "
                        "reachability). Use POST /submit + callback_url for slow runs."
                    ),
                    "stage": "fill_timeout",
                },
            )
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail={"error": f"failed to launch subprocess: {e}", "stage": "subprocess_launch_error"},
            )

        if not envelope_path.exists() or envelope_path.stat().st_size == 0:
            stderr_tail = proc.stderr[-2000:] if proc.stderr else ""
            stdout_tail = proc.stdout[-500:] if proc.stdout else ""
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "subprocess produced no envelope",
                    "stage": "subprocess_silent",
                    "stderr_tail": stderr_tail,
                    "stdout_tail": stdout_tail,
                    "exit_code": proc.returncode,
                },
            )

        try:
            return json.loads(envelope_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": f"subprocess wrote bad envelope: {e}",
                    "stage": "subprocess_bad_envelope",
                    "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
                },
            )
    finally:
        try:
            envelope_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.post("/fill")
def fill_form(data: dict[str, Any]):
    """
    Fill VIDEX form synchronously and return the PDF.
    """
    # Validate / normalise here so we fail fast (under 1 s) before paying
    # the cost of spawning the Playwright subprocess.
    try:
        _, full_name = build_translated_data(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = _run_filler_subprocess(data)

    if result.get("pdf_base64"):
        try:
            pdf_bytes = base64.b64decode(result["pdf_base64"])
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail={"error": f"failed to decode PDF: {e}", "stage": "pdf_decode_error"},
            )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"videx_{full_name}_{timestamp}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    success_count = result.get("success_count", 0)
    fail_count = result.get("fail_count", 0)
    fields_map = result.get("fields") or {}
    failed_fields = sorted([fid for fid, ok in fields_map.items() if not ok])
    validation_error = result.get("validation_error")
    invalid_wrappers = result.get("invalid_wrappers") or []
    if validation_error:
        stage = "videx_validation_error"
        error_msg = f"VIDEX rejected the form: {validation_error}"
    elif result.get("error"):
        stage = "form_filler_exception"
        error_msg = result["error"]
    else:
        stage = "save_pdf_returned_none"
        error_msg = "PDF generation failed (Continue → Download PDF popup not captured)"
    # Compress wrapper info into a flat list of {section, label, current_value,
    # context_snippet} so callers see exactly which red-bordered fields VIDEX
    # is complaining about, no Railway log dive required.
    invalid_summary = [
        {
            "section": w.get("card"),
            "label": w.get("label"),
            "field_id": w.get("inner_id") or None,
            "current_value": w.get("inner_value"),
            "context": w.get("context"),
        }
        for w in invalid_wrappers[:25]
    ]
    raise HTTPException(
        status_code=500,
        detail={
            "error": error_msg,
            "stage": stage,
            "fields_filled": success_count,
            "fields_failed": fail_count,
            "failed_fields": failed_fields[:50],
            "validation_error": validation_error,
            "invalid_fields": invalid_summary,
        },
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
