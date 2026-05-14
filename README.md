# hse_vtb

Материалы кейса HSE / ВТБ (данные, ноутбуки, HTML) и веб‑сервис геоаналитики.

## Веб‑сервис

Инструкции по запуску API, UI и Docker: [`web_service/README.md`](web_service/README.md).

**Деплой (Timeweb и др.):** собирайте образ из [`web_service/Dockerfile`](web_service/Dockerfile) (контекст — каталог `web_service`), не из `frontend/Dockerfile`, чтобы nginx и API были в одном контейнере и не возникал **502**.

## Репозиторий

`origin`: https://github.com/AIhexNICK-MAIL-RU/hse_vtb
