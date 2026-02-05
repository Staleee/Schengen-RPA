# France-Visas RPA API – Playwright + EasyOCR
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (required for browser automation)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Railway sets PORT; use headless browser in production
ENV PORT=8000
ENV HEADLESS=true

EXPOSE 8000

# Run the API server (Railway injects PORT at runtime)
CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT}
