# Эксплуатация (OPS)

## Логирование

По умолчанию uvicorn пишет в stdout. В продакшене оборачивайте в systemd/k8s и собирайте централизованно.

## Память и производительность

- `dataset_final.csv` (~8k строк) помещается в RAM целиком; пик памяти — во время `RandomForest` и `permutation_importance` (сотни МБ).
- Тяжёлый эндпоинт: `POST /ingest` и `POST /retrain` (пересчёт модели).

## Кэширование

v1: кэш **в памяти процесса** (глобальный `state`). Для горизонтального масштабирования вынесите артефакты в объектное хранилище + общую БД.

## Расписание пересчёта

Пример cron на хосте с данными:

```cron
0 3 * * * curl -s -X POST http://api:8000/retrain -H "X-Retrain-Token: $TOKEN" >/tmp/geoatm_retrain.log 2>&1
```

## Docker

См. `web_service/docker-compose.yml`. Важно: `GEOATM_DATA_DIR` внутри контейнера должен указывать на смонтированный том с CSV.

## Безопасность

Смените `security.retrain_token` в YAML или задайте `GEOATM_RETRAIN_TOKEN` в секретах окружения.

## Ошибка 502 у reverse proxy

Типичная причина: фронт (nginx) проксирует на хост **`api`**, которого нет в PaaS. Используйте **единый образ** `web_service/Dockerfile` (сервис `app`): один **uvicorn** слушает **`0.0.0.0:$PORT`** (часто 8080), API под **`/api`**, статика смонтирована в том же процессе.

## Healthcheck не проходит (Timeweb и др.)

Платформа обычно проверяет **`GET /`** или **`HEAD /`** (в Timeweb по умолчанию путь «**/**»). Для Docker **`HEALTHCHECK`** в образе используется **`GET http://127.0.0.1:8080/live`** (скрипт `deploy/docker-health.sh` + **curl**): ответ без Pydantic и без обращения к `state`, чтобы проверка не конкурировала с фоновым ingest. Дополнительно: **`/health`**, **`HEAD /health`**. Нельзя поднимать **только nginx** до старта API. Ingest в **фоне** (`asyncio.to_thread`); **`GET /health`** сразу отдаёт JSON (статус `degraded`, пока данные не загрузились).

**Импорт sklearn** откладывается до первого `ingest` / `explain` — uvicorn быстрее поднимает сокет (важно при жёстком таймауте healthcheck). В образе для Timeweb **`GEOATM_BIND_INTERNAL_8080=1`**: uvicorn всегда на **8080** внутри контейнера. **`HEALTHCHECK`**: **`deploy/docker-health.sh`** (**curl** → **`/live`**, IPv4 **127.0.0.1**, таймауты **1s/3s**). Запасной вариант без curl: **`python3 /app/deploy/healthcheck.py`** (тот же порядок путей **`/live`**, **`/health`**, **`/`**). Старт: **`ENTRYPOINT`** `deploy/start.sh` → **`/usr/local/bin/python3 -m uvicorn`**.
