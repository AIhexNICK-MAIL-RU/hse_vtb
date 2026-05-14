# Единый образ для PaaS (Timeweb и т.п.): uvicorn на 0.0.0.0:8080 (см. GEOATM_BIND_INTERNAL_8080),
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
    PIP_ROOT_USER_ACTION=ignore \
    PORT=8080 \
    GEOATM_BIND_INTERNAL_8080=1 \
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
COPY deploy/healthcheck.py /app/deploy/healthcheck.py
RUN chmod +x /app/deploy/start.sh /app/deploy/healthcheck.py

EXPOSE 8080

# start-period: cold import + ingest; --timeout — лимит на один запуск CMD (healthcheck.py должен уложиться).
HEALTHCHECK --interval=15s --timeout=30s --start-period=180s --retries=16 \
  CMD ["/usr/local/bin/python3", "/app/deploy/healthcheck.py"]

ENTRYPOINT ["/app/deploy/start.sh"]
