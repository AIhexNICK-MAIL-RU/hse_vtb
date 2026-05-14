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
if [ "${GEOATM_AUTO_INGEST:-1}" != "0" ]; then
  if [ ! -r "$DATA_DIR/dataset_final.csv" ]; then
    echo "[start.sh] ОШИБКА ДАННЫХ: нет читаемого файла $DATA_DIR/dataset_final.csv" >&2
    echo "[start.sh] Ingest не сможет загрузить модель. Подключите том/диск к контейнеру в точку /data" >&2
    echo "[start.sh] и положите туда dataset_final.csv (корень кейса). Либо GEOATM_AUTO_INGEST=0 и POST /api/ingest после копирования." >&2
  else
    echo "[start.sh] данные: $DATA_DIR/dataset_final.csv найден" >&2
  fi
fi
echo "[start.sh] uvicorn 0.0.0.0:${LISTEN}" >&2
exec /usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$LISTEN"
