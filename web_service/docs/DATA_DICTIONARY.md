# Словарь данных

Все пути относительно `GEOATM_DATA_DIR`.

## `dataset_final.csv` (основной агрегат по H3)

| Колонка | Тип | Смысл |
|---------|-----|--------|
| `h3_index` | str | Индекс ячейки H3 (резолюция как в исходных данных) |
| `total_records` | int | Количество записей агрегата |
| `unique_customers` | int | Уникальные клиенты |
| `total_count` / `total_sum` | int / float | Число транзакций / сумма в рублях |
| `avg_transaction` … `avg_std` | float | Статистики по чекам; `avg_std` используется как **прокси волатильности** |
| `transactions_per_customer` | float | Транзакции на клиента |
| `sum_per_customer` | float | Сумма на клиента |
| `atm_active_customers`, `atm_activity_records`, `atm_activity` | int | Активность у банкоматов ВТБ |
| `vtb_atm_count`, `vtb_office_count` | int | Плотность собственной сети |
| `metro_count`, `competitor_atm_count`, `mall_count`, `university_count` | int | POI внутри/около ячейки (как в исходной агрегации) |

Ограничения: нет помесячных рядов → сценарии «тренд» и «низкая загрузка» частично **проксируются**.

## Справочники POI

Файлы: `vtb_atms.csv`, `offices.csv`, `competitor_atms.csv`, `metro.csv`, `malls.csv`, `universities.csv`.

Разделитель: `;` или `,` (определяется эвристически по заголовку). Ожидаются колонки с `lat` и `lon` (или эквивалент в `metro.csv`: `station;lat;lon`).

Сервис загружает их для будущего расширения (точечные слои); **текущая модель** использует уже агрегированные счётчики из `dataset_final.csv`.

## `priority_zones.csv`

Кластеры приоритетных мест: `lat`, `lon`, `name`, `type`, `weight`, `points_count`.

## `moscow_population_full*.csv`

Демография населения (не обязателен для работы API v1; может быть подключён в ETL v2).

## `moscow_okrugs_demographics.geojson`

Сейчас в файле **точки** округов с атрибутами (`okrug_code`, доход, плотность и т.д.). Для UI/отчёта зона H3 относится к ближайшей точке (упрощение).

## `export (10).geojson`

Крупный OSM-экспорт (точки). В v1 не используется моделью, оставлен для расширения слоёв.
