"""Скоринг новостроек по сроку сдачи (отдельно от Demand Score / ML по H3)."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.developments_geocode import (
    default_geocode_cache_path,
    default_spisok_path,
    ensure_geocoded_addresses,
    web_service_root,
)
from app.services.features import _read_table

# ~ средняя длина месяца
_DAYS_PER_MONTH = 30.4375

_SPISOK_ADDR_COLS = ("Адрес", "address", "addr")
_SPISOK_APT_COLS = ("Количество квартир", "apartments", "apartment_count", "квартир")
_SPISOK_YEAR_COLS = ("Срок сдачи", "completion_year", "year", "сдача")


def months_until_completion(completion: date, ref: date) -> float:
    return (completion - ref).days / _DAYS_PER_MONTH


def delivery_score_and_tier(
    completion: date,
    ref: date | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """
    Возвращает (delivery_score ∈ [0,1], tier) — чем ближе сдача, тем выше.
    Не смешивается с heuristic_score / ml_score по зонам H3.
    """
    cfg = cfg or {}
    b = (cfg.get("developments") or {}).get("buckets", {})
    ref = ref or date.today()

    m = months_until_completion(completion, ref)

    if m < 0:
        handed = float(b.get("handed_over_score", 0.32))
        return (max(0.0, min(1.0, handed)), "handed_over")

    if m <= float(b.get("months_urgent", 3)):
        return (1.0, "urgent_0_3m")

    if m <= 12:
        lo = float(b.get("score_at_12m", 0.82))
        t = (m - 3) / (12 - 3)
        return (1.0 - (1.0 - lo) * t, "high_3_12m")

    if m <= 24:
        hi = float(b.get("score_at_12m", 0.82))
        lo = float(b.get("score_at_24m", 0.58))
        t = (m - 12) / 12
        return (hi - (hi - lo) * t, "mid_12_24m")

    if m <= 36:
        hi = float(b.get("score_at_24m", 0.58))
        lo = float(b.get("score_at_36m", 0.38))
        t = (m - 24) / 12
        return (hi - (hi - lo) * t, "low_24_36m")

    floor = float(b.get("long_term_floor", 0.14))
    decay = float(b.get("long_term_decay_per_month", 0.012))
    base36 = float(b.get("score_at_36m", 0.38))
    s = base36 - decay * (m - 36)
    return (max(floor, s), "long_term")


def _dev_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("developments") or {}


def resolve_spisok_domov_path(cfg: dict[str, Any]) -> Path | None:
    dc = _dev_cfg(cfg)
    rel = dc.get("spisok_csv")
    if rel:
        p = (web_service_root() / str(rel)).resolve()
        if p.is_file():
            return p
    p = default_spisok_path()
    return p if p.is_file() else None


def resolve_developments_csv(data_dir: Path, cfg: dict[str, Any]) -> Path | None:
    env = os.environ.get("GEOATM_NEW_BUILDINGS_CSV")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.exists() else None

    spisok = resolve_spisok_domov_path(cfg)
    if spisok is not None:
        return spisok

    name = str(_dev_cfg(cfg).get("csv_filename", "new_buildings.csv"))
    p = (data_dir / name).resolve()
    return p if p.exists() else None


def _first_col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    cols = {str(c).strip(): c for c in df.columns}
    for n in names:
        if n in cols:
            return str(cols[n])
    return None


def is_spisok_domov_format(df: pd.DataFrame) -> bool:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return _first_col(df, _SPISOK_ADDR_COLS) is not None and _first_col(df, _SPISOK_YEAR_COLS) is not None


def completion_date_from_value(
    raw: Any,
    *,
    year_month: int = 7,
    year_day: int = 1,
    cfg: dict[str, Any] | None = None,
) -> date | None:
    if cfg:
        dc = _dev_cfg(cfg)
        year_month = int(dc.get("completion_year_month", year_month))
        year_day = int(dc.get("completion_year_day", year_day))
    """Год (2026) → 1 июля; полная дата — как есть."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        y = int(raw)
        if 2000 <= y <= 2100:
            return date(y, year_month, year_day)
    s = str(raw).strip()
    if re.fullmatch(r"\d{4}", s):
        y = int(s)
        if 2000 <= y <= 2100:
            return date(y, year_month, year_day)
    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def normalize_spisok_domov(df: pd.DataFrame, cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    addr_c = _first_col(df, _SPISOK_ADDR_COLS)
    apt_c = _first_col(df, _SPISOK_APT_COLS)
    year_c = _first_col(df, _SPISOK_YEAR_COLS)
    if addr_c is None or year_c is None:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        addr = str(row[addr_c]).strip()
        if not addr:
            continue
        apt = 0
        if apt_c is not None:
            try:
                apt = int(float(row[apt_c]))
            except (TypeError, ValueError):
                apt = 0
        completion = completion_date_from_value(row[year_c], cfg=cfg)
        if completion is None:
            continue
        bid = hashlib.sha256(addr.encode("utf-8")).hexdigest()[:12]
        rows.append(
            {
                "building_id": f"spisok-{bid}",
                "name": addr[:200],
                "address": addr,
                "apartments": apt,
                "completion_date": completion.isoformat(),
                "lat": None,
                "lon": None,
            }
        )
    return pd.DataFrame(rows)


def spisok_domov_to_geocoded_df(
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    allow_network: bool | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Нормализация spisok_domov + координаты из кэша / Nominatim."""
    norm = normalize_spisok_domov(df, cfg)
    if norm.empty:
        return norm, ["spisok_empty_or_bad_columns"]

    dc = _dev_cfg(cfg)
    cache_rel = dc.get("geocode_cache", "screens/spisok_domov_geocoded.csv")
    cache_path = (web_service_root() / str(cache_rel)).resolve()
    if allow_network is None:
        allow_network = os.environ.get("GEOATM_GEOCODE_NETWORK", "1").lower() in {"1", "true", "yes"}

    addresses = norm["address"].astype(str).tolist()
    coords, geo_errors = ensure_geocoded_addresses(
        addresses, cache_path, allow_network=allow_network
    )

    lats: list[float | None] = []
    lons: list[float | None] = []
    for addr in addresses:
        pt = coords.get(addr.strip())
        if pt:
            lats.append(pt[0])
            lons.append(pt[1])
        else:
            lats.append(None)
            lons.append(None)
    norm["lat"] = lats
    norm["lon"] = lons
    ok = norm[norm["lat"].notna() & norm["lon"].notna()].copy()
    return ok, geo_errors


def _pick_date_column(df: pd.DataFrame) -> str | None:
    for c in ("completion_date", "handover_date", "keys_date", "delivery_date", "сдача", "completion"):
        if c in df.columns:
            return c
    return None


def load_developments_from_df(
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    source_meta: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Та же логика, что load_developments, но из уже загруженного DataFrame (SQLite)."""
    meta: dict[str, Any] = dict(source_meta) if source_meta else {"source": "dataframe", "rows": 0, "errors": []}
    meta.setdefault("errors", [])
    if df.empty:
        meta["errors"].append("empty_file")
        return [], meta

    if is_spisok_domov_format(df):
        df, geo_err = spisok_domov_to_geocoded_df(df, cfg)
        meta["errors"].extend(geo_err[:20])
        if df.empty:
            meta["errors"].append("spisok_geocode_no_rows")
            return [], meta

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lat_c = "lat" if "lat" in df.columns else ("latitude" if "latitude" in df.columns else None)
    lon_c = "lon" if "lon" in df.columns else ("longitude" if "longitude" in df.columns else None)
    date_c = _pick_date_column(df)
    if lat_c is None or lon_c is None or date_c is None:
        meta["errors"].append(f"missing_columns lat/lon/date got={list(df.columns)}")
        return [], meta

    ref_override = _dev_cfg(cfg).get("reference_date")
    if ref_override:
        try:
            ref = datetime.strptime(str(ref_override), "%Y-%m-%d").date()
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()

    apt_c = "apartments" if "apartments" in df.columns else None

    out: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_c])
            lon = float(row[lon_c])
        except (TypeError, ValueError):
            meta["errors"].append(f"bad_latlon_row_{idx}")
            continue
        raw_d = row[date_c]
        completion = completion_date_from_value(raw_d, cfg=cfg)
        if completion is None:
            ts = pd.to_datetime(raw_d, errors="coerce")
            if pd.isna(ts):
                meta["errors"].append(f"bad_date_row_{idx}")
                continue
            completion = ts.date()

        score, tier = delivery_score_and_tier(completion, ref=ref, cfg=cfg)
        bid = row.get("building_id", row.get("id", idx))
        name = str(row.get("name", row.get("title", "")) or "")[:500]
        addr = str(row.get("address", row.get("addr", name)) or "")[:500]
        apt = 0
        if apt_c is not None:
            try:
                apt = int(float(row[apt_c]))
            except (TypeError, ValueError):
                apt = 0

        item: dict[str, Any] = {
            "building_id": str(bid),
            "name": name,
            "address": addr,
            "lat": lat,
            "lon": lon,
            "completion_date": completion.isoformat(),
            "delivery_score": round(score, 4),
            "delivery_tier": tier,
            "months_to_completion": round(months_until_completion(completion, ref), 2),
        }
        if apt > 0:
            item["apartments"] = apt
        out.append(item)

    meta["rows"] = len(out)
    return out, meta


def load_developments(data_dir: Path, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Загрузка новостроек: приоритет spisok_domov.csv (screens/), иначе new_buildings.csv.
    Для spisok — геокодирование по адресу (кэш screens/spisok_domov_geocoded.csv).
    """
    path = resolve_developments_csv(data_dir, cfg)
    meta: dict[str, Any] = {"source": str(path) if path else None, "rows": 0, "errors": []}
    if path is None:
        return [], meta

    df = _read_table(path)
    if is_spisok_domov_format(df):
        meta["format"] = "spisok_domov"
    return load_developments_from_df(df, cfg, source_meta=meta)


def developments_geojson(items: list[dict[str, Any]]) -> dict[str, Any]:
    feats = []
    for it in items:
        feats.append(
            {
                "type": "Feature",
                "properties": {k: v for k, v in it.items() if k not in ("lat", "lon")},
                "geometry": {"type": "Point", "coordinates": [float(it["lon"]), float(it["lat"])]},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def build_new_buildings_table_for_sqlite(cfg: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Нормализованная таблица new_buildings для embedded SQLite."""
    path = resolve_spisok_domov_path(cfg) or default_spisok_path()
    meta: dict[str, Any] = {"source": str(path), "errors": []}
    if not path.is_file():
        meta["errors"].append("spisok_not_found")
        return pd.DataFrame(), meta
    raw = _read_table(path)
    df, errs = spisok_domov_to_geocoded_df(raw, cfg, allow_network=False)
    meta["errors"] = errs[:30]
    meta["rows_raw"] = len(raw)
    meta["rows_geocoded"] = len(df)
    return df, meta
