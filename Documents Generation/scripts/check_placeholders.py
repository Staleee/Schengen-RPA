"""Extract {{placeholders}} from each .docx and compare with document_mapping.json."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TEMPLATES = {
    "cover": BASE / "Cover_Letter.docx",
    "sponsor": BASE / "Sponsor_letter.docx",
    "invitation": BASE / "Invitation Letter (Schengen Visa – Domestic Worker_Housemaid).docx",
}
MAPPING_PATH = BASE / "document_mapping.json"
sys.path.insert(0, str(BASE))
from doc_utils import list_placeholder_variables, normalize_key


def load_expected():
    if not MAPPING_PATH.exists():
        return {}
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    mapping = load_expected()
    for name, path in TEMPLATES.items():
        if not path.exists():
            print(f"[{name}] File not found: {path.name}\n")
            continue
        in_file = list_placeholder_variables(path)
        expected = list(mapping.get(name, {}).keys())
        expected_norm = [normalize_key(e) for e in expected]
        only_in_file = [x for x in in_file if x not in expected_norm]
        only_in_code = [x for x in expected_norm if x not in in_file]
        print(f"=== {name} ({path.name}) ===")
        print("In file (placeholders found, incl. split across runs):", in_file)
        print("In code (expected):", expected)
        if only_in_file:
            print("  -> IN FILE BUT NOT IN CODE:", only_in_file)
        if only_in_code:
            print("  -> IN CODE BUT NOT IN FILE:", only_in_code)
        if not only_in_file and not only_in_code:
            print("  -> OK: consistent")
        print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
