# Germany VIDEX RPA – used when building from repo root (Railway Germany service)
# Railway uses this instead of Railpack when Root Directory is empty.
# France service should use Root Directory = "france schengen visa application rpa" (has its own Dockerfile).
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=300

COPY "germany schengen visa application rpa/requirements.txt" .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

COPY "germany schengen visa application rpa" .

ENV PORT=8000
ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "src.api"]
