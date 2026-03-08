# Documents Generation API – Railway
FROM python:3.11-slim

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=300

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn api_server:app --host 0.0.0.0 --port \"$PORT\""]
