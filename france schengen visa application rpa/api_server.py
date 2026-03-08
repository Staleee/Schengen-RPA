"""
France-Visas Automation API Server
==================================
- Register → Verify Email (IMAP) → Login
- Fill application form (as if already logged in; you log in manually in the browser)

Endpoints:
  POST /register            - Register only (manual verification)
  POST /register-and-verify  - Full flow with auto email verification
  POST /login               - Login with verified account
  POST /fill-application    - Fill form fields (no login; manual login in browser)
"""

import asyncio
import os
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import uvicorn

from playwright.sync_api import sync_playwright, Page
from PIL import Image

# Fix SSL for OCR model downloads
ssl._create_default_https_context = ssl._create_unverified_context

from captcha_solver import CaptchaSolver
from email_helper import EmailConfig, EmailReader

app = FastAPI(
    title="France-Visas Automation API",
    description="Full automation: Register → Verify → Login",
    version="2.0.0"
)

executor = ThreadPoolExecutor(max_workers=2)


@app.get("/")
async def root():
    """Root and health probe – Railway can hit / or /health."""
    return {"status": "ok", "service": "france-visas-automation", "version": "2.0"}


# ============== MODELS ==============

class RegistrationRequest(BaseModel):
    last_name: str
    first_name: str
    email: EmailStr
    password: str
    language: str = "English"


class FullFlowRequest(BaseModel):
    """Request for full registration + verification + login flow."""
    last_name: str
    first_name: str
    email: EmailStr
    password: str
    language: str = "English"
    # Email IMAP settings for reading verification email
    email_password: str  # IMAP password (may be app password)
    imap_server: str  # e.g., "mail.yourdomain.com"
    imap_port: int = 993
    imap_use_ssl: bool = True
    # Timing
    email_wait_seconds: int = 300  # Max time to wait for verification email


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# Map structured (DB-style) keys to France form labels/names. Extend as we discover the real form.
FRANCE_FIELD_MAP = {
    "last_name": "Last name",
    "family_name": "Last name",
    "surname": "Last name",
    "maid_surname": "Last name",
    "first_name": "First name",
    "maid_first_name": "First name",
    "date_of_birth": "Date of birth",
    "maid_date_of_birth": "Date of birth",
    "place_of_birth": "Place of birth",
    "maid_place_of_birth": "Place of birth",
    "country_of_birth": "Country of birth",
    "maid_country_of_birth": "Country of birth",
    "nationality": "Nationality",
    "maid_nationality": "Nationality",
    "sex": "Sex",
    "gender": "Sex",
    "maid_sex": "Sex",
    "marital_status": "Marital status",
    "maid_marital_status": "Marital status",
    "email": "Email",
    "client_email": "Email",
    "phone": "Phone",
    "client_phone": "Phone",
    "passport_number": "Passport number",
    "passport_expiry_date": "Passport valid until",
    "passport_issue_date": "Passport date of issue",
    "passport_issuing_country": "Passport issuing country",
    "street": "Street",
    "client_street": "Street",
    "house_number": "House number",
    "client_house_number": "House number",
    "postal_code": "Postal code",
    "client_postal_code": "Postal code",
    "city": "City",
    "client_city": "City",
    "country": "Country",
    "client_country": "Country",
}


class FillApplicationRequest(BaseModel):
    """Fill the visa application form as if already logged in."""
    # Wait this many seconds for you to log in manually in the opened browser (0 = use saved session or assume already on form)
    wait_for_manual_login_seconds: int = 60
    # Raw form fields: key = form label or input name, value = string to fill (takes precedence over structured_*)
    fields: Dict[str, str] = {}
    # Optional structured (DB-style) keys – we map to France form labels. Same names as Germany RPA request body.
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    country_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    sex: Optional[str] = None
    marital_status: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[str] = None
    passport_issue_date: Optional[str] = None
    passport_issuing_country: Optional[str] = None
    street: Optional[str] = None
    house_number: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class FlowResponse(BaseModel):
    success: bool
    message: str
    step_completed: str  # "registration", "verification", "login"
    email: Optional[str] = None
    logged_in: bool = False
    session_url: Optional[str] = None


class FillApplicationResponse(BaseModel):
    success: bool
    message: str
    fields_filled: int = 0
    screenshot_path: Optional[str] = None
    pages_completed: Optional[int] = None  # For full flow


# Visa type on form = one of: Short stay, Long stay, Transit (we normalize from request body).
VISA_TYPE_OPTIONS = {"short stay": "Short stay", "long stay": "Long stay", "transit": "Transit"}


# Current nationality on France form = nationality label (Filipino, Lebanese, etc.), NOT country name (Philippines, Lebanon).
# If request sends country name, we map to this label for the first field only.
COUNTRY_TO_NATIONALITY_LABEL = {
    "Philippines": "Filipino",
    "Lebanon": "Lebanese",
    "India": "Indian",
    "Pakistan": "Pakistani",
    "Bangladesh": "Bangladeshi",
    "Sri Lanka": "Sri Lankan",
    "Egypt": "Egyptian",
    "Morocco": "Moroccan",
    "Tunisia": "Tunisian",
    "Algeria": "Algerian",
    "Indonesia": "Indonesian",
    "United Arab Emirates": "Emirati",
    "UAE": "Emirati",
    "Saudi Arabia": "Saudi",
    "United States": "American",
    "USA": "American",
    "United Kingdom": "British",
    "UK": "British",
    "Nigeria": "Nigerian",
    "Ethiopia": "Ethiopian",
    "Kenya": "Kenyan",
    "Ghana": "Ghanaian",
    "South Africa": "South African",
    "China": "Chinese",
    "Vietnam": "Vietnamese",
    "Thailand": "Thai",
    "Nepal": "Nepalese",
    "Myanmar": "Burmese",
    "Cameroon": "Cameroonian",
    "Senegal": "Senegalese",
    "Ivory Coast": "Ivorian",
    "Côte d'Ivoire": "Ivorian",
}


# Full France Schengen form – request body for multi-step flow (see FIELDS_TO_FILL.md)
class FranceFillRequest(BaseModel):
    wait_for_manual_login_seconds: int = 0  # No wait by default; set e.g. 30 if you need time to log in
    # Page 1 – Your Plans
    current_nationality: Optional[str] = None
    place_of_submission_country: Optional[str] = None  # deposit country
    visa_type: Optional[str] = None  # stay duration
    main_destination: Optional[str] = None
    issuing_authority_travel_document: Optional[str] = None
    travel_document_number: Optional[str] = None
    passport_date_of_issue: Optional[str] = None  # dd/mm/yyyy
    passport_expiry_date: Optional[str] = None  # dd/mm/yyyy
    # Page 2 – Your Information (applicant)
    sex: Optional[str] = None
    marital_status: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    place_of_birth: Optional[str] = None
    date_of_birth: Optional[str] = None  # dd/mm/yyyy (we split to day/month/year)
    country_of_birth: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    sector: Optional[str] = None  # business segment
    # Client (employer + host person) – derived for employer and page 5 host
    client_surname: Optional[str] = None
    client_first_name: Optional[str] = None
    client_street: Optional[str] = None
    client_city: Optional[str] = None
    client_country: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    # Page 3 – Your last Visa
    schengen_last_59_months: Optional[bool] = None  # True = yes, False = no
    valid_visa_start: Optional[str] = None  # if yes
    valid_visa_end: Optional[str] = None
    fingerprints_taken_before: Optional[bool] = None
    # Page 4 – Your Stay
    arrival_date: Optional[str] = None
    departure_date: Optional[str] = None
    number_of_entries: Optional[str] = None
    number_of_stays: Optional[str] = None


# ============== HELPERS ==============

def save_screenshot(page: Page, name: str) -> str:
    debug_dir = Path("debug_screenshots")
    debug_dir.mkdir(exist_ok=True)
    path = debug_dir / f"{name}.png"
    page.screenshot(path=str(path))
    return str(path)


def capture_captcha(page: Page) -> Image.Image:
    images = page.locator('img')
    for i in range(images.count()):
        try:
            img = images.nth(i)
            if img.is_visible():
                box = img.bounding_box()
                if box and 50 < box['width'] < 300 and 20 < box['height'] < 100 and box['y'] > 200:
                    return Image.open(BytesIO(img.screenshot()))
        except:
            continue
    return Image.open(BytesIO(page.screenshot()))


def _refill_email_and_password(page: Page, email: str, password: str) -> None:
    """Re-fill email and password (and confirmation) fields after a failed CAPTCHA cleared them."""
    filled = False
    # By locator (same as initial form)
    try:
        email_inputs = page.locator('input[type="email"], input[name*="email" i]')
        if email_inputs.count() >= 1:
            email_inputs.first.fill(email)
        if email_inputs.count() >= 2:
            email_inputs.nth(1).fill(email)
        password_inputs = page.locator('input[type="password"]')
        if password_inputs.count() >= 1:
            password_inputs.first.fill(password)
        if password_inputs.count() >= 2:
            password_inputs.nth(1).fill(password)
        filled = True
    except Exception:
        pass
    # Fallback: by label (France-Visas may use "Email", "Confirm email", "Password", "Confirm password")
    if not filled:
        try:
            for label in ("Email", "Confirm email", "E-mail", "Confirm e-mail"):
                try:
                    page.get_by_label(label, exact=False).first.fill(email, timeout=2000)
                except Exception:
                    pass
            for label in ("Password", "Confirm password", "Confirm your password"):
                try:
                    page.get_by_label(label, exact=False).first.fill(password, timeout=2000)
                except Exception:
                    pass
        except Exception:
            pass
    time.sleep(0.3)
    print(f"  ↻ Re-filled email and password (confirmation fields)")


def solve_captcha_and_submit(
    page: Page, solver: CaptchaSolver, email: str = "", password: str = "", max_attempts: int = 5
) -> bool:
    """Solve CAPTCHA and submit form. Re-fills email/password on each retry if they get cleared."""
    for attempt in range(1, max_attempts + 1):
        print(f"  → CAPTCHA attempt {attempt}/{max_attempts}")
        
        # After first failure the site often clears email/password confirmation – refill before each retry
        if attempt > 1 and email and password:
            _refill_email_and_password(page, email, password)
        
        # Wait for page to stabilize
        time.sleep(1)
        
        # Find CAPTCHA input
        captcha_input = None
        try:
            captcha_input = page.get_by_label("Security code", exact=False).first
        except:
            pass
        if not captcha_input:
            captcha_input = page.locator('input[type="text"]').last
        
        # Clear any previous entry
        captcha_input.clear()
        
        # Capture and solve CAPTCHA
        captcha_image = capture_captcha(page)
        solution = solver.solve(captcha_image)
        
        if not solution:
            print(f"  ✗ Could not read CAPTCHA, refreshing...")
            try:
                page.locator('button').filter(has=page.locator('svg')).last.click()
                time.sleep(1)
                if email and password:
                    _refill_email_and_password(page, email, password)
            except Exception:
                pass
            continue
        
        # Enter CAPTCHA solution
        captcha_input.fill(solution)
        time.sleep(0.5)
        
        save_screenshot(page, f"captcha_attempt_{attempt}")
        
        # Check if button is enabled
        submit_btn = page.locator('button:has-text("Create an account")').first
        
        # Wait for button to be enabled
        try:
            submit_btn.wait_for(state="visible", timeout=5000)
            if submit_btn.is_disabled():
                print(f"  ✗ Button still disabled, CAPTCHA might be wrong")
                try:
                    page.locator('button').filter(has=page.locator('svg')).last.click()
                    time.sleep(1)
                    if email and password:
                        _refill_email_and_password(page, email, password)
                except Exception:
                    pass
                continue
        except:
            pass
        
        # Submit
        try:
            submit_btn.click(timeout=5000)
        except:
            try:
                page.locator('button[type="submit"]').first.click(timeout=5000)
            except Exception as e:
                print(f"  ✗ Could not click submit: {e}")
                continue
        
        time.sleep(3)
        
        # Check success
        if page.locator('text="Check mailbox"').count() > 0:
            print(f"  ✓ Registration successful!")
            return True
        
        if page.locator('text=/invalid.*security.*code/i').count() > 0:
            print(f"  ✗ Wrong CAPTCHA, will retry...")
            try:
                page.locator('button').filter(has=page.locator('svg')).last.click()
                time.sleep(1)
                if email and password:
                    _refill_email_and_password(page, email, password)
            except Exception:
                pass
            continue
    
    return False


# ============== FULL FLOW ==============

def run_full_flow(data: FullFlowRequest) -> dict:
    """
    Complete flow: Register → Wait for email → Verify → Login
    """
    # Validate IMAP settings so we fail fast with a clear error
    imap = (data.imap_server or "").strip().lower()
    if not imap or imap in ("imap.example.com", "mail.example.com", "example.com"):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid imap_server",
                "hint": "Use your provider's IMAP host, e.g. Gmail: imap.gmail.com (port 993, SSL), Outlook: outlook.office365.com. getaddrinfo failed usually means wrong hostname.",
            },
        )
    
    solver = CaptchaSolver(save_debug_images=True)
    Path("debug_screenshots").mkdir(exist_ok=True)
    Path("captcha_debug").mkdir(exist_ok=True)
    
    # Setup email reader
    email_config = EmailConfig(
        email_address=data.email,
        email_password=data.email_password,
        imap_server=data.imap_server,
        imap_port=data.imap_port,
        use_ssl=data.imap_use_ssl
    )
    email_reader = EmailReader(email_config)
    
    headless = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(viewport={"width": 1400, "height": 900}, locale="en-US")
        page = context.new_page()
        page.set_default_timeout(30000)
        
        try:
            # ===== STEP 1: REGISTRATION =====
            print("\n" + "="*50)
            print("STEP 1: REGISTRATION")
            print("="*50)
            
            # Navigate to registration
            page.goto("https://france-visas.gouv.fr/en/web/france-visas/", wait_until="domcontentloaded", timeout=60000)
            page.goto("https://application-form.france-visas.gouv.fr/fv-fo-dde", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            
            # Click Create Account
            create_btn = page.get_by_role("button", name="Create an account")
            if create_btn.count() > 0:
                create_btn.first.click()
                time.sleep(3)
            
            save_screenshot(page, "step1_registration_page")
            
            # Fill form
            try:
                page.get_by_label("Last name", exact=False).first.fill(data.last_name)
            except:
                page.locator('input[name="lastName"]').fill(data.last_name)
            
            try:
                page.get_by_label("First name", exact=False).first.fill(data.first_name)
            except:
                page.locator('input[name="firstName"]').fill(data.first_name)
            
            email_inputs = page.locator('input[type="email"], input[name*="email" i]')
            if email_inputs.count() >= 1:
                email_inputs.first.fill(data.email)
            if email_inputs.count() >= 2:
                email_inputs.nth(1).fill(data.email)
            
            password_inputs = page.locator('input[type="password"]')
            if password_inputs.count() >= 1:
                password_inputs.first.fill(data.password)
            if password_inputs.count() >= 2:
                password_inputs.nth(1).fill(data.password)
            
            try:
                page.locator('select').first.select_option(label=data.language)
            except:
                pass
            
            save_screenshot(page, "step1_form_filled")
            
            # Solve CAPTCHA and submit (pass email/password so we can refill on each retry when they get cleared)
            if not solve_captcha_and_submit(page, solver, email=data.email, password=data.password):
                browser.close()
                return {
                    "success": False,
                    "message": "Registration failed - CAPTCHA could not be solved",
                    "step_completed": "registration_failed",
                    "email": data.email,
                    "logged_in": False
                }
            
            save_screenshot(page, "step1_registration_complete")
            
            # ===== STEP 2: EMAIL VERIFICATION =====
            print("\n" + "="*50)
            print("STEP 2: EMAIL VERIFICATION")
            print("="*50)
            
            # Connect to email and wait for verification
            if not email_reader.connect():
                browser.close()
                return {
                    "success": False,
                    "message": "Could not connect to email server",
                    "step_completed": "registration",
                    "email": data.email,
                    "logged_in": False
                }
            
            success, verification_link, verification_code = email_reader.wait_for_verification_email(
                sender_contains="interieur.gouv.fr",  # France-Visas sends from noreply@interieur.gouv.fr
                max_wait_seconds=data.email_wait_seconds,
                poll_interval=10
            )
            
            email_reader.disconnect()
            
            if not success or (not verification_link and not verification_code):
                browser.close()
                return {
                    "success": False,
                    "message": "Verification email not received in time (no link or code found)",
                    "step_completed": "registration",
                    "email": data.email,
                    "logged_in": False
                }
            
            if verification_link:
                print(f"  → Opening verification link...")
                page.goto(verification_link, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                save_screenshot(page, "step2_verification_clicked")
                # Page may have a "Confirm" / "Verify" button or link – click it to complete verification
                clicked = False
                for btn_text in ["Confirm", "Verify", "Activate", "Continue", "Valider", "Confirmer", "Confirm my email", "Verify my email", "Confirm your email"]:
                    if clicked:
                        break
                    for role in ["button", "link"]:
                        try:
                            el = page.get_by_role(role, name=btn_text).first
                            if el.is_visible(timeout=1500) and (role != "button" or el.is_enabled()):
                                print(f"  → Clicking '{btn_text}' to confirm verification...")
                                el.click()
                                time.sleep(3)
                                save_screenshot(page, "step2_after_confirm_click")
                                clicked = True
                                break
                        except Exception:
                            continue
                if page.locator('text=/verified|confirmed|success|activated/i').count() > 0:
                    print("  ✓ Email verified via link!")
                else:
                    print("  → Verification page handled, continuing...")
            else:
                print("  → No verification link in email (check your email for link or code)")
            
            save_screenshot(page, "step2_verification_complete")
            time.sleep(2)
            
            # Check if verification link already logged us in (France-Visas often does this)
            current_url = page.url
            logged_in = False
            if page.locator('text="My applications"').count() > 0:
                logged_in = True
            elif page.locator('text="Log out"').count() > 0:
                logged_in = True
            elif page.locator('text="Dashboard"').count() > 0:
                logged_in = True
            elif "application" in current_url.lower() and "required-action" not in current_url:
                logged_in = True
            
            if logged_in:
                print("  ✓ Already logged in after verification link (skipping login step)")
            else:
                # ===== STEP 3: LOGIN (only if not already logged in) =====
                print("\n" + "="*50)
                print("STEP 3: LOGIN")
                print("="*50)
                
                # Navigate to login
                page.goto("https://application-form.france-visas.gouv.fr/fv-fo-dde", wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                save_screenshot(page, "step3_login_page")
                
                # Fill login credentials
                try:
                    page.get_by_label("E-mail", exact=False).first.fill(data.email)
                except Exception:
                    page.locator('input[type="email"]').first.fill(data.email)
                
                try:
                    page.get_by_label("Password", exact=False).first.fill(data.password)
                except Exception:
                    page.locator('input[type="password"]').first.fill(data.password)
                
                save_screenshot(page, "step3_credentials_entered")
                
                # Click login
                try:
                    page.get_by_role("button", name="Log in").first.click()
                except Exception:
                    try:
                        page.get_by_role("button", name="Sign in").first.click()
                    except Exception:
                        page.locator('button[type="submit"]').first.click()
                
                time.sleep(5)
                save_screenshot(page, "step3_after_login")
                
                current_url = page.url
                logged_in = False
                
                # France-Visas may send a login link by email (same sender as verification) – wait for it and open it
                need_login_link = (
                    "required-action" in current_url
                    or page.locator('text=/check your e?-?mail|we sent you|link to log|connexion|connect/i').count() > 0
                )
                if need_login_link and not logged_in:
                    print("  → Login requires opening a link from your email (same sender as verification)...")
                    if email_reader.connect():
                        login_success, login_link, _ = email_reader.wait_for_verification_email(
                            sender_contains="interieur.gouv.fr",
                            max_wait_seconds=min(120, data.email_wait_seconds + 60),
                            poll_interval=10,
                        )
                        email_reader.disconnect()
                        if login_success and login_link:
                            print(f"  → Opening login link from email...")
                            page.goto(login_link, wait_until="domcontentloaded", timeout=60000)
                            time.sleep(3)
                            save_screenshot(page, "step3_after_login_link")
                            current_url = page.url
                            # Click Confirm/Continue if present
                            for btn_text in ["Confirm", "Continue", "Valider", "Confirmer", "Log in", "Sign in"]:
                                try:
                                    btn = page.get_by_role("button", name=btn_text).first
                                    if btn.is_visible(timeout=1500) and btn.is_enabled():
                                        btn.click()
                                        time.sleep(3)
                                        break
                                except Exception:
                                    pass
                            current_url = page.url
            
            # If redirected to VERIFY_EMAIL required-action and we have the code, enter it
            if verification_code and ("VERIFY_EMAIL" in current_url or "required-action" in current_url):
                print("  → VERIFY_EMAIL page detected, entering verification code from email...")
                code_entered = False
                for selector in [
                    'input[name*="code"]', 'input[id*="code"]', 'input[type="text"]',
                    'input[inputmode="numeric"]', 'input[placeholder*="code" i]',
                ]:
                    try:
                        loc = page.locator(selector)
                        if loc.count() > 0 and loc.first.is_visible(timeout=2000):
                            loc.first.fill(verification_code)
                            code_entered = True
                            print(f"  ✓ Entered verification code")
                            break
                    except Exception:
                        continue
                if not code_entered:
                    try:
                        page.get_by_label("Code", exact=False).first.fill(verification_code)
                        code_entered = True
                        print(f"  ✓ Entered verification code (by label)")
                    except Exception:
                        pass
                if code_entered:
                    time.sleep(0.5)
                    for btn_text in ["Submit", "Confirm", "Verify", "Continue", "Valider", "Confirmer"]:
                        try:
                            btn = page.get_by_role("button", name=btn_text).first
                            if btn.is_visible(timeout=1000) and btn.is_enabled():
                                btn.click()
                                break
                        except Exception:
                            pass
                    else:
                        try:
                            page.locator('button[type="submit"]').first.click()
                        except Exception:
                            pass
                    time.sleep(5)
                    save_screenshot(page, "step3_after_verify_code")
                    current_url = page.url
            
            if page.locator('text="My applications"').count() > 0:
                logged_in = True
            elif page.locator('text="Log out"').count() > 0:
                logged_in = True
            elif page.locator('text="Dashboard"').count() > 0:
                logged_in = True
            elif "application" in current_url.lower() and "required-action" not in current_url:
                logged_in = True
            
            browser.close()
            
            if logged_in:
                return {
                    "success": True,
                    "message": "Full flow completed! Account registered, verified, and logged in.",
                    "step_completed": "login",
                    "email": data.email,
                    "logged_in": True,
                    "session_url": current_url
                }
            else:
                return {
                    "success": True,
                    "message": "Account registered and verified. Login may require additional steps.",
                    "step_completed": "verification",
                    "email": data.email,
                    "logged_in": False,
                    "session_url": current_url
                }
            
        except Exception as e:
            save_screenshot(page, "error")
            browser.close()
            email_reader.disconnect()
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "step_completed": "error",
                "email": data.email,
                "logged_in": False
            }


def run_login_only(data: LoginRequest) -> dict:
    """Login only (for already verified accounts)."""
    headless = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(viewport={"width": 1400, "height": 900}, locale="en-US")
        page = context.new_page()
        page.set_default_timeout(30000)
        
        try:
            page.goto("https://application-form.france-visas.gouv.fr/fv-fo-dde", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            
            # Fill credentials
            try:
                page.get_by_label("E-mail", exact=False).first.fill(data.email)
            except:
                page.locator('input[type="email"]').first.fill(data.email)
            
            try:
                page.get_by_label("Password", exact=False).first.fill(data.password)
            except:
                page.locator('input[type="password"]').first.fill(data.password)
            
            # Click login
            try:
                page.get_by_role("button", name="Log in").first.click()
            except:
                page.locator('button[type="submit"]').first.click()
            
            time.sleep(5)
            
            logged_in = (
                page.locator('text="My applications"').count() > 0 or
                page.locator('text="Log out"').count() > 0
            )
            
            current_url = page.url
            browser.close()
            
            return {
                "success": True,
                "message": "Login successful" if logged_in else "Login completed",
                "step_completed": "login",
                "email": data.email,
                "logged_in": logged_in,
                "session_url": current_url
            }
            
        except Exception as e:
            browser.close()
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "step_completed": "error",
                "email": data.email,
                "logged_in": False
            }


# ============== FILL APPLICATION (AS IF LOGGED IN) ==============

def _by_id(page: Page, id_val: str):
    """Locator for JSF-style id (may contain colons)."""
    return page.locator(f'[id="{id_val}"]')


def _fill_by_id(page: Page, id_val: str, value: str) -> bool:
    """Fill input/select by exact id. Returns True if filled."""
    if not value:
        return False
    try:
        loc = _by_id(page, id_val)
        if loc.count() > 0 and loc.first.is_visible(timeout=3000):
            loc.first.fill(str(value))
            return True
    except Exception:
        pass
    return False


def _select_by_id(page: Page, id_val: str, value: str) -> bool:
    """Select dropdown by id (click _label to open, then click option with text)."""
    if not value:
        return False
    try:
        el = _by_id(page, id_val).first
        if el.is_visible(timeout=3000):
            el.click()
            time.sleep(0.5)
            # PrimeFaces: options often in list or panel
            opt = page.get_by_text(str(value), exact=False).first
            if opt.is_visible(timeout=2000):
                opt.click()
                return True
            # Try data-label on li
            try:
                page.locator(f'li[data-label*="{value}" i]').first.click()
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


# ---------- Section-by-section fill with logging and fallback; stop on first skipped field ----------

def _log(msg: str) -> None:
    """Log to console with prefix so we can see what the RPA is doing."""
    print(f"  [FRANCE] {msg}")


def _log_visible_form_fields(page: Page, section: str) -> None:
    """Log what form elements we see on the page (for debugging root cause)."""
    try:
        inputs = page.locator("input, select, [role='combobox']")
        n = inputs.count()
        _log(f"Section {section}: page URL = {page.url}")
        _log(f"Section {section}: visible inputs/selects count = {n}")
        seen = []
        for i in range(min(n, 15)):
            try:
                el = inputs.nth(i)
                if el.is_visible(timeout=500):
                    id_ = el.get_attribute("id") or ""
                    name_ = el.get_attribute("name") or ""
                    if id_ or name_:
                        seen.append(id_ or name_)
            except Exception:
                pass
        if seen:
            _log(f"Section {section}: sample ids/names = {seen[:10]}")
    except Exception as e:
        _log(f"Section {section}: could not list fields: {e}")


def _fill_with_fallback(
    page: Page, section: str, field_id: str, value: str, label_hint: Optional[str] = None
) -> bool:
    """
    Fill input with fallbacks: by id, by name, by label, by placeholder.
    Logs each attempt. Returns True only if filled; False = all fallbacks failed (caller must stop).
    """
    if not value:
        return True  # nothing to fill, not a failure
    value = str(value).strip()
    _log(f"Section {section}: filling field id={field_id!r} with value={value!r}")
    # 1. By id
    try:
        loc = _by_id(page, field_id)
        if loc.count() > 0 and loc.first.is_visible(timeout=2000):
            loc.first.fill(value)
            _log(f"  by id: found and filled")
            return True
    except Exception as e:
        _log(f"  by id: not found or error: {e}")
    # 2. By name (often same as id without form prefix)
    name_candidate = field_id.split(":")[-1] if ":" in field_id else field_id
    try:
        loc = page.locator(f'input[name="{field_id}"], input[name="{name_candidate}"], input[id="{field_id}"]')
        if loc.count() > 0 and loc.first.is_visible(timeout=1500):
            loc.first.fill(value)
            _log(f"  by name: found and filled")
            return True
    except Exception as e:
        _log(f"  by name: not found or error: {e}")
    # 3. By label
    if label_hint:
        try:
            page.get_by_label(label_hint, exact=False).first.fill(value, timeout=1500)
            _log(f"  by label {label_hint!r}: filled")
            return True
        except Exception as e:
            _log(f"  by label: not found or error: {e}")
    try:
        page.get_by_label(field_id, exact=False).first.fill(value, timeout=1000)
        _log(f"  by label (id as label): filled")
        return True
    except Exception:
        pass
    # 4. By placeholder
    try:
        page.locator(f'input[placeholder*="{name_candidate}" i]').first.fill(value, timeout=1000)
        _log(f"  by placeholder: filled")
        return True
    except Exception:
        pass
    _log(f"  FAILED: all fallbacks exhausted for {field_id}")
    return False


def _select_with_fallback(
    page: Page, section: str, field_id: str, value: str, label_hint: Optional[str] = None
) -> bool:
    """
    Select dropdown with fallbacks: by id (click + option), by label select_option.
    Logs each attempt. Returns True only if selected; False = all fallbacks failed.
    """
    if not value:
        return True
    value = str(value).strip()
    _log(f"Section {section}: selecting field id={field_id!r} value={value!r}")
    # 1. By id (click label, then click option)
    try:
        el = _by_id(page, field_id).first
        if el.is_visible(timeout=2000):
            el.click()
            time.sleep(0.5)
            opt = page.get_by_text(value, exact=False).first
            if opt.is_visible(timeout=2000):
                opt.click()
                _log(f"  by id + option text: selected")
                return True
            try:
                page.locator(f'li[data-label*="{value}" i]').first.click()
                _log(f"  by id + li[data-label]: selected")
                return True
            except Exception:
                pass
    except Exception as e:
        _log(f"  by id: not found or error: {e}")
    # 2. By label (select_option)
    if label_hint:
        try:
            page.get_by_label(label_hint, exact=False).first.select_option(value, timeout=1500)
            _log(f"  by label select_option: selected")
            return True
        except Exception as e:
            _log(f"  by label: not found or error: {e}")
    try:
        page.get_by_label(field_id, exact=False).first.select_option(value, timeout=1000)
        _log(f"  by label (id as label): selected")
        return True
    except Exception:
        pass
    _log(f"  FAILED: all fallbacks exhausted for {field_id}")
    return False


def _fill_one_field(page: Page, label_or_name: str, value: str) -> bool:
    """Try to fill a single field by label, name, or placeholder. Returns True if filled."""
    if not value:
        return False
    # By label (exact or partial)
    try:
        page.get_by_label(label_or_name, exact=False).first.fill(value, timeout=2000)
        return True
    except Exception:
        pass
    # By input name
    try:
        page.locator(f'input[name="{label_or_name}"], input[id="{label_or_name}"]').first.fill(value, timeout=2000)
        return True
    except Exception:
        pass
    # By placeholder
    try:
        page.locator(f'input[placeholder*="{label_or_name}" i]').first.fill(value, timeout=2000)
        return True
    except Exception:
        pass
    # Select by label (for dropdowns)
    try:
        page.get_by_label(label_or_name, exact=False).first.select_option(value, timeout=2000)
        return True
    except Exception:
        pass
    return False


def _build_fill_fields(data: FillApplicationRequest) -> Dict[str, str]:
    """Merge structured (DB-style) fields and raw 'fields' into one dict for form filling."""
    out: Dict[str, str] = {}
    structured = {
        "last_name": data.last_name,
        "first_name": data.first_name,
        "date_of_birth": data.date_of_birth,
        "place_of_birth": data.place_of_birth,
        "country_of_birth": data.country_of_birth,
        "nationality": data.nationality,
        "sex": data.sex,
        "marital_status": data.marital_status,
        "email": data.email,
        "phone": data.phone,
        "passport_number": data.passport_number,
        "passport_expiry_date": data.passport_expiry_date,
        "passport_issue_date": data.passport_issue_date,
        "passport_issuing_country": data.passport_issuing_country,
        "street": data.street,
        "house_number": data.house_number,
        "postal_code": data.postal_code,
        "city": data.city,
        "country": data.country,
    }
    for key, value in structured.items():
        if value is not None and str(value).strip():
            form_label = FRANCE_FIELD_MAP.get(key)
            if form_label:
                out[form_label] = str(value).strip()
    for key, value in (data.fields or {}).items():
        out[key] = str(value)
    return out


def run_fill_application(data: FillApplicationRequest) -> dict:
    """
    Open browser, (optionally) wait for you to log in manually, then fill the application form fields.
    No registration or login is done by the RPA – you log in yourself in the opened window.
    Request body: use 'fields' (raw label→value) and/or structured keys (last_name, first_name, etc.).
    """
    headless = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
    Path("debug_screenshots").mkdir(exist_ok=True)
    fields_to_fill = _build_fill_fields(data)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=80)
        context = browser.new_context(viewport={"width": 1400, "height": 900}, locale="en-US")
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            print("\n" + "="*50)
            print("FILL APPLICATION (as if logged in)")
            print("="*50)
            page.goto("https://application-form.france-visas.gouv.fr/fv-fo-dde", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            save_screenshot(page, "fill_step_0_landing")

            if data.wait_for_manual_login_seconds > 0:
                print(f"\n  → Log in manually in the browser. Waiting {data.wait_for_manual_login_seconds} seconds...")
                time.sleep(data.wait_for_manual_login_seconds)
                save_screenshot(page, "fill_step_1_after_manual_login")

            # Try to start a new application if we see a dashboard
            for btn_text in ["New application", "Start an application", "Create application", "Démarrer une demande", "Nouvelle demande", "Start", "Continue"]:
                clicked = False
                for role in ["button", "link"]:
                    try:
                        btn = page.get_by_role(role, name=btn_text).first
                        if btn.is_visible(timeout=1500):
                            btn.click()
                            time.sleep(3)
                            save_screenshot(page, "fill_step_2_after_start")
                            clicked = True
                            break
                    except Exception:
                        continue
                if clicked:
                    break

            # Fill each field (from structured + raw 'fields')
            filled = 0
            for label_or_name, value in fields_to_fill.items():
                if _fill_one_field(page, label_or_name, str(value)):
                    filled += 1
                    print(f"  ✓ Filled: {label_or_name}")
                else:
                    print(f"  ✗ Could not find field: {label_or_name}")
                time.sleep(0.2)

            screenshot_path = save_screenshot(page, "fill_step_3_filled")
            time.sleep(1)
            browser.close()

            return {
                "success": True,
                "message": f"Filled {filled} field(s). Check the browser / screenshot.",
                "fields_filled": filled,
                "screenshot_path": screenshot_path,
            }
        except Exception as e:
            save_screenshot(page, "fill_error")
            browser.close()
            return {
                "success": False,
                "message": str(e),
                "fields_filled": 0,
                "screenshot_path": None,
            }


def _click_button(page: Page, *names: str) -> bool:
    """Click first button/link that matches any of the given names (partial match)."""
    for name in names:
        try:
            btn = page.get_by_role("button", name=name).or_(page.get_by_role("link", name=name)).first
            if btn.is_visible(timeout=2000):
                btn.click()
                return True
        except Exception:
            pass
        try:
            btn = page.locator(f'button:has-text("{name}"), a:has-text("{name}"), span:has-text("{name}")').first
            if btn.is_visible(timeout=2000):
                btn.click()
                return True
        except Exception:
            pass
    return False


# Seconds to leave browser open on failure so user can inspect (no navigation back).
FAILURE_BROWSER_PAUSE_SECONDS = 120


def _fail_section(
    page: Page, section: str, field_id: str, pages_completed: int
) -> dict:
    """Log visible fields, save screenshot, pause so user can inspect (no navigation back), then return error."""
    _log(f"STOPPING: could not fill field {field_id!r} in section {section}")
    _log_visible_form_fields(page, section)
    path = save_screenshot(page, f"france_fail_{section}_{field_id.replace(':', '_')}")
    _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s so you can inspect (no navigation back).")
    time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
    return {
        "success": False,
        "message": f"Could not fill field {field_id} in section {section}. Check logs and screenshot.",
        "fields_filled": 0,
        "pages_completed": pages_completed,
        "screenshot_path": path,
    }


def run_fill_france_application_full(data: FranceFillRequest) -> dict:
    """
    Full France Schengen multi-step form: section by section. If any field is skipped (not filled), we STOP
    immediately, log what we see, save a screenshot, and return without closing the browser (no navigation back).
    Default wait_for_manual_login_seconds=0; set in body if you need time to log in.
    """
    headless = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
    Path("debug_screenshots").mkdir(exist_ok=True)
    d = data
    client_name = ((d.client_surname or "") + " " + (d.client_first_name or "")).strip() or "Employer"
    pages_completed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=80)
        context = browser.new_context(viewport={"width": 1400, "height": 900}, locale="en-US")
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            _log("FRANCE SCHENGEN – FULL FORM (section by section, stop on first skipped field)")
            _log(f"page.goto application-form.france-visas.gouv.fr")
            page.goto("https://application-form.france-visas.gouv.fr/fv-fo-dde", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            save_screenshot(page, "france_0_landing")
            _log(f"Landing page URL: {page.url}")

            if d.wait_for_manual_login_seconds > 0:
                _log(f"Waiting {d.wait_for_manual_login_seconds}s for manual login...")
                time.sleep(d.wait_for_manual_login_seconds)
                save_screenshot(page, "france_1_after_login")
                _log(f"After login URL: {page.url}")

            # Start new application (do not navigate back after this)
            for btn_text in ["New application", "Start an application", "Create application", "Démarrer une demande", "Nouvelle demande"]:
                if _click_button(page, btn_text):
                    _log(f"Clicked start button: {btn_text}")
                    time.sleep(3)
                    save_screenshot(page, "france_2_after_start")
                    _log(f"After start URL: {page.url}")
                    break

            # Detect login page: we must be on the application form, not Keycloak login
            current_url = page.url
            on_login_page = (
                "connect.france-visas.gouv.fr" in current_url
                or "openid-connect/auth" in current_url
                or (page.locator('input[name="username"], input[id="username"]').count() > 0 and page.locator("[id*='formStep1']").count() == 0)
            )
            if on_login_page:
                _log("STOPPING: You are still on the LOGIN page, not the application form.")
                _log("The form fields (formStep1, nationality, etc.) only exist AFTER you log in.")
                _log("Fix: Set wait_for_manual_login_seconds to 60 (or more), run again, and LOG IN in the browser during that wait. Then the RPA will fill the form.")
                _log_visible_form_fields(page, "login_page")
                path = save_screenshot(page, "france_still_on_login_page")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {
                    "success": False,
                    "message": "Still on login page. Set wait_for_manual_login_seconds (e.g. 60), run again, and log in when the browser opens. The form is only visible after login.",
                    "fields_filled": 0,
                    "pages_completed": 0,
                    "screenshot_path": path,
                }

            # ---------- Section 1: Your Plans ----------
            s1 = "1_Your_Plans"
            _log(f"--- Section {s1} ---")
            _log_visible_form_fields(page, s1)

            if d.current_nationality:
                # Form expects nationality label (Filipino, Lebanese), not country (Philippines, Lebanon)
                nationality_label = COUNTRY_TO_NATIONALITY_LABEL.get((d.current_nationality or "").strip()) or (d.current_nationality or "").strip()
                if not _select_with_fallback(page, s1, "formStep1:visas-selected-nationality_label", nationality_label, "Current nationality"):
                    return _fail_section(page, s1, "formStep1:visas-selected-nationality_label", pages_completed)
            if d.place_of_submission_country:
                if not _select_with_fallback(page, s1, "formStep1:Visas-selected-deposit-country_label", d.place_of_submission_country, "Place of submission"):
                    return _fail_section(page, s1, "formStep1:Visas-selected-deposit-country_label", pages_completed)
            if d.visa_type:
                # Normalize: "short stay" / "Short stay" -> "Short stay"; same for Long stay, Transit
                visa_label = VISA_TYPE_OPTIONS.get((d.visa_type or "").strip().lower()) or (d.visa_type or "").strip()
                if not _select_with_fallback(page, s1, "formStep1:Visas-selected-stayDuration_label", visa_label, "Visa type"):
                    return _fail_section(page, s1, "formStep1:Visas-selected-stayDuration_label", pages_completed)
            if d.main_destination:
                if not _select_with_fallback(page, s1, "formStep1:Visas-selected-destination_label", d.main_destination, "Main destination"):
                    return _fail_section(page, s1, "formStep1:Visas-selected-destination_label", pages_completed)
            if d.place_of_submission_country:
                if not _select_with_fallback(page, s1, "formStep1:Visas-selected-deposit-town_label", d.place_of_submission_country, "City of submission"):
                    return _fail_section(page, s1, "formStep1:Visas-selected-deposit-town_label", pages_completed)
            if d.issuing_authority_travel_document:
                if not _select_with_fallback(page, s1, "formStep1:Visas-selected-authority_label", d.issuing_authority_travel_document, "Issuing authority"):
                    return _fail_section(page, s1, "formStep1:Visas-selected-authority_label", pages_completed)
            if not _select_with_fallback(page, s1, "formStep1:Visas-dde-travel-document_label", "Ordinary passport", "Travel document"):
                return _fail_section(page, s1, "formStep1:Visas-dde-travel-document_label", pages_completed)
            if d.travel_document_number:
                if not _fill_with_fallback(page, s1, "formStep1:Visas-dde-travel-document-number", d.travel_document_number, "Travel document number"):
                    return _fail_section(page, s1, "formStep1:Visas-dde-travel-document-number", pages_completed)
            if d.passport_date_of_issue:
                if not _fill_with_fallback(page, s1, "formStep1:Visas-dde-release_date_real_input", d.passport_date_of_issue, "Date of issue"):
                    return _fail_section(page, s1, "formStep1:Visas-dde-release_date_real_input", pages_completed)
            if d.passport_expiry_date:
                if not _fill_with_fallback(page, s1, "formStep1:Visas-dde-expiration_date_input", d.passport_expiry_date, "Expiry date"):
                    return _fail_section(page, s1, "formStep1:Visas-dde-expiration_date_input", pages_completed)
            if not _select_with_fallback(page, s1, "formStep1:Visas-selected-purposeCategory_label", "Tourism", "Your plans"):
                return _fail_section(page, s1, "formStep1:Visas-selected-purposeCategory_label", pages_completed)
            if not _select_with_fallback(page, s1, "formStep1:Visas-selected-purpose_label", "Tourism / Private Visit", "Main purpose"):
                return _fail_section(page, s1, "formStep1:Visas-selected-purpose_label", pages_completed)

            time.sleep(0.5)
            save_screenshot(page, "france_p1_filled")
            if not _click_button(page, "Verify and then Next", "Verify", "Next"):
                _log("Could not click Verify and then Next")
                _log_visible_form_fields(page, s1)
                fail_path = save_screenshot(page, "france_fail_1_verify_next")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {"success": False, "message": "Could not click Verify and then Next", "fields_filled": 0, "pages_completed": 0, "screenshot_path": fail_path}
            time.sleep(3)
            pages_completed = 1
            save_screenshot(page, "france_p1_next")
            _log(f"Section {s1} done. URL: {page.url}")

            # ---------- Section 2: Your Information ----------
            s2 = "2_Your_Information"
            _log(f"--- Section {s2} ---")
            _log_visible_form_fields(page, s2)

            if d.sex:
                if not _select_with_fallback(page, s2, "formStep2:DDE002_102_label", d.sex, "Sex"):
                    return _fail_section(page, s2, "formStep2:DDE002_102_label", pages_completed)
            if d.marital_status:
                if not _select_with_fallback(page, s2, "formStep2:DDE002_104_label", d.marital_status, "Marital status"):
                    return _fail_section(page, s2, "formStep2:DDE002_104_label", pages_completed)
            if d.last_name:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-surname", d.last_name, "Last name"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-surname", pages_completed)
            if d.first_name:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-firstnames", d.first_name, "First name"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-firstnames", pages_completed)
            if d.place_of_birth:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-placeOfBirth", d.place_of_birth, "Place of birth"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-placeOfBirth", pages_completed)
            if d.date_of_birth:
                parts = d.date_of_birth.replace("-", "/").split("/")
                if len(parts) >= 3:
                    for sub_id, val in [
                        ("formStep2:visas-input-applicant-dayOfBirth", parts[0].zfill(2)),
                        ("formStep2:visas-input-applicant-monthOfBirth", parts[1].zfill(2)),
                        ("formStep2:visas-input-applicant-yearOfBirth", parts[2]),
                    ]:
                        if not _fill_with_fallback(page, s2, sub_id, val):
                            return _fail_section(page, s2, sub_id, pages_completed)
            if d.country_of_birth:
                if not _select_with_fallback(page, s2, "formStep2:visas-selected-countryOfBirth_label", d.country_of_birth, "Country of birth"):
                    return _fail_section(page, s2, "formStep2:visas-selected-countryOfBirth_label", pages_completed)
            if d.address:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-street", d.address, "Address"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-street", pages_completed)
            if d.city:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-place", d.city, "City"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-place", pages_completed)
            if d.country:
                if not _select_with_fallback(page, s2, "formStep2:visas-selected-applicant-country_label", d.country, "Country"):
                    return _fail_section(page, s2, "formStep2:visas-selected-applicant-country_label", pages_completed)
            if d.phone:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-phoneNumber", d.phone, "Telephone"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-phoneNumber", pages_completed)
            if d.email:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-email", d.email, "Email"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-email", pages_completed)
            if not _select_with_fallback(page, s2, "formStep2:visas-input-applicant-activity-occupation_label", "Manual worker", "Current job"):
                return _fail_section(page, s2, "formStep2:visas-input-applicant-activity-occupation_label", pages_completed)
            if d.sector:
                if not _select_with_fallback(page, s2, "formStep2:visas-input-applicant-activity-businessSegment_label", d.sector, "Sector"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-activity-businessSegment_label", pages_completed)
            if client_name:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-employer-name", client_name, "Name of employer"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-employer-name", pages_completed)
            if d.client_street:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-employer-street", d.client_street, "Address employer"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-employer-street", pages_completed)
            if d.client_city:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-applicant-employer-place", d.client_city, "City employer"):
                    return _fail_section(page, s2, "formStep2:visas-input-applicant-employer-place", pages_completed)
            if not _select_with_fallback(page, s2, "formStep2:visas-selected-applicant-employer-country_label", "United Arab Emirates", "Country employer"):
                return _fail_section(page, s2, "formStep2:visas-selected-applicant-employer-country_label", pages_completed)
            if d.client_phone:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-phoneNumber-employer", d.client_phone, "Telephone employer"):
                    return _fail_section(page, s2, "formStep2:visas-input-phoneNumber-employer", pages_completed)
            if d.client_email:
                if not _fill_with_fallback(page, s2, "formStep2:visas-input-email-employer", d.client_email, "Email employer"):
                    return _fail_section(page, s2, "formStep2:visas-input-email-employer", pages_completed)

            time.sleep(0.5)
            save_screenshot(page, "france_p2_filled")
            if not _click_button(page, "Next"):
                _log("Could not click Next on section 2")
                fail_path = save_screenshot(page, "france_fail_2_next")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {"success": False, "message": "Could not click Next (section 2)", "fields_filled": 0, "pages_completed": pages_completed, "screenshot_path": fail_path}
            time.sleep(3)
            pages_completed = 2
            save_screenshot(page, "france_p2_next")
            _log(f"Section {s2} done. URL: {page.url}")

            # ---------- Section 3: Your last Visa ----------
            s3 = "3_Your_last_Visa"
            _log(f"--- Section {s3} ---")
            _log_visible_form_fields(page, s3)
            if d.schengen_last_59_months is True:
                try:
                    page.locator(".ui-radiobutton-icon.ui-icon-bullet").first.click()
                except Exception:
                    page.locator('label:has-text("Yes")').first.click()
                time.sleep(0.3)
                if d.valid_visa_start:
                    if not _fill_with_fallback(page, s3, "formStep3:valid-visa-start_input", d.valid_visa_start):
                        return _fail_section(page, s3, "formStep3:valid-visa-start_input", pages_completed)
                if d.valid_visa_end:
                    if not _fill_with_fallback(page, s3, "formStep3:valid-visa-end_input", d.valid_visa_end):
                        return _fail_section(page, s3, "formStep3:valid-visa-end_input", pages_completed)
            else:
                try:
                    page.locator(".ui-radiobutton-icon.ui-icon-blank").first.click()
                except Exception:
                    page.locator('label:has-text("No")').first.click()
            time.sleep(0.5)
            save_screenshot(page, "france_p3_filled")
            if not _click_button(page, "Next"):
                fail_path = save_screenshot(page, "france_fail_3_next")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {"success": False, "message": "Could not click Next (section 3)", "fields_filled": 0, "pages_completed": pages_completed, "screenshot_path": fail_path}
            time.sleep(3)
            pages_completed = 3
            _log(f"Section {s3} done. URL: {page.url}")

            # ---------- Section 4: Your Stay ----------
            s4 = "4_Your_Stay"
            _log(f"--- Section {s4} ---")
            _log_visible_form_fields(page, s4)
            if d.arrival_date:
                if not _fill_with_fallback(page, s4, "formStep4:date-of-arrival_input", d.arrival_date, "Arrival date"):
                    return _fail_section(page, s4, "formStep4:date-of-arrival_input", pages_completed)
            if d.departure_date:
                if not _fill_with_fallback(page, s4, "formStep4:date-of-departure_input", d.departure_date, "Departure date"):
                    return _fail_section(page, s4, "formStep4:date-of-departure_input", pages_completed)
            if d.number_of_entries:
                if not _select_with_fallback(page, s4, "formStep4:visas-selected-applicant-country_label", d.number_of_entries, "Number of entries"):
                    return _fail_section(page, s4, "formStep4:visas-selected-applicant-country_label", pages_completed)
            if d.number_of_stays:
                if not _fill_with_fallback(page, s4, "formStep4:visas-input-applicant-numberOfStays_input", d.number_of_stays, "Number of stays"):
                    return _fail_section(page, s4, "formStep4:visas-input-applicant-numberOfStays_input", pages_completed)
            time.sleep(0.5)
            save_screenshot(page, "france_p4_filled")
            if not _click_button(page, "Next"):
                fail_path = save_screenshot(page, "france_fail_4_next")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {"success": False, "message": "Could not click Next (section 4)", "fields_filled": 0, "pages_completed": pages_completed, "screenshot_path": fail_path}
            time.sleep(3)
            pages_completed = 4
            _log(f"Section {s4} done. URL: {page.url}")

            # ---------- Section 5: Your contacts ----------
            s5 = "5_Your_contacts"
            _log(f"--- Section {s5} ---")
            _log_visible_form_fields(page, s5)
            try:
                page.locator(".ui-chkbox-box.ui-widget").first.click()
            except Exception:
                page.get_by_text("A person will be accommodating me", exact=False).first.click()
            time.sleep(0.3)
            if d.client_surname:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-surname", d.client_surname, "Host name"):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-surname", pages_completed)
            if d.client_first_name:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-firstnames", d.client_first_name, "Host first name"):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-firstnames", pages_completed)
            if d.client_street:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-address", d.client_street):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-address", pages_completed)
            if d.client_city:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-place", d.client_city):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-place", pages_completed)
            if d.client_country:
                if not _select_with_fallback(page, s5, "formStep5:visas-selected-hostPerson-country", d.client_country, "Host country"):
                    return _fail_section(page, s5, "formStep5:visas-selected-hostPerson-country", pages_completed)
            if d.client_phone:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-phoneNumber", d.client_phone):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-phoneNumber", pages_completed)
            if d.client_email:
                if not _fill_with_fallback(page, s5, "formStep5:visas-input-applicant-hostPerson-email", d.client_email):
                    return _fail_section(page, s5, "formStep5:visas-input-applicant-hostPerson-email", pages_completed)
            try:
                page.locator(".ui-chkbox-icon.ui-icon-check").first.click()
            except Exception:
                pass
            time.sleep(0.5)
            save_screenshot(page, "france_p5_filled")
            if not _click_button(page, "Next"):
                fail_path = save_screenshot(page, "france_fail_5_next")
                _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection.")
                time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
                return {"success": False, "message": "Could not click Next (section 5)", "fields_filled": 0, "pages_completed": pages_completed, "screenshot_path": fail_path}
            time.sleep(3)
            pages_completed = 5
            _log(f"Section {s5} done. URL: {page.url}")

            # ---------- Last: Continue → declare → popup → Next ----------
            _log("--- Last page ---")
            _click_button(page, "Continue")
            time.sleep(2)
            try:
                page.locator(".ui-chkbox-box.ui-widget.ui-corner-all.ui-state-default").first.click()
            except Exception:
                page.get_by_text("correct and complete", exact=False).first.click()
            time.sleep(1)
            _click_button(page, "Continue", "Next")
            time.sleep(2)
            try:
                page.get_by_role("button", name="Continue").first.click()
            except Exception:
                pass
            time.sleep(2)
            _click_button(page, "Next")
            save_screenshot(page, "france_final")

            browser.close()
            return {
                "success": True,
                "message": f"France form completed through page {pages_completed}. Check screenshots.",
                "fields_filled": 0,
                "pages_completed": pages_completed,
                "screenshot_path": str(Path("debug_screenshots") / "france_final.png"),
            }
        except Exception as e:
            _log(f"Exception: {e}")
            _log_visible_form_fields(page, "error")
            path = save_screenshot(page, "france_error")
            _log(f"Browser left open for {FAILURE_BROWSER_PAUSE_SECONDS}s for inspection (no navigation back).")
            time.sleep(FAILURE_BROWSER_PAUSE_SECONDS)
            return {
                "success": False,
                "message": str(e),
                "fields_filled": 0,
                "pages_completed": pages_completed,
                "screenshot_path": path,
            }


# ============== ENDPOINTS ==============

@app.post("/register-and-verify", response_model=FlowResponse)
async def register_and_verify(data: FullFlowRequest):
    """
    Full automated flow:
    1. Register new account
    2. Wait for verification email (via IMAP)
    3. Click verification link
    4. Login
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_full_flow, data)
    return FlowResponse(**result)


@app.post("/login", response_model=FlowResponse)
async def login(data: LoginRequest):
    """Login with already verified account."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_login_only, data)
    return FlowResponse(**result)


@app.post("/fill-application", response_model=FillApplicationResponse)
async def fill_application(data: FillApplicationRequest):
    """
    Fill the visa application form as if you are already logged in.
    Opens the browser; you log in manually during the wait, then the RPA fills the fields you pass in `fields`.
    No registration or login is performed by the API.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_fill_application, data)
    return FillApplicationResponse(**result)


@app.post("/fill-application/full", response_model=FillApplicationResponse)
async def fill_application_full(data: FranceFillRequest):
    """
    Full France Schengen multi-step form (Page 1–5 + final).
    You log in manually during wait_for_manual_login_seconds; then the RPA fills all pages with your data and hardcoded values (see FIELDS_TO_FILL.md).
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_fill_france_application_full, data)
    return FillApplicationResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "france-visas-automation", "version": "2.0"}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🇫🇷 FRANCE-VISAS AUTOMATION API")
    print("="*60)
    print("\nEndpoints:")
    print("  POST /register-and-verify - Full flow (register + verify + login)")
    print("  POST /login               - Login only")
    print("  POST /fill-application       - Fill form (manual login + fields)")
    print("  POST /fill-application/full - Full France form (Page 1–5 + final)")
    print("  GET  /health              - Health check")
    port = int(os.environ.get("PORT", 8000))
    print(f"\nDocs: http://localhost:{port}/docs")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)

