"""
France-Visas Registration Automation Script
============================================
Automates the account creation process on the France-Visas portal.

Features:
- Navigates from homepage to get fresh session
- Automatic form filling
- Automatic CAPTCHA solving (OCR + AI Vision)
- Screenshot debugging
"""

import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright, Page

from captcha_solver import CaptchaSolver


# Check if running interactively
INTERACTIVE_MODE = sys.stdin.isatty()


def safe_input(prompt: str = "") -> str:
    """Safe input that works in non-interactive mode."""
    if INTERACTIVE_MODE:
        return input(prompt)
    else:
        print(prompt)
        print("(Non-interactive mode - continuing automatically)")
        return ""


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def save_debug_screenshot(page: Page, name: str) -> str:
    """Save a debug screenshot and return the path."""
    debug_dir = Path("debug_screenshots")
    debug_dir.mkdir(exist_ok=True)
    path = debug_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  📷 Screenshot saved: {path}")
    return str(path)


def navigate_to_registration(page: Page) -> bool:
    """
    Navigate from the France-Visas homepage to the registration page.
    Returns True if successful.
    """
    print("\n🌐 Navigating to France-Visas...")
    
    # Start from the main application form page
    home_url = "https://france-visas.gouv.fr/en/web/france-visas/"
    
    print(f"  → Loading homepage: {home_url}")
    page.goto(home_url, wait_until="networkidle", timeout=60000)
    time.sleep(2)
    save_debug_screenshot(page, "00_homepage")
    
    # Accept cookies if there's a cookie banner
    try:
        cookie_buttons = [
            "Accept all cookies",
            "Accept all",
            "Accepter tout",
            "Accept",
            "OK",
        ]
        for btn_text in cookie_buttons:
            try:
                btn = page.get_by_role("button", name=btn_text)
                if btn.count() > 0 and btn.first.is_visible():
                    print(f"  → Accepting cookies...")
                    btn.first.click()
                    time.sleep(1)
                    break
            except:
                continue
    except:
        pass
    
    # Navigate to the application form
    print("  → Looking for 'Apply online' or similar...")
    
    # Try direct navigation to the application form
    app_url = "https://application-form.france-visas.gouv.fr/fv-fo-dde"
    page.goto(app_url, wait_until="networkidle", timeout=60000)
    time.sleep(3)
    save_debug_screenshot(page, "01_application_form")
    
    # Look for "Create an account" or sign up link
    print("  → Looking for registration link...")
    
    signup_texts = [
        "Create an account",
        "Sign up",
        "Register",
        "Créer un compte",
        "S'inscrire",
        "No account yet",
    ]
    
    for text in signup_texts:
        try:
            link = page.get_by_role("link", name=text)
            if link.count() > 0 and link.first.is_visible():
                print(f"  → Found: '{text}' - clicking...")
                link.first.click()
                time.sleep(3)
                save_debug_screenshot(page, "02_registration_page")
                return True
        except:
            pass
        
        try:
            # Try as button
            btn = page.get_by_role("button", name=text)
            if btn.count() > 0 and btn.first.is_visible():
                print(f"  → Found button: '{text}' - clicking...")
                btn.first.click()
                time.sleep(3)
                save_debug_screenshot(page, "02_registration_page")
                return True
        except:
            pass
        
        try:
            # Try as text link
            elem = page.get_by_text(text, exact=False)
            if elem.count() > 0 and elem.first.is_visible():
                print(f"  → Found text: '{text}' - clicking...")
                elem.first.click()
                time.sleep(3)
                save_debug_screenshot(page, "02_registration_page")
                return True
        except:
            pass
    
    print("  ⚠️ Could not find registration link automatically")
    return True  # Continue anyway, user might provide direct URL


def find_and_fill_field(page: Page, selectors: list, value: str, field_name: str) -> bool:
    """Try multiple selectors to find and fill a field."""
    for selector in selectors:
        try:
            element = page.locator(selector)
            if element.count() > 0 and element.first.is_visible():
                element.first.fill(value)
                print(f"  ✓ {field_name} filled")
                return True
        except:
            continue
    return False


def fill_registration_form(page: Page, config: dict) -> bool:
    """Fill in the registration form fields."""
    
    registration = config["registration"]
    
    print("\n📝 Filling in registration form...")
    save_debug_screenshot(page, "03_before_fill")
    
    # Wait for form to load
    time.sleep(2)
    
    success = True
    
    # === LAST NAME ===
    print("  → Entering last name...")
    filled = False
    try:
        field = page.get_by_label("Last name", exact=False)
        if field.count() > 0:
            field.first.fill(registration["last_name"])
            filled = True
            print(f"  ✓ Last name filled")
    except:
        pass
    if not filled:
        selectors = ['input[name="lastName"]', 'input[name="last_name"]', '#lastName']
        filled = find_and_fill_field(page, selectors, registration["last_name"], "Last name")
    success = success and filled
    
    # === FIRST NAME ===
    print("  → Entering first name...")
    filled = False
    try:
        field = page.get_by_label("First name", exact=False)
        if field.count() > 0:
            field.first.fill(registration["first_name"])
            filled = True
            print(f"  ✓ First name filled")
    except:
        pass
    if not filled:
        selectors = ['input[name="firstName"]', 'input[name="first_name"]', '#firstName']
        filled = find_and_fill_field(page, selectors, registration["first_name"], "First name")
    success = success and filled
    
    # === EMAIL ===
    print("  → Entering email...")
    email_inputs = page.locator('input[type="email"], input[name*="email" i]')
    if email_inputs.count() >= 1:
        email_inputs.first.fill(registration["email"])
        print(f"  ✓ Email filled")
    else:
        try:
            field = page.get_by_label("Email", exact=False).first
            field.fill(registration["email"])
            print(f"  ✓ Email filled")
        except:
            print("  ❌ Could not find email field")
            success = False
    
    # === EMAIL CONFIRMATION ===
    print("  → Confirming email...")
    if email_inputs.count() >= 2:
        email_inputs.nth(1).fill(registration["email"])
        print(f"  ✓ Email confirmation filled")
    else:
        try:
            field = page.get_by_label("E-mail confirmation", exact=False)
            if field.count() > 0:
                field.first.fill(registration["email"])
                print(f"  ✓ Email confirmation filled")
        except:
            print("  ⚠️ Could not find email confirmation field")
    
    # === PASSWORD ===
    print("  → Entering password...")
    password_inputs = page.locator('input[type="password"]')
    if password_inputs.count() >= 1:
        password_inputs.first.fill(registration["password"])
        print(f"  ✓ Password filled")
    else:
        print("  ❌ Could not find password field")
        success = False
    
    # === CONFIRM PASSWORD ===
    print("  → Confirming password...")
    if password_inputs.count() >= 2:
        password_inputs.nth(1).fill(registration["password"])
        print(f"  ✓ Confirm password filled")
    else:
        print("  ⚠️ Could not find confirm password field")
    
    # === LANGUAGE ===
    print("  → Selecting language...")
    try:
        selects = page.locator('select')
        if selects.count() > 0:
            selects.first.select_option(label=registration["language"])
            print(f"  ✓ Language selected: {registration['language']}")
        else:
            # Custom dropdown
            dropdown = page.get_by_text("Select an option")
            if dropdown.count() > 0:
                dropdown.first.click()
                time.sleep(0.5)
                page.get_by_text(registration["language"]).first.click()
                print(f"  ✓ Language selected: {registration['language']}")
    except Exception as e:
        print(f"  ⚠️ Could not select language: {e}")
    
    save_debug_screenshot(page, "04_form_filled")
    return success


def capture_captcha_image(page: Page) -> Image.Image:
    """Capture the CAPTCHA image from the page."""
    print("\n📸 Capturing CAPTCHA image...")
    
    captcha_element = None
    
    # Find images that look like CAPTCHAs
    images = page.locator('img')
    for i in range(images.count()):
        try:
            img = images.nth(i)
            if img.is_visible():
                box = img.bounding_box()
                if box and 50 < box['width'] < 300 and 20 < box['height'] < 100:
                    if box['y'] > 200:  # Not at top of page (logo)
                        captcha_element = img
                        print(f"  → Found CAPTCHA image ({box['width']:.0f}x{box['height']:.0f})")
                        break
        except:
            continue
    
    if captcha_element:
        screenshot_bytes = captcha_element.screenshot()
        image = Image.open(BytesIO(screenshot_bytes))
        
        debug_dir = Path("captcha_debug")
        debug_dir.mkdir(exist_ok=True)
        image.save(debug_dir / "captured_captcha.png")
        
        print(f"  ✓ CAPTCHA captured ({image.width}x{image.height})")
        return image
    
    # Fallback: full page
    print("  ⚠️ Could not locate CAPTCHA element, using full page")
    screenshot_bytes = page.screenshot()
    return Image.open(BytesIO(screenshot_bytes))


def solve_and_enter_captcha(page: Page, solver: CaptchaSolver, max_attempts: int = 3) -> bool:
    """Capture, solve, and enter the CAPTCHA."""
    print("\n" + "="*60)
    print("🔐 AUTOMATIC CAPTCHA SOLVING")
    print("="*60)
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n📍 Attempt {attempt}/{max_attempts}")
        
        captcha_image = capture_captcha_image(page)
        solution = solver.solve(captcha_image)
        
        if solution:
            print(f"\n🎯 CAPTCHA Solution: {solution}")
            
            # Find CAPTCHA input
            captcha_input = None
            
            try:
                field = page.get_by_label("Security code", exact=False)
                if field.count() > 0:
                    captcha_input = field.first
            except:
                pass
            
            if not captcha_input:
                # Find last text input (often CAPTCHA)
                text_inputs = page.locator('input[type="text"]')
                if text_inputs.count() > 0:
                    captcha_input = text_inputs.last
            
            if captcha_input:
                captcha_input.fill(solution)
                save_debug_screenshot(page, "05_captcha_entered")
                print("  ✓ CAPTCHA entered!")
                return True
            else:
                print("  ❌ Could not find CAPTCHA input")
        else:
            print("  ❌ Could not solve CAPTCHA")
        
        # Try refreshing CAPTCHA
        if attempt < max_attempts:
            print("  🔄 Looking for refresh button...")
            try:
                # Look for audio/refresh icons near CAPTCHA
                refresh_btns = page.locator('button, a').filter(has=page.locator('svg, img[alt*="refresh" i]'))
                if refresh_btns.count() > 0:
                    refresh_btns.first.click()
                    time.sleep(1)
            except:
                pass
    
    # Fall back to manual
    print("\n⚠️ AUTOMATIC SOLVING FAILED")
    if INTERACTIVE_MODE:
        print("Please enter the CAPTCHA manually in the browser.")
        safe_input("Press ENTER after entering the CAPTCHA...")
        return True
    return False


def submit_form(page: Page) -> str:
    """
    Submit the registration form.
    Returns: 'success', 'captcha_error', or 'error'
    """
    print("\n📤 Submitting registration form...")
    
    submit_texts = ["Create an account", "Créer un compte", "Submit", "Register"]
    clicked = False
    
    for text in submit_texts:
        try:
            btn = page.get_by_role("button", name=text)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                clicked = True
                break
        except:
            continue
    
    if not clicked:
        try:
            submit = page.locator('button[type="submit"], input[type="submit"]').first
            submit.click()
            clicked = True
        except:
            pass
    
    if not clicked:
        print("  ❌ Could not find submit button")
        return "error"
    
    time.sleep(3)
    save_debug_screenshot(page, "06_after_submit")
    
    # Check for CAPTCHA error
    try:
        error_texts = page.locator('text=/invalid.*security.*code/i, text=/code.*invalid/i, text=/captcha.*error/i')
        if error_texts.count() > 0:
            print("  ⚠️ Invalid CAPTCHA - will retry...")
            return "captcha_error"
    except:
        pass
    
    # Check if still on registration page (means error)
    try:
        if page.locator('text="Create account"').count() > 0:
            # Still on form, check for any error
            errors = page.locator('.error, [class*="error"], [class*="invalid"]')
            if errors.count() > 0:
                error_text = errors.first.text_content()
                if error_text and 'security' in error_text.lower():
                    print(f"  ⚠️ Error: {error_text}")
                    return "captcha_error"
    except:
        pass
    
    print("  ✓ Form submitted!")
    return "success"


def run_registration_automation(direct_url: str = None) -> None:
    """Main function to run the registration automation."""
    
    config = load_config()
    settings = config["settings"]
    
    solver = CaptchaSolver(save_debug_images=True)
    
    print("\n" + "="*60)
    print("🇫🇷 FRANCE-VISAS REGISTRATION AUTOMATION")
    print("="*60)
    print("\n📋 Features:")
    print("  • Automatic navigation to registration")
    print("  • Form auto-fill")
    print("  • CAPTCHA solving (OCR + AI Vision)")
    print("  • Debug screenshots → debug_screenshots/")
    print("="*60 + "\n")
    
    Path("debug_screenshots").mkdir(exist_ok=True)
    Path("captcha_debug").mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        print("🌐 Launching browser...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=settings.get("slow_mo", 100)
        )
        
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="en-US"
        )
        page = context.new_page()
        page.set_default_timeout(settings.get("timeout", 30000))
        
        try:
            if direct_url:
                # User provided a direct URL with fresh session
                print(f"📍 Using provided URL...")
                page.goto(direct_url, wait_until="networkidle", timeout=60000)
                time.sleep(3)
                save_debug_screenshot(page, "00_direct_url")
            else:
                # Navigate from homepage to get fresh session
                navigate_to_registration(page)
            
            # Fill the form
            fill_registration_form(page, config)
            
            # CAPTCHA solving loop with retries
            max_captcha_retries = 5
            for attempt in range(1, max_captcha_retries + 1):
                print(f"\n{'='*60}")
                print(f"🔄 CAPTCHA ATTEMPT {attempt}/{max_captcha_retries}")
                print("="*60)
                
                # Solve and enter CAPTCHA
                solve_and_enter_captcha(page, solver)
                
                # Submit
                result = submit_form(page)
                
                if result == "success":
                    print("\n" + "="*60)
                    print("🎉 REGISTRATION SUCCESSFUL!")
                    print("="*60)
                    break
                elif result == "captcha_error":
                    print(f"\n  🔄 CAPTCHA was wrong, retrying... ({attempt}/{max_captcha_retries})")
                    time.sleep(1)
                    # CAPTCHA refreshes automatically, just need to solve again
                    continue
                else:
                    print("\n  ❌ Submission error")
                    break
            
            print("\nCheck debug_screenshots/ for captured images.")
            
            if INTERACTIVE_MODE:
                safe_input("\nPress ENTER to close browser...")
            else:
                print("\nBrowser closing in 10 seconds...")
                time.sleep(10)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                save_debug_screenshot(page, "error_screenshot")
            except:
                pass
            
            if INTERACTIVE_MODE:
                safe_input("\nPress ENTER to close...")
            else:
                time.sleep(5)
        
        finally:
            browser.close()
            print("\n👋 Done!")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    run_registration_automation(url)
