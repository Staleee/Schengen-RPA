"""Local check: fill AFFIDAVIT-template.pdf with the sample body and verify the output."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf

from affidavit_fill import fill_affidavit_pdf, list_affidavit_placeholders

base = Path(__file__).resolve().parent.parent
template = base / "AFFIDAVIT-template.pdf"
out = base / "output" / "test_affidavit.pdf"

print("placeholders in template:", list_affidavit_placeholders(template))

sample = json.loads((base / "samples" / "affidavit_request.json").read_text(encoding="utf-8"))
mapping = json.loads((base / "document_mapping.json").read_text(encoding="utf-8"))["affidavit"]
subs = {ph: sample.get(rk, "") for rk, ph in mapping.items()}
print("substitutions:", subs)

pdf_bytes = fill_affidavit_pdf(template, subs)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(pdf_bytes)
print(f"wrote {out} ({len(pdf_bytes)} bytes)")

doc = pymupdf.open(out)
print("--- filled text ---")
print(doc[0].get_text())
assert "{{" not in doc[0].get_text(), "placeholder left in output!"
for value in subs.values():
    assert value in doc[0].get_text(), f"missing value: {value}"
pix = doc[0].get_pixmap(dpi=110)
preview = base / "output" / "test_affidavit_preview.png"
pix.save(preview)
print(f"preview: {preview}")
print("OK")
