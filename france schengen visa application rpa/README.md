# France-Visas Registration Automation 🇫🇷

Fully automated RPA script for France-Visas account registration — including **automatic CAPTCHA solving**.

## Features

- ✅ Automatically fills all registration fields
- ✅ **Automatic CAPTCHA solving** using:
  - Tesseract OCR (free, local)
  - OpenAI GPT-4 Vision (more accurate, requires API key)
- ✅ Retry logic for failed attempts
- ✅ Falls back to manual input if automatic solving fails

## Prerequisites

- Python 3.8+
- Tesseract OCR (for local OCR solving)
- OpenAI API key (optional, for AI-powered solving)

### Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download installer from: https://github.com/UB-Mannheim/tesseract/wiki

## Installation

1. **Install Python dependencies:**

```bash
cd "/Users/saharsabbagh/Desktop/france schengen visa application rpa"
pip install -r requirements.txt
```

2. **Install Playwright browsers:**

```bash
playwright install chromium
```

## Configuration

Edit `config.json`:

```json
{
    "registration": {
        "last_name": "YOUR_LAST_NAME",
        "first_name": "YOUR_FIRST_NAME",
        "email": "your.email@example.com",
        "password": "YourSecurePassword123!",
        "language": "English"
    },
    "captcha": {
        "openai_api_key": "sk-your-openai-api-key",
        "max_attempts": 3,
        "save_debug_images": true
    },
    "settings": {
        "headless": false,
        "slow_mo": 100,
        "timeout": 30000
    }
}
```

### CAPTCHA Solving Options

The script uses a two-tier approach:

1. **Tesseract OCR (Free)** - Tries local OCR first
2. **OpenAI GPT-4 Vision (Paid)** - Falls back to AI if OCR fails

To use OpenAI Vision:
- Get an API key from https://platform.openai.com
- Add it to `config.json` under `captcha.openai_api_key`
- Or set environment variable: `export OPENAI_API_KEY=sk-your-key`

### Password Requirements

- At least 12 characters
- At least 1 lowercase letter
- At least 1 uppercase letter
- At least 1 number
- Special characters permitted (except: % & < > = | ')

## Usage

```bash
python france_visa_registration.py
```

With custom URL:

```bash
python france_visa_registration.py "https://connect.france-visas.gouv.fr/realms/usager/login-actions/registration?client_id=fv-fo-keycloak-web&tab_id=YOUR_TAB_ID"
```

## How It Works

1. 🌐 Opens browser and navigates to registration page
2. 📝 Fills in all form fields from config
3. 📸 Captures screenshot of CAPTCHA image
4. 🔍 Analyzes image using OCR/AI to extract text
5. ⌨️ Enters the solved CAPTCHA code
6. 📤 Submits the form
7. 🔄 Retries if CAPTCHA was wrong (up to 3 attempts)
8. ⏸️ Falls back to manual input if all else fails

## Debug Output

CAPTCHA images are saved to `captcha_debug/` folder:
- `original_captcha.png` - Raw CAPTCHA image
- `preprocessed_captcha.png` - After image processing
- `captured_captcha.png` - Screenshot from browser

## Troubleshooting

### Tesseract not found
Make sure Tesseract is installed and in your PATH:
```bash
tesseract --version
```

### CAPTCHA solving accuracy is low
- Try adding your OpenAI API key for GPT-4 Vision
- The debug images in `captcha_debug/` can help diagnose issues

### Session expired
The registration URL contains session tokens. Get a fresh URL from:
https://france-visas.gouv.fr

### Element not found
The website structure may have changed. Check the selectors in the script.

## File Structure

```
france schengen visa application rpa/
├── france_visa_registration.py  # Main automation script
├── captcha_solver.py            # CAPTCHA solving module
├── config.json                  # User configuration
├── requirements.txt             # Python dependencies
├── README.md                    # This file
└── captcha_debug/               # Debug images (created at runtime)
```

## Legal Disclaimer

This tool is for educational and personal use only. Ensure compliance with France-Visas terms of service. Do not use for unauthorized automation or to circumvent security measures.
