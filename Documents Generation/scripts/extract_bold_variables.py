"""Run from Documents Generation folder: python scripts/extract_bold_variables.py
Prints all bold placeholders (variables) from each .docx so you can build REQUEST_BODY.md and Zoho mapping.
"""
import sys
from pathlib import Path

# Add parent so we can import doc_utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doc_utils import list_bold_variables

BASE = Path(__file__).resolve().parent.parent
TEMPLATES = [
    ("Invitation Letter", BASE / "Invitation Letter (Schengen Visa – Domestic Worker_Housemaid).docx"),
    ("Sponsor Letter", BASE / "Sponsor_letter.docx"),
    ("Cover Letter", BASE / "Cover_Letter.docx"),
]

def main():
    print("Bold variables (request body keys) per document:\n")
    all_keys = set()
    for name, path in TEMPLATES:
        if not path.exists():
            print(f"[{name}] File not found: {path}\n")
            continue
        vars_ = list_bold_variables(path)
        print(f"[{name}]")
        for v in vars_:
            print(f"  raw: {v['raw']!r}  ->  key: {v['key']!r}")
            all_keys.add(v["key"])
        print()
    print("All unique keys (use these in request body):")
    for k in sorted(all_keys):
        print(f"  {k}")


if __name__ == "__main__":
    main()
