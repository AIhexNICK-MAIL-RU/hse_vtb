# Единый образ для PaaS (Timeweb и т.п.): один процесс uvicorn на 0.0.0.0:$PORT,
# API под /api, статика SPA из dist, /health на корне для healthcheck.
# Раньше nginx слушал 8080 только после долгого старта API — проверка здоровья не проходила.

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

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
