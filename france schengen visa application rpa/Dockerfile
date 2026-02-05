# France-Visas RPA API – optimized for Railway (faster build, pip cache)
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Longer pip timeout so large packages (torch, easyocr) don't fail
ENV PIP_DEFAULT_TIMEOUT=300

# Copy requirements first for better caching
COPY requirements.txt .

# Install torch (CPU) first so easyocr reuses it – cached layer when only code changes
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install rest of Python deps (easyocr skips torch)
RUN pip install --no-cache-dir -r requirements.txt

# Single step: Chromium + system deps (faster than two RUNs)
RUN playwright install chromium --with-deps

# Copy application code last so code changes don't invalidate heavy layers
COPY . .

ENV PORT=8000
ENV HEADLESS=true
EXPOSE 8000

CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT}
