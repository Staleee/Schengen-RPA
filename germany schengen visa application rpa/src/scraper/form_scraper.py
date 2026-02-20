"""
VIDEX Form Scraper - Extracts all form fields from the VIDEX visa application.

The VIDEX form has 6 main sections/tabs:
1. Angaben zur Person (Personal Data)
2. Kontaktdaten (Contact Details)
3. Unterlagen (Documents)
4. Reisedaten (Travel Data)
5. Referenz (Reference)
6. Kostenübernahme (Cost Coverage)
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from playwright.sync_api import sync_playwright, Page
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

VIDEX_URL = "https://videx.diplo.de/videx/visum-erfassung/videx-kurzfristiger-aufenthalt"

# Tab names in German (for clicking) and English (for display)
FORM_TABS = [
    {"de": "Angaben zur Person", "en": "Personal Data", "index": 0},
    {"de": "Kontaktdaten", "en": "Contact Details", "index": 1},
    {"de": "Unterlagen", "en": "Documents", "index": 2},
    {"de": "Reisedaten", "en": "Travel Data", "index": 3},
    {"de": "Referenz", "en": "Reference", "index": 4},
    {"de": "Kostenübernahme", "en": "Cost Coverage", "index": 5},
]


@dataclass
class FormField:
    """Represents a single form field."""
    id: str
    name: str
    label: str
    field_type: str  # text, select, radio, checkbox, date, textarea, file
    required: bool
    selector: str
    section: str  # Which tab/section this field belongs to
    options: list[dict] = field(default_factory=list)  # For selects: [{"value": "M", "label": "Male"}, ...]
    max_length: Optional[int] = None
    placeholder: Optional[str] = None
    default_value: Optional[str] = None


@dataclass
class FormSection:
    """Represents a section/tab of the form."""
    index: int
    name_de: str
    name_en: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class FormSchema:
    """Complete form schema."""
    url: str
    language: str = "en"
    sections: list[FormSection] = field(default_factory=list)
    total_fields: int = 0
    required_fields: int = 0
    optional_fields: int = 0


class VidexFormScraper:
    """Scrapes the VIDEX form to extract all field definitions."""

    def __init__(self, headless: bool = False, language: str = "en"):
        self.headless = headless
        self.language = language
        self.schema = FormSchema(url=VIDEX_URL, language=language)
        self.all_field_ids = set()  # Track all scraped field IDs to avoid duplicates

    def _switch_to_english(self, page: Page) -> bool:
        """Switch the VIDEX form to English language."""
        console.print("[cyan]Switching to English language...[/cyan]")
        
        try:
            # The language selector is a dropdown at the top-left
            lang_selector = page.locator("select").first
            if lang_selector.is_visible(timeout=3000):
                # Try to select English
                try:
                    lang_selector.select_option(label="English")
                    console.print("[green]Selected English language[/green]")
                    page.wait_for_timeout(2000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    return True
                except Exception:
                    pass
        except Exception:
            pass
        
        # Try alternative selectors
        alt_selectors = [
            "select:has(option:has-text('English'))",
            "select:has(option:has-text('Deutsch'))",
        ]
        
        for selector in alt_selectors:
            try:
                element = page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.select_option(label="English")
                    console.print("[green]Selected English from dropdown[/green]")
                    page.wait_for_timeout(2000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except Exception:
                continue
        
        console.print("[yellow]Could not switch to English, continuing with current language[/yellow]")
        return False

    def _click_tab(self, page: Page, tab_info: dict) -> bool:
        """Click on a specific tab to navigate to that section."""
        tab_name_de = tab_info["de"]
        tab_name_en = tab_info["en"]
        tab_index = tab_info["index"]
        
        console.print(f"[cyan]Navigating to tab: {tab_name_en}...[/cyan]")
        
        # Try various selectors to find and click the tab
        tab_selectors = [
            f"text={tab_name_en}",
            f"text={tab_name_de}",
            f"a:has-text('{tab_name_en}')",
            f"a:has-text('{tab_name_de}')",
            f"div:has-text('{tab_name_en}')",
            f"div:has-text('{tab_name_de}')",
            f"span:has-text('{tab_name_en}')",
            f"span:has-text('{tab_name_de}')",
            f"li:has-text('{tab_name_en}')",
            f"li:has-text('{tab_name_de}')",
            f"button:has-text('{tab_name_en}')",
            f"button:has-text('{tab_name_de}')",
        ]
        
        for selector in tab_selectors:
            try:
                tab = page.locator(selector).first
                if tab.is_visible(timeout=1000):
                    tab.click()
                    page.wait_for_timeout(1500)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    console.print(f"[green]Clicked tab: {tab_name_en}[/green]")
                    return True
            except Exception:
                continue
        
        # Try clicking by index in the tab bar
        try:
            tab_bar = page.locator("[class*='tab'], [class*='nav'], [role='tablist']").first
            if tab_bar.is_visible(timeout=1000):
                tabs = tab_bar.locator("a, div, span, li, button").all()
                if tab_index < len(tabs):
                    tabs[tab_index].click()
                    page.wait_for_timeout(1500)
                    console.print(f"[green]Clicked tab by index: {tab_index}[/green]")
                    return True
        except Exception:
            pass
        
        console.print(f"[yellow]Could not click tab: {tab_name_en}[/yellow]")
        return False

    def _expand_all_sections(self, page: Page) -> None:
        """Expand any collapsed sections/accordions on the current page."""
        # Look for expand/collapse buttons or accordions
        expand_selectors = [
            "[class*='collapse'] button",
            "[class*='accordion'] button",
            "[class*='expand']",
            "button:has-text('+')",
            "button:has-text('Show')",
            "button:has-text('Anzeigen')",
            "[aria-expanded='false']",
        ]
        
        for selector in expand_selectors:
            try:
                buttons = page.locator(selector).all()
                for button in buttons:
                    if button.is_visible():
                        button.click()
                        page.wait_for_timeout(300)
            except Exception:
                continue

    def _scroll_page(self, page: Page) -> None:
        """Scroll through the page to ensure all lazy-loaded elements are visible."""
        try:
            # Scroll to bottom and back
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
        except Exception:
            pass

    def _extract_fields_from_section(self, page: Page, section_name: str) -> list[FormField]:
        """Extract all form fields from the current section using JavaScript."""
        fields = []
        
        # Expand any collapsed sections
        self._expand_all_sections(page)
        
        # Scroll to load lazy elements
        self._scroll_page(page)
        
        try:
            elements = page.evaluate("""() => {
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])');
                const selects = document.querySelectorAll('select');
                const textareas = document.querySelectorAll('textarea');
                
                const allElements = [...inputs, ...selects, ...textareas];
                
                return allElements.map((el, index) => {
                    const id = el.id || '';
                    const name = el.name || '';
                    
                    // Skip language selector
                    if (id === '' && name === '' && el.tagName === 'SELECT') {
                        const firstOption = el.options[0];
                        if (firstOption && (firstOption.text.includes('Deutsch') || firstOption.text.includes('English'))) {
                            return null;
                        }
                    }
                    
                    // Get label - try multiple methods
                    let label = '';
                    
                    // Method 1: label[for]
                    if (id) {
                        try {
                            const labelEl = document.querySelector('label[for="' + CSS.escape(id) + '"]');
                            if (labelEl) {
                                label = labelEl.textContent.trim();
                            }
                        } catch(e) {}
                    }
                    
                    // Method 2: Parent label
                    if (!label) {
                        const parentLabel = el.closest('label');
                        if (parentLabel) {
                            label = parentLabel.textContent.trim();
                        }
                    }
                    
                    // Method 3: Previous sibling
                    if (!label) {
                        let prev = el.previousElementSibling;
                        while (prev && !label) {
                            if (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'DIV') {
                                const text = prev.textContent.trim();
                                if (text && text.length < 200) {
                                    label = text;
                                }
                            }
                            prev = prev.previousElementSibling;
                        }
                    }
                    
                    // Method 4: Parent's label child
                    if (!label && el.parentElement) {
                        const parentLabel = el.parentElement.querySelector('label');
                        if (parentLabel && parentLabel !== el) {
                            label = parentLabel.textContent.trim();
                        }
                    }
                    
                    // Method 5: Look in parent containers
                    if (!label) {
                        let parent = el.parentElement;
                        for (let i = 0; i < 3 && parent && !label; i++) {
                            const labels = parent.querySelectorAll('label, .label, [class*="label"]');
                            for (const lbl of labels) {
                                if (!lbl.contains(el)) {
                                    const text = lbl.textContent.trim();
                                    if (text && text.length < 200) {
                                        label = text;
                                        break;
                                    }
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }
                    
                    // Fallback
                    if (!label) {
                        label = el.placeholder || el.title || name || id || 'Field ' + index;
                    }
                    
                    // Check required - look for * in label or required attribute
                    let required = el.required || el.getAttribute('aria-required') === 'true';
                    if (label.includes('*')) required = true;
                    if ((el.className || '').toLowerCase().includes('required')) required = true;
                    
                    // Get options for select (capture both value and label)
                    let options = [];
                    if (el.tagName === 'SELECT') {
                        options = Array.from(el.options).map(o => ({
                            value: o.value || '',
                            label: o.text.trim()
                        })).filter(o => o.value || o.label);
                    }
                    
                    // Determine field type
                    let fieldType = 'text';
                    if (el.tagName === 'SELECT') fieldType = 'select';
                    else if (el.tagName === 'TEXTAREA') fieldType = 'textarea';
                    else if (el.type === 'checkbox') fieldType = 'checkbox';
                    else if (el.type === 'radio') fieldType = 'radio';
                    else if (el.type === 'date') fieldType = 'date';
                    else if (el.type === 'file') fieldType = 'file';
                    else if (el.type === 'email') fieldType = 'email';
                    else if (el.type === 'tel') fieldType = 'tel';
                    else if (el.type === 'number') fieldType = 'number';
                    
                    // Check visibility
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;
                    
                    return {
                        id: id,
                        name: name,
                        label: label.replace(/\\*/g, '').replace(/:/g, '').trim(),
                        fieldType: fieldType,
                        required: required,
                        options: options,  // Capture all options
                        maxLength: el.maxLength > 0 ? el.maxLength : null,
                        placeholder: el.placeholder || null,
                        value: el.value || null,
                        isVisible: isVisible,
                        tagName: el.tagName.toLowerCase()
                    };
                }).filter(x => x !== null);
            }""")
        except Exception as e:
            console.print(f"[red]Error extracting elements: {e}[/red]")
            elements = []
        
        for elem_info in elements:
            try:
                if not elem_info.get("isVisible", False):
                    continue
                
                elem_id = elem_info.get("id", "")
                elem_name = elem_info.get("name", "")
                
                # Create unique identifier
                unique_id = elem_id or elem_name or f"field_{len(fields)}"
                
                # Skip if already scraped
                if unique_id in self.all_field_ids:
                    continue
                self.all_field_ids.add(unique_id)
                
                # Build selector using attribute format
                if elem_id:
                    css_selector = f'[id="{elem_id}"]'
                elif elem_name:
                    tag = elem_info.get("tagName", "input")
                    css_selector = f'{tag}[name="{elem_name}"]'
                else:
                    css_selector = f'[id="{unique_id}"]'
                
                form_field = FormField(
                    id=unique_id,
                    name=elem_name,
                    label=elem_info.get("label", "Unknown"),
                    field_type=elem_info.get("fieldType", "text"),
                    required=elem_info.get("required", False),
                    selector=css_selector,
                    section=section_name,
                    options=elem_info.get("options", []),
                    max_length=elem_info.get("maxLength"),
                    placeholder=elem_info.get("placeholder"),
                    default_value=elem_info.get("value")
                )
                
                fields.append(form_field)
                
            except Exception as e:
                console.print(f"[yellow]Warning: Could not process element: {e}[/yellow]")
                continue
        
        return fields

    def _handle_popups(self, page: Page) -> None:
        """Handle any popups or dialogs."""
        popup_selectors = [
            "button:has-text('OK')",
            "button:has-text('Accept')",
            "button:has-text('Close')",
            "[class*='cookie'] button",
        ]
        
        for selector in popup_selectors:
            try:
                button = page.locator(selector).first
                if button.is_visible(timeout=500):
                    button.click()
                    page.wait_for_timeout(300)
            except Exception:
                continue

    def scrape(self) -> FormSchema:
        """Main scraping method - navigates through all tabs and extracts fields."""
        console.print("[bold blue]Starting VIDEX form scraping...[/bold blue]")
        console.print(f"[cyan]Form has {len(FORM_TABS)} sections to scrape[/cyan]")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            page = context.new_page()
            
            # Handle dialogs automatically
            page.on("dialog", lambda dialog: dialog.accept())
            
            try:
                console.print(f"[cyan]Navigating to {VIDEX_URL}[/cyan]")
                page.goto(VIDEX_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                
                # Handle any initial popups
                self._handle_popups(page)
                
                # Switch to English
                if self.language == "en":
                    self._switch_to_english(page)
                    page.wait_for_timeout(1500)
                    self._handle_popups(page)
                
                # Take screenshot of initial page
                screenshots_dir = Path(__file__).parent.parent.parent / "screenshots"
                screenshots_dir.mkdir(exist_ok=True)
                page.screenshot(path=str(screenshots_dir / "scrape_initial.png"))
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Scraping sections...", total=len(FORM_TABS))
                    
                    for tab_info in FORM_TABS:
                        section_name = tab_info["en"]
                        progress.update(task, description=f"Scraping: {section_name}...")
                        
                        # Click the tab
                        self._click_tab(page, tab_info)
                        page.wait_for_timeout(1000)
                        
                        # Handle any popups that appear
                        self._handle_popups(page)
                        
                        # Extract fields from this section
                        fields = self._extract_fields_from_section(page, section_name)
                        
                        # Create section
                        section = FormSection(
                            index=tab_info["index"],
                            name_de=tab_info["de"],
                            name_en=section_name,
                            fields=fields
                        )
                        
                        self.schema.sections.append(section)
                        console.print(f"[green]{section_name}: Found {len(fields)} fields[/green]")
                        
                        # Take screenshot
                        page.screenshot(path=str(screenshots_dir / f"scrape_section_{tab_info['index']}.png"))
                        
                        progress.advance(task)
                
                # Calculate totals
                for section in self.schema.sections:
                    for field in section.fields:
                        self.schema.total_fields += 1
                        if field.required:
                            self.schema.required_fields += 1
                        else:
                            self.schema.optional_fields += 1
                
                console.print(f"\n[bold green]Scraping complete![/bold green]")
                console.print(f"Total sections: {len(self.schema.sections)}")
                console.print(f"Total fields: {self.schema.total_fields}")
                console.print(f"Required fields: {self.schema.required_fields}")
                console.print(f"Optional fields: {self.schema.optional_fields}")
                
            except Exception as e:
                console.print(f"[bold red]Error during scraping: {e}[/bold red]")
                import traceback
                traceback.print_exc()
                raise
            finally:
                browser.close()
        
        return self.schema

    def save_schema(self, output_path: Path) -> None:
        """Save the scraped schema to a JSON file."""
        def serialize(obj):
            if hasattr(obj, '__dict__'):
                return {k: serialize(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            else:
                return obj
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serialize(self.schema), f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Schema saved to {output_path}[/green]")


def scrape_videx_form(headless: bool = False, output_path: Optional[Path] = None, language: str = "en") -> FormSchema:
    """
    Convenience function to scrape the VIDEX form.
    
    Args:
        headless: Run browser in headless mode
        output_path: Path to save the schema JSON
        language: Language to use (en for English, de for German)
    
    Returns:
        FormSchema with all extracted fields
    """
    scraper = VidexFormScraper(headless=headless, language=language)
    schema = scraper.scrape()
    
    if output_path:
        scraper.save_schema(output_path)
    
    return schema


if __name__ == "__main__":
    # Quick test
    output_dir = Path(__file__).parent.parent.parent / "output"
    schema = scrape_videx_form(headless=False, output_path=output_dir / "fields_schema.json", language="en")
