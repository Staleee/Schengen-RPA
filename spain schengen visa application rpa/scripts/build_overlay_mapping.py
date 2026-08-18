"""Build a rect-based overlay map for a flat (non-AcroForm) harmonised Schengen PDF.

For every logical field we locate its printed label, then bound the value to the label's *cell*
using the form's own ruling lines (nearest vertical rule to the right = cell right edge; nearest
horizontal rule below = cell bottom edge) and the label's own text extent:

  * "right" fields: the value starts just after the END OF THE LABEL LINE (all label words on
    that baseline), so it never lands on the label's own trailing text
    (e.g. "(Former family name(s)):").
  * "below" fields: the value starts just below the LABEL BLOCK (the label plus any wrapped
    continuation lines), so it never overlaps a wrapped label.

The value is written inside the resulting rect by overlay_fill.fill_overlay_pdf (wrapping + font
auto-shrink). Checkboxes anchor to the real ☐ glyph (U+2610) nearest-left of the option label.

    python scripts/build_overlay_mapping.py portugal   # -> countries/portugal_overlay.json

Always render + eyeball:  python scripts/render_overlay_preview.py portugal
Per-form quirks (cramped cells, duplicate labels) are corrected in OVERRIDES below.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS = BASE_DIR / "assets"

# (key, label substring, mode, multiline). mode: "right" = value after the label line;
# "below" = value in the blank area below the label block.
TEXT_FIELDS = [
    ("surname",                 "Surname (Family name)",        "right", False),
    ("maid_surname_at_birth",   "Surname at birth",             "right", False),
    ("given_names",             "First name(s)",                "right", False),
    ("maid_date_of_birth",      "Date of birth",                "below", False),
    ("maid_place_of_birth",     "Place of birth",               "right", False),
    ("country_of_birth",        "Country of birth",             "right", False),
    ("nationality",             "Current nation",               "below", False),
    ("passport_number",         "Number of travel",             "below", False),
    ("passport_issue_date",     "Date of issue",                "below", False),
    ("passport_expiry_date",    "Valid until",                  "below", False),
    ("passport_issuing_country","Issued by",                    "below", False),
    ("applicant_address_email", "home address",                 "below", True),
    ("occupation",              "Current occupation",           "right", False),
    ("employer_sponsor_address","Employer",                     "below", True),
    ("purpose_additional_info", "Additional information on purpose", "below", True),
    ("destination_member_states_line", "Member State of main",  "below", False),
    ("first_entry_member_state","Member State of first",        "below", False),
    ("arrival_date",            "Intended date of arrival",     "below", False),
    ("departure_date",          "Intended date of departure",   "below", False),
    ("partner_name",            "inviting",                     "below", True),
    ("partner_address_email",   "mail address of inviting",     "below", True),
]

# (key, option-label substring). The tick box is the ☐ glyph just left of the option label.
CHECK_FIELDS = [
    ("sex_male",                        "Male"),
    ("sex_female",                      "Female"),
    ("marital_status_single",           "Single"),
    ("marital_status_married",          "Married"),
    ("travel_doc_ordinary_passport",    "Ordinary passport"),
    ("purpose_tourism",                 "Tourism"),
    ("entries_one",                     "Single entry"),
    ("entries_two",                     "Two entries"),
    ("entries_multiple",                "Multiple entries"),
    ("all_expenses_covered_during_stay","All expenses covered during the stay"),
]

SPECS = {
    "portugal": {"pdf": "portugal_schengen_form.pdf"},
    "greece":   {"pdf": "greece_schengen_form.pdf"},
    "bulgaria": {"pdf": "bulgaria_schengen_form.pdf"},
    "italy":    {"pdf": "italy_conslagos.pdf"},
}

# Per-form, per-key spec overrides merged on top of the auto-computed spec. Use for cramped cells
# or duplicate labels where the auto cell is wrong. Values are partial specs (rect / mode / etc.).
OVERRIDES: dict = {
    "portugal": {},
    "greece": {},
    "bulgaria": {
        # Field 30: "inviting" appears in both the name label and the address sub-label with
        # justified 4-line wrapping, so pin both values explicitly. Name -> trailing blank of the
        # label's last line; address+email -> blank area below the address sub-label block.
        "partner_name":          {"page": 3, "rect": [319.0, 418.0, 433.0, 433.5], "align": "left", "valign": "bottom", "fontsize": 8.5},
        "partner_address_email": {"page": 3, "rect": [70.0, 503.5, 250.0, 532.0], "align": "left", "valign": "top", "fontsize": 8.0, "min_fontsize": 6.0, "multiline": True},
    },
    "italy": {
        # Field 28 arrival/departure are label + dotted line to the RIGHT (not a cell below),
        # so pin the value onto each dotted line explicitly.
        "arrival_date":   {"page": 3, "rect": [283.0, 55.0, 505.0, 66.5], "align": "left", "valign": "bottom", "fontsize": 9.0},
        "departure_date": {"page": 3, "rect": [314.0, 87.0, 505.0, 98.5], "align": "left", "valign": "bottom", "fontsize": 9.0},
    },
}

_MARGIN = 6.0
_BOX_W = 7.0


def _hrules(page):
    ys = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 1.2 and abs(it[2].x - it[1].x) > 20:
                ys.append((round((it[1].y + it[2].y) / 2, 1), min(it[1].x, it[2].x), max(it[1].x, it[2].x)))
            elif it[0] == "re" and it[1].height < 2.5 and it[1].width > 20:
                ys.append((round(it[1].y0, 1), it[1].x0, it[1].x1))
    return ys


def _vrules(page):
    xs = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l" and abs(it[1].x - it[2].x) < 1.2 and abs(it[2].y - it[1].y) > 20:
                xs.append((round((it[1].x + it[2].x) / 2, 1), min(it[1].y, it[2].y), max(it[1].y, it[2].y)))
            elif it[0] == "re" and it[1].width < 2.5 and it[1].height > 20:
                xs.append((round(it[1].x0, 1), it[1].y0, it[1].y1))
    return xs


def _block_right(vrules, page_width):
    """The applicant-block's right border x: the rightmost vertical rule that is still within the
    left ~78% of the page (excludes the 'for official use' column's right/page border). Used as the
    cell-right fallback for the thin identity rows (fields 1-3) that sit above the ruled grid."""
    cands = [x for (x, _y0, _y1) in vrules if x <= 0.78 * page_width]
    return max(cands) if cands else page_width - 40.0


def _cell_right(vrules, L, page_width):
    ys = (L.y0 + L.y1) / 2
    cands = [x for (x, y0, y1) in vrules if x > L.x1 + 2 and y0 - 3 <= ys <= y1 + 3]
    return min(cands) if cands else _block_right(vrules, page_width)


def _cell_left(vrules, L):
    ys = (L.y0 + L.y1) / 2
    cands = [x for (x, y0, y1) in vrules if x < L.x0 - 1 and y0 - 3 <= ys <= y1 + 3]
    return max(cands) if cands else L.x0 - 4.0


def _cell_bottom(hrules, L, above_y=None):
    """First horizontal rule crossing the label's x below the label. When ``above_y`` is given
    (the label-block bottom), rules hugging it (< 6pt) are skipped so we return the true cell
    floor, not a label underline."""
    floor = (above_y if above_y is not None else L.y1) + (6.0 if above_y is not None else 1.0)
    cands = [y for (y, x0, x1) in hrules if y > floor and x0 - 3 <= L.x0 and x1 + 3 >= L.x0]
    return min(cands) if cands else (above_y or L.y1) + 16.0


def _label_line_end(words, L, cell_right):
    """Right edge of the label text on the label's baseline: walk the words on that line from the
    label rightward and stop at the first big gap (the blank input area), so text in a neighbouring
    column (e.g. the 'for official use' box that shares the row) is never treated as label."""
    cy = (L.y0 + L.y1) / 2
    line = sorted((w for w in words if w[0] >= L.x0 - 2 and w[2] <= cell_right + 1 and w[1] - 2 <= cy <= w[3] + 2),
                  key=lambda w: w[0])
    end = L.x1
    for w in line:
        if w[0] - end > 25:  # gap to the blank input area -> label ends here
            break
        end = max(end, w[2])
    return end


def _label_block_bottom(words, L, cell_left, cell_right, cell_bottom):
    """Bottom y of the label block: the label line plus wrapped continuation lines that hug it
    (gap < 6pt). Stops before the blank input area / stacked sub-labels."""
    region = [w for w in words if w[0] >= cell_left - 2 and w[2] <= cell_right + 1
              and w[1] >= L.y0 - 2 and w[3] <= cell_bottom - 1]
    if not region:
        return L.y1
    # group into lines by y0
    region.sort(key=lambda w: (round(w[1], 0), w[0]))
    lines = []
    for w in region:
        if lines and abs(w[1] - lines[-1][0]) < 3:
            lines[-1][1] = max(lines[-1][1], w[3])
            lines[-1][0] = min(lines[-1][0], w[1])
        else:
            lines.append([w[1], w[3]])
    lines.sort()
    bottom = lines[0][1]
    for top, bot in lines[1:]:
        if top - bottom < 6:
            bottom = bot
        else:
            break
    return bottom


def _box_tokens(page):
    """List of (x0, y0, x1, y1) rects for every ☐ glyph on the page."""
    out = []
    for w in page.get_text("words"):
        txt = w[4]
        if "\u2610" in txt or "\u25A1" in txt or "\u2751" in txt:
            # box is the leading glyph cell; width ~ _BOX_W
            out.append((w[0], w[1], w[0] + _BOX_W, w[3]))
    return out


def _seg_points(page):
    """Endpoints of every SHORT drawing segment (len < 16) and corners of small rects (< 16px).
    Long cell-border rules are excluded, so clusters of these points isolate the small tick-box
    squares that some forms (e.g. Italy conslagos) draw as vector line segments rather than a ☐
    glyph."""
    pts = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                dx, dy = it[2].x - it[1].x, it[2].y - it[1].y
                if (dx * dx + dy * dy) ** 0.5 < 16:
                    pts.append((it[1].x, it[1].y))
                    pts.append((it[2].x, it[2].y))
            elif it[0] == "re" and it[1].width < 16 and it[1].height < 16:
                pts.append((it[1].x0, it[1].y0))
                pts.append((it[1].x1, it[1].y1))
    return pts


def _segment_box(seg_pts, L):
    """A vector-drawn tick box just left of option label ``L`` (bbox of the short-segment points in
    the region left of the label), or None."""
    cy = (L.y0 + L.y1) / 2
    near = [(x, y) for (x, y) in seg_pts if L.x0 - 22 <= x <= L.x0 + 3 and cy - 8 <= y <= cy + 8]
    if len(near) < 6:
        return None
    xs = [p[0] for p in near]
    ys = [p[1] for p in near]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if 4 <= x1 - x0 <= 14 and 4 <= y1 - y0 <= 14:
        return (x0, y0, x1, y1)
    return None


def build(country: str) -> None:
    spec = SPECS[country]
    doc = fitz.open(str(ASSETS / spec["pdf"]))
    overrides = OVERRIDES.get(country, {})
    overlay: dict = {}

    def locate(label):
        for pno in range(len(doc)):
            rects = doc[pno].search_for(label)
            if rects:
                r = rects[0]
                for rr in rects[1:]:
                    if abs(rr.y0 - r.y0) < 3:
                        r |= rr
                return pno, r
        return None, None

    for key, label, mode, multiline in TEXT_FIELDS:
        pno, L = locate(label)
        if L is None:
            print(f"  !! text label not found: {key}: {label!r}")
            continue
        page = doc[pno]
        words = page.get_text("words")
        vr, hr = _vrules(page), _hrules(page)
        cright = _cell_right(vr, L, page.rect.width)
        cleft = _cell_left(vr, L)
        line_end = _label_line_end(words, L, cright)
        block_bottom = _label_block_bottom(words, L, cleft, cright, _cell_bottom(hr, L))
        cbottom = _cell_bottom(hr, L, above_y=block_bottom)

        s = None
        if mode == "right" and cright - line_end >= 42:
            rect = [round(line_end + 5, 1), round(L.y0 - 1, 1), round(cright - _MARGIN, 1), round(L.y1 + 1.5, 1)]
            s = {"page": pno + 1, "rect": rect, "align": "left", "valign": "bottom", "fontsize": 9.0}

        if s is None:  # below the label block, or a "right" field with no room on the line
            top = block_bottom + 2
            if cbottom - block_bottom < 11 and not multiline:
                # cell too short below the label -> place on the label line, right of the label
                left = max(cleft + 4, line_end + 5, cright - 96)
                s = {"page": pno + 1, "rect": [round(left, 1), round(L.y0 - 1, 1), round(cright - 2, 1), round(L.y1 + 1.5, 1)],
                     "align": "right", "valign": "bottom", "fontsize": 8.0}
            elif multiline:
                s = {"page": pno + 1, "rect": [round(cleft + 4, 1), round(block_bottom + 1, 1), round(cright - _MARGIN, 1), round(cbottom - 1, 1)],
                     "align": "left", "valign": "top", "fontsize": 8.5, "min_fontsize": 6.0, "multiline": True}
            else:
                bot = min(cbottom - 2, top + 13)
                s = {"page": pno + 1, "rect": [round(cleft + 4, 1), round(top, 1), round(cright - _MARGIN, 1), round(bot, 1)],
                     "align": "left", "valign": "bottom", "fontsize": 9.0}
        s.update(overrides.get(key, {}))
        overlay[key] = s

    boxes_by_page = {}
    segpts_by_page = {}
    for key, option in CHECK_FIELDS:
        pno, L = locate(option)
        if L is None:
            print(f"  !! checkbox option not found: {key}: {option!r}")
            continue
        if pno not in boxes_by_page:
            boxes_by_page[pno] = _box_tokens(doc[pno])
            segpts_by_page[pno] = _seg_points(doc[pno])
        cy = (L.y0 + L.y1) / 2
        left = [b for b in boxes_by_page[pno] if b[2] <= L.x0 + 2 and abs((b[1] + b[3]) / 2 - cy) < 6]
        seg = _segment_box(segpts_by_page[pno], L)
        if left:
            b = max(left, key=lambda r: r[2])  # nearest ☐ glyph to the left of the label
            bx0, by0, bx1, by1 = b
        elif seg is not None:
            bx0, by0, bx1, by1 = seg  # vector-drawn square (e.g. Italy conslagos)
        else:
            bx0, by0, bx1, by1 = L.x0 - 10, cy - 3.5, L.x0 - 3, cy + 3.5
        # square, centred mark region
        bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
        half = min(_BOX_W, by1 - by0) / 2
        box = [round(bcx - half, 1), round(bcy - half, 1), round(bcx + half, 1), round(bcy + half, 1)]
        s = {"page": pno + 1, "check": True, "box": box}
        s.update(overrides.get(key, {}))
        overlay[key] = s

    # Override-only keys (explicit specs for cells with no reliable auto anchor: residence,
    # phones, fingerprints "No", sponsor, etc.).
    for key, spec in overrides.items():
        if key not in overlay and isinstance(spec, dict) and ("rect" in spec or "box" in spec):
            overlay[key] = dict(spec)

    doc.close()
    out = BASE_DIR / "countries" / f"{country}_overlay.json"
    out.write_text(json.dumps(overlay, indent=1), encoding="utf-8")
    n_txt = sum(1 for v in overlay.values() if not v.get("check"))
    n_chk = sum(1 for v in overlay.values() if v.get("check"))
    print(f"WROTE {out.name} ({n_txt} text + {n_chk} checkbox)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "portugal")
