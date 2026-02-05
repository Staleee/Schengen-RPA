# Schengen RPA – Unified API (France + Germany)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy root requirements and unified API
COPY requirements.txt .
COPY schengen_api.py .

# Copy France app
COPY "france schengen visa application rpa" "france schengen visa application rpa"

# Copy Germany app (including output/ for defaults/schema)
COPY "germany schengen visa application rpa" "germany schengen visa application rpa"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (both France and Germany use it)
RUN playwright install chromium
RUN playwright install-deps chromium

# Railway: PORT set at runtime; headless for France RPA
ENV PORT=8000
ENV HEADLESS=true

EXPOSE 8000

CMD uvicorn schengen_api:app --host 0.0.0.0 --port ${PORT}
