#!/bin/sh
set -e

LISTEN_PORT="${PORT:-8080}"
echo "[entrypoint] PORT (nginx listen) = ${LISTEN_PORT}"

# Конфиг nginx: прокси на uvicorn в том же контейнере (без хоста api — иначе 502 на PaaS)
sed "s/LISTEN_PORT/${LISTEN_PORT}/g" /opt/nginx-site.conf > /etc/nginx/sites-available/default
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Проверка конфига
nginx -t

# API в фоне (только localhost — снаружи доступ через nginx /api/)
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
python <<'PY'
import time
import urllib.error
import urllib.request

for i in range(90):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        print("[entrypoint] API health OK")
        break
    except Exception:
        time.sleep(0.5)
else:
    print("[entrypoint] WARNING: API /health did not respond in time")
PY

exec nginx -g "daemon off;"
