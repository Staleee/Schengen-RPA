# Turkey Schengen API — LibreOffice required for POST /fill-docx-pdf on Linux (Railway).
# In Railway: set the service root directory to this folder (turkey schengen visa application rpa).

FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        fontconfig \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Railway sets PORT; default 8092 for local docker run
CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8092}"]
