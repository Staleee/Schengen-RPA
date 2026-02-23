# Germany VIDEX RPA API – Railway
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300
ENV DEBIAN_FRONTEND=noninteractive
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + system deps (non-interactive for Railway)
RUN playwright install chromium --with-deps

# Copy application code last
COPY . .

ENV PORT=8000
ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "src.api"]
