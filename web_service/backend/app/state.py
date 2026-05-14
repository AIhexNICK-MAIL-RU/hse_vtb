from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.services.features import (
    compute_heuristic_scores,
    enrich_geo,
    load_core_dataset,
    load_poi_layers,
    load_priority_zones,
    tag_scenarios,
)
from app.services.ml_train import train_models


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
    last_error: str | None = None

    def loaded(self) -> bool:
        return self.df is not None and self.bundle is not None

    def ingest(self, data_dir: Any | None = None) -> None:
        root = Path(data_dir) if data_dir is not None else settings.data_dir
        self.cfg = settings.merged_config
        self.last_error = None
        try:
            df = load_core_dataset(root)
            df = compute_heuristic_scores(df, self.cfg)
            df = tag_scenarios(df, self.cfg)
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
        except Exception as e:  # noqa: BLE001 — явный лог для ingest
            self.last_error = str(e)
            raise


state = AppState()
