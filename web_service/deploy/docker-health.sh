#!/bin/sh
# Сверхлёгкий liveness: укладывается в жёсткий --timeout HEALTHCHECK у части PaaS (5–10 с).
# Только IPv4 loopback — без зависимости от резолва localhost → ::1.
set -e
PORT="${GEOATM_HEALTH_PORT:-8080}"
if [ -f /tmp/.geoatm_listen_port ]; then
  read -r PORT < /tmp/.geoatm_listen_port || true
fi
exec curl -fsS --connect-timeout 1 --max-time 3 "http://127.0.0.1:${PORT}/live"
