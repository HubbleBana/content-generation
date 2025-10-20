FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl git dos2unix && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

COPY app/ ./app/
COPY entrypoint.sh /app/entrypoint.sh
# Normalize line endings in case of CRLF and ensure executable
RUN dos2unix /app/entrypoint.sh || true && chmod +x /app/entrypoint.sh

# Data dirs
RUN mkdir -p /app/data/outputs /app/data/logs /app/data/templates

EXPOSE 8000

ENV WEB_CONCURRENCY=1 \
    GUNICORN_TIMEOUT=1800 \
    GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker \
    GUNICORN_KEEPALIVE=75 \
    GUNICORN_GRACEFUL_TIMEOUT=120

CMD ["/bin/sh", "/app/entrypoint.sh"]
