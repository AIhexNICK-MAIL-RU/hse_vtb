# Единый образ для PaaS (Timeweb и т.п.): один процесс uvicorn на 0.0.0.0:$PORT,
# API под /api, статика SPA из dist, /health на корне для healthcheck.
# sklearn подгружается только при ingest/explain — быстрее bind порта после старта.

FROM node:20-alpine AS frontend
WORKDIR /src
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.13-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    GEOATM_DATA_DIR=/data \
    GEOATM_AUTO_INGEST=1 \
    GEOATM_API_PREFIX=/api \
    GEOATM_STATIC_DIR=/app/static

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY backend/config /app/config

COPY --from=frontend /src/dist /app/static

COPY deploy/start.sh /app/deploy/start.sh
RUN chmod +x /app/deploy/start.sh

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=20 \
  CMD python -c "import os,urllib.request; from pathlib import Path; raw=Path('/tmp/.geoatm_listen_port').read_text().strip() if Path('/tmp/.geoatm_listen_port').is_file() else (os.environ.get('PORT') or '8080'); p=int(raw) if raw.isdigit() else 8080; urllib.request.urlopen(f'http://127.0.0.1:{p}/', timeout=4).read(65536)"

CMD ["/app/deploy/start.sh"]
