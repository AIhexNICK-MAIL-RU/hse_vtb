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

  const placementBlock = p.placement ? buildPlacementHtml(p.placement) : "";

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
    ${placementBlock}
  </div>`;
}

/** Строка расстояния до POI + координаты в title при наведении */
function distPoiRow(icon, lineRu, n) {
  const ic = escapeHtml(icon);
  if (!n || typeof n !== "object") {
    return `<div class="zp-item zp-muted"><span class="zp-item-ico">${ic}</span><div class="zp-item-main"><div class="zp-item-line">${escapeHtml(lineRu)}</div><div class="zp-item-val">нет данных в справочнике</div></div></div>`;
  }
  const name = escapeHtml(n.name || "—");
  const dm = escapeHtml(String(n.distance_m ?? "—"));
  const lat = Number(n.lat);
  const lon = Number(n.lon);
  const coord =
    Number.isFinite(lat) && Number.isFinite(lon) ? `${lat.toFixed(6)}, ${lon.toFixed(6)}` : "—";
  const lineEsc = escapeHtml(lineRu);
  const hint = escapeHtml(`${lineRu}: ${n.name || ""} | WGS84 ${coord}`);
  return `<div class="zp-item" title="${hint}">
    <span class="zp-item-ico">${ic}</span>
    <div class="zp-item-main">
      <div class="zp-item-line">${lineEsc}</div>
      <div class="zp-item-val">${name} · <span class="zp-mono">${dm} м</span></div>
    </div>
  </div>`;
}

export function buildPlacementHtml(placement) {
  if (!placement || typeof placement !== "object") return "";
  const r = placement.radius_m ?? 400;
  const summary = escapeHtml(placement.summary || "");
  const ncr = placement.competitors_in_radius;
  const head = `<div class="zp-placement-head">
    <div class="zp-item-line"><strong>Зона размещения АТМ</strong> · окружность ~${escapeHtml(String(r))} м</div>
    <div class="zp-placement-summary">${summary}</div>
    ${typeof ncr === "number" ? `<div class="zp-item-line zp-muted">Конкурентов в радиусе: ${escapeHtml(String(ncr))}</div>` : ""}
  </div>`;

  const rows = [
    distPoiRow("🚇", "Метро (ближайшая станция)", placement.nearest_metro),
    distPoiRow("🏢", "ТЦ / крупная торговля", placement.nearest_mall),
    distPoiRow("🛒", "Рынок", placement.nearest_market),
    distPoiRow("🔧", "Строймагазин", placement.nearest_hardware),
    distPoiRow("🎓", "ВУЗ", placement.nearest_university),
    distPoiRow("🏛", "Офис (справочник)", placement.nearest_office),
    distPoiRow("🏧", "Банкомат ВТБ", placement.nearest_vtb_atm),
    distPoiRow("🏪", "Банкомат конкурента", placement.nearest_competitor_atm),
  ].join("");

  return `<div class="zp-placement">${head}<div class="zp-list zp-list-tight">${rows}</div></div>`;
}
