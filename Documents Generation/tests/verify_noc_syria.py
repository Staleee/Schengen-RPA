"""Generate the Syria maid NOC and check PDF output (Arabic RTL + LTR numeric fields).

Runs against the deployed Documents Generation service (Docker image with LibreOffice).
Without LibreOffice, /generate returns .docx and rendering checks are skipped.

    DOCGEN_BASE_URL=http://localhost:8000 python tests/verify_noc_syria.py

Or via docker compose (see tests/README.md).
"""

from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

import pymupdf

BASE_URL = os.environ.get("DOCGEN_BASE_URL", "http://localhost:8000").rstrip("/")
OUT_DIR = Path(__file__).resolve().parent / "output"
SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "noc_syria_request.json"

_PRESENTATION_FORMS = range(0xFB50, 0xFF00)


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
        f"{BASE_URL}/generate?document_type=noc-syria",
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
    print(f"\nnoc-syria  ({len(content)} bytes, {content_type})")
    failures += _check(
        "converted to PDF (LibreOffice present in the image)",
        is_pdf,
        "" if is_pdf else "got .docx — LibreOffice missing, cannot check rendering",
    )
    if not is_pdf:
        (OUT_DIR / "noc_syria.docx").write_bytes(content)
        print(f"\nartifacts in {OUT_DIR}")
        return 1

    pdf_path = OUT_DIR / "noc_syria.pdf"
    pdf_path.write_bytes(content)
    text = _pdf_text(content).replace("‑", "-")

    failures += _check("no unsubstituted placeholders", "{{" not in text)
    deshaped_early = "".join(unicodedata.normalize("NFKC", c) for c in text)
    failures += _check("maid name (Arabic) present", "ماريا" in deshaped_early)
    failures += _check("companion name (Arabic) present", "مكتوم" in deshaped_early)
    failures += _check(
        "companion title from gender (m → السيد)",
        "السيد" in deshaped_early,
    )
    failures += _check("passport number printed", "P12345678" in text)
    failures += _check("monthly salary printed", "1500" in text)
    failures += _check("annual salary printed", "18000" in text)

    failures += _check(
        "maid EID formatted 784-1990-1234567-1",
        "784-1990-1234567-1" in text,
    )
    failures += _check(
        "raw unformatted EID not printed",
        "784199012345671" not in text,
    )

    failures += _check(
        "issue date intact (not reordered by bidi)",
        "1 October, 2026" in text,
    )
    failures += _check(
        "joining date intact (not reordered by bidi)",
        "15 March, 2019" in text,
    )
    failures += _check(
        "r-visa expiry intact (not reordered by bidi)",
        "20 June, 2030" in text,
    )
    failures += _check(
        "signatory phone intact (not reordered by bidi)",
        "+971 505544143" in text,
    )

    shaped = sum(1 for c in text if ord(c) in _PRESENTATION_FORMS)
    base_arabic = sum(1 for c in text if 0x0600 <= ord(c) <= 0x06FF)
    failures += _check(
        "Arabic text present on page",
        shaped + base_arabic > 40,
        f"shaped={shaped} base={base_arabic}",
    )
    failures += _check("maid nationality (Arabic) present", "فلبينية" in deshaped_early)

    doc = pymupdf.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=110).save(str(OUT_DIR / f"noc_syria_p{i}.png"))
    finally:
        doc.close()

    print(f"\nartifacts in {OUT_DIR}")
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
