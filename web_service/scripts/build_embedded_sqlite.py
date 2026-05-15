#!/usr/bin/env python3
"""
Сборка встроенной SQLite из CSV/GeoJSON кейса (корень репозитория по умолчанию).
Результат: backend/app/embedded/geoatm.sqlite — попадает в образ при COPY backend/app.

Запуск из каталога web_service:
  python3 scripts/build_embedded_sqlite.py
Или с путём к корню кейса:
  python3 scripts/build_embedded_sqlite.py /path/to/case_root
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# web_service/scripts/ → web_service → repo root
_SCRIPT = Path(__file__).resolve()
WEB_SERVICE = _SCRIPT.parents[1]
REPO_ROOT_DEFAULT = WEB_SERVICE.parent
OUT_DB = WEB_SERVICE / "backend" / "app" / "embedded" / "geoatm.sqlite"

TABLES = [
    ("dataset_final", "dataset_final.csv"),
    ("vtb_atms", "vtb_atms.csv"),
    ("offices", "offices.csv"),
    ("competitor_atms", "competitor_atms.csv"),
    ("metro", "metro.csv"),
    ("malls", "malls.csv"),
    ("universities", "universities.csv"),
    ("markets", "markets.csv"),
    ("hardware_stores", "hardware_stores.csv"),
    ("priority_zones", "priority_zones.csv"),
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
    head = "\n".join(text)
    sep = ";" if head.count(";") > head.count(",") else ","
    return pd.read_csv(path, sep=sep)


def _population_path(data_dir: Path) -> Path | None:
    for name in ("moscow_population_full.csv", "moscow_population_full (1).csv"):
        p = data_dir / name
        if p.exists():
            return p
    return None


def _build_okrugs_df(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "moscow_okrugs_demographics.geojson"
    if not path.exists():
        return pd.DataFrame(columns=["okrug_code", "okrug_name", "lat", "lon", "meta_json"])
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
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
                "meta_json": json.dumps(props, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO_ROOT_DEFAULT
    out = OUT_DB
    out.parent.mkdir(parents=True, exist_ok=True)
    if not (src / "dataset_final.csv").exists():
        print(f"error: нет {src / 'dataset_final.csv'}", file=sys.stderr)
        return 1

    con = sqlite3.connect(out)
    try:
        meta = pd.DataFrame(
            [
                ("schema_version", "2"),
                ("built_at_utc", datetime.now(timezone.utc).isoformat()),
                ("source_root", str(src)),
            ],
            columns=["k", "v"],
        )
        meta.to_sql("meta", con, if_exists="replace", index=False)

        for table, fname in TABLES:
            df = _read_csv(src / fname)
            if df.empty and table == "dataset_final":
                print("error: dataset_final пустой", file=sys.stderr)
                return 1
            if df.empty or len(df.columns) == 0:
                print(f"  {table}: пропуск (нет файла или пустой {fname})")
                continue
            df.to_sql(table, con, if_exists="replace", index=False)
            print(f"  {table}: {len(df)} rows")

        ok = _build_okrugs_df(src)
        ok.to_sql("okrugs", con, if_exists="replace", index=False)
        print(f"  okrugs: {len(ok)} rows")

        pop_path = _population_path(src)
        if pop_path:
            pop = _read_csv(pop_path)
            pop.to_sql("population", con, if_exists="replace", index=False)
            print(f"  population: {len(pop)} rows")

        nb_written = False
        spisok = WEB_SERVICE / "screens" / "spisok_domov.csv"
        if spisok.is_file():
            sys.path.insert(0, str(WEB_SERVICE / "backend"))
            from app.config import settings as app_settings  # noqa: E402
            from app.services.developments import build_new_buildings_table_for_sqlite  # noqa: E402

            nb_df, nb_meta = build_new_buildings_table_for_sqlite(app_settings.merged_config)
            if not nb_df.empty:
                nb_df.to_sql("new_buildings", con, if_exists="replace", index=False)
                print(f"  new_buildings: {len(nb_df)} rows (из spisok_domov.csv)")
                nb_written = True
            elif nb_meta.get("errors"):
                print(f"  new_buildings: spisok пропуск — {nb_meta['errors'][:3]}", file=sys.stderr)
        if not nb_written:
            nb = src / "new_buildings.csv"
            if nb.exists():
                df = _read_csv(nb)
                df.to_sql("new_buildings", con, if_exists="replace", index=False)
                print(f"  new_buildings: {len(df)} rows")
    finally:
        con.close()

    size_kb = out.stat().st_size // 1024
    print(f"ok: {out} ({size_kb} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
