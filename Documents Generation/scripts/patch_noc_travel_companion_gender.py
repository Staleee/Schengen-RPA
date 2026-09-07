"""Add the {{companion_gender}} token to the noc-travel.docx travel-party clause.

The tourist-visa maid NOC clause named the companion with nationality only:

    ... accompanied by {{companion_salutation_name}}. {{companion_name}},
    {{companion_nationality}}, holding passport number {{companion_passport_number}}...

Tourist Visa issues rows 1 & 3 (Lebanon / Egypt) require the companion's gender to appear too.
This inserts ``{{companion_gender}}`` right after the nationality so the clause reads
"..., {{companion_nationality}}, {{companion_gender}}, holding passport number ...". Idempotent.

    python scripts/patch_noc_travel_companion_gender.py
"""

from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = BASE_DIR / "noc-travel.docx"

ANCHOR = "{{companion_nationality}}, holding passport number"
REPLACEMENT = "{{companion_nationality}}, {{companion_gender}}, holding passport number"


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")

    doc = Document(TEMPLATE)
    patched = False
    for para in doc.paragraphs:
        for run in para.runs:
            if "{{companion_gender}}" in run.text:
                print(f"Already patched -> {TEMPLATE.name}")
                return
            if ANCHOR in run.text:
                run.text = run.text.replace(ANCHOR, REPLACEMENT)
                patched = True
                break
        if patched:
            break

    if not patched:
        raise SystemExit(f"Could not find companion clause anchor in {TEMPLATE.name}")

    doc.save(TEMPLATE)
    print(f"Inserted {{{{companion_gender}}}} into companion clause -> {TEMPLATE.name}")


if __name__ == "__main__":
    main()
