"""Point the invitation letter's travel-section country references at {{destinations}}.

The letter must reflect every destination country when a case visits more than one. We keep
{{schengen_country}} for embassy addressing / subject / "will not work in" (the primary country),
and switch only the two travel-itinerary spots to the new {{destinations}} placeholder:

  * body sentence "... to accompany me during my trip to {{schengen_country}}."
  * "Destination: {{schengen_country}}"

Idempotent: rerunning it is a no-op once the runs already say 'destinations'.

    python scripts/patch_invitation_destinations.py
"""

from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = BASE_DIR / "Invitation Letter (Schengen Visa \u2013 Domestic Worker_Housemaid).docx"


def main() -> None:
    doc = Document(str(TEMPLATE))
    changed = 0
    for p in doc.paragraphs:
        text = p.text
        if "during my trip to" in text or text.strip().startswith("Destination:"):
            for r in p.runs:
                if r.text == "schengen_country":
                    r.text = "destinations"
                    changed += 1
    doc.save(str(TEMPLATE))
    print(f"patched {changed} run(s) -> {{destinations}} in {TEMPLATE.name}")


if __name__ == "__main__":
    main()
