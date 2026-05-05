"""
Diagnostic: open VIDEX in Chromium and dump the DOM around the
residence-permit and 'assumption of all expenses' checkboxes so we
can fix the selectors.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://videx.diplo.de/videx/visum-erfassung/videx-kurzfristiger-aufenthalt"


def main() -> int:
    out_dir = Path("/debug_out/dom_inspect")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 4000}, locale="en-US")
        page = context.new_page()

        print(f"navigating to {URL}", flush=True)
        page.goto(URL, timeout=90000, wait_until="domcontentloaded")
        page.wait_for_selector('input[id="antragsteller.familienname"]', timeout=30000)

        # switch to English (this triggers a navigation)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                page.locator("select").first.select_option(label="English")
            page.wait_for_selector('input[id="antragsteller.familienname"]', timeout=30000)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"language switch warning: {e}", flush=True)

        # 1) Look for any element whose id contains 'aufenthaltsberechtigung'
        print("\n=== Elements with id*=aufenthaltsberechtigung ===", flush=True)
        ids_js = """
        () => {
          const els = Array.from(document.querySelectorAll('[id]'));
          return els
            .filter(e => e.id.toLowerCase().includes('aufenthaltsberechtigung'))
            .map(e => ({ id: e.id, tag: e.tagName, type: e.getAttribute('type'), name: e.getAttribute('name'), visible: e.offsetParent !== null }));
        }
        """
        for el in page.evaluate(ids_js):
            print(f"  {el}", flush=True)

        # 2) Look for any element whose id contains 'kostenuebernahme'
        print("\n=== Elements with id*=kostenuebernahme ===", flush=True)
        ids2_js = """
        () => {
          const els = Array.from(document.querySelectorAll('[id]'));
          return els
            .filter(e => e.id.toLowerCase().includes('kostenuebernahme'))
            .map(e => ({ id: e.id, tag: e.tagName, type: e.getAttribute('type'), name: e.getAttribute('name'), visible: e.offsetParent !== null }));
        }
        """
        for el in page.evaluate(ids2_js):
            print(f"  {el}", flush=True)

        # 3) Look for label text "residence in a country other than"
        print("\n=== Labels containing 'residence in' ===", flush=True)
        lbl_js = """
        () => {
          const labels = Array.from(document.querySelectorAll('label, mat-label, span, div'));
          return labels
            .filter(l => (l.textContent || '').toLowerCase().includes('residence in a country other than'))
            .slice(0, 5)
            .map(l => ({
              tag: l.tagName,
              for: l.getAttribute('for'),
              text: (l.textContent || '').trim().slice(0, 100),
              outerStart: l.outerHTML.slice(0, 200),
            }));
        }
        """
        for el in page.evaluate(lbl_js):
            print(f"  {el}", flush=True)

        # 4) Take a screenshot of section 4 area (Residence in other country)
        try:
            section_lbl = page.get_by_text("Residence in a country other than", exact=False).first
            section_lbl.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(400)
            page.screenshot(path=str(out_dir / "section4_residence_in_other_country.png"))
            print(f"\nsaved {out_dir / 'section4_residence_in_other_country.png'}", flush=True)
        except Exception as e:
            print(f"\ncould not screenshot residence section: {e}", flush=True)

        # 5) Take a screenshot of the costs section
        try:
            costs_lbl = page.get_by_text("All expenses covered during", exact=False).first
            costs_lbl.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(400)
            page.screenshot(path=str(out_dir / "section9_assumption_of_costs.png"))
            print(f"saved {out_dir / 'section9_assumption_of_costs.png'}", flush=True)
        except Exception as e:
            print(f"could not screenshot costs section: {e}", flush=True)

        # 6) Dump the full page HTML for offline grep
        (out_dir / "page.html").write_text(page.content(), encoding="utf-8")
        print(f"saved {out_dir / 'page.html'}", flush=True)

        # 7) Try several strategies for the residence question's Yes input.
        residence_q = "Is your residence in a country other than that of your current nationality?"
        print("\n=== Residence question lookup strategies ===", flush=True)

        try:
            cb = page.get_by_label(residence_q, exact=False).first
            print(f"  get_by_label visible? {cb.is_visible(timeout=1000)}, count={cb.count()}", flush=True)
        except Exception as e:
            print(f"  get_by_label exception: {e}", flush=True)

        # find via app-pass-restricted-checkbox-texts containing the text,
        # then walk up to the surrounding form-check/app-checkbox group
        js = """
        (q) => {
          const txts = Array.from(document.querySelectorAll('app-pass-restricted-checkbox-texts, label, span, div'));
          const node = txts.find(n => (n.textContent || '').includes(q));
          if (!node) return { found: false };
          // Walk up to find a parent that ALSO contains an input[type=checkbox]
          let p = node;
          for (let i = 0; i < 8 && p; i++) {
            const inputs = p.querySelectorAll('input[type="checkbox"]');
            if (inputs.length > 0) {
              return {
                found: true,
                ancestorTag: p.tagName,
                ancestorClass: p.className,
                ancestorOuter: p.outerHTML.slice(0, 300),
                inputs: Array.from(inputs).map(i => ({
                  id: i.id || null,
                  name: i.name || null,
                  classList: i.className,
                  parentText: ((i.closest('label') || i.parentElement)?.textContent || '').trim().slice(0, 80),
                })),
              };
            }
            p = p.parentElement;
          }
          return { found: false, reason: 'no checkbox ancestor' };
        }
        """
        result = page.evaluate(js, residence_q)
        print(f"  ancestor-walk result: {result}", flush=True)

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
