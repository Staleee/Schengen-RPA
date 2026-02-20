# Separate environments for each Schengen RPA

Each Schengen app has its **own virtual environment** so you can run France and Germany in isolation (no dependency conflicts).

---

## Quick setup (one-time per project)

### France

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\france schengen visa application rpa"
.\setup_env.ps1
```

This creates `.venv`, installs France’s dependencies, and installs Playwright Chromium.

**Windows – Tesseract (for CAPTCHA):** Install and add to PATH: https://github.com/UB-Mannheim/tesseract/wiki

### Germany

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\germany schengen visa application rpa"
.\setup_env.ps1
```

This creates `.venv`, installs Germany’s dependencies, and installs Playwright Chromium.

---

## Run each app (after setup)

### France

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\france schengen visa application rpa"
.\.venv\Scripts\Activate.ps1
python api_server.py
```

Then open: http://localhost:8000/docs

**Or without activating:**  
` .\.venv\Scripts\python api_server.py `

### Germany

```powershell
cd "c:\Users\user\Desktop\maids.cc\RPAs\germany schengen visa application rpa"
.\.venv\Scripts\Activate.ps1
python -m src.api
```

Then open: http://localhost:8000/docs (or use port 8000 if France isn’t running).

**Or without activating:**  
` .\.venv\Scripts\python -m src.api `

---

## Summary

| Project  | Folder                          | Venv        | Run command                    |
|----------|----------------------------------|-------------|---------------------------------|
| France   | `france schengen visa application rpa` | `.venv`     | `python api_server.py`         |
| Germany  | `germany schengen visa application rpa` | `.venv`     | `python -m src.api`            |

Each folder has its own `.venv`; they don’t share dependencies. Run the setup script once per project, then use the run commands above whenever you want to test that app.
