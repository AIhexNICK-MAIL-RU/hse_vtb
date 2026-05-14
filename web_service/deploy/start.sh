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
DATA_DIR="${GEOATM_DATA_DIR:-/data}"
EMB_SQL="/app/app/embedded/geoatm.sqlite"
if [ "${GEOATM_AUTO_INGEST:-1}" != "0" ]; then
  if [ -r "$DATA_DIR/dataset_final.csv" ]; then
    echo "[start.sh] данные: CSV $DATA_DIR/dataset_final.csv" >&2
  elif [ "${GEOATM_USE_SQLITE:-1}" != "0" ] && [ -r "$EMB_SQL" ]; then
    echo "[start.sh] данные: встроенная БД $EMB_SQL (без тома /data)" >&2
  elif [ "${GEOATM_USE_SQLITE:-1}" != "0" ] && [ -r "./app/embedded/geoatm.sqlite" ]; then
    echo "[start.sh] данные: встроенная БД ./app/embedded/geoatm.sqlite" >&2
  else
    echo "[start.sh] ВНИМАНИЕ: нет $DATA_DIR/dataset_final.csv и нет встроенной geoatm.sqlite — ingest может упасть." >&2
    echo "[start.sh] Смонтируйте /data или соберите БД: python3 scripts/build_embedded_sqlite.py" >&2
  fi
fi
echo "[start.sh] uvicorn 0.0.0.0:${LISTEN}" >&2
exec /usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$LISTEN"
