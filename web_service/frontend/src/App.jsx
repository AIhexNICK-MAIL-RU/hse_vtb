import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { CircleMarker, LayerGroup, MapContainer, Popup, TileLayer, GeoJSON, useMap } from "react-leaflet";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

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
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setZones(data.zones || []);
      setModelVersion(data.model_version || "");
    } catch (e) {
      console.error(e);
      setZones([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadSummary() {
    try {
      const params = new URLSearchParams();
      params.set("scenario", scenario);
      const res = await fetch(`${API_BASE}/summary?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSummary(data.text || "");
    } catch (e) {
      console.error(e);
      setSummary("Не удалось загрузить summary (проверьте API).");
    }
  }

  useEffect(() => {
    loadZones();
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
        <div className="meta">model_version: {modelVersion || "—"}</div>

        <label className="row-check">
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

        <label>Сценарий H3</label>
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
          <option value="any">Все</option>
          <option value="white_spots">Белые пятна</option>
          <option value="competitor">Перехват конкурента</option>
          <option value="growth_retail">Динамика ТЦ/вузов (прокси)</option>
          <option value="low_utilization">Низкая загрузка</option>
        </select>

        <label>Мин. Demand Score (эвристика), пусто = без фильтра</label>
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
              layer.bindPopup(
                `<div style="font-size:12px;line-height:1.35">
                  <div><b>H3</b>: ${p.h3}</div>
                  <div><b>ML</b>: ${p.ml?.toFixed?.(3)}</div>
                  <div><b>DS</b>: ${p.ds?.toFixed?.(3)}</div>
                  <div><b>Теги</b>: ${p.tags || "—"}</div>
                </div>`
              );
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
                    <div style={{ fontSize: 12, lineHeight: 1.4, minWidth: 180 }}>
                      <div>
                        <b>{d.name || d.building_id}</b>
                      </div>
                      <div>
                        <b>delivery_score</b>: {d.delivery_score?.toFixed?.(3)}
                      </div>
                      <div>
                        <b>tier</b>: {d.delivery_tier}
                      </div>
                      <div>
                        <b>Сдача</b>: {d.completion_date}
                      </div>
                      <div>
                        <b>Мес. до сдачи</b>: {d.months_to_completion}
                      </div>
                      {d.address ? (
                        <div>
                          <b>Адрес</b>: {d.address}
                        </div>
                      ) : null}
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
