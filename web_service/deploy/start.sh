#!/bin/sh
set -e
# Timeweb и др. PaaS: PORT должен совпадать с пробуемым портом (часто 8080).
# Некорректное значение — слушаем 8080, чтобы healthcheck и EXPOSE совпадали.
LISTEN="${PORT:-8080}"
case "$LISTEN" in *[!0-9]*) LISTEN=8080;; esac
printf '%s' "$LISTEN" > /tmp/.geoatm_listen_port
echo "[start.sh] listening on 0.0.0.0:${LISTEN}" >&2
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$LISTEN"
