import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { CircleMarker, LayerGroup, MapContainer, Popup, TileLayer, GeoJSON, useMap } from "react-leaflet";
import { buildZonePopupHtml, DEV_POPUP, formatNum } from "./glossary.js";

/** Прод: тот же хост, префикс /api. Подпуть деплоя: учитываем import.meta.env.BASE_URL (Vite). */
const viteApi = import.meta.env.VITE_API_URL;
const viteBase = import.meta.env.BASE_URL || "/";
const basePrefix = viteBase === "/" ? "" : viteBase.replace(/\/$/, "");
const API_BASE =
  viteApi != null && String(viteApi).trim() !== ""
    ? String(viteApi).trim().replace(/\/$/, "")
    : `${basePrefix}/api`;

const HEALTH_POLL_MS = 2000;
const HEALTH_WAIT_MS = 180_000;

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
        <div className="zp-item-val" title={valueTitle}>
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

  const geojson = useMemo(() => {
    const features = zones.map((z) => ({
      type: "Feature",
      properties: {
        h3: z.h3_index,
        ml: z.ml_score,
        ds: z.heuristic_score,
        tags: z.scenario_tags?.join(", ") || "",
      },
      geometry: {
        type: "Polygon",
        coordinates: [z.polygon],
      },
    }));
    return { type: "FeatureCollection", features };
  }, [zones]);

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
        await loadZones();
        await loadDevelopments();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadDevelopments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showNewBuildings]);

  return (
    <div className="layout">
      <aside className="panel">
        <h1>VTB GeoATM — приоритет зон</h1>
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
          <GeoJSON
            key={modelVersion + scenario + zones.length}
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
              layer.bindPopup(buildZonePopupHtml(p));
            }}
          />
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
                        <DevFieldRow meta={DEV_POPUP.coords}>
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
