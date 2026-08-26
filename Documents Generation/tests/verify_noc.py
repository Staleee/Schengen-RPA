"""Generate the maid NOC against the running service and check what comes out.

Two things this is here for.

**Emirates ID format.** The NOC was printing the maid's EID exactly as the ERP stored it, which
is free text — so a value like "784199012345671" went out unpunctuated instead of in the
official 784-YYYY-NNNNNNN-C form. Formatting now happens in variable_enrichment. A value that
is not 15 digits (the reported "487627" is simply missing digits) cannot be repaired by
formatting, so it prints as given and the service says so rather than inventing digits.

**The Arabic page renders correctly.** This runs inside the service image, which carries
LibreOffice, so the letter is really converted to PDF here and the Arabic page can be checked —
shaped, right-to-left, correct page order. On a machine without LibreOffice the endpoint falls
back to .docx and none of that is observable, which is why this check lives in Docker.

    docker compose -f tests/docker-compose.yml up --build --abort-on-container-exit
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
from typing import Dict, List, Optional, Tuple

import pymupdf

BASE_URL = os.environ.get("DOCGEN_BASE_URL", "http://localhost:8000").rstrip("/")
OUT_DIR = Path(__file__).resolve().parent / "output"

# Arabic presentation forms — what a shaped Arabic glyph run extracts as.
_PRESENTATION_FORMS = range(0xFB50, 0xFF00)

PAYLOAD: Dict[str, object] = {
    "date_issued": "26 August, 2026",
    "consulate_full_name": "Turkish Consulate General in Dubai, UAE",
    "worker_name": "Kusnayati BT Sukriyadi Rademun",
    "destination_country": "Turkey",
    "companion_name": "Baharul Alam Shayeb",
    "companion_passport": "BX 118822",
    "companion_eid": "784198812345678",
    "worker_nationality": "Indonesian",
    "worker_passport": "AS 940577",
    "worker_eid": "784199012345671",
    "employment_start_date": "13 February, 2017",
    "visa_expiry_date": "14 February, 2029",
    "employer_name": "Baharul Alam Shayeb",
    "employment_basis": "long-term",
    "monthly_salary": "1400.0",
    "annual_salary": "16800",
    "trip_purpose": "Tourism",
    "travel_start_date": "28 August, 2026",
    "travel_end_date": "29 August, 2026",
}


def _wait_for_service(timeout: float = 180.0) -> None:
    deadline = time.time() + timeout
    last: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/variables", timeout=5) as r:
                if r.status == 200:
                    print(f"service up at {BASE_URL}")
                    return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(2)
    raise SystemExit(f"service never became healthy at {BASE_URL}: {last}")


def _generate(payload: Dict[str, object], document_type: str) -> Tuple[bytes, str]:
    request = urllib.request.Request(
        f"{BASE_URL}/generate?document_type={document_type}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"/generate returned {exc.code}: {exc.read().decode('utf-8','replace')}")


def _pdf_text(pdf_bytes: bytes) -> List[str]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def _check(label: str, ok: bool, detail: str = "") -> int:
    print("  %-4s %-46s %s" % ("ok" if ok else "FAIL", label, detail))
    return 0 if ok else 1


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _wait_for_service()
    failures = 0

    content, content_type = _generate(dict(PAYLOAD), "noc-turkey")
    is_pdf = content.startswith(b"%PDF")
    print(f"\nnoc-turkey  ({len(content)} bytes, {content_type})")
    failures += _check(
        "converted to PDF (LibreOffice present in the image)", is_pdf,
        "" if is_pdf else "got .docx — LibreOffice missing, cannot check rendering",
    )
    if not is_pdf:
        (OUT_DIR / "noc_turkey.docx").write_bytes(content)
        print(f"\nartifacts in {OUT_DIR}")
        return 1

    pdf_path = OUT_DIR / "noc_turkey.pdf"
    pdf_path.write_bytes(content)
    pages = _pdf_text(content)

    failures += _check("two pages (English + Arabic)", len(pages) == 2, f"got {len(pages)}")
    # The formatted EID uses non-breaking hyphens so it cannot split across a line; normalise
    # them back to "-" so the assertions read as the number a person would recognise.
    pages = [p.replace("‑", "-") for p in pages]
    english, arabic = (pages + ["", ""])[:2]

    # Emirates ID: formatted, and the raw unpunctuated form gone.
    failures += _check("worker EID formatted 784-1990-1234567-1",
                       "784-1990-1234567-1" in english)
    failures += _check("raw unformatted EID not printed",
                       "784199012345671" not in english)
    failures += _check("companion EID formatted 784-1988-1234567-8",
                       "784-1988-1234567-8" in english)

    # The letter still reads correctly at full length.
    failures += _check("maid name printed in full",
                       "Kusnayati BT Sukriyadi Rademun" in english)
    failures += _check("no unsubstituted placeholders",
                       "{{" not in english and "{{" not in arabic)

    # Arabic page: shaped glyph runs, right-to-left, on page 2.
    shaped = sum(1 for c in arabic if ord(c) in _PRESENTATION_FORMS)
    base_arabic = sum(1 for c in arabic if 0x0600 <= ord(c) <= 0x06FF)
    failures += _check("Arabic page carries Arabic text", shaped + base_arabic > 80,
                       f"shaped={shaped} base={base_arabic}")
    # Extracting Arabic from a rendered PDF is lossy in one specific way: a lam-alef ligature
    # comes back as its two letters in visual order, so "لا" extracts as "ال" and "الإ" as
    # "اإل". Asserting on phrases that contain one would fail on a correctly rendered page, so
    # these probes deliberately avoid lam-alef. The page image in tests/output is the check for
    # the rest.
    # Probed one word at a time. Beyond the lam-alef issue, PyMuPDF emits this page's Arabic
    # words in visual (right-to-left) order, so a multi-word phrase does not appear contiguously
    # even when the page renders perfectly — word membership is the order-independent check.
    deshaped = "".join(unicodedata.normalize("NFKC", c) for c in arabic)
    for word, what in (
        ("شهادة", "Arabic title word 1"),
        ("مانع", "Arabic title word 2"),
        ("سفر", "Arabic title word 3"),
        ("معلومات", "Arabic section headings"),
        ("الخادمة", "Arabic 'domestic worker' heading word"),
        ("الرحلة", "Arabic 'trip' heading word"),
        ("الهوية", "Arabic 'Emirates ID' phrase (was shattered in the old template)"),
    ):
        failures += _check(f"{what} present", word in deshaped)
    # Bidi check: inside right-to-left text the EID's segments used to be reordered and split
    # across a line break. It must extract from the Arabic page as one intact run.
    failures += _check("Arabic page shows the EID intact (not reordered by bidi)",
                       "784-1990-1234567-1" in arabic)
    failures += _check("Arabic page shows the date intact (not reordered by bidi)",
                       "26 August, 2026" in arabic)
    failures += _check("Arabic page shows the phone intact (not reordered by bidi)",
                       "+971 505544143" in arabic)
    # The companion clause mixes Arabic with LTR values, so its passport and EID are isolated
    # individually rather than as a whole value.
    failures += _check("Arabic companion EID intact inside the Arabic clause",
                       "784-1988-1234567-8" in arabic)
    failures += _check("Arabic companion passport intact inside the Arabic clause",
                       "BX 118822" in arabic)

    # An EID that cannot be repaired must survive untouched rather than being invented.
    broken = dict(PAYLOAD, worker_eid="487627")
    content2, _ = _generate(broken, "noc-turkey")
    (OUT_DIR / "noc_turkey_bad_eid.pdf").write_bytes(content2)
    english2 = _pdf_text(content2)[0]
    print("\nnoc-turkey with an unrepairable EID ('487627')")
    failures += _check("printed as given, not invented", "487627" in english2)
    # The companion EID in this payload is still valid and formats normally, so only the
    # worker's own formatted form must be absent — a blanket "784-" check would catch that one.
    failures += _check("no digits invented for the broken value",
                       "784-1990-" not in english2 and "784-0487-" not in english2)

    doc = pymupdf.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=110).save(str(OUT_DIR / f"noc_turkey_p{i}.png"))
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
