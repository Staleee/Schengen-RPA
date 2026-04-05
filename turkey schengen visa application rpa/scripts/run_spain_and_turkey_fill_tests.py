#!/usr/bin/env python3
"""
Run Spain + Turkey fill smoke tests; write outputs under each RPA's examples/ folder.

Spain:  examples/spain_fill_test_run.pdf
Turkey: examples/turkey_fill_test_run.pdf (needs LibreOffice) or examples/turkey_fill_test_run.docx

Usage (from this repo):
  cd "turkey schengen visa application rpa"
  python scripts/run_spain_and_turkey_fill_tests.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent
TURKEY_ROOT = SCRIPT.parent
SCHENGEN_ROOT = TURKEY_ROOT.parent
SPAIN_ROOT = SCHENGEN_ROOT / "spain schengen visa application rpa"


def _write_bytes_with_fallback(path: Path, data: bytes) -> Path:
    """Write bytes; if the file is open elsewhere (Windows), use a timestamped name."""
    try:
        path.write_bytes(data)
        return path
    except PermissionError:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        alt = path.with_name(f"{path.stem}_{stamp}{path.suffix}")
        alt.write_bytes(data)
        print(f"  (primary locked) wrote -> {alt.name}", file=sys.stderr)
        return alt


def main() -> int:
    spain_examples = SPAIN_ROOT / "examples"
    turkey_examples = TURKEY_ROOT / "examples"
    spain_examples.mkdir(parents=True, exist_ok=True)
    turkey_examples.mkdir(parents=True, exist_ok=True)

    # --- Spain ---
    spain_payload_path = SPAIN_ROOT / "test_payload.json"
    if not spain_payload_path.is_file():
        print(f"Spain: missing {spain_payload_path}", file=sys.stderr)
        return 1
    spain_payload = json.loads(spain_payload_path.read_text(encoding="utf-8"))
    spain_pdf = SPAIN_ROOT / "assets" / "schengen_visa_application_form_english.pdf"
    if not spain_pdf.is_file():
        print("Spain: downloading template PDF…", file=sys.stderr)
        import urllib.request

        spain_pdf.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(
            "https://uae.blsspainvisa.com/assets/pdf/schengen_visa_application_form_english.pdf",
            spain_pdf,
        )
    sys.path.insert(0, str(SPAIN_ROOT))
    from pdf_fill import fill_spain_schengen_pdf  # noqa: E402

    spain_bytes = fill_spain_schengen_pdf(spain_payload, merge_business_rules=True)
    if not spain_bytes.startswith(b"%PDF"):
        print("Spain: output is not a PDF", file=sys.stderr)
        return 1
    spain_out = spain_examples / "spain_fill_test_run.pdf"
    spain_out = _write_bytes_with_fallback(spain_out, spain_bytes)
    print(f"Spain OK -> {spain_out} ({len(spain_bytes)} bytes)")

    # --- Turkey ---
    sys.path.insert(0, str(TURKEY_ROOT))
    from turkey_docx_fill import (  # noqa: E402
        convert_docx_bytes_to_pdf,
        fill_turkey_docx_bytes,
        resolve_word_template,
    )

    turkey_payload_path = TURKEY_ROOT / "examples" / "EXAMPLE_FILL_REQUEST.json"
    if not turkey_payload_path.is_file():
        turkey_payload_path = TURKEY_ROOT / "REQUEST_BODY_TEMPLATE_TURKEY.json"
    turkey_payload = json.loads(turkey_payload_path.read_text(encoding="utf-8"))
    tpl = resolve_word_template()
    if not tpl.is_file():
        print(f"Turkey: template missing: {tpl}", file=sys.stderr)
        return 1
    docx_bytes = fill_turkey_docx_bytes(tpl, turkey_payload)
    if not docx_bytes.startswith(b"PK"):
        print("Turkey: output is not a docx zip", file=sys.stderr)
        return 1

    pdf_bytes = convert_docx_bytes_to_pdf(docx_bytes)
    if pdf_bytes and pdf_bytes.startswith(b"%PDF"):
        turkey_out = _write_bytes_with_fallback(
            turkey_examples / "turkey_fill_test_run.pdf", pdf_bytes
        )
        print(f"Turkey OK -> {turkey_out} ({len(pdf_bytes)} bytes) [PDF]")
    else:
        turkey_out = _write_bytes_with_fallback(
            turkey_examples / "turkey_fill_test_run.docx", docx_bytes
        )
        print(f"Turkey OK -> {turkey_out} ({len(docx_bytes)} bytes) [DOCX fallback]")
        print(
            "  For PDF: install LibreOffice, or on Windows use Microsoft Word + pip install pywin32",
            file=sys.stderr,
        )

    print("\nOutput filenames:")
    print(f"  - {spain_out.name}")
    print(f"  - {turkey_out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
