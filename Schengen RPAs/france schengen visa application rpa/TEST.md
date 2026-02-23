# Testing the France RPA

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
