#!/bin/sh
# Ensure we are in /app
cd /app

: ${WEB_CONCURRENCY:=1}
: ${GUNICORN_TIMEOUT:=1800}
: ${GUNICORN_WORKER_CLASS:=uvicorn.workers.UvicornWorker}
: ${GUNICORN_KEEPALIVE:=75}
: ${GUNICORN_GRACEFUL_TIMEOUT:=120}

exec gunicorn app.main:app \
  --bind 0.0.0.0:8000 \
  --workers ${WEB_CONCURRENCY} \
  --worker-class ${GUNICORN_WORKER_CLASS} \
  --timeout ${GUNICORN_TIMEOUT} \
  --keep-alive ${GUNICORN_KEEPALIVE} \
  --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT}
