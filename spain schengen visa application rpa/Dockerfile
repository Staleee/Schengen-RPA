# Schengen visa-application filler (Spain + the additional country templates).
# Production deploys via railpack.json; this image is the same service, used by
# tests/docker-compose.yml to exercise the live HTTP endpoint.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8090
EXPOSE 8090

CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT}"]
