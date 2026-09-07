"""Remove the baked-in signature + stamp image from noc-travel.docx.

The tourist-visa maid NOC template had a hardcoded signature+stamp block (``word/media/image1.jpg``,
placed just after the "Maids CC Domestic Worker Services LLC" line) drawn straight onto the page.
The global signatory rule makes the signature and company stamp *request parameters*
(``signature_image_url`` / ``stamp_image_url``, embedded at fill time by ``doc_utils`` around the
``{{signatory_name}}`` line), so the baked image must go — otherwise every NOC shows a fixed
signature that can never be changed or cleared.

This strips the body ``<w:drawing>`` that embeds that image, drops its relationship and the media
file, and leaves the header letterhead (``image2.png``) untouched. Idempotent.

    python scripts/patch_noc_travel_remove_baked_signature.py
"""

import re
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = BASE_DIR / "noc-travel.docx"
DOC_XML = "word/document.xml"
RELS_XML = "word/_rels/document.xml.rels"


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")

    with zipfile.ZipFile(TEMPLATE) as z:
        names = z.namelist()
        document = z.read(DOC_XML).decode("utf-8")
        rels = z.read(RELS_XML).decode("utf-8")

    # Which body drawings embed which relationship id.
    embed_ids = set()
    for block in re.findall(r"<w:drawing>.*?</w:drawing>", document, flags=re.S):
        embed_ids.update(re.findall(r'r:embed="([^"]+)"', block))
    if not embed_ids:
        print(f"Already patched (no body drawings) -> {TEMPLATE.name}")
        return

    # Map each embedded rId to its media target so we know which media file to drop.
    media_targets = {}
    for rid in embed_ids:
        m = re.search(rf'Id="{re.escape(rid)}"[^>]*Target="([^"]+)"', rels)
        if m:
            media_targets[rid] = "word/" + m.group(1).lstrip("/")

    # Remove every body drawing (the only body image on this template is the signature/stamp;
    # the letterhead lives in the header and is not touched).
    new_document = re.sub(r"<w:drawing>.*?</w:drawing>", "", document, flags=re.S)
    # Drop the now-orphaned image relationships.
    new_rels = rels
    for rid in embed_ids:
        new_rels = re.sub(rf'<Relationship\b[^>]*Id="{re.escape(rid)}"[^>]*/>', "", new_rels)

    drop_media = set(media_targets.values())

    tmp = TEMPLATE.with_suffix(".docx.tmp")
    with zipfile.ZipFile(TEMPLATE) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in drop_media:
                continue
            if item.filename == DOC_XML:
                zout.writestr(item, new_document)
            elif item.filename == RELS_XML:
                zout.writestr(item, new_rels)
            else:
                zout.writestr(item, zin.read(item.filename))

    shutil.move(str(tmp), str(TEMPLATE))
    print(f"Removed baked signature/stamp {sorted(drop_media)} (rels {sorted(embed_ids)}) -> {TEMPLATE.name}")


if __name__ == "__main__":
    main()
