FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

COPY app/ ./app/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Directory dati nel volume
RUN mkdir -p /app/data/outputs /app/data/logs /app/data/templates

EXPOSE 8000

# Tune gunicorn via env, enforce via entrypoint
ENV WEB_CONCURRENCY=1 \
    GUNICORN_TIMEOUT=1800 \
    GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker \
    GUNICORN_KEEPALIVE=75 \
    GUNICORN_GRACEFUL_TIMEOUT=120

CMD ["/app/entrypoint.sh"]
