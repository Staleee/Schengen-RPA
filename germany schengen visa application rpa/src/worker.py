"""
Worker: poll Redis for VIDEX jobs, run form filler, POST result to Zoho callback URL.
Run as second Railway service: CMD python -m src.worker
Requires REDIS_URL. Set HEADLESS=true.
"""

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_fill import build_translated_data
from form_runner import run_form_filler
from jobs import pop_job, set_job_status

CALLBACK_TIMEOUT = 60


def _post_callback(url: str, payload: dict) -> bool:
    """POST JSON to callback URL. Returns True on 2xx."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=CALLBACK_TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"Callback POST failed: {e}", flush=True)
        return False


def process_one():
    job = pop_job(timeout=10)
    if not job:
        return False
    job_id = job.get("job_id")
    body = job.get("body") or {}
    callback_url = (job.get("callback_url") or "").strip()
    record_id = job.get("record_id") or ""

    set_job_status(job_id, "processing")

    try:
        translated_data, full_name = build_translated_data(body)
    except ValueError as e:
        set_job_status(job_id, "failed", error=str(e))
        if callback_url:
            _post_callback(callback_url, {
                "job_id": job_id,
                "record_id": record_id,
                "status": "failed",
                "error": str(e),
            })
        return True

    result = run_form_filler(translated_data, full_name)
    pdf_content = result.get("pdf_content")
    error = result.get("error")

    if pdf_content and not error:
        pdf_b64 = base64.b64encode(pdf_content).decode("ascii")
        set_job_status(job_id, "completed")
        if callback_url:
            _post_callback(callback_url, {
                "job_id": job_id,
                "record_id": record_id,
                "status": "completed",
                "filename": f"videx_{full_name}.pdf",
                "pdf_base64": pdf_b64,
            })
    else:
        err_msg = error or "PDF generation failed"
        set_job_status(job_id, "failed", error=err_msg)
        if callback_url:
            _post_callback(callback_url, {
                "job_id": job_id,
                "record_id": record_id,
                "status": "failed",
                "error": err_msg,
            })
    return True


def main():
    if not os.environ.get("REDIS_URL", "").strip():
        print("REDIS_URL not set; worker cannot run.", flush=True)
        sys.exit(1)
    print("VIDEX worker started. Waiting for jobs...", flush=True)
    while True:
        try:
            process_one()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Worker error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
