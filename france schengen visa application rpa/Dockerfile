# France-Visas RPA API – Tesseract OCR (image under 4GB for Railway)
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300

# Install Tesseract OCR (small; no PyTorch/EasyOCR)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps (no torch, no easyocr)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium for Playwright
RUN playwright install chromium --with-deps

# Copy application code last
COPY . .

ENV PORT=8000
ENV HEADLESS=true
EXPOSE 8000

CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT}
