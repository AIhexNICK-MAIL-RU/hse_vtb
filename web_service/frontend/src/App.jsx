import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { CircleMarker, Circle, LayerGroup, MapContainer, Popup, TileLayer, GeoJSON, Tooltip, useMap } from "react-leaflet";
import { buildZonePopupHtml, DEV_POPUP, formatNum } from "./glossary.js";

/** Прод: тот же хост, префикс /api. Подпуть деплоя: учитываем import.meta.env.BASE_URL (Vite). */
const viteApi = import.meta.env.VITE_API_URL;
const viteBase = import.meta.env.BASE_URL || "/";
const basePrefix = viteBase === "/" ? "" : viteBase.replace(/\/$/, "");
const LOGO_URL = `${basePrefix}/VTB_Logo_2018.svg.png`;
const API_BASE =
  viteApi != null && String(viteApi).trim() !== ""
    ? String(viteApi).trim().replace(/\/$/, "")
    : `${basePrefix}/api`;

const HEALTH_POLL_MS = 2000;
const HEALTH_WAIT_MS = 180_000;

const POI_LAYER_ORDER = [
  "competitor_atms",
  "vtb_atms",
  "metro",
  "malls",
  "universities",
  "offices",
  "markets",
  "hardware_stores",
];

const POI_LAYER_LABELS = {
  competitor_atms: "Банкоматы конкурентов",
  vtb_atms: "Банкоматы ВТБ",
  metro: "Метро",
  malls: "ТЦ / торговля",
  universities: "ВУЗы",
  offices: "Офисы",
  markets: "Рынки",
  hardware_stores: "Строймагазины",
};

const POI_DOT = {
  competitor_atms: { r: 5, color: "#14532d", fill: "#22c55e" },
  vtb_atms: { r: 5, color: "#1e3a8a", fill: "#2563eb" },
  metro: { r: 5, color: "#155e75", fill: "#06b6d4" },
  malls: { r: 4, color: "#9a3412", fill: "#fb923c" },
  universities: { r: 4, color: "#5b21b6", fill: "#a855f7" },
  offices: { r: 3, color: "#374151", fill: "#94a3b8" },
  markets: { r: 4, color: "#92400e", fill: "#fbbf24" },
  hardware_stores: { r: 4, color: "#78350f", fill: "#d97706" },
};

function FitBoth({ zonesGeo, devGeo }) {
  const map = useMap();
  useEffect(() => {
    const layers = [];
    try {
      if (zonesGeo?.features?.length) layers.push(L.geoJSON(zonesGeo));
      if (devGeo?.features?.length) layers.push(L.geoJSON(devGeo));
      if (!layers.length) return;
      let u = layers[0].getBounds();
      for (let i = 1; i < layers.length; i += 1) u = u.extend(layers[i].getBounds());
      if (u.isValid()) map.fitBounds(u, { padding: [28, 28] });
    } catch {
      map.setView([55.75, 37.62], 10);
    }
  }, [zonesGeo, devGeo, map]);
  return null;
}

function scoreColor(ml) {
  const t = Math.max(0, Math.min(1, ml));
  const r = Math.round(255 * (1 - t));
  const g = Math.round(200 * t);
  const b = 80;
  return `rgb(${r},${g},${b})`;
}

function deliveryColor(score) {
  if (score >= 0.92) return "#dc2626";
  if (score >= 0.72) return "#ea580c";
  if (score >= 0.5) return "#ca8a04";
  return "#64748b";
}

function DevFieldRow({ meta, children, valueTitle }) {
  return (
    <div className="zp-item" title={meta.hint}>
      <span className="zp-item-ico" aria-hidden="true">
        {meta.icon}
      </span>
      <div className="zp-item-main">
        <div className="zp-item-line">
          <abbr className="zp-item-abbr" title={meta.hint}>
            {meta.label}
          </abbr>
          <span className="zp-item-sep">·</span>
          <span className="zp-item-suffix">{meta.suffix}</span>
        </div>
        <div className="zp-item-val" title={valueTitle || meta.hint}>
          {children}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [scenario, setScenario] = useState("any");
  const [minScore, setMinScore] = useState("");
  const [limit, setLimit] = useState(400);
  const [loading, setLoading] = useState(false);
  const [zones, setZones] = useState([]);
  const [modelVersion, setModelVersion] = useState("");
  const [summary, setSummary] = useState("");
  const [showNewBuildings, setShowNewBuildings] = useState(true);
  const [developments, setDevelopments] = useState([]);
  const [devSource, setDevSource] = useState("");
  const [backendStatus, setBackendStatus] = useState("Проверка API…");
  const [poiGeo, setPoiGeo] = useState(null);
  const [poiError, setPoiError] = useState("");
  const [showPlacementCircles, setShowPlacementCircles] = useState(true);
  const [poiVisibility, setPoiVisibility] = useState({
    competitor_atms: true,
    vtb_atms: true,
    metro: true,
    malls: true,
    universities: true,
    offices: false,
    markets: true,
    hardware_stores: true,
  });
  /** Категория POI для выделенного блока «расстояние от центра H3» в попапе зоны */
  const [focusPoiCategory, setFocusPoiCategory] = useState("");

  const geojson = useMemo(() => {
    const features = zones.map((z) => ({
      type: "Feature",
      properties: {
        h3: z.h3_index,
        ml: z.ml_score,
        ds: z.heuristic_score,
        retention: z.retention_proxy_score,
        pressure: z.competition_pressure_score,
        tags: z.scenario_tags?.join(", ") || "",
        profileTags: z.profile_tags?.join(", ") || "",
        placement: z.placement || null,
      },
      geometry: {
        type: "Polygon",
        coordinates: [z.polygon],
      },
    }));
    return { type: "FeatureCollection", features };
  }, [zones]);

  const poiCounts = useMemo(() => {
    if (!poiGeo) return {};
    const o = {};
    for (const k of POI_LAYER_ORDER) {
      o[k] = poiGeo[k]?.features?.length ?? 0;
    }
    return o;
  }, [poiGeo]);

  const devGeoJson = useMemo(() => {
    const features = developments.map((d) => ({
      type: "Feature",
      properties: { ...d },
      geometry: { type: "Point", coordinates: [d.lon, d.lat] },
    }));
    return { type: "FeatureCollection", features };
  }, [developments]);

  async function waitForDataReady() {
    const t0 = Date.now();
    setBackendStatus("Ожидание загрузки данных на сервере…");
    while (Date.now() - t0 < HEALTH_WAIT_MS) {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) throw new Error(String(res.status));
        const h = await res.json();
        if (h.data_loaded) {
          setBackendStatus("");
          return true;
        }
        const hint = h.last_error ? ` Ошибка: ${h.last_error}` : "";
        setBackendStatus(`Сервер ещё грузит датасет (ingest)…${hint}`);
      } catch (e) {
        console.error(e);
        setBackendStatus("Не удаётся связаться с API (/api/health). Проверьте URL и том /data.");
      }
      await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
    }
    setBackendStatus(
      "Данные так и не загрузились за отведённое время. Проверьте том /data (dataset_final.csv), логи контейнера и GEOATM_AUTO_INGEST=1.",
    );
    return false;
  }

  async function loadDevelopments() {
    if (!showNewBuildings) return;
    try {
      const res = await fetch(`${API_BASE}/developments`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setDevelopments(data.items || []);
      setDevSource(data.source || "");
    } catch (e) {
      console.error(e);
      setDevelopments([]);
      setDevSource("");
    }
  }

  async function loadZones() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("scenario", scenario);
      params.set("limit", String(limit));
      params.set("include_placement", "true");
      if (minScore !== "") params.set("min_score", minScore);
      const res = await fetch(`${API_BASE}/zones?${params.toString()}`);
      if (res.status === 503) {
        const t = await res.text();
        throw new Error(`503: данные ещё не готовы. ${t}`);
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setZones(data.zones || []);
      setModelVersion(data.model_version || "");
    } catch (e) {
      console.error(e);
      setZones([]);
      setBackendStatus(`Не удалось загрузить зоны: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadPoiLayers() {
    setPoiError("");
    try {
      const res = await fetch(`${API_BASE}/poi/geojson`);
      if (!res.ok) throw new Error(await res.text());
      setPoiGeo(await res.json());
    } catch (e) {
      console.error(e);
      setPoiGeo(null);
      setPoiError(e?.message || String(e));
    }
  }

  async function loadSummary() {
    try {
      const params = new URLSearchParams();
      params.set("scenario", scenario);
      const res = await fetch(`${API_BASE}/summary?${params.toString()}`);
      if (res.status === 503) {
        const t = await res.text();
        throw new Error(`Данные не загружены (503). Дождитесь ingest или проверьте /data. ${t}`);
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSummary(data.text || "");
    } catch (e) {
      console.error(e);
      setSummary(e?.message || "Не удалось загрузить summary (проверьте API).");
    }
  }

  useEffect(() => {
    (async () => {
      const ok = await waitForDataReady();
      if (ok) {
        await Promise.all([loadZones(), loadDevelopments(), loadPoiLayers()]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadDevelopments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showNewBuildings]);

  useEffect(() => {
    if (!modelVersion) return;
    loadZones();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario]);

  return (
    <div className="layout">
      <aside className="panel">
        <header className="brand-header">
          <img
            className="brand-logo"
            src={LOGO_URL}
            alt="ВТБ"
            width={168}
            height={48}
            decoding="async"
          />
          <div className="brand-text">
            <h1>GeoATM</h1>
            <p className="brand-sub">Приоритет зон H3</p>
          </div>
        </header>
        {backendStatus ? <div className="meta warn">{backendStatus}</div> : null}
        <div className="meta">API: {API_BASE}</div>
        <div className="meta">model_version: {modelVersion || "—"}</div>

        <label className="row-check" title="Слой точек новостроек; размер маркера и цвет — по delivery_score (см. попап).">
          <input
            type="checkbox"
            checked={showNewBuildings}
            onChange={(e) => setShowNewBuildings(e.target.checked)}
          />
          Новостройки (delivery_score)
        </label>
        <div className="meta">
          точек: {developments.length}
          {devSource ? ` · файл: ${devSource.split("/").pop()}` : ""}
        </div>

        <div className="panel-sub">Слои POI · координаты в подсказке при наведении</div>
        {poiError ? <div className="meta warn">POI: {poiError}</div> : null}
        {!poiError && poiGeo ? (
          <div className="meta">Слои загружены; при 0 точек слой пустой (нет данных в справочнике).</div>
        ) : null}
        <label className="row-check row-check-dense" title="Окружность вокруг центра ячейки H3 — зона оценки точки размещения АТМ (радиус из конфига API).">
          <input type="checkbox" checked={showPlacementCircles} onChange={(e) => setShowPlacementCircles(e.target.checked)} />
          Окружность зоны АТМ
        </label>
        {POI_LAYER_ORDER.map((k) => (
          <label key={k} className="row-check row-check-dense">
            <input
              type="checkbox"
              checked={!!poiVisibility[k]}
              onChange={(e) => setPoiVisibility((prev) => ({ ...prev, [k]: e.target.checked }))}
            />
            {POI_LAYER_LABELS[k]} ({poiGeo ? poiCounts[k] ?? 0 : "…"})
          </label>
        ))}

        <label title="В попапе ячейки H3 сверху показывается расстояние от центра зоны до ближайшей точки выбранной категории (те же данные, что в блоке размещения).">
          Расстояние до категории (в попапе зоны)
        </label>
        <select value={focusPoiCategory} onChange={(e) => setFocusPoiCategory(e.target.value)}>
          <option value="">Не выделять</option>
          {POI_LAYER_ORDER.map((k) => (
            <option key={k} value={k}>
              {POI_LAYER_LABELS[k]}
            </option>
          ))}
        </select>

        <label title="Фильтр зон по меткам сценария в ячейке H3 (см. теги на карте).">
          Сценарий (теги H3)
        </label>
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
          <option value="any">Все</option>
          <option value="white_spots">Белые пятна</option>
          <option value="competitor">Перехват конкурента</option>
          <option value="growth_retail">Динамика ТЦ/вузов (прокси)</option>
          <option value="low_utilization">Низкая загрузка</option>
        </select>

        <label title="DS — эвристический Demand Score по ячейке H3 (0–1), не путать с ML-priority.">
          Мин. DS (Demand Score), пусто = без фильтра
        </label>
        <input value={minScore} onChange={(e) => setMinScore(e.target.value)} placeholder="например 0.65" />

        <label>Лимит зон на карте</label>
        <input type="number" min={50} max={3000} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />

        <button disabled={loading} onClick={loadZones}>
          {loading ? "Загрузка…" : "Обновить карту"}
        </button>
        <button type="button" onClick={loadSummary} style={{ marginTop: 8, background: "#6366f1" }}>
          Суммаризация (RU)
        </button>

        <div className="summary">{summary}</div>
      </aside>

      <main className="map-wrap">
        <MapContainer center={[55.75, 37.62]} zoom={10} scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBoth zonesGeo={geojson} devGeo={showNewBuildings ? devGeoJson : { type: "FeatureCollection", features: [] }} />
          {showPlacementCircles &&
            zones.map((z) =>
              z.placement ? (
                <Circle
                  key={`plc-${z.h3_index}`}
                  center={[z.lat, z.lon]}
                  radius={z.placement.radius_m}
                  pathOptions={{
                    color: "#1d4ed8",
                    weight: 1,
                    fillColor: "#2563eb",
                    fillOpacity: 0.06,
                  }}
                />
              ) : null,
            )}
          <GeoJSON
            key={`${modelVersion}-${scenario}-${zones.length}-p-${focusPoiCategory}`}
            data={geojson}
            style={(feat) => {
              const ml = feat?.properties?.ml ?? 0;
              return {
                color: "#0f172a",
                weight: 1,
                fillColor: scoreColor(ml),
                fillOpacity: 0.32,
              };
            }}
            onEachFeature={(feat, layer) => {
              const p = feat.properties;
              layer.bindPopup(buildZonePopupHtml(p, { focusCategory: focusPoiCategory }));
            }}
          />
          {poiGeo &&
            POI_LAYER_ORDER.map((k) => {
              if (!poiVisibility[k]) return null;
              const data = poiGeo[k];
              if (!data?.features?.length) return null;
              return (
                <GeoJSON
                  key={`poi-${k}-${data.features.length}`}
                  data={data}
                  pointToLayer={(feat, latlng) => {
                    const kind = feat?.properties?.kind || k;
                    const st = POI_DOT[kind] || POI_DOT.competitor_atms;
                    return L.circleMarker(latlng, {
                      radius: st.r,
                      color: st.color,
                      weight: 1,
                      fillColor: st.fill,
                      fillOpacity: 0.88,
                    });
                  }}
                  onEachFeature={(feature, layer) => {
                    const raw = feature.properties?.title_tooltip || "";
                    const html = String(raw).replace(/\n/g, "<br/>");
                    layer.bindTooltip(html, {
                      sticky: true,
                      direction: "top",
                      opacity: 0.95,
                      className: "poi-tip",
                    });
                  }}
                />
              );
            })}
          {showNewBuildings && developments.length > 0 && (
            <LayerGroup>
              {developments.map((d) => (
                <CircleMarker
                  key={d.building_id}
                  center={[d.lat, d.lon]}
                  radius={5 + d.delivery_score * 12}
                  pathOptions={{
                    color: "#0f172a",
                    weight: 1,
                    fillColor: deliveryColor(d.delivery_score),
                    fillOpacity: 0.88,
                  }}
                >
                  <Tooltip direction="top" opacity={0.95} sticky className="poi-tip">
                    {typeof d.lat === "number" && typeof d.lon === "number" ? (
                      <>
                        <div className="tip-title">{d.name || d.building_id || "Новостройка"}</div>
                        <div className="tip-coords">
                          {d.lat.toFixed(6)}, {d.lon.toFixed(6)}
                        </div>
                      </>
                    ) : (
                      "Нет координат"
                    )}
                  </Tooltip>
                  <Popup>
                    <div className="zp-shell dev-popup">
                      <div className="zp-header">
                        <span className="zp-header-ico" title="Новостройка, delivery_score">
                          🏗
                        </span>
                        <div className="zp-header-text">
                          <div className="zp-header-title">{d.name || "Объект"}</div>
                          <div className="zp-header-sub">{d.building_id || "Новостройка · VTB GeoATM"}</div>
                        </div>
                      </div>
                      <div className="zp-list">
                        <DevFieldRow
                          meta={DEV_POPUP.coords}
                          valueTitle={
                            typeof d.lat === "number" && typeof d.lon === "number"
                              ? `WGS84: ${d.lat.toFixed(6)}, ${d.lon.toFixed(6)}`
                              : undefined
                          }
                        >
                          <span className="zp-mono">
                            {typeof d.lat === "number" && typeof d.lon === "number"
                              ? `${d.lat.toFixed(4)}, ${d.lon.toFixed(4)}`
                              : "—"}
                          </span>
                        </DevFieldRow>
                        <DevFieldRow meta={DEV_POPUP.delivery_score}>{formatNum(d.delivery_score)}</DevFieldRow>
                        <DevFieldRow meta={DEV_POPUP.delivery_tier}>{d.delivery_tier ?? "—"}</DevFieldRow>
                        <DevFieldRow meta={DEV_POPUP.completion}>{d.completion_date ?? "—"}</DevFieldRow>
                        <DevFieldRow meta={DEV_POPUP.months_to_completion}>
                          {d.months_to_completion ?? "—"}
                        </DevFieldRow>
                        {d.apartments != null && d.apartments > 0 ? (
                          <DevFieldRow meta={DEV_POPUP.apartments}>{d.apartments}</DevFieldRow>
                        ) : null}
                        {d.address ? <DevFieldRow meta={DEV_POPUP.address}>{d.address}</DevFieldRow> : null}
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </LayerGroup>
          )}
        </MapContainer>
      </main>
    </div>
  );
}
