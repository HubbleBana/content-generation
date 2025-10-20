# backend/Dockerfile — FIX stabile per SSE e stato in-memory
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Directory dati nel volume
RUN mkdir -p /app/data/outputs /app/data/logs /app/data/templates

EXPOSE 8000

# 🔧 Avvio con uvicorn single-process per evitare desincronizzazioni tra worker
#   - http keep-alive e timeouts alzati per stream SSE lunghi
#   - no-reload in produzione
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--timeout-keep-alive", "120", "--limit-concurrency", "100"]
