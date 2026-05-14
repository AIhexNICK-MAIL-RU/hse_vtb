from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _default_data_dir() -> Path:
    # web_service/backend/app/config.py → parents[3] = корень кейса с CSV
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEOATM_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default_factory=_default_data_dir)

    @property
    def merged_config(self) -> dict[str, Any]:
        default_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
        base = load_yaml_config(default_path)
        override = os.environ.get("GEOATM_CONFIG_PATH")
        if override:
            base = _deep_merge(base, load_yaml_config(Path(override)))
        return base


settings = Settings()
