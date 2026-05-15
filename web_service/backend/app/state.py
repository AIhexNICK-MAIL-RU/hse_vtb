from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.services.developments import (
    load_developments,
    load_developments_from_df,
    resolve_spisok_domov_path,
)
from app.services.features import (
    compute_heuristic_scores,
    compute_retention_metrics,
    enrich_geo,
    load_core_dataset,
    load_poi_layers,
    load_priority_zones,
    tag_scenarios,
)
from app.services.sqlite_data import (
    load_core_dataset_sqlite,
    load_developments_rows_sqlite,
    load_okrug_reference_sqlite,
    load_poi_layers_sqlite,
    load_priority_zones_sqlite,
    resolve_sqlite_path,
)


def _version_token(df: pd.DataFrame, metrics: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(str(len(df)).encode())
    h.update(str(metrics.get("spearman_ml_vs_heuristic")).encode())
    digest = h.hexdigest()[:10]
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{digest}"


@dataclass
class AppState:
    cfg: dict[str, Any] = field(default_factory=dict)
    df: pd.DataFrame | None = None
    bundle: dict[str, Any] | None = None
    model_version: str = "uninitialized"
    poi: dict[str, pd.DataFrame] | None = None
    priority_zones: pd.DataFrame | None = None
    developments: list[dict[str, Any]] = field(default_factory=list)
    developments_meta: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None

    def loaded(self) -> bool:
        return self.df is not None and self.bundle is not None

    def ingest(self, data_dir: Any | None = None) -> None:
        from app.services.ml_train import train_models

        root = Path(data_dir) if data_dir is not None else settings.data_dir
        self.cfg = settings.merged_config
        self.last_error = None
        self.developments = []
        self.developments_meta = {}
        try:
            sqlite = resolve_sqlite_path()
            if sqlite is not None:
                df = load_core_dataset_sqlite(sqlite)
                df = compute_heuristic_scores(df, self.cfg)
                df = tag_scenarios(df, self.cfg)
                df = compute_retention_metrics(df, self.cfg)
                okr = load_okrug_reference_sqlite(sqlite)
                df = enrich_geo(df, root, self.cfg, okrug_ref=okr)
                bundle = train_models(df, self.cfg)
                df = df.copy()
                df["ml_score"] = bundle["ml_score"].reindex(df.index).astype(float)
                df["cluster_id"] = bundle["cluster_id"].reindex(df.index).astype(int)
                metrics = bundle["metrics"]
                self.model_version = _version_token(df, metrics)
                self.df = df
                self.bundle = bundle
                self.poi = load_poi_layers_sqlite(sqlite)
                self.priority_zones = load_priority_zones_sqlite(sqlite)
                if resolve_spisok_domov_path(self.cfg) is not None:
                    try:
                        self.developments, self.developments_meta = load_developments(root, self.cfg)
                    except Exception as e:  # noqa: BLE001
                        self.developments = []
                        self.developments_meta = {"source": None, "rows": 0, "errors": [str(e)]}
                else:
                    nb_df, nb_meta = load_developments_rows_sqlite(sqlite)
                    if nb_df is not None and not nb_df.empty:
                        self.developments, self.developments_meta = load_developments_from_df(
                            nb_df, self.cfg, source_meta=nb_meta
                        )
                    else:
                        try:
                            self.developments, self.developments_meta = load_developments(root, self.cfg)
                        except Exception as e:  # noqa: BLE001
                            self.developments = []
                            self.developments_meta = {"source": None, "rows": 0, "errors": [str(e)]}
            else:
                df = load_core_dataset(root)
                df = compute_heuristic_scores(df, self.cfg)
                df = tag_scenarios(df, self.cfg)
                df = compute_retention_metrics(df, self.cfg)
                df = enrich_geo(df, root, self.cfg)
                bundle = train_models(df, self.cfg)
                df = df.copy()
                df["ml_score"] = bundle["ml_score"].reindex(df.index).astype(float)
                df["cluster_id"] = bundle["cluster_id"].reindex(df.index).astype(int)
                metrics = bundle["metrics"]
                self.model_version = _version_token(df, metrics)
                self.df = df
                self.bundle = bundle
                self.poi = load_poi_layers(root)
                self.priority_zones = load_priority_zones(root)
                try:
                    self.developments, self.developments_meta = load_developments(root, self.cfg)
                except Exception as e:  # noqa: BLE001
                    self.developments = []
                    self.developments_meta = {"source": None, "rows": 0, "errors": [str(e)]}
        except Exception as e:  # noqa: BLE001 — явный лог для ingest
            self.last_error = str(e)
            raise


state = AppState()
