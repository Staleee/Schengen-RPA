"""One-time patch for the Schengen maid NOC AcroForm (Travel_NOC_Fillable.pdf).

Two layout defects in the template:

1. English page: the client's Emirates ID field (``companion_eid``) exists TWICE —
   once inside the companion sentence ("... holder of passport number X, Emirates ID: Y")
   and once more as a stray widget starting the next line, so the EID prints twice.
   Fix: delete the stray second widget (the one below the companion line).

2. Arabic page: the form was authored over a flattened filled sample, so the page's
   static text still contains the old example values (names, passport/EID numbers,
   dates, salaries). Filling the form overlaid new values on top of the stale ones.
   Fix: redact the static text underneath every Arabic-page widget rect — EXCEPT the
   two fields whose correct Arabic rendering is authored static text and which pymupdf
   cannot re-shape inside a form field appearance:
     - employment_basis  (أساس طويل الأمد)
     - trip_purpose      (السياحة)
   Those two stay static; ``acroform_fill.fill_acroform_pdf`` skips them on the
   Arabic page so the English value is never overlaid.

Idempotent: re-running finds no stray widget and no stale text (redactions over
already-clean rects are no-ops).

    python scripts/patch_noc_schengen_template.py
"""

from pathlib import Path

import pymupdf

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = BASE_DIR / "Travel_NOC_Fillable.pdf"

ENGLISH_PAGE = 0
ARABIC_PAGE = 1

# Arabic-page fields whose value is authored static Arabic text (see module docstring).
ARABIC_STATIC_FIELDS = ("employment_basis", "trip_purpose")

# The duplicate companion_eid on the English page sits below the companion sentence line.
STRAY_EID_MIN_Y = 275


def main() -> None:
    doc = pymupdf.open(str(TEMPLATE))

    # 1. English page: drop the stray duplicate companion_eid widget.
    page_en = doc[ENGLISH_PAGE]
    deleted = 0
    for w in list(page_en.widgets() or []):
        if w.field_name == "companion_eid" and w.rect.y0 > STRAY_EID_MIN_Y:
            page_en.delete_widget(w)
            deleted += 1
    print(f"  stray companion_eid widgets removed from English page: {deleted}")

    # 2. Arabic page: redact stale static sample text under widget rects.
    page_ar = doc[ARABIC_PAGE]
    redactions = 0
    for w in list(page_ar.widgets() or []):
        if w.field_name in ARABIC_STATIC_FIELDS:
            continue
        r = w.rect
        # Slight inflation to catch ascenders/descenders of the stale text.
        page_ar.add_redact_annot(pymupdf.Rect(r.x0 - 1.5, r.y0 - 1.5, r.x1 + 1.5, r.y1 + 1.5))
        redactions += 1
    if redactions:
        page_ar.apply_redactions()
    print(f"  Arabic page: redacted stale text under {redactions} widget rect(s)")

    # Save via a temp file: pymupdf refuses in-place non-incremental saves, and an
    # incremental save would keep the redacted sample data recoverable in the file's
    # history — the whole point is to purge it (it is real PII from an old example).
    tmp = TEMPLATE.with_name(TEMPLATE.stem + ".patched.tmp.pdf")
    doc.save(str(tmp), deflate=True, garbage=3)
    doc.close()
    tmp.replace(TEMPLATE)
    print(f"Done -> {TEMPLATE.name}")


if __name__ == "__main__":
    main()
