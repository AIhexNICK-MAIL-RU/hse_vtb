# VTB GeoATM — веб‑сервис геоаналитики размещения банкоматов

## Быстрый старт (локально)

Требования: **Python 3.13** (рекомендуется; **не используйте 3.14 без колёс** для `numpy/scikit-learn`).

```bash
cd web_service/backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEOATM_DATA_DIR="/абсолютный/путь/к/корню/кейса"   # нужен, если GEOATM_USE_SQLITE=0
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

## Встроенная SQLite (по умолчанию в репозитории)

В `backend/app/embedded/geoatm.sqlite` лежит снимок CSV/GeoJSON из корня кейса. При **`GEOATM_USE_SQLITE=1`** (по умолчанию) ingest **сначала** читает эту БД, если файл существует; **том `/data` в облаке не обязателен**.

Пересборка после обновления CSV в корне репозитория:

```bash
cd web_service
python3 scripts/build_embedded_sqlite.py
```

Файл попадает в Docker-образ через `COPY backend/app` (отдельный шаг в CI не нужен, если sqlite закоммичен).

Чтобы принудительно работать только с файлами из каталога (игнорировать встроенную БД): **`GEOATM_USE_SQLITE=0`**. Свой файл БД: **`GEOATM_SQLITE_PATH=/путь/geoatm.sqlite`**.

## Docker Compose (одной командой)

Из каталога `web_service/`:

```bash
docker compose up --build
```

Поднимается сервис **`app`** (единый контейнер: **один** uvicorn на `0.0.0.0:8080`, API с префиксом `/api`, статика из собранного фронта). Так нет 502 из‑за отсутствия хоста `api` и healthcheck сразу видит ответ на порту **8080** (**`GET /live`**, **`GET /`** или **`GET /health`**, поддерживается и **`HEAD`**).

- UI + API через один порт: `http://localhost:8080` (`/api/...` — REST, остальное — SPA).
- Данные: **по умолчанию** — встроенная **`geoatm.sqlite`** в образе; либо том `..` → `/data` (CSV), если отключить SQLite.

Раздельный режим (только локально): `docker compose --profile split up --build` — сервисы `api` (8000) и `web` (8081).

### Timeweb / один контейнер

1. **Корень сборки:** каталог `web_service` репозитория.  
2. **Dockerfile:** `Dockerfile` (в корне `web_service`, не `frontend/Dockerfile`).  
3. **Порт:** внутри контейнера приложение слушает **`8080`** (при `GEOATM_BIND_INTERNAL_8080=1` в образе). В панели укажите внутренний порт **8080**; внешний порт может быть любым.  
4. **Путь проверки состояния** в панели Timeweb: **`/live`** (минимальный ответ без логики данных), **`/`** или **`/health`** — для GET и HEAD дают **200**.  
5. **Команда запуска** в панели Timeweb: оставьте **пустой / по умолчанию** — образ использует **`ENTRYPOINT`** `deploy/start.sh` (как в Dockerfile). Если платформа требует явную команду:  
   `/usr/local/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080`  
6. **Порт внутри контейнера** в образе зафиксирован на **8080** (`GEOATM_BIND_INTERNAL_8080=1`), чтобы healthcheck и панель не расходились с переменной `PORT`.  
7. **Данные:** в образе из репозитория уже есть **`backend/app/embedded/geoatm.sqlite`** — Timeweb может работать **без** тома `/data`.  
   - Том **`/data`** нужен, если хотите подменить датасет без пересборки образа (`GEOATM_USE_SQLITE=0` или свежие CSV только на диске).  
   - Пересборка встроенной БД после смены CSV: `cd web_service && python3 scripts/build_embedded_sqlite.py`, затем commit и redeploy.

- API (Swagger): `http://<хост>:<порт>/api/docs`  
- UI: `http://<хост>:<порт>/` — после деплоя страница **ждёт `GET /api/health`** (`data_loaded`), затем подгружает зоны; при ошибке ingest в панели виден текст `last_error` из health.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `GEOATM_BIND_INTERNAL_8080` | В образе **`1`** (Timeweb): всегда слушать **8080** внутри контейнера, игнорируя ошибочный `PORT` от панели. Для нестандартного порта в compose/k8s — **`0`**. |
| `PORT` | Используется только если **`GEOATM_BIND_INTERNAL_8080=0`** (по умолчанию в образе Timeweb не влияет на bind). |
| `GEOATM_API_PREFIX` | Префикс REST (в образе **`/api`**; локально с Vite — пусто) |
| `GEOATM_STATIC_DIR` | Каталог со статикой SPA (в образе **`/app/static`**) |
| `GEOATM_DATA_DIR` | Каталог с CSV (используется при **`GEOATM_USE_SQLITE=0`** или для `new_buildings.csv`, если её нет в SQLite) |
| `GEOATM_USE_SQLITE` | **`1`** — если есть встроенный или `GEOATM_SQLITE_PATH` файл, грузить оттуда; **`0`** — только файлы из `GEOATM_DATA_DIR` |
| `GEOATM_SQLITE_PATH` | Явный путь к `.sqlite` (иначе — `app/embedded/geoatm.sqlite` рядом с кодом) |
| `GEOATM_AUTO_INGEST` | `1` — загрузить данные при старте API |
| `GEOATM_CONFIG_PATH` | Путь к YAML, переопределяющему `backend/config/default.yaml` |
| `GEOATM_CORS_ORIGINS` | Список origin через запятую (по умолчанию `*`) |
| `GEOATM_NEW_BUILDINGS_CSV` | Абсолютный путь к CSV новостроек (иначе `GEOATM_DATA_DIR/new_buildings.csv`) |
| `GEOATM_RETRAIN_TOKEN` | Токен для `POST /retrain` (если не задан — из YAML `security.retrain_token`) |

Пример формата новостроек: скопируйте `new_buildings.example.csv` из корня кейса в `new_buildings.csv` в том же каталоге, что и `dataset_final.csv`.

Положите `Кейс_бизнес-информатика.pdf` рядом с данными (в `GEOATM_DATA_DIR`) — сервис его не читает, но так проще сдавать работу одним архивом.

## Документация

См. каталог `docs/` внутри `web_service/`.
