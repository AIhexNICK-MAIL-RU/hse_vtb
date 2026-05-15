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
  retention: {
    icon: "◎",
    label: "Удержание",
    hint: "Прокси удержания 0–1: уникальные клиенты, средний чек, частота операций и стабильность (низкая волатильность avg_std). См. docs/RETENTION_IDEAS.md.",
    suffix: "прокси",
  },
  pressure: {
    icon: "⚡",
    label: "Давление",
    hint: "Давление среды 0–1: плотность банкоматов конкурентов и метро (транзитные узлы). Не равно ML-приоритету.",
    suffix: "конкуренция+транзит",
  },
  profile: {
    icon: "◇",
    label: "Профиль",
    hint: "Краткий профиль ячейки: транзит+ритейл, устойчивый спрос, конкурентный коридор с ВТБ.",
    suffix: "тип зоны",
  },
};

export const SCENARIO_TAG_LABELS = {
  any: "все",
  white_spots: "белые пятна",
  competitor: "перехват конкурента",
  growth_retail: "динамика ТЦ/ВУЗов (прокси)",
  low_utilization: "низкая загрузка",
};

export const PROFILE_TAG_LABELS = {
  transit_retail_hub: "транзит + ритейл",
  stable_demand: "устойчивый спрос",
  competitive_corridor: "конкурентный коридор (ВТБ+конкуренты)",
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
  apartments: {
    icon: "🏢",
    label: "Квартир",
    hint: "Количество квартир в доме из spisok_domov.csv — масштаб объекта.",
    suffix: "шт.",
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

export function formatProfileTags(tagsStr) {
  if (!tagsStr || !String(tagsStr).trim()) return "—";
  return String(tagsStr)
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => PROFILE_TAG_LABELS[t] || t)
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

export const FOCUS_POI_CATEGORY = {
  metro: { field: "nearest_metro", title: "Ближайшее метро", icon: "🚇" },
  malls: { field: "nearest_mall", title: "Ближайший ТЦ / крупная торговля", icon: "🏢" },
  markets: { field: "nearest_market", title: "Ближайший рынок", icon: "🛒" },
  hardware_stores: { field: "nearest_hardware", title: "Ближайший строймагазин", icon: "🔧" },
  universities: { field: "nearest_university", title: "Ближайший ВУЗ", icon: "🎓" },
  offices: { field: "nearest_office", title: "Ближайший офис (справочник)", icon: "🏛" },
  vtb_atms: { field: "nearest_vtb_atm", title: "Ближайший банкомат ВТБ", icon: "🏧" },
  competitor_atms: { field: "nearest_competitor_atm", title: "Ближайший банкомат конкурента", icon: "🏪" },
};

export function buildFocusCategoryHtml(placement, categoryId) {
  if (!placement || !categoryId || typeof categoryId !== "string") return "";
  const meta = FOCUS_POI_CATEGORY[categoryId];
  if (!meta) return "";
  const n = placement[meta.field];
  const title = escapeHtml(meta.title);
  const ic = escapeHtml(meta.icon);
  if (!n || typeof n !== "object") {
    return `<div class="zp-focus-box zp-muted">
      <div class="zp-focus-title">${ic} ${title}</div>
      <div class="zp-focus-val">Нет точки в справочнике или нет координат</div>
    </div>`;
  }
  const name = escapeHtml(n.name || "—");
  const dm = escapeHtml(String(n.distance_m ?? "—"));
  const lat = Number(n.lat);
  const lon = Number(n.lon);
  const coord =
    Number.isFinite(lat) && Number.isFinite(lon) ? `${lat.toFixed(6)}, ${lon.toFixed(6)}` : "—";
  const hint = escapeHtml(`${meta.title}: ${n.name || ""} | WGS84 ${coord}`);
  return `<div class="zp-focus-box" title="${hint}">
    <div class="zp-focus-title">${ic} Выбранная категория: ${title}</div>
    <div class="zp-focus-val"><strong>${name}</strong> · <span class="zp-mono">${dm} м</span> от центра ячейки</div>
    <div class="zp-focus-sub zp-mono">${escapeHtml(coord)}</div>
  </div>`;
}

export function buildZonePopupHtml(props, options = {}) {
  const p = props || {};
  const focusCategory = options.focusCategory || "";
  const Z = ZONE_POPUP;
  const h3v = escapeHtml(p.h3);
  const mlv = escapeHtml(formatNum(p.ml));
  const dsv = escapeHtml(formatNum(p.ds));
  const tagsRaw = p.tags || "";
  const tagsPretty = escapeHtml(formatScenarioTags(tagsRaw));
  const retv = escapeHtml(formatNum(p.retention));
  const pressv = escapeHtml(formatNum(p.pressure));
  const profRaw = p.profileTags || "";
  const profPretty = escapeHtml(formatProfileTags(profRaw));

  const headIcon = escapeHtml(Z.headerIcon);
  const headTitle = escapeHtml(Z.headerTitle);
  const headSub = escapeHtml(Z.headerSub);

  const focusBlock =
    focusCategory && p.placement ? buildFocusCategoryHtml(p.placement, focusCategory) : "";
  const placementBlock = p.placement ? buildPlacementHtml(p.placement) : "";

  return `<div class="zp-shell">
    <div class="zp-header">
      <span class="zp-header-ico" title="Зона расчёта приоритета по H3">${headIcon}</span>
      <div class="zp-header-text">
        <div class="zp-header-title">${headTitle}</div>
        <div class="zp-header-sub">${headSub}</div>
      </div>
    </div>
    ${focusBlock}
    <div class="zp-list">
      ${itemRow(Z.h3, `<span class="zp-mono">${h3v}</span>`)}
      ${itemRow(Z.ml, mlv)}
      ${itemRow(Z.ds, dsv)}
      ${itemRow(Z.retention, retv)}
      ${itemRow(Z.pressure, pressv)}
      ${itemRow(Z.tags, tagsPretty, tagsRaw || undefined)}
      ${itemRow(Z.profile, profPretty, profRaw || undefined)}
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
