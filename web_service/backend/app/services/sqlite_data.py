"""Загрузка датасета из встроенной SQLite (собирается scripts/build_embedded_sqlite.py)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


def embedded_sqlite_default_path() -> Path:
    """Путь к встроенной БД рядом с пакетом app (в образе: /app/app/embedded/geoatm.sqlite)."""
    return Path(__file__).resolve().parent.parent / "embedded" / "geoatm.sqlite"


def resolve_sqlite_path() -> Path | None:
    """
    Порядок: GEOATM_SQLITE_PATH → встроенный geoatm.sqlite → None (тогда CSV из data_dir).

    Отключить SQLite: GEOATM_USE_SQLITE=0
    """
    if os.environ.get("GEOATM_USE_SQLITE", "1").lower() in {"0", "false", "no"}:
        return None
    env = os.environ.get("GEOATM_SQLITE_PATH", "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    emb = embedded_sqlite_default_path()
    if emb.is_file():
        return emb
    return None


def _open_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_core_dataset_sqlite(path: Path) -> pd.DataFrame:
    with _open_readonly(path) as con:
        return pd.read_sql_query("SELECT * FROM dataset_final", con)


def load_priority_zones_sqlite(path: Path) -> pd.DataFrame:
    with _open_readonly(path) as con:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='priority_zones'")
        if not cur.fetchone():
            return pd.DataFrame()
        return pd.read_sql_query("SELECT * FROM priority_zones", con)


def load_poi_layers_sqlite(path: Path) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    mapping = [
        ("vtb_atms", "vtb_atms"),
        ("offices", "offices"),
        ("competitor_atms", "competitor_atms"),
        ("metro", "metro"),
        ("malls", "malls"),
        ("universities", "universities"),
        ("markets", "markets"),
        ("hardware_stores", "hardware_stores"),
    ]
    with _open_readonly(path) as con:
        for key, table in mapping:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cur.fetchone():
                out[key] = pd.read_sql_query(f'SELECT * FROM "{table}"', con)
            else:
                out[key] = pd.DataFrame()
    return out


def load_okrug_reference_sqlite(path: Path) -> pd.DataFrame:
    with _open_readonly(path) as con:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='okrugs'")
        if not cur.fetchone():
            return pd.DataFrame(columns=["okrug_code", "okrug_name", "lat", "lon", "meta"])
        df = pd.read_sql_query("SELECT * FROM okrugs", con)
    if df.empty:
        return pd.DataFrame(columns=["okrug_code", "okrug_name", "lat", "lon", "meta"])
    if "meta_json" in df.columns:
        df["meta"] = df["meta_json"].apply(lambda s: json.loads(s) if isinstance(s, str) else {})
        df = df.drop(columns=["meta_json"])
    elif "meta" not in df.columns:
        df["meta"] = [{}] * len(df)
    return df


def load_developments_rows_sqlite(path: Path) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Сырые строки new_buildings из SQLite, если таблица есть; иначе (None, meta)."""
    meta: dict[str, Any] = {"source": f"sqlite:{path.name}", "rows": 0, "errors": []}
    with _open_readonly(path) as con:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='new_buildings'")
        if not cur.fetchone():
            return None, {**meta, "source": None}
        df = pd.read_sql_query("SELECT * FROM new_buildings", con)
    meta["rows"] = len(df)
    return df, meta
