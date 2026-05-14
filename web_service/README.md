# VTB GeoATM — веб‑сервис геоаналитики размещения банкоматов

## Быстрый старт (локально)

Требования: **Python 3.13** (рекомендуется; **не используйте 3.14 без колёс** для `numpy/scikit-learn`).

```bash
cd web_service/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEOATM_DATA_DIR="/абсолютный/путь/к/корню/кейса"   # каталог, где лежит dataset_final.csv
export GEOATM_AUTO_INGEST=1
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

Фронтенд (Vite):

```bash
cd web_service/frontend
npm install
npm run dev
```

Откройте `http://localhost:5173` — запросы к API проксируются на `http://127.0.0.1:8000`.

## Docker Compose (одной командой)

Из каталога `web_service/`:

```bash
docker compose up --build
```

Поднимается сервис **`app`** (единый контейнер: **один** uvicorn на `0.0.0.0:8080`, API с префиксом `/api`, статика из собранного фронта). Так нет 502 из‑за отсутствия хоста `api` и healthcheck сразу видит ответ на порту **8080** (**`GET /live`**, **`GET /`** или **`GET /health`**, поддерживается и **`HEAD`**).

- UI + API через один порт: `http://localhost:8080` (`/api/...` — REST, остальное — SPA).
- Данные: том `..` → `/data` (корень кейса с `dataset_final.csv`).

Раздельный режим (только локально): `docker compose --profile split up --build` — сервисы `api` (8000) и `web` (8081).

### Timeweb / один контейнер

1. **Корень сборки:** каталог `web_service` репозитория.  
2. **Dockerfile:** `Dockerfile` (в корне `web_service`, не `frontend/Dockerfile`).  
3. **Порт:** внутри контейнера приложение слушает **`8080`** (при `GEOATM_BIND_INTERNAL_8080=1` в образе). В панели укажите внутренний порт **8080**; внешний порт может быть любым.  
4. **Путь проверки состояния** в панели Timeweb: **`/live`** (минимальный ответ без логики данных), **`/`** или **`/health`** — для GET и HEAD дают **200**.  
5. **Команда запуска** в панели Timeweb: оставьте **пустой / по умолчанию** — образ использует **`ENTRYPOINT`** `deploy/start.sh` (как в Dockerfile). Если платформа требует явную команду:  
   `/usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080`  
6. **Порт внутри контейнера** в образе зафиксирован на **8080** (`GEOATM_BIND_INTERNAL_8080=1`), чтобы healthcheck и панель не расходились с переменной `PORT`.  
7. **Данные (обязательно):** образ из GitHub **не содержит** `dataset_final.csv` — без тома каталог **`/data` в контейнере пустой**, ingest выдаёт ошибку «Нет dataset_final.csv в /data».  
   - В панели Timeweb Apps: подключите **диск / volume / хранилище** к приложению с **точкой монтирования внутри контейнера** **`/data`**.  
   - Загрузите в это хранилище **как минимум** `dataset_final.csv` из корня кейса (и при необходимости GeoJSON/CSV из кейса — см. `docs/DATA_DICTIONARY.md`).  
   - Перезапустите контейнер или сделайте redeploy. Проверка: `GET /api/health` → `data_loaded: true`.  
   - Если диск нельзя смонтировать в `/data`, задайте переменную **`GEOATM_DATA_DIR`** на фактический путь (абсолютный внутри контейнера).  
   - Временно без данных: **`GEOATM_AUTO_INGEST=0`**, затем после появления файлов — **`POST /api/ingest`**.

- API (Swagger): `http://<хост>:<порт>/api/docs`  
- UI: `http://<хост>:<порт>/` — после деплоя страница **ждёт `GET /api/health`** (`data_loaded`), затем подгружает зоны; при ошибке ingest в панели виден текст `last_error` из health.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `GEOATM_BIND_INTERNAL_8080` | В образе **`1`** (Timeweb): всегда слушать **8080** внутри контейнера, игнорируя ошибочный `PORT` от панели. Для нестандартного порта в compose/k8s — **`0`**. |
| `PORT` | Используется только если **`GEOATM_BIND_INTERNAL_8080=0`** (по умолчанию в образе Timeweb не влияет на bind). |
| `GEOATM_API_PREFIX` | Префикс REST (в образе **`/api`**; локально с Vite — пусто) |
| `GEOATM_STATIC_DIR` | Каталог со статикой SPA (в образе **`/app/static`**) |
| `GEOATM_DATA_DIR` | Каталог с `dataset_final.csv` и справочниками |
| `GEOATM_AUTO_INGEST` | `1` — загрузить данные при старте API |
| `GEOATM_CONFIG_PATH` | Путь к YAML, переопределяющему `backend/config/default.yaml` |
| `GEOATM_CORS_ORIGINS` | Список origin через запятую (по умолчанию `*`) |
| `GEOATM_NEW_BUILDINGS_CSV` | Абсолютный путь к CSV новостроек (иначе `GEOATM_DATA_DIR/new_buildings.csv`) |
| `GEOATM_RETRAIN_TOKEN` | Токен для `POST /retrain` (если не задан — из YAML `security.retrain_token`) |

Пример формата новостроек: скопируйте `new_buildings.example.csv` из корня кейса в `new_buildings.csv` в том же каталоге, что и `dataset_final.csv`.

Положите `Кейс_бизнес-информатика.pdf` рядом с данными (в `GEOATM_DATA_DIR`) — сервис его не читает, но так проще сдавать работу одним архивом.

## Документация

См. каталог `docs/` внутри `web_service/`.
