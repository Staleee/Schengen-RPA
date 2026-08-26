"""Drive the running RPA over HTTP with static payloads and check field 33 on every template.

Field 33 is "Cost of travelling and living during the applicant's stay is covered". For the
maids.cc flow all three of its boxes belong ticked — the client sponsors the trip and is the
host already named in §30/§31:

    [x] by a sponsor (host, company, organisation), please specify:
    [x]     referred to in field 30 or 31
    [x] All expenses covered during the stay

Four separate faults kept that from happening: "referred to in field 30 or 31" had no mapping
on the harmonised form, pro-backend sent costs_paid_by_sponsor_host=false, the Swiss template
never mapped its sponsor box, and the whole field-33 default lived only in the Spain merge —
which the multi-country path never reaches. So this checks each country, not just Spain.

The two fill engines need different checks. AcroForm templates (harmonised/Spain, Switzerland)
carry a real checkbox whose value can be read back. Overlay templates (Italy, Greece, Bulgaria,
Portugal) are flat PDFs where a tick is two crossing vector lines drawn into the box, so the
check looks for drawn segments inside the box rect from that country's overlay map. Either way a
cropped PNG of the region is written next to the PDF, so the result can be reviewed by eye and
not only asserted.

Run the whole thing (service + checks):

    docker compose -f tests/docker-compose.yml up --build --abort-on-container-exit

Against an already-running service:

    RPA_BASE_URL=http://localhost:8090 python tests/verify_field33.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf

BASE_URL = os.environ.get("RPA_BASE_URL", "http://localhost:8090").rstrip("/")
SERVICE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "output"

# Run as `python tests/verify_field33.py`, so the service package dir is not on sys.path.
sys.path.insert(0, str(SERVICE_DIR))

SPONSOR = "by a sponsor (host, company, organisation)"
REFERRED = "referred to in field 30 or 31"
ALL_EXPENSES = "All expenses covered during the stay"

# label -> AcroForm field name, per template.
HARMONISED_FIELDS = {
    SPONSOR: "por un patrocinador anfitrión empresa u organizaci",
    REFERRED: "indicado en las casillas 30 031",
    ALL_EXPENSES: "Todos los gastos de estancia están cubiertosAll ex",
}
SWISS_FIELDS = {
    SPONSOR: "by a sponsor host company organisation please specify",
    ALL_EXPENSES: "All expenses covered during the stay",
}
# The Swiss template builds §33 "referred to in field 30 or 31" as a one-character TEXT input
# named `undefined`, not a checkbox, so it is ticked by typing a mark into it.
SWISS_TEXT_MARKS = {REFERRED: "undefined"}
# label -> overlay-map key, for the flat templates.
OVERLAY_KEYS = {
    SPONSOR: "costs_paid_by_sponsor_host",
    REFERRED: "costs_sponsor_referred_in_field_30_or_31",
    ALL_EXPENSES: "all_expenses_covered_during_stay",
}

CHECKED_VALUES = (True, "On", "/On", "Yes", "/Yes")

# A realistic body shaped like pro-backend's buildBlsVisa payload, kept in step with
# generate_review_samples.py.
STATIC_PAYLOAD: Dict[str, object] = {
    "maid_surname": "BALABAG",
    "maid_surname_at_birth": "BALABAG",
    "maid_first_names": "EVELYN BAGUIO",
    "maid_date_of_birth": "04.01.1976",
    "maid_place_of_birth": "Lagonglong Misamis",
    "nationality": "Filipino",
    "maid_gender": "F",
    "marital_status": "single",
    "passport_number": "P0150695D",
    "passport_issue_date": "06.08.2021",
    "passport_expiry_date": "05.08.2031",
    "passport_issuing_country": "Philippines",
    "maid_address": "Al Barsha 2, Dubai",
    "maid_email": "evelyn@example.com",
    "maid_phone": "+971501112233",
    "uae_residence_visa_number": "201/2024/1234567",
    "uae_residence_visa_expiry": "01.01.2027",
    "occupation": "Domestic Worker",
    "employer_sponsor_address": (
        "Maids CC Domestic Workers Services - Umm Suqeim Street, Al Barsha 2, Dubai"
    ),
    "purpose_tourism": True,
    "destination_member_state_line": "Spain",
    "first_entry_member_state": "Spain",
    "arrival_date": "10.09.2026",
    "departure_date": "20.09.2026",
    "entries_multiple": True,
    "client_name": "AHMED AL MANSOURI",
    "client_email": "ahmed@example.com",
    "client_phone": "+971509998877",
    "client_erp_address": "Villa 12, Al Barsha 2, Dubai, United Arab Emirates",
    "client_hotel_address": "Hotel Catalonia, Barcelona, Spain",
    "sponsor_client_name": "AHMED AL MANSOURI",
    "sponsor_client_email": "ahmed@example.com",
    "sponsor_client_phone": "+971509998877",
    "place_and_date": "United Arab Emirates, 26.08.2026",
}

ALL_ON = {SPONSOR: True, REFERRED: True, ALL_EXPENSES: True}
ALL_OFF = {SPONSOR: False, REFERRED: False, ALL_EXPENSES: False}
ALL_OFF_PAYLOAD: Dict[str, object] = {
    "all_expenses_covered_during_stay": False,
    "costs_paid_by_sponsor_host": False,
    "costs_sponsor_referred_in_field_30_or_31": False,
}

# (case name, country or None for Spain, payload overrides, expected state per label)
CASES: List[Tuple[str, Optional[str], Dict[str, object], Dict[str, bool]]] = [
    (
        "spain-as-pro-backend-sends",
        None,
        {
            "all_expenses_covered_during_stay": True,
            "costs_paid_by_sponsor_host": True,
            "costs_sponsor_referred_in_field_30_or_31": True,
        },
        ALL_ON,
    ),
    (
        # No cost keys at all: the RPA's own defaults have to tick all three, so a caller that
        # never learned the new key still produces a correct form.
        "spain-caller-omits-cost-keys",
        None,
        {},
        ALL_ON,
    ),
    (
        # An explicit false must still win, or the defaults would be a silent override.
        "spain-caller-sends-false",
        None,
        ALL_OFF_PAYLOAD,
        ALL_OFF,
    ),
    ("switzerland-defaults", "switzerland", {}, ALL_ON),
    ("switzerland-caller-sends-false", "switzerland", ALL_OFF_PAYLOAD, ALL_OFF),
    ("italy-defaults", "italy", {}, ALL_ON),
    ("greece-defaults", "greece", {}, ALL_ON),
    ("bulgaria-defaults", "bulgaria", {}, ALL_ON),
    ("portugal-defaults", "portugal", {}, ALL_ON),
    ("greece-caller-sends-false", "greece", ALL_OFF_PAYLOAD, ALL_OFF),
]

# Italy moved to the ops-provided fillable template, so it is an AcroForm now — and like the
# Swiss form its tick boxes are one-character TEXT inputs rather than checkboxes.
OVERLAY_COUNTRIES = ("greece", "bulgaria", "portugal")
ITALY_TEXT_MARKS = {
    SPONSOR: "Cost_paid_by_sponsor",
    REFERRED: "Sponsor_referred_field",
    ALL_EXPENSES: "Sponsor_means_all_expenses",
}


def _wait_for_service(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as response:
                if response.status == 200:
                    print(f"service up at {BASE_URL}")
                    return
        except (urllib.error.URLError, OSError) as exc:  # not listening yet
            last_error = exc
            time.sleep(1)
    raise SystemExit(f"service never became healthy at {BASE_URL}: {last_error}")


def _post_fill_pdf(payload: Dict[str, object]) -> bytes:
    request = urllib.request.Request(
        f"{BASE_URL}/fill-pdf",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"/fill-pdf returned {exc.code}: {exc.read().decode('utf-8', 'replace')}")
    if not body.startswith(b"%PDF"):
        raise SystemExit("/fill-pdf did not return a PDF")
    return body


def _overlay_boxes(country: str) -> Dict[str, Tuple[int, pymupdf.Rect]]:
    """label -> (page index, tick box) from the country's overlay map."""
    path = SERVICE_DIR / "countries" / f"{country}_overlay.json"
    overlay = json.loads(path.read_text(encoding="utf-8"))
    boxes: Dict[str, Tuple[int, pymupdf.Rect]] = {}
    for label, key in OVERLAY_KEYS.items():
        spec = overlay.get(key)
        if isinstance(spec, dict) and spec.get("box"):
            # Overlay maps store 1-based page numbers (fill_overlay_pdf subtracts one).
            boxes[label] = (int(spec["page"]) - 1, pymupdf.Rect(spec["box"]))
    return boxes


def _box_alignment(country: str, boxes: Dict[str, Tuple[int, pymupdf.Rect]]) -> Dict[str, bool]:
    """Does each mapped tick box actually sit on the template's own checkbox?

    A tick drawn faithfully into a box the overlay map placed slightly wrong still reads as
    "checked" to _overlay_state — that is how Bulgaria's "referred to in field 30 or 31" tick
    ended up straddling the edge of its box, next to the option instead of in it. So compare the
    mapped box against the empty-box glyphs (U+2610) printed in the blank template. Pages whose
    boxes are vector squares rather than glyphs (Italy's conslagos form) have nothing to compare
    against and are reported as skipped.
    """
    from multi_country_fill import ASSETS_DIR, COUNTRY_CONFIGS, normalize_country

    template = ASSETS_DIR / COUNTRY_CONFIGS[normalize_country(country)].template
    aligned: Dict[str, bool] = {}
    doc = pymupdf.open(template)
    try:
        for label, (page_no, box) in boxes.items():
            if page_no >= doc.page_count:
                continue
            glyphs = [
                pymupdf.Rect(char["bbox"])
                for block in doc[page_no].get_text("rawdict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
                for char in span["chars"]
                if char["c"] == "☐"
            ]
            if not glyphs:
                continue  # vector-drawn boxes; nothing to compare against
            centre = pymupdf.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
            aligned[label] = any(glyph.contains(centre) for glyph in glyphs)
    finally:
        doc.close()
    return aligned


def _acroform_state(pdf_path: Path, fields: Dict[str, str]) -> Dict[str, bool]:
    wanted = {name: label for label, name in fields.items()}
    found: Dict[str, bool] = {}
    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for widget in page.widgets() or []:
                label = wanted.get(widget.field_name)
                if label is not None:
                    found[label] = widget.field_value in CHECKED_VALUES
    finally:
        doc.close()
    return found


def _text_mark_state(pdf_path: Path, fields: Dict[str, str]) -> Dict[str, bool]:
    """Ticked = a non-empty mark typed into the text input standing in for a checkbox."""
    wanted = {name: label for label, name in fields.items()}
    found: Dict[str, bool] = {}
    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for widget in page.widgets() or []:
                label = wanted.get(widget.field_name)
                if label is not None:
                    found[label] = bool(str(widget.field_value or "").strip())
    finally:
        doc.close()
    return found


def _overlay_state(pdf_path: Path, boxes: Dict[str, Tuple[int, pymupdf.Rect]]) -> Dict[str, bool]:
    """A tick is drawn as crossing line segments inside the box, so look for drawn geometry."""
    found: Dict[str, bool] = {}
    doc = pymupdf.open(pdf_path)
    try:
        for label, (page_no, box) in boxes.items():
            if page_no >= doc.page_count:
                continue
            probe = pymupdf.Rect(box.x0 - 1, box.y0 - 1, box.x1 + 1, box.y1 + 1)
            segments = 0
            for drawing in doc[page_no].get_drawings():
                for item in drawing["items"]:
                    if item[0] != "l":  # line segment
                        continue
                    if probe.contains(item[1]) and probe.contains(item[2]):
                        segments += 1
            # _draw_check draws two diagonals; one stray segment is not a tick.
            found[label] = segments >= 2
    finally:
        doc.close()
    return found


def _render_region(
    pdf_path: Path, page_no: int, clip: pymupdf.Rect, png_path: Path
) -> None:
    doc = pymupdf.open(pdf_path)
    try:
        if page_no >= doc.page_count:
            return
        page = doc[page_no]
        clip = pymupdf.Rect(
            max(0, clip.x0 - 20), max(0, clip.y0 - 30),
            min(page.rect.x1, clip.x1 + 320), min(page.rect.y1, clip.y1 + 30),
        )
        page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip).save(png_path)
    finally:
        doc.close()


def _acroform_region(pdf_path: Path, fields: Dict[str, str]) -> Optional[Tuple[int, pymupdf.Rect]]:
    doc = pymupdf.open(pdf_path)
    try:
        names = set(fields.values())
        for page in doc:
            rects = [pymupdf.Rect(w.rect) for w in page.widgets() or [] if w.field_name in names]
            if not rects:
                continue
            clip = rects[0]
            for rect in rects[1:]:
                clip |= rect
            return page.number, clip
    finally:
        doc.close()
    return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _wait_for_service()

    failures = 0
    for name, country, overrides, expected in CASES:
        payload = dict(STATIC_PAYLOAD)
        if country:
            payload["country"] = country
        payload.update(overrides)

        pdf_path = OUT_DIR / f"{name}.pdf"
        pdf_path.write_bytes(_post_fill_pdf(payload))

        alignment: Dict[str, bool] = {}
        if country in OVERLAY_COUNTRIES:
            boxes = _overlay_boxes(country)
            actual = _overlay_state(pdf_path, boxes)
            alignment = _box_alignment(country, boxes)
            engine = "overlay"
            region = None
            if boxes:
                page_no = min(p for p, _ in boxes.values())
                clip = None
                for p, box in boxes.values():
                    if p != page_no:
                        continue
                    clip = box if clip is None else (clip | box)
                region = (page_no, clip) if clip is not None else None
        else:
            if country == "italy":
                fields = {}
                actual = _text_mark_state(pdf_path, ITALY_TEXT_MARKS)
                engine = "acroform/marks"
                region = _acroform_region(pdf_path, ITALY_TEXT_MARKS)
            else:
                fields = SWISS_FIELDS if country == "switzerland" else HARMONISED_FIELDS
                actual = _acroform_state(pdf_path, fields)
                if country == "switzerland":
                    actual.update(_text_mark_state(pdf_path, SWISS_TEXT_MARKS))
                engine = "acroform"
                region = _acroform_region(pdf_path, fields)

        if region is not None:
            _render_region(pdf_path, region[0], region[1], OUT_DIR / f"{name}_field33.png")

        print(f"\n{name}  [{engine}]  {pdf_path.name}")
        for label, want in expected.items():
            if label not in actual:
                print(f"  FAIL {label:<44} box not found in template/overlay map")
                failures += 1
                continue
            ok = actual[label] == want
            failures += 0 if ok else 1
            note = ""
            if label in alignment:
                if not alignment[label]:
                    note = "  <- BOX MISPLACED: not on the template checkbox"
                    failures += 1
                else:
                    note = "  (box on template checkbox)"
            print(
                "  %-4s %-44s expected=%-7s actual=%-7s%s"
                % (
                    "ok" if ok else "FAIL",
                    label,
                    "checked" if want else "off",
                    "checked" if actual[label] else "off",
                    note,
                )
            )

    print(f"\nartifacts in {OUT_DIR}")
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
