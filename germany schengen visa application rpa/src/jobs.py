"""
Redis-backed job queue for async VIDEX PDF generation.
- API: enqueue job with body + callback_url, return job_id immediately.
- Worker: pop job, run form filler, POST result to callback_url.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, Optional

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
QUEUE_KEY = "videx:queue"
JOB_PREFIX = "videx:job:"
JOB_TTL = 86400  # 24h


def _redis():
    if not REDIS_URL:
        return None
    try:
        import redis
        return redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None


def enqueue_job(body: Dict[str, Any], callback_url: str, record_id: Optional[str] = None) -> Optional[str]:
    """
    Push job to Redis. Returns job_id or None if Redis unavailable.
    body: same as POST /fill (applicant + client data).
    callback_url: we POST the result here when done (JSON with pdf_base64, status, job_id, record_id).
    """
    r = _redis()
    if not r:
        return None
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "body": body,
        "callback_url": callback_url,
        "record_id": record_id or "",
        "status": "queued",
        "created_at": time.time(),
    }
    key = JOB_PREFIX + job_id
    r.setex(key, JOB_TTL, json.dumps(job))
    r.rpush(QUEUE_KEY, job_id)
    return job_id


def pop_job(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Block until a job is available (or timeout). Returns job dict or None."""
    r = _redis()
    if not r:
        return None
    result = r.blpop(QUEUE_KEY, timeout=timeout)
    if not result:
        return None
    _, job_id = result
    key = JOB_PREFIX + job_id
    raw = r.get(key)
    if not raw:
        return None
    return json.loads(raw)


def set_job_status(job_id: str, status: str, error: Optional[str] = None):
    """Update job status (processing, completed, failed). PDF is not stored in Redis; worker POSTs it to callback only."""
    r = _redis()
    if not r:
        return
    key = JOB_PREFIX + job_id
    raw = r.get(key)
    if not raw:
        return
    job = json.loads(raw)
    job["status"] = status
    if error is not None:
        job["error"] = error
    r.setex(key, JOB_TTL, json.dumps(job))


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status and result (for GET /job/{job_id})."""
    r = _redis()
    if not r:
        return None
    raw = r.get(JOB_PREFIX + job_id)
    if not raw:
        return None
    return json.loads(raw)


def is_redis_available() -> bool:
    return _redis() is not None
