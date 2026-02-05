# Schengen RPA – Unified API (France + Germany)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy root requirements and unified API
COPY requirements.txt .
COPY schengen_api.py .

# Copy France app (JSON form handles paths with spaces)
COPY ["france schengen visa application rpa", "france schengen visa application rpa"]

# Copy Germany app (including output/ for defaults/schema)
COPY ["germany schengen visa application rpa", "germany schengen visa application rpa"]

# Install CPU-only PyTorch first (EasyOCR uses it; CPU build is ~1GB smaller)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies (opencv-headless + no GUI deps)
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium only (both apps use it)
RUN playwright install chromium && playwright install-deps chromium

# Shrink image: remove pip and Playwright caches
RUN rm -rf /root/.cache/pip /root/.cache/ms-playwright 2>/dev/null; true

# Railway: PORT set at runtime; headless for France RPA
ENV PORT=8000
ENV HEADLESS=true

EXPOSE 8000

CMD uvicorn schengen_api:app --host 0.0.0.0 --port ${PORT}
