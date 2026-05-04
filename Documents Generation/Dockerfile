# Documents Generation API – Railway
FROM python:3.11-slim

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=300

# LibreOffice headless for .docx → .pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Patch letter templates with {{addressee}} placeholder (idempotent).
RUN python scripts/patch_addressee_placeholder.py

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port \"$PORT\""]
