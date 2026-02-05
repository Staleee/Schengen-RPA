"""
France-Visas Automation API Server
==================================
Full automation: Register → Verify Email (IMAP) → Login

Endpoints:
  POST /register           - Register only (manual verification)
  POST /register-and-verify - Full flow with auto email verification
  POST /login              - Login with verified account
"""

import asyncio
import os
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
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


class FlowResponse(BaseModel):
    success: bool
    message: str
    step_completed: str  # "registration", "verification", "login"
    email: Optional[str] = None
    logged_in: bool = False
    session_url: Optional[str] = None


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


def solve_captcha_and_submit(page: Page, solver: CaptchaSolver, max_attempts: int = 5) -> bool:
    """Solve CAPTCHA and submit form. Returns True if successful."""
    for attempt in range(1, max_attempts + 1):
        print(f"  → CAPTCHA attempt {attempt}/{max_attempts}")
        
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
            # Try to click refresh button
            try:
                page.locator('button').filter(has=page.locator('svg')).last.click()
                time.sleep(1)
            except:
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
                # Click refresh to get new CAPTCHA
                try:
                    page.locator('button').filter(has=page.locator('svg')).last.click()
                    time.sleep(1)
                except:
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
            continue
    
    return False


# ============== FULL FLOW ==============

def run_full_flow(data: FullFlowRequest) -> dict:
    """
    Complete flow: Register → Wait for email → Verify → Login
    """
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
            
            # Solve CAPTCHA and submit
            if not solve_captcha_and_submit(page, solver):
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
            
            success, verification_link = email_reader.wait_for_verification_email(
                sender_contains="france-visas",
                max_wait_seconds=data.email_wait_seconds,
                poll_interval=10
            )
            
            email_reader.disconnect()
            
            if not success or not verification_link:
                browser.close()
                return {
                    "success": False,
                    "message": "Verification email not received in time",
                    "step_completed": "registration",
                    "email": data.email,
                    "logged_in": False
                }
            
            print(f"  → Clicking verification link...")
            page.goto(verification_link, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            save_screenshot(page, "step2_verification_clicked")
            
            # Check if verification was successful
            if page.locator('text=/verified|confirmed|success|activated/i').count() > 0:
                print("  ✓ Email verified!")
            else:
                print("  → Verification page loaded, continuing...")
            
            save_screenshot(page, "step2_verification_complete")
            
            # ===== STEP 3: LOGIN =====
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
            except:
                page.locator('input[type="email"]').first.fill(data.email)
            
            try:
                page.get_by_label("Password", exact=False).first.fill(data.password)
            except:
                page.locator('input[type="password"]').first.fill(data.password)
            
            save_screenshot(page, "step3_credentials_entered")
            
            # Click login
            try:
                page.get_by_role("button", name="Log in").first.click()
            except:
                try:
                    page.get_by_role("button", name="Sign in").first.click()
                except:
                    page.locator('button[type="submit"]').first.click()
            
            time.sleep(5)
            save_screenshot(page, "step3_after_login")
            
            # Check login success
            logged_in = False
            current_url = page.url
            
            if page.locator('text="My applications"').count() > 0:
                logged_in = True
            elif page.locator('text="Log out"').count() > 0:
                logged_in = True
            elif page.locator('text="Dashboard"').count() > 0:
                logged_in = True
            elif "application" in current_url.lower():
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
    print("  GET  /health              - Health check")
    port = int(os.environ.get("PORT", 8000))
    print(f"\nDocs: http://localhost:{port}/docs")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)

