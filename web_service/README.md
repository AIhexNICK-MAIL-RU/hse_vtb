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

- API: `http://localhost:8000/docs`
- UI (nginx + прокси `/api`): `http://localhost:8080`

Том `..` монтируется в контейнер как `/data` — это **родительский каталог `web_service`**, т.е. корень кейса с CSV/GeoJSON.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `GEOATM_DATA_DIR` | Каталог с `dataset_final.csv` и справочниками |
| `GEOATM_AUTO_INGEST` | `1` — загрузить данные при старте API |
| `GEOATM_CONFIG_PATH` | Путь к YAML, переопределяющему `backend/config/default.yaml` |
| `GEOATM_CORS_ORIGINS` | Список origin через запятую (по умолчанию `*`) |
| `GEOATM_RETRAIN_TOKEN` | Токен для `POST /retrain` (иначе берётся из YAML `security.retrain_token`) |

## PDF кейса

Положите `Кейс_бизнес-информатика.pdf` рядом с данными (в `GEOATM_DATA_DIR`) — сервис его не читает, но так проще сдавать работу одним архивом.

## Документация

См. каталог `docs/` внутри `web_service/`.
