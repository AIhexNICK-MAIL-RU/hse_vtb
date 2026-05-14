# HTTP API (кратко)

Полная схема: `GET /docs` (Swagger UI).

## Примеры `curl`

```bash
curl -s http://localhost:8000/health | jq
```

```bash
curl -s "http://localhost:8000/zones?scenario=white_spots&limit=50" | jq ".count, .model_version"
```

```bash
curl -s "http://localhost:8000/zones/89118180927ffff/explain" | jq ".narrative, .top_features[:3]"
```

```bash
curl -s http://localhost:8000/developments | jq ".count, .items[0]"
```

```bash
curl -s "http://localhost:8000/summary?scenario=competitor" | jq -r ".text"
```

```bash
curl -s -X POST "http://localhost:8000/ingest" | jq
```

```bash
curl -s -X POST "http://localhost:8000/retrain" -H "X-Retrain-Token: dev-change-me" | jq
```

## Ошибки

| Код | Когда |
|-----|--------|
| 400 | Ошибка загрузки данных / битый путь |
| 401 | Неверный токен `POST /retrain` |
| 404 | Неизвестный `h3` в `/zones/{h3}/explain` |
| 503 | Данные не загружены (выключен auto-ingest и не вызван `/ingest`) |
