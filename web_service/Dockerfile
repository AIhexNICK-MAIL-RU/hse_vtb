# Единый образ для PaaS (Timeweb и т.п.): nginx + FastAPI в одном контейнере.
# Иначе nginx с proxy_pass http://api:8000 даёт 502, если контейнер api не поднят в той же сети.

# --- frontend ---
FROM node:20-alpine AS frontend
WORKDIR /src
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- runtime ---
FROM python:3.13-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    GEOATM_DATA_DIR=/data \
    GEOATM_AUTO_INGEST=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY backend/config /app/config

COPY --from=frontend /src/dist /usr/share/nginx/html

COPY deploy/nginx-site.conf /opt/nginx-site.conf
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
