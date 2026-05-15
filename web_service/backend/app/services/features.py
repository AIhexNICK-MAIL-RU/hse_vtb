from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import h3
import numpy as np
import pandas as pd


def _read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
    head = "\n".join(text)
    sep = ";" if head.count(";") > head.count(",") else ","
    return pd.read_csv(path, sep=sep)


def _population_path(data_dir: Path) -> Path:
    candidates = [
        data_dir / "moscow_population_full.csv",
        data_dir / "moscow_population_full (1).csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return data_dir / "moscow_population_full.csv"


def load_okrug_reference(data_dir: Path) -> pd.DataFrame:
    """Точки/метаданные округов из GeoJSON (в датасете — Point)."""
    path = data_dir / "moscow_okrugs_demographics.geojson"
    if not path.exists():
        return pd.DataFrame(columns=["okrug_code", "okrug_name", "lat", "lon", "meta"])
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for feat in raw.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        coords = geom.get("coordinates")
        if not coords or geom.get("type") != "Point":
            continue
        lon, lat = float(coords[0]), float(coords[1])
        rows.append(
            {
                "okrug_code": str(props.get("okrug_code", "")),
                "okrug_name": str(props.get("okrug_name", "")),
                "lat": lat,
                "lon": lon,
                "meta": props,
            }
        )
    return pd.DataFrame(rows)


def assign_okrug(lat: float, lon: float, ref: pd.DataFrame) -> str | None:
    if ref.empty:
        return None
    best: tuple[float, str] | None = None
    for _, r in ref.iterrows():
        d = (lat - r["lat"]) ** 2 + (lon - r["lon"]) ** 2
        code = r["okrug_code"] or r["okrug_name"]
        if best is None or d < best[0]:
            best = (d, str(code))
    return best[1] if best else None


def h3_to_latlon(h: str) -> tuple[float, float]:
    lat, lng = h3.cell_to_latlng(h)
    return float(lat), float(lng)


def h3_to_polygon_geojson(h: str) -> list[list[float]]:
    boundary = h3.cell_to_boundary(h)
    ring: list[list[float]] = []
    for lat, lng in boundary:
        ring.append([float(lng), float(lat)])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def minmax_series(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").astype(float)
    lo, hi = float(np.nanmin(s)), float(np.nanmax(s))
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def compute_heuristic_scores(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    w = cfg.get("demand_score", {}).get("weights", {})
    w_sum = float(w.get("total_sum", 0.35))
    w_uc = float(w.get("unique_customers", 0.25))
    w_tpc = float(w.get("transactions_per_customer", 0.20))
    w_poi = float(w.get("poi_score", 0.12))
    w_comp = float(w.get("competitor_proximity", 0.08))

    out = df.copy()
    out["norm_total_sum"] = minmax_series(out["total_sum"])
    out["norm_unique_customers"] = minmax_series(out["unique_customers"])
    out["norm_tpc"] = minmax_series(out["transactions_per_customer"])

    poi = (
        pd.to_numeric(out["metro_count"], errors="coerce").fillna(0)
        + pd.to_numeric(out["mall_count"], errors="coerce").fillna(0)
        + pd.to_numeric(out["university_count"], errors="coerce").fillna(0)
    )
    out["poi_score"] = poi
    out["norm_poi"] = minmax_series(out["poi_score"])
    out["norm_comp"] = minmax_series(out["competitor_atm_count"])

    out["heuristic_score"] = (
        w_sum * out["norm_total_sum"]
        + w_uc * out["norm_unique_customers"]
        + w_tpc * out["norm_tpc"]
        + w_poi * out["norm_poi"]
        + w_comp * out["norm_comp"]
    ).clip(0, 1)
    return out


def white_spot_thresholds(df: pd.DataFrame, cfg: dict[str, Any]) -> tuple[float, float]:
    """
    Пороги для «белых пятен» среди кандидатов (нет ВТБ и atm_activity=0).
    Абсолютный white_spot_threshold=0.7 на этом датасете недостижим (max DS ~0.22);
    по умолчанию — перцентили внутри подвыборки кандидатов.
    """
    ds_cfg = cfg.get("demand_score", {})
    uc_pct = int(ds_cfg.get("min_unique_customers_percentile", 50))
    ds_pct = int(ds_cfg.get("white_spot_ds_percentile", 75))
    atm_act = pd.to_numeric(df.get("atm_activity"), errors="coerce").fillna(0).astype(int)
    cand = (df["vtb_atm_count"].astype(int) == 0) & (atm_act == 0)
    sub = df.loc[cand]
    if sub.empty:
        return float("inf"), float("inf")
    uc_thr = float(np.percentile(sub["unique_customers"].astype(float), uc_pct))
    if "white_spot_ds_percentile" in ds_cfg:
        ds_thr = float(np.percentile(sub["heuristic_score"].astype(float), ds_pct))
    else:
        ds_thr = float(ds_cfg.get("white_spot_threshold", 0.70))
    return ds_thr, uc_thr


def tag_scenarios(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    scen = cfg.get("scenarios", {})
    comp_min = int(scen.get("competitor_min_atms", 2))
    low_pct = int(scen.get("low_utilization_sum_per_customer_percentile", 25))
    vol_pct = int(scen.get("growth_volatility_percentile", 75))
    ds_thr, uc_thr = white_spot_thresholds(out, cfg)

    spc_low = float(np.percentile(out["sum_per_customer"].astype(float), low_pct))
    vol_thr = float(np.percentile(pd.to_numeric(out["avg_std"], errors="coerce").fillna(0), vol_pct))

    tags: list[list[str]] = []
    for _, r in out.iterrows():
        t: list[str] = []
        vtb = int(r["vtb_atm_count"])
        comp = int(r["competitor_atm_count"])
        atm_act = int(r.get("atm_activity", 0) or 0)
        h = float(r["heuristic_score"])
        uc = float(r["unique_customers"])
        mall = int(r["mall_count"])
        avg_std = float(r.get("avg_std") or 0) if pd.notna(r.get("avg_std")) else 0.0
        spc = float(r.get("sum_per_customer") or 0)

        if vtb == 0 and atm_act == 0 and uc >= uc_thr and h >= ds_thr:
            t.append("white_spots")
        if comp >= comp_min and vtb == 0:
            t.append("competitor")
        if (mall >= 1 or int(r["university_count"]) >= 1) and avg_std >= vol_thr:
            t.append("growth_retail")
        if vtb >= 1 and spc <= spc_low:
            t.append("low_utilization")
        tags.append(t)
    out["scenario_tags"] = tags
    return out


def compute_retention_metrics(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Прокси удержания и давления конкуренции по H3 (см. docs/RETENTION_IDEAS.md)."""
    out = df.copy()
    rc = cfg.get("retention", {})
    w_uc = float(rc.get("proxy_weight_unique", 0.28))
    w_spc = float(rc.get("proxy_weight_spc", 0.24))
    w_tpc = float(rc.get("proxy_weight_tpc", 0.24))
    w_stable = float(rc.get("proxy_weight_stability", 0.24))
    ws = w_uc + w_spc + w_tpc + w_stable
    if ws <= 0:
        ws = 1.0
    w_uc, w_spc, w_tpc, w_stable = w_uc / ws, w_spc / ws, w_tpc / ws, w_stable / ws

    norm_uc = minmax_series(out["unique_customers"])
    norm_spc = minmax_series(out["sum_per_customer"])
    norm_tpc = minmax_series(out["transactions_per_customer"])
    vol = pd.to_numeric(out.get("avg_std"), errors="coerce").fillna(0).astype(float)
    norm_vol = minmax_series(vol)
    stability = (1.0 - norm_vol).clip(0, 1)

    out["retention_proxy_score"] = (
        w_uc * norm_uc + w_spc * norm_spc + w_tpc * norm_tpc + w_stable * stability
    ).clip(0, 1).astype(float)

    nc = float(rc.get("pressure_weight_competitor", 0.65))
    nm = float(rc.get("pressure_weight_metro", 0.35))
    s = nc + nm
    if s <= 0:
        s = 1.0
    nc, nm = nc / s, nm / s
    norm_comp = minmax_series(out["competitor_atm_count"])
    norm_metro = minmax_series(out["metro_count"])
    out["competition_pressure_score"] = (nc * norm_comp + nm * norm_metro).clip(0, 1).astype(float)

    metro_thr = float(
        pd.to_numeric(out["metro_count"], errors="coerce").fillna(0).quantile(0.75)
    )
    med_h = float(out["heuristic_score"].median())
    ret_stable_thr = float(rc.get("stable_demand_retention_min", 0.65))
    norm_comp_row = minmax_series(out["competitor_atm_count"])

    prof: list[list[str]] = []
    for row_idx in out.index:
        r = out.loc[row_idx]
        mc = int(pd.to_numeric(r.get("metro_count"), errors="coerce") or 0)
        mall = int(pd.to_numeric(r.get("mall_count"), errors="coerce") or 0)
        uni = int(pd.to_numeric(r.get("university_count"), errors="coerce") or 0)
        vtb = int(pd.to_numeric(r.get("vtb_atm_count"), errors="coerce") or 0)
        comp = int(pd.to_numeric(r.get("competitor_atm_count"), errors="coerce") or 0)
        ret = float(out.loc[row_idx, "retention_proxy_score"])
        h = float(out.loc[row_idx, "heuristic_score"])
        nc_val = float(norm_comp_row.loc[row_idx])
        t: list[str] = []
        if mc >= metro_thr and (mall >= 1 or uni >= 1):
            t.append("transit_retail_hub")
        if ret >= ret_stable_thr and h >= med_h:
            t.append("stable_demand")
        if vtb >= 1 and comp >= int(rc.get("competitive_corridor_min_competitors", 2)) and nc_val >= float(
            rc.get("competitive_corridor_norm_comp_min", 0.4)
        ):
            t.append("competitive_corridor")
        prof.append(t)
    out["profile_tags"] = prof
    return out


def enrich_geo(
    df: pd.DataFrame,
    data_dir: Path,
    cfg: dict[str, Any],
    *,
    okrug_ref: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = df.copy()
    latlons = [h3_to_latlon(h) for h in out["h3_index"].astype(str)]
    out["lat"] = [x[0] for x in latlons]
    out["lon"] = [x[1] for x in latlons]
    ref = okrug_ref if okrug_ref is not None else load_okrug_reference(data_dir)
    out["okrug"] = [assign_okrug(lat, lon, ref) for lat, lon in zip(out["lat"], out["lon"], strict=False)]
    return out


def load_core_dataset(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "dataset_final.csv"
    if not path.exists():
        hint = (
            f"Нет dataset_final.csv в {data_dir}. "
            "В облаке (Timeweb и др.): смонтируйте постоянное хранилище в каталог **/data** "
            "внутри контейнера и загрузите туда файлы кейса (dataset_final.csv и справочники), "
            "либо задайте GEOATM_DATA_DIR на каталог, где они уже лежат."
        )
        raise FileNotFoundError(hint)
    return pd.read_csv(path)


def load_priority_zones(data_dir: Path) -> pd.DataFrame:
    return _read_table(data_dir / "priority_zones.csv")


def load_poi_layers(data_dir: Path) -> dict[str, pd.DataFrame]:
    out = {
        "vtb_atms": _read_table(data_dir / "vtb_atms.csv"),
        "offices": _read_table(data_dir / "offices.csv"),
        "competitor_atms": _read_table(data_dir / "competitor_atms.csv"),
        "metro": _read_table(data_dir / "metro.csv"),
        "malls": _read_table(data_dir / "malls.csv"),
        "universities": _read_table(data_dir / "universities.csv"),
        "markets": _read_table(data_dir / "markets.csv"),
        "hardware_stores": _read_table(data_dir / "hardware_stores.csv"),
    }
    return out


FEATURE_COLUMNS = [
    "total_sum",
    "unique_customers",
    "transactions_per_customer",
    "records_per_customer",
    "sum_per_customer",
    "metro_count",
    "mall_count",
    "university_count",
    "competitor_atm_count",
    "vtb_atm_count",
    "vtb_office_count",
    "atm_activity",
    "atm_active_customers",
    "heuristic_score",
]
