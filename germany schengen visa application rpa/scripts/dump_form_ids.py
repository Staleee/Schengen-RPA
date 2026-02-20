"""
Dump all form field IDs (and labels) from the live VIDEX page so you can compare
with our schema and fix missing/wrong IDs.

Run from project root:
  python scripts/dump_form_ids.py

Output: output/videx_form_ids_dump.json and output/videx_form_ids_dump.txt
Then you can diff or search for "Country", "Telephone", etc. to see the exact IDs the form uses.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
VIDEX_URL = "https://videx.diplo.de/videx/visum-erfassung/videx-kurzfristiger-aufenthalt"


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT))
    from playwright.sync_api import sync_playwright

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUTPUT_DIR / "videx_form_ids_dump.json"
    out_txt = OUTPUT_DIR / "videx_form_ids_dump.txt"

    fields = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(VIDEX_URL, timeout=90000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        # Switch to English if possible
        try:
            page.locator("select").first.select_option(label="English")
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # All inputs and selects
        for tag in ["input", "select"]:
            els = page.locator(tag).all()
            for i, el in enumerate(els):
                try:
                    fid = el.get_attribute("id")
                    name = el.get_attribute("name")
                    typ = el.get_attribute("type") or (tag if tag == "select" else "text")
                    placeholder = el.get_attribute("placeholder") or ""
                    if not fid and not name:
                        continue
                    id_or_name = fid or name or f"no-id-{tag}-{i}"
                    # Try label: get by "for" or parent
                    label_text = ""
                    try:
                        label_el = page.locator(f"label[for='{id_or_name}']").first
                        if label_el.count() > 0:
                            label_text = (label_el.text_content() or "").strip()[:80]
                    except Exception:
                        pass
                    if not label_text:
                        try:
                            aria = el.get_attribute("aria-label") or ""
                            if aria:
                                label_text = aria[:80]
                        except Exception:
                            pass
                    entry = {
                        "id": fid,
                        "name": name,
                        "type": typ,
                        "placeholder": placeholder,
                        "label": label_text,
                    }
                    fields.append(entry)
                except Exception as e:
                    fields.append({"error": str(e), "index": i})
        browser.close()

    # Dedupe by id (keep first)
    seen = set()
    unique = []
    for e in fields:
        if "error" in e:
            unique.append(e)
            continue
        k = e.get("id") or e.get("name") or ""
        if k and k not in seen:
            seen.add(k)
            unique.append(e)
        elif not k:
            unique.append(e)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    lines = []
    for e in unique:
        if "error" in e:
            lines.append(f"ERROR: {e['error']}")
            continue
        lid = e.get("id") or "(no id)"
        lbl = (e.get("label") or "").strip()
        typ = e.get("type") or ""
        lines.append(f"{lid}\t{typ}\t{lbl}")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Dumped {len(unique)} fields to {out_json} and {out_txt}")
    print("Search for 'Country', 'Telephone', 'phone', 'land', 'telefon' to find the exact IDs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
