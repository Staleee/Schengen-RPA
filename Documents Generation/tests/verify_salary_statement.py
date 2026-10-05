"""Generate the Turkey Embassy salary statement and check PDF output.

Runs against the deployed Documents Generation service (Docker image with LibreOffice).
Without LibreOffice, /generate returns .docx and rendering checks are skipped.

    DOCGEN_BASE_URL=http://localhost:8000 python tests/verify_salary_statement.py

Or via docker compose (see tests/README.md).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

import pymupdf

BASE_URL = os.environ.get("DOCGEN_BASE_URL", "http://localhost:8000").rstrip("/")
OUT_DIR = Path(__file__).resolve().parent / "output"
SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "salary_statement_request.json"


def _wait_for_service() -> None:
    last: Exception | None = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(2)
    raise SystemExit(f"service never became healthy at {BASE_URL}: {last}")


def _generate(payload: Dict[str, object]) -> Tuple[bytes, str]:
    request = urllib.request.Request(
        f"{BASE_URL}/generate?document_type=salary-statement",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"/generate returned {exc.code}: {exc.read().decode('utf-8', 'replace')}")


def _pdf_text(pdf_bytes: bytes) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _check(label: str, ok: bool, detail: str = "") -> int:
    print("  %-4s %-46s %s" % ("ok" if ok else "FAIL", label, detail))
    return 0 if ok else 1


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _wait_for_service()

    with open(SAMPLES, encoding="utf-8") as f:
        payload: Dict[str, object] = json.load(f)

    failures = 0
    content, content_type = _generate(payload)
    is_pdf = content.startswith(b"%PDF")
    print(f"\nsalary-statement  ({len(content)} bytes, {content_type})")
    failures += _check(
        "converted to PDF (LibreOffice present in the image)",
        is_pdf,
        "" if is_pdf else "got .docx — LibreOffice missing, cannot check rendering",
    )
    if not is_pdf:
        (OUT_DIR / "salary_statement.docx").write_bytes(content)
        print(f"\nartifacts in {OUT_DIR}")
        return 1

    pdf_path = OUT_DIR / "salary_statement.pdf"
    pdf_path.write_bytes(content)
    text = _pdf_text(content)

    failures += _check("no unsubstituted placeholders", "{{" not in text)
    failures += _check("maid name present", "Jane Doe" in text)
    failures += _check("client name present", "John Smith" in text)
    failures += _check("six salary amounts present", text.count("1500") >= 6)
    failures += _check(
        "newest payment month present",
        "September" in text or "15 September" in text,
    )

    print(f"\nartifacts in {OUT_DIR}")
    return failures


if __name__ == "__main__":
    sys.exit(main())
