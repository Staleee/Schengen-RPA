"""
Form Filler - Automates filling the VIDEX visa application form.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Locator, TimeoutError as PlaywrightTimeout, Download
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

VIDEX_URL = "https://videx.diplo.de/videx/visum-erfassung/videx-kurzfristiger-aufenthalt"

# Fill order: one section at a time so we don't skip or fill randomly.
# Each section: (display_name, list of field_id prefixes that belong to this section).
# A field is in a section if field_id equals a prefix or starts with prefix + "." or prefix + "[".
FORM_SECTIONS = [
    ("1. Personal details (applicant)", [
        "antragsteller.familienname", "antragsteller.vorname", "antragsteller.geburtsdatum",
        "antragsteller.geburtsort", "antragsteller.geburtsland", "antragsteller.geschlecht",
        "antragsteller.familienstand", "antragsteller.staatsangehoerigkeitListe",
        # VIDEX requires "Original nationality" (Nationality at birth) on the
        # Personal-data block; without this prefix the field was being silently
        # dropped from every section and never filled.
        "antragsteller.staatsangehoerigkeitBeiGeburtListe",
        "antragsteller.geburtsname", "rechtAufFreizuegigkeit",
    ]),
    ("2. Occupation", [
        "antragsteller.personendaten.berufdaten",
    ]),
    ("3. Contact / applicant address", [
        "antragsteller.personendaten.staendigeAnschrift",
    ]),
    ("4. Residence in other country", [
        "antragsteller.aufenthaltsberechtigung",
    ]),
    ("5. Documents / travel document", [
        "antragsteller.pass", "antragsteller.nationaleIdentNr",
    ]),
    ("6. Biometric data", [
        "antragsteller.biometrie",
    ]),
    ("7. Travel data", [
        "reisedaten.aufenthaltszweckListe", "reisedaten.angegebenerReisezweck",
        "reisedaten.weitereInformationen", "reisedaten.ersteinreiseStaat",
        "reisedaten.hauptzielListe", "reisedaten.letzteVisumStickernummer",
        "visumdaten",
    ]),
    ("8. Reference / Householder", [
        "referenz",
    ]),
    ("9. Assumption of costs", [
        "reisedaten.reisekostenUebernahme", "reisedaten.lebensunterhalt",
    ]),
]


class FormFillerError(Exception):
    """Raised when form filling encounters an error."""
    pass


class VidexFormFiller:
    """
    Automates filling the VIDEX visa application form.
    """

    def __init__(
        self,
        applicant_data: dict[str, Any],
        schema_path: Optional[Path] = None,
        headless: bool = False,
        slow_mo: int = 0,
        screenshot_on_error: bool = True,
        screenshot_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        """
        Initialize the form filler.
        
        Args:
            applicant_data: Flat dictionary of field_id -> value
            schema_path: Path to the schema file for field mappings
            headless: Run browser in headless mode
            slow_mo: Slow down operations by this many milliseconds
            screenshot_on_error: Take screenshot when errors occur
            screenshot_dir: Directory to save screenshots
            output_dir: Directory to save the generated PDF
        """
        self.data = applicant_data
        self.schema_path = schema_path
        self.headless = headless
        self.slow_mo = slow_mo
        self.screenshot_on_error = screenshot_on_error
        self.screenshot_dir = screenshot_dir or Path("./screenshots")
        self.output_dir = output_dir or Path("./output")
        
        self.field_mappings: dict[str, dict] = {}
        self.page: Optional[Page] = None
        self.pdf_path: Optional[Path] = None
        self.validation_error: Optional[str] = None
        # When VIDEX rejects the form we capture every ng-invalid wrapper
        # (label, surrounding text, current value) so the API caller can see
        # what the human user would see as red borders.
        self.invalid_wrappers: list[dict] = []
        self._load_field_mappings()

    @staticmethod
    def _field_in_section(field_id: str, prefixes: list[str]) -> bool:
        """True if field_id belongs to this section (matches any prefix)."""
        for p in prefixes:
            if field_id == p or field_id.startswith(p + ".") or field_id.startswith(p + "["):
                return True
        return False

    # Fields that depend on a parent control being checked first (so their UI
    # is rendered) — process them last within their section.
    _DEFERRED_PREFIXES = (
        "reisedaten.lebensunterhalt.",  # revealed by checking a "third party" payer
    )

    def _get_fields_for_section(self, section_index: int) -> list[str]:
        """Return ordered list of field IDs in self.data that belong to this section.

        Within a section we sort alphabetically for determinism, but defer any
        fields under ``_DEFERRED_PREFIXES`` to the end so their parent toggles
        (e.g. "a third party"/"the inviting person" in section 9) are checked
        first and the dependent sub-section actually renders.
        """
        if section_index < 0 or section_index >= len(FORM_SECTIONS):
            return []
        _, prefixes = FORM_SECTIONS[section_index]
        out = []
        for field_id in self.data:
            if not self._field_in_section(field_id, prefixes):
                continue
            val = self.data.get(field_id)
            if val is None:
                continue
            if val == "" and not isinstance(val, bool):
                continue
            out.append(field_id)
        out.sort()
        primary = [f for f in out if not f.startswith(self._DEFERRED_PREFIXES)]
        deferred = [f for f in out if f.startswith(self._DEFERRED_PREFIXES)]
        return primary + deferred

    def _scroll_field_into_view(self, field_id: str) -> None:
        """Scroll so the element for this field is in view."""
        selector = self._get_selector(field_id)
        try:
            el = self.page.locator(selector).first
            if el.count() > 0:
                el.scroll_into_view_if_needed(timeout=2000)
                self.page.wait_for_timeout(50)
        except Exception:
            pass

    def _load_field_mappings(self) -> None:
        """Load field mappings from schema."""
        if not self.schema_path or not self.schema_path.exists():
            console.print("[yellow]No schema file, will use field IDs as selectors[/yellow]")
            return
        
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Support both "sections" (new) and "form_pages" (old) structure
        pages_list = schema.get("sections", schema.get("form_pages", []))
        
        for page in pages_list:
            for field in page.get("fields", []):
                field_id = field.get("id")
                if field_id:
                    self.field_mappings[field_id] = {
                        "selector": field.get("selector", f'[id="{field_id}"]'),
                        "type": field.get("field_type", "text"),
                        "required": field.get("required", False),
                        "options": field.get("options", []),
                        "page": page.get("page_number", 1)
                    }
        
        console.print(f"[cyan]Loaded {len(self.field_mappings)} field mappings from schema[/cyan]")

    def _take_screenshot(self, name: str) -> Optional[Path]:
        """Take a screenshot for debugging."""
        if not self.page:
            return None
        
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.screenshot_dir / f"{name}_{timestamp}.png"
        
        try:
            # Full page so we can see every section, not just the viewport.
            self.page.screenshot(path=str(filepath), full_page=True)
            console.print(f"[cyan]Screenshot saved: {filepath}[/cyan]")
            return filepath
        except Exception as e:
            console.print(f"[yellow]Could not save screenshot: {e}[/yellow]")
            return None

    def _switch_to_english(self) -> bool:
        """Switch the form language to English. The change triggers a full
        re-render of the Angular form, so we wait for the first applicant
        input *and* a select option to be present afterwards — without that
        wait, the very first fields (familienname, familienstand) sometimes
        race the re-render and silently fail."""
        console.print("[cyan]Switching language to English...[/cyan]")
        try:
            lang_selector = self.page.locator("select").first
            if not lang_selector.is_visible(timeout=2000):
                console.print("[yellow]Language selector not found, page may already be in English[/yellow]")
                return False
            try:
                lang_selector.select_option(label="English")
            except Exception as e:
                console.print(f"[yellow]Could not select English: {e}[/yellow]")
                return False

            console.print("[green]Language switched to English[/green]")
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            # Wait for the first applicant input AND the marital-status dropdown
            # to be fully populated before returning. Without this, fills race
            # the Angular re-render after the language switch.
            try:
                self.page.wait_for_selector(
                    'input[id="antragsteller.familienname"]', state="visible", timeout=15000
                )
                self.page.wait_for_function(
                    """() => {
                        const sel = document.querySelector('select[id="antragsteller.familienstand"]');
                        return sel && sel.options && sel.options.length > 1;
                    }""",
                    timeout=15000,
                )
            except Exception as wait_err:
                console.print(f"[yellow]Post-language-switch wait incomplete: {wait_err}[/yellow]")
            self.page.wait_for_timeout(400)
            return True
        except Exception as e:
            console.print(f"[yellow]Error switching language: {e}[/yellow]")
            return False

    def _get_selector(self, field_id: str) -> str:
        """Get the CSS selector for a field."""
        if field_id in self.field_mappings:
            return self.field_mappings[field_id]["selector"]
        
        # Fallback: use attribute selector (works with IDs containing periods)
        return f'[id="{field_id}"], [name="{field_id}"]'

    def _get_field_type(self, field_id: str) -> str:
        """Get the field type for a field."""
        if field_id in self.field_mappings:
            return self.field_mappings[field_id]["type"]
        return "text"

    def _wait_for_element(self, selector: str, timeout: int = 10000) -> Optional[Locator]:
        """Wait for an element to be visible."""
        try:
            element = self.page.locator(selector).first
            element.wait_for(state="visible", timeout=timeout)
            return element
        except PlaywrightTimeout:
            return None

    def _dump_invalid_inputs(self, label: str = "") -> None:
        """Print every <input>/<select>/<textarea> currently flagged as
        ng-invalid by Angular OR sitting under a mandatory (`*`) label with
        no value. Useful right after VIDEX shows its validation modal."""
        console.print(f"[cyan]Querying invalid inputs ({label})...[/cyan]")
        try:
            invalid = self.page.evaluate(
                """
                () => {
                  const out = [];
                  // 1) Anything Angular itself marked invalid.
                  const ngInvalid = document.querySelectorAll(
                    'input.ng-invalid, select.ng-invalid, textarea.ng-invalid'
                  );
                  // 2) Anything visually "required" (label with leading * or
                  //    aria-required) that is empty.
                  const candidates = new Set(ngInvalid);
                  for (const lbl of document.querySelectorAll('label, .col-form-label, span, div')) {
                    const txt = (lbl.textContent || '').trim();
                    if (!txt.startsWith('*')) continue;
                    // Find the input(s) bound to this label
                    let scope = lbl.closest('.row, .col-md-3, .col-md-4, .col-md-6, .col-md-12, .form-group, .card, .form-check') || lbl.parentElement;
                    if (!scope) continue;
                    for (const el of scope.querySelectorAll('input,select,textarea')) {
                      if (el.type === 'hidden') continue;
                      if (el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio')) {
                        // skip checkbox groups for the empty check
                        continue;
                      }
                      const v = (el.value || '').trim();
                      if (!v) candidates.add(el);
                    }
                  }
                  for (const el of candidates) {
                    let lbl = '';
                    if (el.id) {
                      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                      if (l) lbl = (l.textContent || '').trim();
                    }
                    if (!lbl) {
                      const wrap = el.closest('label, .form-group, .row, .col-md-3, .col-md-4, .col-md-6, .col-md-12');
                      if (wrap) lbl = (wrap.textContent || '').trim().split('\\n')[0].slice(0, 80);
                    }
                    out.push({
                      id: el.id || null,
                      name: el.getAttribute('name'),
                      type: el.tagName + (el.type ? ':' + el.type : ''),
                      value: (el.value || '').slice(0, 40),
                      label: lbl.slice(0, 80),
                    });
                    if (out.length >= 30) break;
                  }
                  return out;
                }
                """
            )
            if invalid:
                console.print(f"[bold yellow]VIDEX flagged these inputs invalid ({len(invalid)}):[/bold yellow]")
                for entry in invalid:
                    console.print(f"  - {entry}")
                self.invalid_inputs = invalid
        except Exception as inv_err:
            console.print(f"[yellow]Could not enumerate invalid inputs: {inv_err}[/yellow]")

    def _extract_validation_modal_text(self) -> Optional[str]:
        """If VIDEX shows the 'An error occurred' modal listing sections with
        invalid mandatory fields, return a short summary string. Otherwise None.
        """
        try:
            dialog = self.page.locator(
                "[role='dialog']:visible, [role='alertdialog']:visible, .modal.show, .modal:visible"
            ).first
            if not dialog.is_visible(timeout=500):
                return None
            text = (dialog.inner_text(timeout=500) or "").strip()
            lowered = text.lower()
            if "error" in lowered and ("mandatory" in lowered or "fields" in lowered):
                # Compress whitespace for a one-line summary
                return " ".join(text.split())
            return None
        except Exception:
            return None

    def _click_checkbox_near_text(self, field_id: str, label_text: str) -> bool:
        """
        Click the <input type='checkbox'> that sits next to ``label_text`` in
        document order. Used as a fallback when VIDEX renders the checkbox
        without an `id` attribute (post-2025 Angular layout).

        Strategy 1: Playwright's get_by_label (handles classic `<label>` shape).
        Strategy 2: JS-side innermost-text-node lookup, then click the FIRST
                    following input[type=checkbox] in document order.
        """
        try:
            cb = self.page.get_by_label(label_text, exact=False).first
            if cb.is_visible(timeout=1500):
                cb.check(timeout=1500)
                console.print(f"[green]Checked (by label) {field_id}: {label_text}[/green]")
                self.page.wait_for_timeout(300)
                return True
        except Exception:
            pass

        try:
            # Run the lookup entirely in the page so we pick the *innermost*
            # element containing the text (xpath's `(//*[contains(...)])[1]`
            # would otherwise return the outermost container — usually <body>).
            handle = self.page.evaluate_handle(
                """
                (text) => {
                  const lower = text.toLowerCase();
                  const all = document.querySelectorAll('app-pass-restricted-checkbox-texts, label, span, p, div');
                  // Pick innermost: smallest element whose own text contains the label.
                  let best = null;
                  for (const el of all) {
                    const t = (el.innerText || el.textContent || '').toLowerCase();
                    if (!t.includes(lower)) continue;
                    // prefer elements with no children that themselves match
                    const childMatch = Array.from(el.children).some(
                      c => ((c.innerText || c.textContent || '').toLowerCase()).includes(lower)
                    );
                    if (childMatch) continue;
                    best = el;
                    break;
                  }
                  if (!best) return null;
                  // Walk forward in document order to the first <input type=checkbox>.
                  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                  walker.currentNode = best;
                  let n = walker.nextNode();
                  while (n) {
                    if (n.tagName === 'INPUT' && n.getAttribute('type') === 'checkbox') {
                      return n;
                    }
                    n = walker.nextNode();
                  }
                  return null;
                }
                """,
                label_text,
            )
            if handle is None:
                console.print(f"[yellow]_click_checkbox_near_text: no element returned for {field_id}[/yellow]")
                return False
            element = handle.as_element()
            if element is None:
                console.print(f"[yellow]_click_checkbox_near_text: handle was not an Element for {field_id}[/yellow]")
                return False
            element.scroll_into_view_if_needed(timeout=1500)
            try:
                element.check(timeout=1500)
            except Exception:
                element.click(timeout=1500)
            console.print(f"[green]Checked (near text) {field_id}: {label_text}[/green]")
            self.page.wait_for_timeout(300)
            return True
        except Exception as e:
            console.print(f"[yellow]_click_checkbox_near_text failed for {field_id}: {e}[/yellow]")
        return False

    def _click_yes_no_near_text(self, question: str, want_yes: bool) -> bool:
        """
        VIDEX 2025 renders some Yes/No questions as a pair of unidentified
        <input type='checkbox'> elements (no id, no formcontrolname, only the
        visible "Yes" / "No" labels). The visual default-checked state is *not*
        registered with the form-control until the user actually clicks one of
        them, so Angular keeps marking the wrapper invalid.
        Examples currently affected:
          - "Are you applying for yourself?"          (Personal details)
          - "Have your fingerprints been collected previously…" (Documents)
        Locate the question text, walk forward in document order, and click
        the first checkbox (Yes) or the second checkbox (No).
        """
        idx = 0 if want_yes else 1
        choice = "Yes" if want_yes else "No"
        try:
            # Anchor via Playwright's locator engine (handles text split across
            # multiple <span>s, which is what VIDEX's Angular template does).
            anchor = self.page.get_by_text(question, exact=False).first
            if anchor.count() == 0 or not anchor.is_visible():
                console.print(f"[yellow]_click_yes_no_near_text: anchor not visible for {question!r}[/yellow]")
                return False
            anchor.scroll_into_view_if_needed(timeout=1500)
            handle = anchor.evaluate_handle(
                """
                (anchor, idx) => {
                  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                  walker.currentNode = anchor;
                  const found = [];
                  let n = walker.nextNode();
                  while (n && found.length < 6) {
                    if (n.tagName === 'INPUT' && n.getAttribute('type') === 'checkbox') {
                      found.push(n);
                    }
                    n = walker.nextNode();
                  }
                  return found[idx] || null;
                }
                """,
                idx,
            )
            element = handle.as_element() if handle else None
            if element is None:
                console.print(f"[yellow]_click_yes_no_near_text: no checkbox after anchor for {question!r}[/yellow]")
                return False
            element.scroll_into_view_if_needed(timeout=1500)
            try:
                element.check(timeout=1500)
            except Exception:
                element.click(timeout=1500)
            console.print(f"[green]Clicked {choice} for: {question[:60]}…[/green]")
            self.page.wait_for_timeout(200)
            return True
        except Exception as e:
            console.print(f"[yellow]_click_yes_no_near_text failed for {question!r}: {e}[/yellow]")
            return False

    def _check_required_yes_no_questions(self) -> None:
        """
        Click any VIDEX 2025 Yes/No question whose default-checked state isn't
        registered as a form-control interaction. Without this Angular keeps
        the wrapper ng-invalid and the Continue → Download PDF popup never
        opens.
        """
        # We always apply on behalf of the maid herself, so the answer is
        # definitively Yes for the "Are you applying for yourself?" question.
        self._click_yes_no_near_text("Are you applying for yourself?", want_yes=True)
        # Fingerprints: respect the boolean we received from the caller.
        ftaken = self.data.get("antragsteller.biometrie.fingerabdrueckeErfassungsDatum_vorhanden")
        # Fallback to the raw input field if the schema-mapped one is missing.
        if ftaken is None:
            ftaken = self.data.get("fingerprints_taken_before")
        want_yes = bool(ftaken)
        self._click_yes_no_near_text(
            "Have your fingerprints been collected previously",
            want_yes=want_yes,
        )

    @staticmethod
    def _normalize_phone(value: str) -> str:
        """VIDEX expects phone without leading + (wrong format). Strip + and trim."""
        if not value or not isinstance(value, str):
            return str(value) if value else ""
        s = value.strip()
        if s.startswith("+"):
            s = s[1:].strip()
        return s

    def _normalize_date_value(self, value: str) -> str:
        """Normalize a date to VIDEX's dd.mm.yyyy. Accepts dotted, dashed and slashed
        day/month/year forms plus ISO yyyy-mm-dd; anything unrecognised passes through."""
        if not value or not isinstance(value, str):
            return str(value) if value else ""
        s = value.strip()
        # Already dd.mm.yyyy
        if len(s) == 10 and s[2] == "." and s[5] == ".":
            return s
        # ISO / year-first: yyyy-mm-dd, yyyy/mm/dd, yyyy.mm.dd
        if len(s) >= 10 and s[4] in "-/." and s[7] in "-/.":
            try:
                y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
                if y > 1900:
                    return f"{d:02d}.{m:02d}.{y:04d}"
            except (ValueError, IndexError):
                pass
        # Day-first with slashes or dashes: dd/mm/yyyy, dd-mm-yyyy, dd.mm.yy(yy)
        parts = re.split(r"[./\-]", s)
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            try:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:  # two-digit year
                    y += 2000
                if 1 <= d <= 31 and 1 <= m <= 12 and y > 1900:
                    return f"{d:02d}.{m:02d}.{y:04d}"
            except (ValueError, IndexError):
                pass
        return s

    def _fill_reference_place_of_birth(self, value: str) -> bool:
        """Try every reasonable way to find and fill the reference/householder Place of birth."""
        value = str(value).strip()
        if not value:
            return False

        def do_fill(inp, method_name: str) -> bool:
            """Fill and optionally retry with click+type if value didn't stick."""
            try:
                inp.scroll_into_view_if_needed(timeout=2000)
                self.page.wait_for_timeout(200)
                inp.fill(value)
                self.page.wait_for_timeout(150)
                current = inp.input_value()
                if current == value or (current and value in current):
                    console.print(f"[green]Filled reference Place of birth ({method_name}): {value}[/green]")
                    return True
                inp.click()
                self.page.wait_for_timeout(150)
                inp.fill("")
                inp.press_sequentially(value, delay=30)
                self.page.wait_for_timeout(150)
                console.print(f"[green]Filled reference Place of birth ({method_name}, type): {value}[/green]")
                return True
            except Exception:
                return False

        # 0) Scroll Householder into view so the field is visible
        try:
            h = self.page.get_by_text("Householder", exact=False).first
            if h.is_visible(timeout=2000):
                h.scroll_into_view_if_needed()
                self.page.wait_for_timeout(300)
        except Exception:
            pass

        # 1) Input with id or name containing referenz + geburtsort
        for sel in [
            'input[id="referenz.ansprechpartner.geburtsort"]',
            'input[name="referenz.ansprechpartner.geburtsort"]',
            'input[id*="referenz"][id*="geburtsort"]',
            'input[name*="referenz"][name*="geburtsort"]',
        ]:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=1500) and do_fill(el, "selector"):
                    return True
            except Exception:
                continue

        # 2) Householder block: scroll into view, then get Place of birth by label or by id containing geburtsort
        try:
            block = self.page.locator("section, fieldset, div[class*='section'], div[class*='referenz'], mat-card").filter(has_text="Householder").first
            if block.is_visible(timeout=2000):
                block.scroll_into_view_if_needed()
                self.page.wait_for_timeout(200)
                el = block.get_by_label("Place of birth", exact=False).first
                if el.is_visible(timeout=1000) and do_fill(el, "householder-label"):
                    return True
                el = block.locator("input[id*='geburtsort']").first
                if el.is_visible(timeout=800) and do_fill(el, "householder-id"):
                    return True
                # Order in form: Family name, First name, Sex, DoB, Place of birth, Nationality... Get 5th text input (index 4) that isn't date
                inputs = block.locator("input[type='text']")
                for i in range(min(inputs.count(), 10)):
                    inp = inputs.nth(i)
                    if not inp.is_visible(timeout=300):
                        continue
                    ph = (inp.get_attribute("placeholder") or "").lower()
                    if "dd.mm" in ph:
                        continue
                    aid = (inp.get_attribute("id") or "").lower()
                    if "geburtsdatum" in aid:
                        continue
                    if "geburtsort" in aid:
                        if do_fill(inp, "householder-geburtsort"):
                            return True
                    if i == 4:
                        if do_fill(inp, "householder-5th-input"):
                            return True
        except Exception:
            pass

        # 3) Place of birth by label (second = reference), then first
        for idx in [1, 0]:
            try:
                ref_place = self.page.get_by_label("Place of birth", exact=False).nth(idx)
                if ref_place.is_visible(timeout=2000) and do_fill(ref_place, f"label-nth{idx}"):
                    return True
            except Exception:
                continue

        # 4) Section "Householder" / "Type of reference" then get_by_label
        for heading in ["Householder", "Type of reference"]:
            try:
                block = self.page.locator("section, fieldset, div[class*='section'], div[class*='referenz'], mat-card").filter(has_text=heading).first
                if block.is_visible(timeout=1500):
                    el = block.get_by_label("Place of birth", exact=False).first
                    if el.is_visible(timeout=1000) and do_fill(el, f"block-{heading}"):
                        return True
            except Exception:
                continue

        # 5) Input in referenz block with id containing geburtsort
        try:
            block = self.page.locator("[class*='referenz']").first
            if block.is_visible(timeout=1500):
                el = block.locator("input[id*='geburtsort']").first
                if el.is_visible(timeout=800) and do_fill(el, "referenz-id"):
                    return True
        except Exception:
            pass

        # 6) Second "Place of birth" label's for= input
        try:
            if self.page.get_by_text("Place of birth", exact=False).count() >= 2:
                lbl = self.page.get_by_text("Place of birth", exact=False).nth(1)
                if lbl.is_visible(timeout=500):
                    input_id = lbl.get_attribute("for")
                    if input_id:
                        inp = self.page.locator(f"[id='{input_id}']").first
                        if inp.is_visible(timeout=500) and do_fill(inp, "2nd-label-for"):
                            return True
        except Exception:
            pass

        # 7) XPath: * containing "Place of birth" then following input (same row/section)
        try:
            inp = self.page.locator("xpath=//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'place of birth')]/following::input[not(contains(@placeholder, 'dd.mm'))][1]").first
            if inp.is_visible(timeout=1500) and do_fill(inp, "xpath-following"):
                return True
        except Exception:
            pass

        return False

    def _fill_text_field(self, field_id: str, value: str) -> bool:
        """Fill a text input field."""
        # Normalize date values for VIDEX (dd.mm.yyyy)
        if (
            "geburtsdatum" in field_id.lower()
            or "datum" in field_id.lower()
            or "gueltigkeit" in field_id.lower()
            or ("fingerabdruecke" in field_id.lower() and "ErfassungsDatum" in field_id and "_vorhanden" not in field_id)
        ):
            value = self._normalize_date_value(str(value))
        # VIDEX phone fields: no leading + (wrong format)
        elif "telefon" in field_id.lower():
            value = self._normalize_phone(str(value))
        selector = self._get_selector(field_id)
        # Family name (section 1): use longer timeout and try alternative selector if needed
        timeout = 8000 if field_id == "antragsteller.familienname" else 10000
        element = self._wait_for_element(selector, timeout=timeout)
        if not element and field_id == "antragsteller.familienname":
            try:
                alt = self.page.locator('input[id*="familienname"]').first
                if alt.count() > 0:
                    alt.scroll_into_view_if_needed(timeout=3000)
                    alt.wait_for(state="visible", timeout=3000)
                    element = alt
            except Exception:
                pass
        if not element:
            # Fallback for date-of-birth: VIDEX may use label or different id
            if "geburtsdatum" in field_id.lower():
                for label in ["Date of birth (dd.mm.yyyy)", "Date of birth", "Geburtsdatum", "dd.mm.yyyy"]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=1000):
                            el.fill(value)
                            console.print(f"[green]Filled date (by label) {field_id}: {value}[/green]")
                            return True
                    except Exception:
                        continue
                # Try input near "Date of birth" text
                try:
                    el = self.page.locator("input[placeholder*='dd.mm'], input[placeholder*='date'], input[id*='geburtsdatum']").first
                    if el.is_visible(timeout=1000):
                        el.fill(value)
                        console.print(f"[green]Filled date (fallback) {field_id}: {value}[/green]")
                        return True
                except Exception:
                    pass
            # Fallback for reference/householder Place of birth (referenz.ansprechpartner.geburtsort)
            if field_id == "referenz.ansprechpartner.geburtsort":
                filled = self._fill_reference_place_of_birth(value)
                if filled:
                    return True
            # Fallback for Personal details: First name(s) and Family name (section 1)
            if field_id == "antragsteller.vorname":
                for label in ["First name(s)", "First name", "Vorname"]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=1000):
                            el.fill(str(value))
                            console.print(f"[green]Filled first name (by label) {field_id}: {value}[/green]")
                            return True
                    except Exception:
                        continue
            if field_id == "antragsteller.familienname":
                for label in ["Family name", "Surname", "Familienname"]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=1000):
                            el.fill(str(value))
                            console.print(f"[green]Filled family name (by label) {field_id}: {value}[/green]")
                            return True
                    except Exception:
                        continue
            # Fallback for Contact Data (applicant address) - fill by label if id selector fails
            contact_labels = {
                "antragsteller.personendaten.staendigeAnschrift.strasse": ["Street", "Straße", "Str."],
                "antragsteller.personendaten.staendigeAnschrift.hausnummer": ["House number", "Hausnummer"],
                "antragsteller.personendaten.staendigeAnschrift.plz": ["Postal code", "PLZ", "Zip"],
                "antragsteller.personendaten.staendigeAnschrift.ort": ["Town", "City", "Ort"],
                "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.telefon": ["Telephone", "Phone", "Telefon"],
                "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.email": ["E-mail", "Email", "E-Mail"],
            }
            if field_id in contact_labels:
                val_str = str(value)
                if "telefon" in field_id:
                    val_str = self._normalize_phone(val_str)
                for label in contact_labels[field_id]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=1000):
                            el.fill(val_str)
                            console.print(f"[green]Filled Contact Data (by label) {field_id}: {value}[/green]")
                            return True
                    except Exception:
                        continue
            # Assumption of costs: "Other (please specify)" text field - often not in schema
            if field_id == "reisedaten.lebensunterhalt.sonstigesAngabe":
                for label in ["Other (please specify)", "If other, please specify", "Sonstige Angabe", "Other"]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=1000):
                            el.fill(str(value))
                            console.print(f"[green]Filled (by label) {field_id}: {value}[/green]")
                            return True
                    except Exception:
                        continue
                if not str(value).strip():
                    return True
                console.print(f"[yellow]Optional field not found: {field_id}, skipping[/yellow]")
                return True
            console.print(f"[yellow]Field not found: {field_id} ({selector})[/yellow]")
            return False
        
        try:
            # Detect element type at runtime
            tag_name = element.evaluate("el => el.tagName.toLowerCase()")
            input_type = element.get_attribute("type") or "text"
            
            if tag_name == "select":
                # This is a select element, use select_option
                return self._fill_select_field(field_id, str(value))
            elif input_type in ["checkbox", "radio"]:
                # Shouldn't be here, but handle gracefully
                return self._fill_checkbox_field(field_id, bool(value))
            
            # Date/read-only: click first so Angular bindings accept the value
            if "geburtsdatum" in field_id.lower() or "datum" in field_id.lower():
                try:
                    element.click()
                    self.page.wait_for_timeout(200)
                except Exception:
                    pass
            element.fill(str(value))
            console.print(f"[green]Filled {field_id}: {value[:30]}{'...' if len(str(value)) > 30 else ''}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error filling {field_id}: {e}[/red]")
            return False

    def _fill_country_select(self, field_id: str, value: str) -> bool:
        """Country dropdowns: find select by id, match option by trimmed label (form often has trailing space)."""
        value_clean = (value or "").strip()
        if not value_clean:
            return True
        value_lower = value_clean.lower()
        # IDs from VIDEX: country of birth, occupation country, applicant address (Contact Data) country
        select_ids = [
            "antragsteller.geburtsland",
            "antragsteller.personendaten.berufdaten.land",
            "antragsteller.personendaten.staendigeAnschrift.land",
        ]
        if field_id not in select_ids:
            return False
        try:
            # Attribute selector works with dots in id
            sel = self.page.locator(f'select[id="{field_id}"]').first
            sel.scroll_into_view_if_needed(timeout=2000)
            self.page.wait_for_timeout(80)
            opts = sel.locator("option").all()
            for opt in opts:
                text = (opt.text_content() or "").strip()
                if not text:
                    continue
                if text.lower() == value_lower or value_lower in text.lower():
                    v = opt.get_attribute("value")
                    if v:
                        sel.select_option(value=v)
                        console.print(f"[green]Selected {field_id}: {text}[/green]")
                        return True
            return False
        except Exception as e:
            console.print(f"[yellow]Country select {field_id}: {e}[/yellow]")
            return False

    def _fill_select_field(self, field_id: str, value: str) -> bool:
        """Fill a select/dropdown field."""
        # Country of birth + occupation country: use robust path first (trimmed option match)
        if field_id in (
            "antragsteller.geburtsland",
            "antragsteller.personendaten.berufdaten.land",
            "antragsteller.personendaten.staendigeAnschrift.land",
        ):
            if self._fill_country_select(field_id, value):
                return True
        selector = self._get_selector(field_id)
        element = self._wait_for_element(selector, timeout=2000)
        
        if not element and field_id == "referenz.referenzArt":
            # Fallback: Type of reference may be in a different DOM (e.g. label "Type of reference")
            try:
                el = self.page.get_by_label("Type of reference", exact=False).first
                if el.is_visible(timeout=2000):
                    value_lower = value.lower().strip()
                    el.select_option(label=value)  # try exact label first
                    console.print(f"[green]Selected (by label) referenz.referenzArt: {value}[/green]")
                    self.page.wait_for_timeout(300)
                    return True
            except Exception:
                try:
                    select_el = self.page.locator("select").filter(has_text="reference").first
                    if select_el.is_visible(timeout=1500):
                        select_el.select_option(label=value)
                        console.print(f"[green]Selected (fallback) referenz.referenzArt: {value}[/green]")
                        self.page.wait_for_timeout(300)
                        return True
                except Exception:
                    pass
        if not element and field_id == "antragsteller.familienstand":
            # Fallback: Marital status by label (section 1)
            try:
                el = self.page.get_by_label("Marital status", exact=False).first
                if el.is_visible(timeout=2000):
                    el.select_option(label=value.strip())
                    console.print(f"[green]Selected (by label) familienstand: {value}[/green]")
                    self.page.wait_for_timeout(150)
                    return True
            except Exception:
                pass

        if not element:
            console.print(f"[yellow]Select field not found: {field_id}[/yellow]")
            return False
        
        try:
            # Get options mapping from schema to find value code
            options_mapping = self.field_mappings.get(field_id, {}).get("options", [])
            value_code = None  # Start with None to detect if we found a match
            matched_label = None
            
            # Try to find the value code from our mappings
            value_lower = value.lower().strip()
            for opt in options_mapping:
                opt_label = opt.get("label", "") if isinstance(opt, dict) else str(opt)
                opt_value = opt.get("value", opt_label) if isinstance(opt, dict) else str(opt)
                
                # Exact match on label (highest priority)
                if opt_label.lower().strip() == value_lower:
                    value_code = opt_value
                    matched_label = opt_label
                    break
                # Partial match: input contains label or label contains input
                if value_code is None and (value_lower in opt_label.lower() or opt_label.lower() in value_lower):
                    value_code = opt_value
                    matched_label = opt_label
            
            # If no match found in schema, fallback to raw value
            if value_code is None:
                console.print(f"[yellow]Warning: No exact match in schema for {field_id}='{value}', trying raw value[/yellow]")
                value_code = value
            
            # Try to select using label first (Angular uses dynamic indices for values)
            # Then fall back to value code, then partial text match
            selected = False
            try:
                # Try label first - this is most reliable for Angular apps
                element.select_option(label=matched_label or value)
                selected = True
            except Exception as e1:
                try:
                    # Try by value code from schema
                    element.select_option(value=value_code)
                    selected = True
                except Exception as e2:
                    # Last resort: iterate through options on page and match by text
                    page_options = element.locator("option").all()
                    for opt in page_options:
                        opt_text = (opt.text_content() or "").strip()
                        opt_text_lower = opt_text.lower()
                        # Exact match first
                        if opt_text_lower == value_lower:
                            opt_val = opt.get_attribute("value")
                            if opt_val:
                                element.select_option(value=opt_val)
                                value_code = opt_val
                                matched_label = opt_text
                                selected = True
                                break
                    
                    # If no exact match, try partial match
                    if not selected:
                        for opt in page_options:
                            opt_text = (opt.text_content() or "").strip()
                            opt_text_lower = opt_text.lower()
                            if value_lower in opt_text_lower or opt_text_lower in value_lower:
                                opt_val = opt.get_attribute("value")
                                if opt_val:
                                    element.select_option(value=opt_val)
                                    value_code = opt_val
                                    matched_label = opt_text
                                    selected = True
                                    break
                    
                    if not selected:
                        available = [(o.get_attribute('value'), (o.text_content() or '')[:30]) for o in page_options[:5]]
                        console.print(f"[yellow]Debug {field_id}: No match for '{value}'[/yellow]")
                        console.print(f"[yellow]       Available: {available}[/yellow]")
            
            if selected:
                display_label = matched_label or value
                console.print(f"[green]Selected {field_id}: {display_label} (code: {value_code})[/green]")
                # Wait briefly after select in case it triggers UI changes
                self.page.wait_for_timeout(80)
                return True
            else:
                console.print(f"[red]Failed to select {field_id}: No matching option for '{value}'[/red]")
                return False
        except Exception as e:
            if "closed" in str(e).lower():
                console.print(f"[red]Browser closed during select {field_id} - page may have navigated[/red]")
            else:
                console.print(f"[red]Error selecting {field_id}: {e}[/red]")
            return False

    def _fill_radio_field(self, field_id: str, value: str) -> bool:
        """Fill a radio button field."""
        # Radio buttons often have the same name but different values
        selector = f"input[name='{field_id}'][value='{value}'], #{field_id}[value='{value}']"
        element = self._wait_for_element(selector)
        
        if not element:
            # Try alternative selector
            selector = self._get_selector(field_id)
            element = self._wait_for_element(selector)
        
        if not element:
            console.print(f"[yellow]Radio field not found: {field_id}[/yellow]")
            return False
        
        try:
            element.check()
            console.print(f"[green]Checked radio {field_id}: {value}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error checking radio {field_id}: {e}[/red]")
            return False

    def _fill_checkbox_field(self, field_id: str, value: bool) -> bool:
        """Fill a checkbox field. Fallback: try by label for VIDEX checkboxes that
        no longer have stable IDs (the German portal moved many controls into
        Angular components without `id` attributes around 2025)."""
        selector = self._get_selector(field_id)
        element = self._wait_for_element(selector, timeout=3000)

        # Label-based fallbacks for known label-only checkboxes. Updated to cover
        # the residence-permit checkbox (now an unlabeled <input type="checkbox">
        # rendered next to "Is your residence in a country other than that of
        # your current nationality?") and the assumption-of-costs checkbox.
        LABEL_FALLBACKS = {
            "reisedaten.reisekostenUebernahme.antragsteller": "the applicant him/herself",
            "reisedaten.reisekostenUebernahme.dritte": "a third party",
            "reisedaten.reisekostenUebernahme.einlader": "the inviting person",
            "reisedaten.lebensunterhalt.bar": "Cash",
            "reisedaten.lebensunterhalt.reiseschecks": "Traveller's cheques",
            "reisedaten.lebensunterhalt.kreditkarten": "Credit cards",
            "reisedaten.lebensunterhalt.unterkunft": "Accommodation provided",
            "reisedaten.lebensunterhalt.vollstaendigeKostenuebernahme": "All expenses covered during the stay",
            "reisedaten.lebensunterhalt.befoerderung": "Pre-paid transport",
            # VIDEX 2025 layout: this Yes/No question lives in the Contact data
            # section. The Yes radio/checkbox has no id; we have to find it via
            # the question text and then click the first Yes input below it.
            "antragsteller.aufenthaltsberechtigung": (
                "Is your residence in a country other than that of your current nationality?"
            ),
        }

        if not element:
            if value and field_id in LABEL_FALLBACKS:
                label = LABEL_FALLBACKS[field_id]
                if self._click_checkbox_near_text(field_id, label):
                    return True
            if not value:
                return True
            console.print(f"[yellow]Checkbox not found: {field_id}[/yellow]")
            return False
        
        try:
            if value:
                element.check()
                console.print(f"[green]Checked checkbox {field_id}[/green]")
                if "aufenthaltsberechtigung" in field_id and "artDerRueckkehrberechtigung" not in field_id:
                    self.page.wait_for_timeout(250)
            else:
                if element.is_checked():
                    element.uncheck()
                    console.print(f"[cyan]Unchecked checkbox {field_id}[/cyan]")
            self.page.wait_for_timeout(100)
            return True
        except Exception as e:
            console.print(f"[red]Error with checkbox {field_id}: {e}[/red]")
            return False

    def _fill_date_field(self, field_id: str, value: str) -> bool:
        """Fill a date field (dd.mm.yyyy for VIDEX)."""
        value = self._normalize_date_value(str(value))
        # Reuse text field logic including fallbacks for geburtsdatum
        return self._fill_text_field(field_id, value)

    def _fill_field(self, field_id: str, value: Any) -> bool:
        """Fill a single field based on its type."""
        field_type = self._get_field_type(field_id)
        
        # Handle checkboxes specially - False means uncheck, True means check
        # Also treat boolean values as checkboxes even if field_type is unknown
        if field_type == "checkbox" or isinstance(value, bool):
            return self._fill_checkbox_field(field_id, bool(value))
        
        # Skip empty values for non-checkbox fields
        if value is None or value == "":
            return True
        
        if field_type == "select":
            return self._fill_select_field(field_id, str(value))
        elif field_type == "radio":
            return self._fill_radio_field(field_id, str(value))
        elif field_type == "date":
            return self._fill_date_field(field_id, str(value))
        else:
            return self._fill_text_field(field_id, str(value))

    def _handle_popup_dialog(self) -> bool:
        """
        Handle any popup dialogs/warnings that appear on the page.
        Returns True if a dialog was handled.
        Only targets actual modal/popup containers, not main form buttons.
        """
        # Look for specific modal content - not just containers
        # The cdk-overlay-container is always present in Angular but empty when no popup
        try:
            # Check for visible dialog with actual content
            dialog = self.page.locator("[role='dialog']:visible, [role='alertdialog']:visible, .modal.show, .modal:visible").first
            if not dialog.is_visible(timeout=300):
                return False
        except Exception:
            return False
        
        # Found a visible dialog - try to close it
        popup_close_selectors = [
            "[role='dialog'] button:has-text('OK')",
            "[role='dialog'] button:has-text('Schließen')",
            "[role='dialog'] button:has-text('Close')",
            "[role='alertdialog'] button:has-text('OK')",
            ".modal button:has-text('OK')",
            ".modal button:has-text('Close')",
            ".modal button.close",
            "button[aria-label='Close']",
        ]
        
        for selector in popup_close_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=500):
                    console.print(f"[yellow]Closing popup/dialog: {selector}[/yellow]")
                    button.click()
                    self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        
        # Handle cookie consent banners
        cookie_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Accept all')",
            "[class*='cookie'] button",
            "#cookie-accept",
        ]
        
        for selector in cookie_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=500):
                    console.print(f"[yellow]Accepting cookies: {selector}[/yellow]")
                    button.click()
                    self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        
        return False

    def _setup_dialog_handler(self) -> None:
        """Set up handler for JavaScript alert/confirm/prompt dialogs."""
        def handle_dialog(dialog):
            console.print(f"[yellow]Dialog appeared: {dialog.type} - {dialog.message}[/yellow]")
            dialog.accept()
        
        self.page.on("dialog", handle_dialog)

    def _navigate_to_next_page(self) -> bool:
        """Try to navigate to the next form page."""
        # First, try to handle any open popups
        self._handle_popup_dialog()
        
        next_button_selectors = [
            "button:has-text('Continue')",
            "button:has-text('Weiter')",
            "button:has-text('Further')",
            "button:has-text('Next')",
            "button:has-text('Fortfahren')",
            "button[type='submit']:not(:has-text('Submit')):not(:has-text('Absenden'))",
            "input[type='submit'][value*='Continue']",
            "input[type='submit'][value*='Weiter']",
            "input[type='submit'][value*='Next']",
            ".next-button",
            "[class*='next']",
            "[class*='weiter']",
        ]
        
        for selector in next_button_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible() and button.is_enabled():
                    button.click()
                    self.page.wait_for_timeout(1000)
                    
                    # Check for and handle any validation popups after clicking
                    self._handle_popup_dialog()
                    
                    self.page.wait_for_load_state("networkidle", timeout=15000)
                    return True
            except Exception:
                continue
        
        return False

    def _get_current_page_fields(self) -> list[str]:
        """Get field IDs that should be on the current page."""
        visible_fields = []
        # Use longer timeout for reference/cost sections (they may be below fold or in same long page)
        long_timeout = 2000
        
        for field_id in self.data.keys():
            selector = self._get_selector(field_id)
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=long_timeout if "referenz" in field_id or "reisedaten.reisekosten" in field_id or "reisedaten.lebensunterhalt" in field_id else 500):
                    visible_fields.append(field_id)
                    continue
            except Exception:
                pass
            # Date-of-birth: include if we have value and a date input is visible by label (VIDEX may not use id)
            if "geburtsdatum" in field_id.lower() and self.data.get(field_id):
                for label in ["Date of birth (dd.mm.yyyy)", "Date of birth", "Geburtsdatum"]:
                    try:
                        el = self.page.get_by_label(label, exact=False).first
                        if el.is_visible(timeout=300):
                            visible_fields.append(field_id)
                            break
                    except Exception:
                        continue
            # Reference/Householder Place of birth: include whenever we have value and reference section is on page
            if field_id == "referenz.ansprechpartner.geburtsort" and self.data.get(field_id):
                try:
                    ref_place = self.page.get_by_label("Place of birth", exact=False).nth(1)
                    if ref_place.is_visible(timeout=long_timeout):
                        visible_fields.append(field_id)
                except Exception:
                    pass
                if field_id not in visible_fields:
                    try:
                        ref_place = self.page.get_by_label("Place of birth", exact=False).nth(0)
                        if ref_place.is_visible(timeout=long_timeout) and self.page.get_by_text("Householder", exact=False).or_(self.page.get_by_text("Type of reference", exact=False)).first.is_visible(timeout=500):
                            visible_fields.append(field_id)
                    except Exception:
                        pass
                if field_id not in visible_fields:
                    try:
                        block = self.page.locator("section, fieldset, [class*='referenz']").filter(has_text="Householder").first
                        if block.is_visible(timeout=1000):
                            visible_fields.append(field_id)
                    except Exception:
                        pass
        
        return visible_fields

    def fill_form(self, submit: bool = False, save_pdf: bool = True) -> dict[str, Any]:
        """
        Fill the entire form with the applicant data.
        
        Args:
            submit: Whether to submit the form at the end
            save_pdf: Whether to save the form as PDF after filling
        
        Returns:
            Dictionary with 'fields' (field results) and 'pdf_path' (saved PDF path)
        """
        results = {}
        
        # Clear screenshots from previous run so they don't pile up (each run = fresh set)
        if self.screenshot_dir and self.screenshot_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.screenshot_dir)
            except Exception:
                pass
        if self.screenshot_dir:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        console.print("[bold blue]Starting VIDEX form automation...[/bold blue]")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                downloads_path=str(self.output_dir)
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                accept_downloads=True
            )
            self.page = context.new_page()

            self._setup_dialog_handler()
            
            try:
                # Navigate to the form
                console.print(f"[cyan]Navigating to {VIDEX_URL}[/cyan]")
                # Use domcontentloaded: VIDEX is an Angular SPA and may never fire "load"
                self.page.goto(VIDEX_URL, timeout=90000, wait_until="domcontentloaded")
                
                # Wait for page content to actually load (Angular app needs time)
                console.print(f"[cyan]Waiting for form to load...[/cyan]")
                try:
                    # Wait for a specific form element to appear
                    self.page.wait_for_selector("input[id='antragsteller.familienname']", timeout=20000)
                    console.print(f"[green]Form loaded successfully[/green]")
                except Exception:
                    console.print(f"[yellow]Form elements not found, waiting longer...[/yellow]")
                    self.page.wait_for_timeout(2000)
                
                # Debug: Check what we have on the page
                input_count = self.page.locator("input").count()
                select_count = self.page.locator("select").count()
                console.print(f"[cyan]Found {input_count} inputs and {select_count} selects on page[/cyan]")
                
                # If no inputs found, try waiting more
                if input_count == 0:
                    console.print(f"[yellow]No form elements detected, waiting for Angular to load...[/yellow]")
                    self.page.wait_for_timeout(2000)
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    input_count = self.page.locator("input").count()
                    select_count = self.page.locator("select").count()
                    console.print(f"[cyan]After wait: Found {input_count} inputs and {select_count} selects[/cyan]")
                
                # Handle any initial popups (cookies, warnings, etc.)
                self._handle_popup_dialog()
                
                # Switch to English
                self._switch_to_english()
                
                self.page.wait_for_timeout(300)
                
                # Take initial screenshot
                self._take_screenshot("initial_page")
                
                filled_fields: set[str] = set()
                total_to_fill = len([k for k, v in self.data.items() if v is not None and (v != "" or isinstance(v, bool))])
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("{task.completed}/{task.total}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Filling form by section...", total=total_to_fill)
                    
                    # Fill one section at a time in fixed order (no random order, no missing sections)
                    for section_index, (section_name, _prefixes) in enumerate(FORM_SECTIONS):
                        fields_in_section = self._get_fields_for_section(section_index)
                        new_in_section = [f for f in fields_in_section if f not in filled_fields]
                        if not new_in_section:
                            continue
                        
                        progress.update(task, description=f"Section: {section_name}")
                        console.print(f"[bold cyan]--- {section_name} ---[/bold cyan]")
                        
                        # Section 1 (Personal details): scroll to top so first fields are in view
                        if section_index == 0:
                            try:
                                self.page.evaluate("window.scrollTo(0, 0)")
                                self.page.wait_for_timeout(200)
                            except Exception:
                                pass
                        # Scroll so this section is in view (Contact Data and below are often below the fold)
                        elif section_index >= 2:
                            try:
                                self.page.evaluate("window.scrollBy(0, 400)")
                                self.page.wait_for_timeout(100)
                            except Exception:
                                pass
                        
                        # Contact Data (section 3): scroll first field into view so whole block is visible
                        if section_index == 3:
                            self.page.wait_for_timeout(150)
                            try:
                                first_contact = self.page.locator('[id="antragsteller.personendaten.staendigeAnschrift.strasse"]').first
                                if first_contact.count() > 0:
                                    first_contact.scroll_into_view_if_needed(timeout=3000)
                                    self.page.wait_for_timeout(200)
                            except Exception:
                                pass
                        for field_id in new_in_section:
                            value = self.data.get(field_id)
                            # Include checkboxes (True/False)
                            if value is None or (value == "" and not isinstance(value, bool)):
                                continue
                            try:
                                self._scroll_field_into_view(field_id)
                                success = self._fill_field(field_id, value)
                                results[field_id] = success
                            except Exception as fill_err:
                                console.print(f"[red]Exception filling {field_id}: {fill_err}[/red]")
                                results[field_id] = False
                            filled_fields.add(field_id)
                            progress.advance(task)
                        
                        if section_index == 3:
                            self.page.wait_for_timeout(250)
                        self.page.wait_for_timeout(80)
                    
                    if len(filled_fields) >= total_to_fill:
                        console.print("[green]All fields filled![/green]")
                    
                    # VIDEX 2025: a couple of Yes/No questions render as
                    # un-id'd checkbox pairs whose visual default isn't bound
                    # to the Angular form-control. Without this the wrapper
                    # stays ng-invalid and the Continue→Download popup never
                    # appears (manifests as the generic "PDF generation failed"
                    # error the user reported after the ZERP-55 redeploy).
                    self._check_required_yes_no_questions()

                    self._take_screenshot("all_sections_filled")
                
                # Handle submission
                if submit:
                    self._submit_form()
                else:
                    console.print("[yellow]Form filled but NOT submitted (--submit flag not set)[/yellow]")
                    self._take_screenshot("final_not_submitted")
                
                # Check if all fields were filled successfully before proceeding to PDF
                success_count = sum(1 for v in results.values() if v)
                total_fields = len(self.data)
                
                if success_count < total_fields:
                    console.print(f"[yellow]Warning: Only {success_count}/{total_fields} fields filled[/yellow]")
                    failed_fields = [k for k, v in results.items() if not v]
                    if failed_fields:
                        console.print(f"[yellow]Failed fields: {failed_fields[:10]}{'...' if len(failed_fields) > 10 else ''}[/yellow]")

                # The post-Continue diagnostic in _save_pdf does the real work
                # because Angular only marks fields as touched/invalid after
                # validation runs.
                
                # Save PDF only after all fields are filled
                saved_path = None
                if save_pdf:
                    console.print(f"\n[bold cyan]All {success_count} fields filled. Saving form as PDF...[/bold cyan]")
                    saved_path = self._save_pdf()
                
                # Summary
                fail_count = len(results) - success_count
                
                console.print(f"\n[bold]Form Filling Summary:[/bold]")
                console.print(f"  [green]Successful: {success_count}[/green]")
                console.print(f"  [red]Failed: {fail_count}[/red]")
                if saved_path:
                    console.print(f"  [cyan]PDF saved: {saved_path}[/cyan]")
                
            except Exception as e:
                console.print(f"[bold red]Error during form filling: {e}[/bold red]")
                if self.screenshot_on_error:
                    self._take_screenshot("error")
                raise FormFillerError(str(e))
            finally:
                # Keep browser open briefly for debugging if not headless
                if not self.headless:
                    console.print("[cyan]Browser will close in 5 seconds...[/cyan]")
                    self.page.wait_for_timeout(5000)
                browser.close()
        
        return {
            "fields": results,
            "pdf_path": self.pdf_path,
            "success_count": sum(1 for v in results.values() if v),
            "fail_count": len(results) - sum(1 for v in results.values() if v),
            "validation_error": getattr(self, "validation_error", None),
            "invalid_wrappers": getattr(self, "invalid_wrappers", []),
        }

    def _submit_form(self) -> None:
        """Submit the form."""
        submit_selectors = [
            "button[type='submit']:has-text('Submit')",
            "button[type='submit']:has-text('Absenden')",
            "button:has-text('Submit')",
            "button:has-text('Absenden')",
            "input[type='submit']",
        ]
        
        for selector in submit_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible() and button.is_enabled():
                    console.print("[bold yellow]Submitting form...[/bold yellow]")
                    button.click()
                    self.page.wait_for_load_state("networkidle", timeout=30000)
                    self._take_screenshot("submitted")
                    console.print("[bold green]Form submitted![/bold green]")
                    return
            except Exception:
                continue
        
        console.print("[red]Could not find submit button[/red]")

    def _navigate_to_print_page(self) -> bool:
        """
        Navigate through the form to reach the final print/summary page.
        Keeps pressing "Further" / "Weiter" until we find the print button or can't continue.
        """
        console.print("[cyan]Navigating to print page by clicking 'Continue'...[/cyan]")
        
        max_attempts = 15
        for attempt in range(max_attempts):
            # Take screenshot at each step for debugging
            self._take_screenshot(f"navigate_step_{attempt}")
            
            # Check if we're on the print page
            print_button_selectors = [
                "button:has-text('Drucken')",
                "button:has-text('Print')",
                "button:has-text('Print application')",
                "button:has-text('Antrag drucken')",
                "button:has-text('PDF')",
                "a:has-text('Drucken')",
                "a:has-text('Print')",
                "a:has-text('PDF')",
                "a:has-text('Print application')",
                "[class*='print']",
            ]
            
            for selector in print_button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.is_visible(timeout=1000):
                        console.print(f"[green]Found print page with button: {selector}[/green]")
                        return True
                except Exception:
                    continue
            
            # Check for summary/review page indicators
            summary_indicators = [
                "text=Summary",
                "text=Zusammenfassung",
                "text=Review",
                "text=Überprüfen",
                "text=Application Preview",
                "text=Antragsvorschau",
            ]
            
            for indicator in summary_indicators:
                try:
                    if self.page.locator(indicator).first.is_visible(timeout=500):
                        console.print(f"[green]Found summary/review page: {indicator}[/green]")
                        return True
                except Exception:
                    continue
            
            # Handle any popups/dialogs before clicking
            self._handle_popup_dialog()
            
            # Try to click "Continue" / "Weiter" button
            further_clicked = False
            further_selectors = [
                "button:has-text('Continue')",
                "button:has-text('Weiter')",
                "button:has-text('Further')",
                "button:has-text('Next')",
                "a:has-text('Continue')",
                "a:has-text('Weiter')",
                "input[value*='Continue']",
                "input[value*='Weiter']",
            ]
            
            for selector in further_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.is_visible(timeout=1000) and button.is_enabled():
                        console.print(f"[cyan]Clicking '{selector}' (attempt {attempt + 1})...[/cyan]")
                        button.click()
                        self.page.wait_for_timeout(2000)
                        
                        # Handle any validation popups
                        self._handle_popup_dialog()
                        
                        try:
                            self.page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        
                        further_clicked = True
                        break
                except Exception as e:
                    console.print(f"[dim]Selector {selector} not found: {e}[/dim]")
                    continue
            
            if not further_clicked:
                console.print("[yellow]Could not find 'Further' button, checking for print options...[/yellow]")
                break
        
        return False

    def _save_pdf(self) -> Optional[Path]:
        """
        Save the generated PDF from VIDEX.
        Clicks Continue -> waits for popup -> clicks Download PDF button.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Get applicant name for filename if available
        name = self.data.get("antragsteller.familienname", "applicant")
        if not name:
            name = "applicant"
        name = "".join(c if c.isalnum() else "_" for c in str(name))
        
        pdf_filename = f"videx_application_{name}_{timestamp}.pdf"
        pdf_path = self.output_dir / pdf_filename
        
        # Step 1: Click the Continue button to trigger the popup
        console.print("[cyan]Clicking Continue button to open PDF popup...[/cyan]")
        
        continue_selectors = [
            "button:has-text('Continue')",
            "button:has-text('Weiter')",
            "button:has-text('Further')",
        ]
        
        continue_clicked = False
        for selector in continue_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=2000) and button.is_enabled():
                    console.print(f"[green]Found Continue button: {selector}[/green]")
                    button.click()
                    continue_clicked = True
                    break
            except Exception:
                continue
        
        if not continue_clicked:
            console.print("[yellow]Could not find Continue button[/yellow]")
        
        # Wait for popup to appear
        self.page.wait_for_timeout(2000)
        self._take_screenshot("after_continue_click")

        # If VIDEX validation rejected the form, surface the failed sections
        # instead of returning the generic "Download PDF button not found".
        validation_text = self._extract_validation_modal_text()
        if validation_text:
            console.print(f"[bold red]VIDEX validation error: {validation_text}[/bold red]")
            self.validation_error = validation_text
            # Capture invalid inputs both with the modal still up and after it
            # closes — Angular sometimes resets touched/invalid state on close.
            self._dump_invalid_inputs(label="while-modal-open")
            try:
                self.page.locator("[role='dialog']:visible button:has-text('OK')").first.click(timeout=1500)
                self.page.wait_for_timeout(800)
            except Exception:
                pass
            # After dismissing the modal, VIDEX repaints red borders on the
            # offending controls. Capture a full-page screenshot so the operator
            # can see exactly which fields are flagged.
            self._take_screenshot("after_modal_dismissed_red_borders")
            self._dump_invalid_inputs(label="after-modal-closed")
            try:
                wrappers = self.page.evaluate(
                    """
                    () => {
                      const out = [];
                      const els = document.querySelectorAll('.ng-invalid');
                      for (const el of els) {
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'form' || tag === 'ng-form') continue;
                        const lbl = el.querySelector('label, .col-form-label');
                        const inner = el.querySelector('input,select,textarea');
                        // Walk up to find the nearest section card / panel and
                        // grab whatever text precedes this element so we know
                        // which question it belongs to.
                        let card = el.closest('app-collapse-card, .card, .panel, fieldset, section');
                        let cardTitle = null;
                        if (card) {
                          const t = card.querySelector('.card-header, .panel-heading, h2, h3, legend');
                          cardTitle = t ? (t.innerText || '').trim().slice(0, 80) : null;
                        }
                        // Surrounding text: walk back through preceding siblings/cousins
                        let preceding = '';
                        let scope = el.parentElement;
                        while (scope && preceding.length < 200) {
                          const text = (scope.innerText || '').trim();
                          if (text) { preceding = text.slice(0, 200); break; }
                          scope = scope.parentElement;
                        }
                        out.push({
                          tag,
                          card: cardTitle,
                          label: lbl ? (lbl.innerText || '').trim().slice(0, 80) : null,
                          inner_id: inner ? inner.id : null,
                          inner_tag: inner ? inner.tagName.toLowerCase() : null,
                          inner_value: inner ? (inner.value || '').slice(0, 40) : null,
                          inner_type: inner ? inner.type : null,
                          context: preceding.replace(/\\s+/g, ' ').slice(0, 160),
                        });
                      }
                      return out.slice(0, 25);
                    }
                    """
                )
                console.print(f"[bold yellow]ng-invalid wrappers ({len(wrappers)}):[/bold yellow]")
                for w in wrappers:
                    console.print(f"  • card={w['card']!r}")
                    console.print(f"    label={w['label']!r} inner=<{w['inner_tag']} id={w['inner_id']!r} type={w['inner_type']!r} value={w['inner_value']!r}>")
                    console.print(f"    context={w['context']!r}")
                # Persist for the caller (api.py) so the HTTP response can
                # include the diagnostic without forcing the operator to dig
                # into Railway logs.
                self.invalid_wrappers = wrappers
            except Exception as e:
                console.print(f"[red]wrapper dump failed: {e}[/red]")
                self.invalid_wrappers = []
            return None

        # Step 2: Find and click "Download PDF" button in the popup
        console.print("[cyan]Looking for Download PDF button in popup...[/cyan]")
        self.page.wait_for_timeout(1000)
        
        # The Download PDF button is in the modal - look for it specifically
        pdf_button = self.page.locator("a:has-text('Download PDF'), button:has-text('Download PDF')").first
        
        if not pdf_button.is_visible(timeout=5000):
            console.print("[yellow]Download PDF button not found in popup[/yellow]")
            return None
        
        console.print("[green]Found 'Download PDF' button in popup[/green]")
        
        # Method 1: Try to capture download event
        try:
            with self.page.expect_download(timeout=10000) as download_info:
                pdf_button.click()
            
            download = download_info.value
            console.print(f"[cyan]Download started: {download.suggested_filename}[/cyan]")
            download.save_as(str(pdf_path))
            console.print(f"[bold green]PDF saved: {pdf_path}[/bold green]")
            self.pdf_path = pdf_path
            return pdf_path
            
        except Exception as e:
            console.print(f"[yellow]Download event not captured: {e}[/yellow]")
        
        # Method 2: The link might open PDF in a new tab/window
        console.print("[cyan]Checking for new window with PDF...[/cyan]")
        
        # Click and wait for new page
        with self.page.context.expect_page(timeout=10000) as new_page_info:
            pdf_button.click()
        
        try:
            new_page = new_page_info.value
            new_page.wait_for_load_state("load", timeout=15000)
            console.print(f"[cyan]New page opened: {new_page.url}[/cyan]")
            
            # Check if the new page is a PDF blob or URL
            if 'blob:' in new_page.url or '.pdf' in new_page.url.lower():
                # Try to get the PDF content from the new page
                console.print("[cyan]Saving PDF from new window...[/cyan]")
                
                # Use JavaScript to get the PDF blob data
                try:
                    # For blob URLs, fetch the blob and save it
                    pdf_content = new_page.evaluate("""
                        async () => {
                            const response = await fetch(window.location.href);
                            const blob = await response.blob();
                            const buffer = await blob.arrayBuffer();
                            return Array.from(new Uint8Array(buffer));
                        }
                    """)
                    
                    # Write the PDF content to file
                    with open(str(pdf_path), 'wb') as f:
                        f.write(bytes(pdf_content))
                    
                    console.print(f"[bold green]PDF saved: {pdf_path}[/bold green]")
                    self.pdf_path = pdf_path
                    new_page.close()
                    return pdf_path
                    
                except Exception as fetch_err:
                    console.print(f"[yellow]Could not fetch PDF blob: {fetch_err}[/yellow]")
            
            new_page.close()
            
        except Exception as page_err:
            console.print(f"[yellow]No new page opened: {page_err}[/yellow]")
        
        # Method 3: Check Downloads folder
        console.print("[cyan]Checking Downloads folder...[/cyan]")
        import os
        import time
        import shutil
        
        downloads_dir = os.path.expanduser("~/Downloads")
        self.page.wait_for_timeout(3000)
        
        for attempt in range(5):
            try:
                recent_pdfs = sorted(
                    [f for f in os.listdir(downloads_dir) if f.lower().endswith('.pdf')],
                    key=lambda x: os.path.getmtime(os.path.join(downloads_dir, x)),
                    reverse=True
                )
                
                if recent_pdfs:
                    latest_pdf = os.path.join(downloads_dir, recent_pdfs[0])
                    if time.time() - os.path.getmtime(latest_pdf) < 30:
                        shutil.copy(latest_pdf, str(pdf_path))
                        console.print(f"[bold green]PDF copied from Downloads: {pdf_path}[/bold green]")
                        self.pdf_path = pdf_path
                        return pdf_path
            except Exception:
                pass
            
            self.page.wait_for_timeout(1000)
        
        # If we got here, the download wasn't captured
        console.print("[red]Could not download the PDF from VIDEX[/red]")
        console.print("[yellow]Please check the Downloads folder manually[/yellow]")
        
        return None

    def _print_form(self) -> None:
        """Trigger the browser print dialog (for manual printing)."""
        try:
            console.print("[cyan]Opening print dialog...[/cyan]")
            self.page.keyboard.press("Control+P")
            self.page.wait_for_timeout(2000)
        except Exception as e:
            console.print(f"[yellow]Could not open print dialog: {e}[/yellow]")


def fill_videx_form(
    data_path: Path,
    schema_path: Optional[Path] = None,
    defaults_path: Optional[Path] = None,
    headless: bool = False,
    submit: bool = False,
    save_pdf: bool = True,
    output_dir: Optional[Path] = None
) -> dict[str, Any]:
    """
    Convenience function to fill the VIDEX form.
    
    Args:
        data_path: Path to applicant data JSON (can use English field names)
        schema_path: Path to schema JSON (for field mappings)
        defaults_path: Path to defaults JSON (applied before user data)
        headless: Run in headless mode
        submit: Actually submit the form
        save_pdf: Save the form as PDF
        output_dir: Directory to save the PDF
    
    Returns:
        Dictionary with field results and PDF path
    """
    from .data_loader import ApplicantDataLoader
    
    loader = ApplicantDataLoader(
        data_path,
        schema_path,
        defaults_path=defaults_path,
        use_english=True
    )
    loader.load()
    
    # Validate data
    is_valid, missing = loader.validate()
    if not is_valid:
        console.print(f"[yellow]Warning: Missing required fields: {missing}[/yellow]")
    
    filler = VidexFormFiller(
        applicant_data=loader.get_all_values(),
        schema_path=schema_path,
        headless=headless,
        output_dir=output_dir or data_path.parent
    )
    
    return filler.fill_form(submit=submit, save_pdf=save_pdf)


if __name__ == "__main__":
    # Test
    base_path = Path(__file__).parent.parent.parent
    data_path = base_path / "output" / "applicant_template.json"
    schema_path = base_path / "output" / "fields_schema.json"
    
    if data_path.exists():
        results = fill_videx_form(data_path, schema_path, headless=False, submit=False)
    else:
        console.print("[red]No applicant data file found. Create one first.[/red]")

