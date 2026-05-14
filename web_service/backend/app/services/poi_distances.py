"""Расстояния до POI, GeoJSON слоёв и контекст зоны размещения АТМ."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

EARTH_R_M = 6_371_000.0

_NAME_COLUMNS = (
    "name",
    "title",
    "station",
    "label",
    "address",
    "addr",
    "bank",
    "operator",
    "id",
    "building_id",
)


def haversine_m(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Вектор расстояний в метрах (WGS84)."""
    p1 = math.radians(lat1)
    t1 = math.radians(lon1)
    p2 = np.radians(lat2.astype(float))
    t2 = np.radians(lon2.astype(float))
    dp = p2 - p1
    dt = np.abs(t2 - t1)
    dt = np.minimum(dt, 2 * math.pi - dt)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dt / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))
    return EARTH_R_M * c


def detect_lat_lon_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if df.empty:
        return None, None
    lower = {str(c).lower(): c for c in df.columns}
    lat_k = ("lat", "latitude", "широта")
    lon_k = ("lon", "lng", "longitude", "долгота")
    lat_c = next((lower[k] for k in lat_k if k in lower), None)
    lon_c = next((lower[k] for k in lon_k if k in lower), None)
    return lat_c, lon_c


def pick_label_row(row: pd.Series, fallback: str) -> str:
    for c in _NAME_COLUMNS:
        if c in row.index and pd.notna(row[c]) and str(row[c]).strip():
            return str(row[c]).strip()[:200]
    return fallback


def nearest_poi(
    center_lat: float,
    center_lon: float,
    df: pd.DataFrame,
    *,
    fallback_name: str,
) -> dict[str, Any] | None:
    if df is None or df.empty:
        return None
    lat_c, lon_c = detect_lat_lon_columns(df)
    if not lat_c or not lon_c:
        return None
    try:
        lat = pd.to_numeric(df[lat_c], errors="coerce")
        lon = pd.to_numeric(df[lon_c], errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    mask = lat.notna() & lon.notna()
    if not bool(mask.any()):
        return None
    sub = df.loc[mask].reset_index(drop=True)
    latv = pd.to_numeric(sub[lat_c], errors="coerce").to_numpy()
    lonv = pd.to_numeric(sub[lon_c], errors="coerce").to_numpy()
    d = haversine_m(center_lat, center_lon, latv, lonv)
    j = int(np.nanargmin(d))
    dist = float(d[j])
    if not math.isfinite(dist):
        return None
    row = sub.iloc[j]
    return {
        "name": pick_label_row(row, fallback_name),
        "lat": float(latv[j]),
        "lon": float(lonv[j]),
        "distance_m": int(round(dist)),
    }


def count_within_radius(
    center_lat: float,
    center_lon: float,
    df: pd.DataFrame,
    radius_m: float,
) -> int:
    if df is None or df.empty or radius_m <= 0:
        return 0
    lat_c, lon_c = detect_lat_lon_columns(df)
    if not lat_c or not lon_c:
        return 0
    lat = pd.to_numeric(df[lat_c], errors="coerce")
    lon = pd.to_numeric(df[lon_c], errors="coerce")
    mask = lat.notna() & lon.notna()
    if not bool(mask.any()):
        return 0
    sub = df.loc[mask]
    d = haversine_m(center_lat, center_lon, sub[lat_c].astype(float).to_numpy(), sub[lon_c].astype(float).to_numpy())
    return int(np.sum(d <= radius_m))


def df_to_geojson_features(
    df: pd.DataFrame,
    *,
    kind: str,
    label_fallback: str,
    max_features: int = 8000,
) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    lat_c, lon_c = detect_lat_lon_columns(df)
    if not lat_c or not lon_c:
        return []
    lat = pd.to_numeric(df[lat_c], errors="coerce")
    lon = pd.to_numeric(df[lon_c], errors="coerce")
    mask = lat.notna() & lon.notna()
    sub = df.loc[mask].copy()
    if sub.empty:
        return []
    if len(sub) > max_features:
        sub = sub.sample(n=max_features, random_state=42)
    feats: list[dict[str, Any]] = []
    for _, row in sub.iterrows():
        la = float(row[lat_c])
        lo = float(row[lon_c])
        name = pick_label_row(row, label_fallback)
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lo, la]},
                "properties": {
                    "kind": kind,
                    "name": name,
                    "lat": round(la, 6),
                    "lon": round(lo, 6),
                    "title_tooltip": f"{name}\n{la:.6f}, {lo:.6f}",
                },
            }
        )
    return feats


def build_placement_payload(
    center_lat: float,
    center_lon: float,
    h3: str,
    poi: dict[str, pd.DataFrame],
    *,
    radius_m: int,
    ml_score: float,
    heuristic_score: float,
    scenario_tags: list[str],
) -> dict[str, Any]:
    """Словарь под Pydantic PlacementOut."""
    nm = nearest_poi(center_lat, center_lon, poi.get("metro") or pd.DataFrame(), fallback_name="станция")
    mall = nearest_poi(center_lat, center_lon, poi.get("malls") or pd.DataFrame(), fallback_name="объект")
    uni = nearest_poi(center_lat, center_lon, poi.get("universities") or pd.DataFrame(), fallback_name="ВУЗ")
    off = nearest_poi(center_lat, center_lon, poi.get("offices") or pd.DataFrame(), fallback_name="офис")
    vtb = nearest_poi(center_lat, center_lon, poi.get("vtb_atms") or pd.DataFrame(), fallback_name="ВТБ")
    comp = nearest_poi(center_lat, center_lon, poi.get("competitor_atms") or pd.DataFrame(), fallback_name="конкурент")
    mkt = nearest_poi(center_lat, center_lon, poi.get("markets") or pd.DataFrame(), fallback_name="рынок")
    hw = nearest_poi(center_lat, center_lon, poi.get("hardware_stores") or pd.DataFrame(), fallback_name="строймагазин")

    n_comp = count_within_radius(center_lat, center_lon, poi.get("competitor_atms") or pd.DataFrame(), float(radius_m))

    tags_ru = ", ".join(scenario_tags) if scenario_tags else "без тегов"
    parts = [
        f"Кандидат на АТМ — центр ячейки H3; окружность ~{radius_m} м (пешая зона оценки). "
        f"ML={ml_score:.3f}, DS={heuristic_score:.3f}; сценарии: {tags_ru}.",
    ]
    if comp:
        parts.append(
            f"Ближайший конкурент: «{comp['name']}» ~{comp['distance_m']} м; "
            f"в радиусе {radius_m} м: {n_comp} АТМ конкурентов (слой на карте)."
        )
    else:
        parts.append("Нет ближайшего конкурента с координатами — проверьте competitor_atms.csv.")
    if not mkt and not hw:
        parts.append("Рынки/строймагазины: при необходимости добавьте markets.csv и hardware_stores.csv с колонками lat, lon.")

    return {
        "radius_m": radius_m,
        "summary": " ".join(parts),
        "nearest_metro": nm,
        "nearest_mall": mall,
        "nearest_market": mkt,
        "nearest_hardware": hw,
        "nearest_university": uni,
        "nearest_office": off,
        "nearest_vtb_atm": vtb,
        "nearest_competitor_atm": comp,
        "competitors_in_radius": n_comp,
    }


def poi_layers_to_geojson(poi: dict[str, pd.DataFrame], max_per: int = 8000) -> dict[str, Any]:
    """Имена ключей = стабильные id слоя для фронта."""
    mapping: list[tuple[str, str, str]] = [
        ("competitor_atms", "competitor_atms", "Банкомат конкурента"),
        ("vtb_atms", "vtb_atms", "Банкомат ВТБ"),
        ("metro", "metro", "Метро"),
        ("malls", "malls", "ТЦ / торговый объект"),
        ("universities", "universities", "ВУЗ"),
        ("offices", "offices", "Офис"),
        ("markets", "markets", "Рынок"),
        ("hardware_stores", "hardware_stores", "Строймагазин"),
    ]
    out: dict[str, Any] = {}
    for key, _df_key, fb in mapping:
        feats = df_to_geojson_features(poi.get(key) or pd.DataFrame(), kind=key, label_fallback=fb, max_features=max_per)
        out[key] = {"type": "FeatureCollection", "features": feats}
    return out
