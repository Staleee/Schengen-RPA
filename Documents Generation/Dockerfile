# Documents Generation API – Railway
FROM python:3.11-slim

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=300

# LibreOffice headless for .docx → .pdf.
#
# Fonts matter as much as LibreOffice itself, and BOTH families are needed:
#
#   fonts-liberation  — Liberation Sans/Serif are metric-compatible stand-ins for Arial and
#                       Times New Roman. Without them the image had only DejaVu, so the client
#                       NOC asked for Arial and came out in DejaVu *Serif*: sans-serif text
#                       printed as serif.
#   fonts-dejavu-core — the only Arabic coverage here, used by the maid NOC's Arabic page.
#                       Liberation has none, and libreoffice-core satisfies its font dependency
#                       with whichever alternative is present: asking for Liberation alone
#                       dropped DejaVu and the whole Arabic page rendered as empty boxes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-core \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Patch letter templates with {{addressee}} placeholder (idempotent).
RUN python scripts/patch_addressee_placeholder.py

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port \"$PORT\""]
