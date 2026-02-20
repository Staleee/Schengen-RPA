# France-Visas RPA 🇫🇷

API for France-Visas registration, email verification, and login.

## Setup

From the **france schengen visa application rpa** folder:

- **PowerShell:** `.\setup_env.ps1`
- **CMD:** `setup_env.bat`

Then run: `.\.venv\Scripts\python api_server.py` (or activate venv and `python api_server.py`).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/register-and-verify` | Full flow: register → verify email (IMAP) → login |
| POST | `/login` | Login only (verified account) |

Request bodies use **snake_case** (e.g. `last_name`, `first_name`, `email`, `password`, `language`, `email_password`, `imap_server`, `imap_port`, `imap_use_ssl`, `email_wait_seconds`).

## Testing

See **TEST.md** for request body examples, Gmail IMAP settings, and curl/Postman steps.

## File structure

```
france schengen visa application rpa/
├── api_server.py      # FastAPI server
├── captcha_solver.py  # CAPTCHA (ddddocr / EasyOCR / Tesseract)
├── email_helper.py    # IMAP verification link/code
├── requirements.txt
├── setup_env.ps1 / setup_env.bat
├── TEST.md
├── Dockerfile         # For Railway deploy
└── railway.json
```

## Legal

For authorized use only. Comply with France-Visas terms of service.
