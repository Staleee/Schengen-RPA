"""Point the sponsor and cover letters' travel-sentence country references at {{destinations}}.

The letters must reflect every destination country when a case visits more than one
(e.g. "Spain and France"). We keep {{schengen_country}} for the embassy/consulate
addressee line (the single application country) and switch only the travel sentences
to the {{destinations}} placeholder:

  Sponsor_letter.docx
    "I intend to travel to {{schengen_country}} for leisure purposes ..."

  Cover_Letter.docx
    "... short-term Schengen visa to travel to {{schengen_country}} from ..."
    "... during their leisure trip to {{schengen_country}}, in my capacity ..."

Same approach as patch_invitation_destinations.py: the placeholder name sits in its
own run ({{ + name + }} are split across runs), so we replace the run whose text is
exactly "schengen_country" inside the targeted paragraphs only.

Idempotent: rerunning it is a no-op once the runs already say 'destinations'.

    python scripts/patch_letters_destinations.py
"""

from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent

# filename -> paragraph marker phrases that identify the travel sentences
TARGETS = {
    "Sponsor_letter.docx": ["I intend to travel to"],
    "Cover_Letter.docx": ["to travel to", "leisure trip to"],
}


def patch_file(path: Path, markers: list[str]) -> None:
    if not path.exists():
        print(f"  ERROR: template not found: {path.name}")
        return

    doc = Document(str(path))
    changed = 0
    for p in doc.paragraphs:
        text = p.text
        if not any(marker in text for marker in markers):
            continue
        for r in p.runs:
            if r.text == "schengen_country":
                r.text = "destinations"
                changed += 1
            elif r.text == "{{schengen_country}}":
                r.text = "{{destinations}}"
                changed += 1

    if changed:
        doc.save(str(path))
        print(f"  [{path.name}] patched {changed} run(s) -> {{{{destinations}}}}")
    else:
        print(f"  [{path.name}] SKIP (already patched or phrase not found)")


def main() -> None:
    print("Pointing sponsor/cover travel sentences at {{destinations}} ...")
    for filename, markers in TARGETS.items():
        patch_file(BASE_DIR / filename, markers)
    print("Done.")


if __name__ == "__main__":
    main()
