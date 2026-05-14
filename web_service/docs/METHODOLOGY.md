# Методология

## Эвристический Demand Score (baseline)

Нормировка min-max по всему датасету для каждого компонента, затем взвешенная сумма (см. `backend/config/default.yaml` и `scenario_analysis.html`):

\[
DS = 0.35\,z(\text{total\_sum}) + 0.25\,z(\text{unique\_customers}) + 0.20\,z(\text{tpc}) + 0.12\,z(\text{poi}) + 0.08\,z(\text{comp})
\]

где `poi = metro + mall + university`, `comp = competitor_atm_count`.

## Четыре сценария (теги)

1. **white_spots** — `vtb_atm_count = 0`, `atm_activity = 0`, `unique_customers ≥ P50`, `DS ≥ порога` (по умолчанию 0.70).
2. **competitor** — `competitor_atm_count ≥ 2` и `vtb_atm_count = 0`.
3. **growth_retail** — **прокси**: наличие ТЦ/вуза и высокая волатильность `avg_std` относительно P75 (вместо `growth_rate` из презентации, т.к. в финальном CSV нет динамики по периодам).
4. **low_utilization** — `vtb_atm_count ≥ 1` и низкий `sum_per_customer` (ниже P25 по всему датасету).

## Псевдо-разметка для supervised ML

Целевой признак **не является реальным бизнес-таргетом** (нет измеренного ROI).

Правило v1:

- **класс 1 (приоритет)**: выполняется сильный «белый пятно» **или** «перехват конкурента» с умеренным DS;
- **класс 0 (фон)**: низкий DS или явное насыщение сетью ВТБ;
- **неоднозначные** строки (`-1`) исключаются из обучения.

Модель: `RandomForestClassifier` + вероятность положительного класса как **`ml_score`**.

## Unsupervised

`StandardScaler` + `KMeans(k=6)` по набору числовых признаков (см. `FEATURE_COLUMNS` в коде) → **`cluster_id`**.

## Согласование ML vs эвристики

В ответах обучения считаются:

- Spearman (через ранги, без обязательного `scipy`) между `ml_score` и `heuristic_score`;
- Kendall τ — **если доступен `scipy`** (в Docker/Linux обычно есть транзитивно из `scikit-learn`);
- `coverage@k`: доля псевдо-позитивов среди топ-`k` зон по `ml_score`;
- bootstrap-дисперсия τ по подвыборкам 80%.

## Ограничения методики

- Нет временной динамики → сценарии 3–4 **частично эвристичны**.
- Округ определяется ближайшей точкой из GeoJSON, а не полигоном границ.
- Псевдо-метки зависят от порогов YAML — меняйте их осознанно и фиксируйте `model_version`.
