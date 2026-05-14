/** Подписи для UI карты (DATA_DICTIONARY.md, METHODOLOGY.md). Вёрстка — как в web_service/screens/. */

export const ZONE_POPUP = {
  headerIcon: "⬡",
  headerTitle: "Зона приоритета",
  headerSub: "Ячейка H3 · VTB GeoATM",
  h3: {
    icon: "⬡",
    label: "H3",
    hint: "Геоиндекс ячейки Uber H3: по ней агрегируются транзакции, POI и счётчики ВТБ/конкурентов.",
    suffix: "ячейка сетки",
  },
  ml: {
    icon: "◎",
    label: "ML",
    hint: "Приоритет 0–1 от модели (RandomForest): похожесть ячейки на высокий спрос по признакам. Карта сортирует зоны по ML.",
    suffix: "приоритет модели",
  },
  ds: {
    icon: "◆",
    label: "DS",
    hint: "Demand Score 0–1 — эвристика спроса по правилам и CSV; обучение ML опирается на DS, это не дубль ML.",
    suffix: "спрос (эвристика)",
  },
  tags: {
    icon: "▣",
    label: "Теги",
    hint: "Сценарии бизнес-гипотез для ячейки (белые пятна, конкурент, тренд ТЦ/ВУЗов и т.д.).",
    suffix: "сценарии",
  },
};

export const SCENARIO_TAG_LABELS = {
  any: "все",
  white_spots: "белые пятна",
  competitor: "перехват конкурента",
  growth_retail: "динамика ТЦ/ВУЗов (прокси)",
  low_utilization: "низкая загрузка",
};

export const DEV_POPUP = {
  delivery_score: {
    icon: "📊",
    label: "delivery_score",
    hint: "Приоритет доставки 0–1 от горизонта сдачи; не смешивается с DS/ML по H3.",
    suffix: "срочность новостройки",
  },
  delivery_tier: {
    icon: "⚡",
    label: "tier",
    hint: "Категория срочности по delivery_score.",
    suffix: "уровень",
  },
  months_to_completion: {
    icon: "📅",
    label: "мес. до сдачи",
    hint: "Месяцев до даты ключей; влияет на delivery_score.",
    suffix: "горизонт",
  },
  completion: {
    icon: "🔑",
    label: "Сдача",
    hint: "Плановая дата сдачи (ключи) из файла новостроек.",
    suffix: "дата",
  },
  address: {
    icon: "🏠",
    label: "Адрес",
    hint: "Строка адреса из данных новостройки.",
    suffix: "строка",
  },
  coords: {
    icon: "📍",
    label: "Координаты",
    hint: "Широта и долгота в градусах WGS84 (EPSG:4326), как на карте.",
    suffix: "точка",
  },
};

export function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function formatNum(v, digits = 3) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

export function formatScenarioTags(tagsStr) {
  if (!tagsStr || !String(tagsStr).trim()) return "—";
  return String(tagsStr)
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => SCENARIO_TAG_LABELS[t] || t)
    .join(", ");
}

function itemRow(field, valueHtml, valuePlainForTitle) {
  const hint = escapeHtml(field.hint);
  const label = escapeHtml(field.label);
  const suffix = escapeHtml(field.suffix);
  const icon = escapeHtml(field.icon);
  const vt = valuePlainForTitle ? ` title="${escapeHtml(valuePlainForTitle)}"` : "";
  return `<div class="zp-item" title="${hint}">
    <span class="zp-item-ico" aria-hidden="true">${icon}</span>
    <div class="zp-item-main">
      <div class="zp-item-line">
        <abbr class="zp-item-abbr" title="${hint}">${label}</abbr>
        <span class="zp-item-sep">·</span>
        <span class="zp-item-suffix">${suffix}</span>
      </div>
      <div class="zp-item-val"${vt}>${valueHtml}</div>
    </div>
  </div>`;
}

export function buildZonePopupHtml(props) {
  const p = props || {};
  const Z = ZONE_POPUP;
  const h3v = escapeHtml(p.h3);
  const mlv = escapeHtml(formatNum(p.ml));
  const dsv = escapeHtml(formatNum(p.ds));
  const tagsRaw = p.tags || "";
  const tagsPretty = escapeHtml(formatScenarioTags(tagsRaw));

  const headIcon = escapeHtml(Z.headerIcon);
  const headTitle = escapeHtml(Z.headerTitle);
  const headSub = escapeHtml(Z.headerSub);

  return `<div class="zp-shell">
    <div class="zp-header">
      <span class="zp-header-ico" title="Зона расчёта приоритета по H3">${headIcon}</span>
      <div class="zp-header-text">
        <div class="zp-header-title">${headTitle}</div>
        <div class="zp-header-sub">${headSub}</div>
      </div>
    </div>
    <div class="zp-list">
      ${itemRow(Z.h3, `<span class="zp-mono">${h3v}</span>`)}
      ${itemRow(Z.ml, mlv)}
      ${itemRow(Z.ds, dsv)}
      ${itemRow(Z.tags, tagsPretty, tagsRaw || undefined)}
    </div>
  </div>`;
}
