# Germany VIDEX RPA API – Railway
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300
ENV DEBIAN_FRONTEND=noninteractive
# Reuse Chromium that ships in the base image (matches pinned playwright==1.40.0).
# Re-running `playwright install` here would download a different Chromium for
# whichever playwright pip resolved, which is what broke VIDEX automation after
# the ZERP-55 redeploy. Skip it.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application code last
COPY . .

ENV PORT=8000
ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "src.api"]
