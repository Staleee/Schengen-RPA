# Testing the France RPA

## 0a. Full France form (multi-step) – POST /fill-application/full

Use this to run the **entire** France Schengen form (Page 1 → … → Page 5 → Continue → declare → Next).

**Behavior:** If you use `wait_for_manual_login_seconds: 0`, you must already be logged in before calling the API. If the RPA sees the **login page** (connect.france-visas.gouv.fr), it stops and tells you: set `wait_for_manual_login_seconds: 60` (or more), run again, and **log in in the browser** during that wait. The sample body uses 60 so you have time to log in when testing. Section by section: if **any field is skipped** (could not be filled), the RPA **stops immediately**, logs what it sees (section, URL, visible field ids), saves a screenshot, and leaves the **browser open for 120 seconds** so you can inspect (no navigation back). Each field is tried by **id → name → label → placeholder** (fallback); all attempts are logged to the console.

1. Start the server: `python api_server.py` (browser visible).
2. Open **http://localhost:8000/docs** → **POST /fill-application/full**.
3. Click "Try it out" and paste the body from **SAMPLE_REQUEST_BODY.json** (or see REQUEST_BODY_REFERENCE.md §5).
4. Click **Execute**. A Chromium window opens; **log in manually** within the wait time.
5. The RPA then fills Page 1 (Your Plans), clicks "Verify and then Next", fills Page 2 (Your Information), … through Page 5 (Your contacts), then Continue → declare → popup → Next (download).

Screenshots: `debug_screenshots/france_*.png` (e.g. `france_p1_filled.png`, `france_final.png`).

---

## 0b. Fill application only (no registration/login) – POST /fill-application

To **skip registration and login** and only fill the form as if you're already logged in:

1. Start the server: `python api_server.py` (browser visible).
2. Open **http://localhost:8000/docs** → **POST /fill-application**.
3. Click "Try it out" and use a body like:

```json
{
  "wait_for_manual_login_seconds": 60,
  "fields": {
    "Last name": "Test",
    "First name": "User",
    "Email": "you@example.com"
  }
}
```

4. Click **Execute**. A Chromium window opens and goes to France-Visas.
5. **Log in manually** in that window within 60 seconds (use your real account).
6. After the wait, the RPA will try to click "New application" (or similar) and fill the `fields` you provided. Keys in `fields` are matched to form labels or input names (e.g. `"Last name"`, `"First name"`, `"lastName"`, etc.).

Screenshots are saved in `debug_screenshots/` (e.g. `fill_step_1_after_manual_login.png`, `fill_step_3_filled.png`).

---

## 1. Run the API locally (see the browser)

From the **france schengen visa application rpa** folder:

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\france schengen visa application rpa"
pip install -r requirements.txt
playwright install chromium
```

**Windows:** Install Tesseract and add it to PATH: https://github.com/UB-Mannheim/tesseract/wiki

Then start the server **with the browser visible** (don’t set `HEADLESS`):

```powershell
python api_server.py
```

You should see:
- `🇫🇷 FRANCE-VISAS AUTOMATION API`
- `Docs: http://localhost:8000/docs`
- Server listening on port 8000

---

## 2. Quick checks (no real registration)

- **Health:** Open in browser: http://localhost:8000/health  
  Expected: `{"status":"ok","service":"france-visas-automation","version":"2.0"}`

- **Docs:** Open: http://localhost:8000/docs  
  Use Swagger to see endpoints and try **POST /register-and-verify** with a test body.

---

## 3. Full flow test (register + verify + login)

You need **one real email** with **IMAP** (e.g. Gmail with an App Password).

**Option A – Browser (e.g. Postman or Thunder Client)**

1. **POST** `http://localhost:8000/register-and-verify`
2. **Headers:** `Content-Type: application/json`
3. **Body (raw JSON):**

```json
{
  "last_name": "Test",
  "first_name": "User",
  "email": "YOUR_REAL_EMAIL@gmail.com",
  "password": "YourSecurePassword123!",
  "language": "English",
  "email_password": "YOUR_GMAIL_APP_PASSWORD",
  "imap_server": "imap.gmail.com",
  "imap_port": 993,
  "imap_use_ssl": true,
  "email_wait_seconds": 300
}
```

Replace `YOUR_REAL_EMAIL@gmail.com` and `YOUR_GMAIL_APP_PASSWORD`. For Gmail: use an [App Password](https://myaccount.google.com/apppasswords), not your normal password.

**Option B – cURL (PowerShell)**

```powershell
curl -X POST "http://localhost:8000/register-and-verify" `
  -H "Content-Type: application/json" `
  -d '{\"last_name\":\"Test\",\"first_name\":\"User\",\"email\":\"YOUR_EMAIL@gmail.com\",\"password\":\"YourSecurePassword123!\",\"language\":\"English\",\"email_password\":\"YOUR_APP_PASSWORD\",\"imap_server\":\"imap.gmail.com\",\"imap_port\":993,\"imap_use_ssl\":true,\"email_wait_seconds\":300}'
```

---

## 4. What you should see

1. A **Chromium window** opens (because you didn’t set `HEADLESS=true`).
2. It goes to France-Visas → application form → **Create an account**.
3. Form is filled: last name, first name, email, email confirmation, password, password confirmation, language.
4. CAPTCHA is solved and the form is submitted.
5. The script connects to your email (IMAP), waits for the France-Visas verification email, and opens the verification link in the same tab.
6. Then it goes to the login page, fills email + password, and clicks **Log in**.
7. The API returns JSON with `success`, `message`, `logged_in`, `session_url`.

If something fails, check the **terminal** for errors and the **browser** to see which step failed. Screenshots are saved in `debug_screenshots/`.

---

## 5. Test the deployed API (Railway)

Same as above, but use your **France Railway URL** instead of `http://localhost:8000`:

**POST** `https://YOUR-FRANCE-URL.up.railway.app/register-and-verify`  
with the same JSON body. On Railway the browser runs headless (no window), but the response and logs will show success or failure.
