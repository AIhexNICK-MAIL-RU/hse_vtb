"""Скоринг новостроек по сроку сдачи (отдельно от Demand Score / ML по H3)."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.features import _read_table

# ~ средняя длина месяца
_DAYS_PER_MONTH = 30.4375


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

    # Уже сдано — оставляем заметный, но низкий приоритет «окна возможностей»
    if m < 0:
        handed = float(b.get("handed_over_score", 0.32))
        return (max(0.0, min(1.0, handed)), "handed_over")

    # До 3 мес — максимум
    if m <= float(b.get("months_urgent", 3)):
        return (1.0, "urgent_0_3m")

    # До 12 мес (≈ этот год + ближайшие кварталы) — высокий плато-плато с лёгким спадом
    if m <= 12:
        lo = float(b.get("score_at_12m", 0.82))
        t = (m - 3) / (12 - 3)
        return (1.0 - (1.0 - lo) * t, "high_3_12m")

    # До 24 мес — средний
    if m <= 24:
        hi = float(b.get("score_at_12m", 0.82))
        lo = float(b.get("score_at_24m", 0.58))
        t = (m - 12) / 12
        return (hi - (hi - lo) * t, "mid_12_24m")

    # До 36 мес — ниже
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


def resolve_developments_csv(data_dir: Path, cfg: dict[str, Any]) -> Path | None:
    env = os.environ.get("GEOATM_NEW_BUILDINGS_CSV")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.exists() else None
    name = str((cfg.get("developments") or {}).get("csv_filename", "new_buildings.csv"))
    p = (data_dir / name).resolve()
    return p if p.exists() else None


def _pick_date_column(df: pd.DataFrame) -> str | None:
    for c in ("completion_date", "handover_date", "keys_date", "delivery_date", "сдача", "completion"):
        if c in df.columns:
            return c
    return None


def load_developments(data_dir: Path, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Загрузка CSV новостроек. Обязательные поля: lat, lon + колонка даты сдачи.
    """
    path = resolve_developments_csv(data_dir, cfg)
    meta: dict[str, Any] = {"source": str(path) if path else None, "rows": 0, "errors": []}
    if path is None:
        return [], meta

    df = _read_table(path)
    if df.empty:
        meta["errors"].append("empty_file")
        return [], meta

    df.columns = [str(c).strip() for c in df.columns]
    lat_c = "lat" if "lat" in df.columns else ("latitude" if "latitude" in df.columns else None)
    lon_c = "lon" if "lon" in df.columns else ("longitude" if "longitude" in df.columns else None)
    date_c = _pick_date_column(df)
    if lat_c is None or lon_c is None or date_c is None:
        meta["errors"].append(f"missing_columns lat/lon/date got={list(df.columns)}")
        return [], meta

    ref_override = (cfg.get("developments") or {}).get("reference_date")
    if ref_override:
        try:
            ref = datetime.strptime(str(ref_override), "%Y-%m-%d").date()
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()

    out: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_c])
            lon = float(row[lon_c])
        except (TypeError, ValueError):
            meta["errors"].append(f"bad_latlon_row_{idx}")
            continue
        raw_d = row[date_c]
        ts = pd.to_datetime(raw_d, errors="coerce")
        if pd.isna(ts):
            meta["errors"].append(f"bad_date_row_{idx}")
            continue
        completion = ts.date()

        score, tier = delivery_score_and_tier(completion, ref=ref, cfg=cfg)
        bid = row.get("building_id", row.get("id", idx))
        name = str(row.get("name", row.get("title", "")) or "")[:500]
        addr = str(row.get("address", row.get("addr", "")) or "")[:500]

        out.append(
            {
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
        )

    meta["rows"] = len(out)
    return out, meta


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
