"""Check the reported Spain application-form fields against the running service.

Six issues were reported on submitted Spain applications: fields 5 (place of birth), 8 (sex),
9 (marital status) and 14 (date of issue) printing blank; both boxes of field 19 needing to be
blank but being filled; and field 20's tick missing.

They split into two kinds, and this checks both:

* **19 and 20 were code faults.** Field 19 (the applicant's own address/email and phone) was
  being filled and now stays blank — note the §31 *host* phone is a different widget and must
  still be filled, so that is asserted too. Field 20 is a RadioButton group, not a checkbox:
  both widgets share one field name and each carries its own on-state, so the old "/On" write
  did nothing and the field always printed blank.
* **5, 8, 9 and 14 were not mapping faults.** All four are mapped correctly and fill whenever
  the value arrives; they come off the maid's profile, so a blank box means a blank profile.
  Nothing here can invent a marital status for a visa form, so instead the service reports the
  fields that will print blank. This asserts both halves: they fill when the data is there, and
  they are named in the report when it is not.

Run via tests/docker-compose.yml, or against a running service with
RPA_BASE_URL=http://localhost:8090 python tests/verify_application_fields.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

import pymupdf

BASE_URL = os.environ.get("RPA_BASE_URL", "http://localhost:8090").rstrip("/")
SERVICE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "output"
sys.path.insert(0, str(SERVICE_DIR))

# printed field -> AcroForm field name on the harmonised template.
TEXT_FIELDS = {
    "4 date of birth": "Texto1",
    "5 place of birth": "Texto2",
    "13 travel document number": "Texto10",
    "14 date of issue": "Texto11",
    "15 valid until": "Texto12",
    "16 issued by": "Texto13",
}
TICK_FIELDS = {
    "8 sex (female)": "MujerFemale",
    "9 marital status (single)": "ChkBox",
}
# §9 has a box per status. Only single and married were ever mapped, so a maid whose ERP civil
# status is DIVORCED or WIDOW had the whole field left blank.
MARITAL_BOXES = {
    "single": "ChkBox",
    "married": "ChkBox-0",
    "divorced": "ChkBox-1",
    "widowed": "ChkBox-2",
}
# Must come out blank: the applicant's own address/email and her phone.
MUST_BE_BLANK = {
    "19 address + email": "Texto18",
    "19 phone": "Números de teléfonoTelephone numbers",
}
# Must stay filled: the §31 host phone is a different widget that happens to share a label.
MUST_BE_FILLED = {"31 host phone": "Números de teléfonoTelephone numbers-0"}
FIELD_20_RADIO = "20 Residente en un país distinto del país de nacio"

# A complete profile, shaped like pro-backend's buildBlsVisa body.
COMPLETE: Dict[str, object] = {
    "maid_surname": "BALABAG",
    "maid_first_names": "EVELYN BAGUIO",
    "maid_date_of_birth": "04.01.1976",
    "maid_place_of_birth": "Lagonglong Misamis",
    "nationality": "Filipino",
    "maid_gender": "Female",
    "marital_status": "single",
    "passport_number": "P0150695D",
    "passport_issue_date": "06.08.2021",
    "passport_expiry_date": "05.08.2031",
    "passport_issuing_country": "Philippines",
    "maid_address": "Al Barsha 2, Dubai",
    "maid_email": "evelyn@example.com",
    "maid_phone": "+971501112233",
    "maid_uae_resident": True,
    "uae_residence_visa_number": "201/2024/1234567",
    "uae_residence_visa_expiry": "01.01.2027",
    "occupation": "Domestic Worker",
    "purpose_tourism": True,
    "arrival_date": "10.09.2026",
    "departure_date": "20.09.2026",
    "client_name": "AHMED AL MANSOURI",
    "client_phone": "+971509998877",
    # The §31 host contact resolves off the client only when they are the travel companion,
    # which is what pro-backend sends for these applications.
    "client_is_travel_companion": True,
    "client_hotel_address": "Hotel Catalonia, Barcelona, Spain",
    "place_and_date": "United Arab Emirates, 26.08.2026",
}

# What an incomplete maid profile looks like: the four reported fields have no source value.
# An unknown gender must still tick a box: every applicant here is a housemaid and the templates
# are written for one, so §8 defaults to female rather than printing blank.
SEX_DEFAULT_CASES = (
    ("gender absent", {}, "MujerFemale"),
    ("gender = Female", {"maid_gender": "Female"}, "MujerFemale"),
    ("gender = F", {"maid_gender": "F"}, "MujerFemale"),
    ("gender = Male", {"maid_gender": "Male"}, "VarónMale"),
    ("gender = M", {"maid_gender": "M"}, "VarónMale"),
)

PROFILE_GAPS = (
    "maid_gender", "sex_male", "sex_female",
    "marital_status", "marital_status_single", "marital_status_married",
    "maid_place_of_birth", "passport_issue_date",
)


def _wait_for_service(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as r:
                if r.status == 200:
                    print(f"service up at {BASE_URL}")
                    return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(1)
    raise SystemExit(f"service never became healthy at {BASE_URL}: {last}")


def _fill(payload: Dict[str, object]) -> bytes:
    request = urllib.request.Request(
        f"{BASE_URL}/fill-pdf",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"/fill-pdf returned {exc.code}: {exc.read().decode('utf-8','replace')}")


def _values(pdf_path: Path) -> Dict[str, object]:
    """field name -> value; radio groups collapse to the selected widget's on-state."""
    out: Dict[str, object] = {}
    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for w in page.widgets() or []:
                name, value = w.field_name, w.field_value
                if w.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                    if value not in (None, "", "Off"):
                        out[name] = value
                    out.setdefault(name, "Off")
                elif name not in out or not str(out.get(name) or "").strip():
                    out[name] = value
    finally:
        doc.close()
    return out


def _render(pdf_path: Path, page_no: int, clip: pymupdf.Rect, png: Path) -> None:
    doc = pymupdf.open(pdf_path)
    try:
        doc[page_no].get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2), clip=clip).save(png)
    finally:
        doc.close()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _wait_for_service()
    failures = 0

    # --- complete profile: everything reported as missing should be present -------------
    pdf = OUT_DIR / "application-complete-profile.pdf"
    pdf.write_bytes(_fill(dict(COMPLETE)))
    values = _values(pdf)
    print(f"\ncomplete profile  ({pdf.name})")

    for label, field in TEXT_FIELDS.items():
        got = str(values.get(field) or "").strip()
        ok = bool(got)
        failures += 0 if ok else 1
        print("  %-4s %-28s %r" % ("ok" if ok else "FAIL", label, got))

    for label, field in TICK_FIELDS.items():
        ok = values.get(field) in (True, "On", "/On")
        failures += 0 if ok else 1
        print("  %-4s %-28s %s" % ("ok" if ok else "FAIL", label, "ticked" if ok else "off"))

    for label, field in MUST_BE_BLANK.items():
        got = str(values.get(field) or "").strip()
        ok = not got
        failures += 0 if ok else 1
        print("  %-4s %-28s %s" % ("ok" if ok else "FAIL", label + " (blank)", "blank" if ok else repr(got)))

    for label, field in MUST_BE_FILLED.items():
        got = str(values.get(field) or "").strip()
        ok = bool(got)
        failures += 0 if ok else 1
        print("  %-4s %-28s %r" % ("ok" if ok else "FAIL", label + " (kept)", got))

    selected = str(values.get(FIELD_20_RADIO) or "Off")
    ok = "siyes" in re.sub(r"#([0-9A-Fa-f]{2})", "", selected).lower().replace(" ", "")
    failures += 0 if ok else 1
    print("  %-4s %-28s %s" % ("ok" if ok else "FAIL", "20 residence radio (Yes)",
                               "Yes selected" if ok else f"got {selected!r}"))
    _render(pdf, 1, pymupdf.Rect(40, 140, 560, 265), OUT_DIR / "application-fields-19-20.png")
    _render(pdf, 0, pymupdf.Rect(40, 320, 560, 480), OUT_DIR / "application-fields-4-9.png")

    # --- incomplete profile: the blank fields have to be named, not silently skipped ----
    thin = {k: v for k, v in COMPLETE.items() if k not in PROFILE_GAPS}
    pdf2 = OUT_DIR / "application-incomplete-profile.pdf"
    pdf2.write_bytes(_fill(thin))
    values2 = _values(pdf2)
    print(f"\nincomplete profile  ({pdf2.name})")

    from pdf_fill import missing_required_fields
    from spain_merge import merge_spain_schengen_body

    reported = missing_required_fields(merge_spain_schengen_body(thin))
    # §8 sex is deliberately absent: it defaults to female rather than printing blank, so it can
    # never be one of the reported gaps.
    for expected in ("5 place of birth", "9 marital status", "14 date of issue"):
        ok = expected in reported
        failures += 0 if ok else 1
        print("  %-4s reported blank: %-28s %s" % ("ok" if ok else "FAIL", expected,
                                                   "" if ok else f"(report was {list(reported)})"))
    # 19 and 20 are code-driven, so they must still be right on an incomplete profile.
    ok = not str(values2.get(MUST_BE_BLANK["19 address + email"]) or "").strip()
    failures += 0 if ok else 1
    print("  %-4s %-28s %s" % ("ok" if ok else "FAIL", "19 still blank", "blank" if ok else "filled"))
    sel2 = str(values2.get(FIELD_20_RADIO) or "Off")
    ok = "siyes" in re.sub(r"#([0-9A-Fa-f]{2})", "", sel2).lower().replace(" ", "")
    failures += 0 if ok else 1
    print("  %-4s %-28s %s" % ("ok" if ok else "FAIL", "20 still Yes", "Yes selected" if ok else sel2))

    # --- every civil status the ERP can hold has to tick its own box ---------------------
    print("\nmarital status (ERP HousemaidCivilStatus values)")
    for status, field in MARITAL_BOXES.items():
        pdf3 = OUT_DIR / f"application-marital-{status}.pdf"
        pdf3.write_bytes(_fill(dict(COMPLETE, marital_status=status)))
        vals3 = _values(pdf3)
        ticked = [name for name in MARITAL_BOXES.values() if vals3.get(name) in (True, "On", "/On")]
        ok = ticked == [field]
        failures += 0 if ok else 1
        print("  %-4s %-12s -> %-10s %s" % ("ok" if ok else "FAIL", status, field,
                                            "" if ok else f"ticked={ticked}"))

    # --- §8 sex: never blank, and an explicit male still wins ---------------------------
    print("\nsex (defaults to female when unknown)")
    for label, override, expected_box in SEX_DEFAULT_CASES:
        payload = {k: v for k, v in COMPLETE.items() if k != "maid_gender"}
        payload.update(override)
        pdf4 = OUT_DIR / ("application-sex-" + label.replace(" ", "-").replace("=", "") + ".pdf")
        pdf4.write_bytes(_fill(payload))
        vals4 = _values(pdf4)
        ticked = [b for b in ("MujerFemale", "VarónMale") if vals4.get(b) in (True, "On", "/On")]
        ok = ticked == [expected_box]
        failures += 0 if ok else 1
        print("  %-4s %-16s -> %-12s %s" % ("ok" if ok else "FAIL", label, expected_box,
                                            "" if ok else f"ticked={ticked}"))

    # --- field 20's mark has to be visible, not merely set ------------------------------
    doc = pymupdf.open(OUT_DIR / "application-complete-profile.pdf")
    try:
        marked = False
        for page in doc:
            for w in page.widgets() or []:
                if w.field_name == FIELD_20_RADIO and w.field_value not in (None, "", "Off"):
                    band = pymupdf.Rect(w.rect)
                    for drawing in page.get_drawings():
                        for item in drawing["items"]:
                            if item[0] == "l" and band.contains(item[1]) and band.contains(item[2]):
                                marked = True
        failures += 0 if marked else 1
        print("\n  %-4s 20 selected radio carries a drawn cross, not just the faint built-in dot"
              % ("ok" if marked else "FAIL"))
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
