#!/bin/sh
set -e
# Timeweb Apps: в логах деплоя порт сервиса — 8080/tcp. Платформа иногда задаёт PORT,
# не совпадающий с тем, что реально пробуют healthcheck/прокси → слушаем фиксированный
# внутренний порт 8080 (см. GEOATM_BIND_INTERNAL_8080 в Dockerfile). Для compose/k8s
# выставьте GEOATM_BIND_INTERNAL_8080=0 и при необходимости PORT.
if [ "${GEOATM_BIND_INTERNAL_8080:-1}" = "1" ]; then
  LISTEN=8080
else
  LISTEN="${PORT:-8080}"
  case "$LISTEN" in *[!0-9]*) LISTEN=8080;; esac
fi
printf '%s' "$LISTEN" > /tmp/.geoatm_listen_port
echo "[start.sh] uvicorn 0.0.0.0:${LISTEN}" >&2
exec /usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$LISTEN"
