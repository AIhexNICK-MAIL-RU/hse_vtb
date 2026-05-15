import os
from pathlib import Path

import pytest

os.environ.setdefault("GEOATM_AUTO_INGEST", "0")

from app.services.features import (  # noqa: E402
    compute_heuristic_scores,
    compute_retention_metrics,
    enrich_geo,
    h3_to_latlon,
    h3_to_polygon_geojson,
    load_core_dataset,
    tag_scenarios,
)


def test_h3_latlon_polygon():
    h = "89118180927ffff"
    lat, lon = h3_to_latlon(h)
    assert 55.0 < lat < 56.0
    assert 36.0 < lon < 38.5
    poly = h3_to_polygon_geojson(h)
    assert isinstance(poly, list) and len(poly) >= 4
    assert len(poly[0]) == 2


def test_dataset_pipeline_smoke():
    root = Path(__file__).resolve().parents[3]
    if not (root / "dataset_final.csv").exists():
        pytest.skip("dataset_final.csv not present in case root")
    cfg = {
        "demand_score": {
            "weights": {
                "total_sum": 0.35,
                "unique_customers": 0.25,
                "transactions_per_customer": 0.20,
                "poi_score": 0.12,
                "competitor_proximity": 0.08,
            },
            "white_spot_threshold": 0.70,
            "min_unique_customers_percentile": 50,
        },
        "scenarios": {
            "competitor_min_atms": 2,
            "low_utilization_sum_per_customer_percentile": 25,
            "growth_volatility_percentile": 75,
        },
        "retention": {},
    }
    df = load_core_dataset(root)
    df = compute_heuristic_scores(df, cfg)
    df = tag_scenarios(df, cfg)
    df = compute_retention_metrics(df, cfg)
    df = enrich_geo(df, root, cfg)
    assert "heuristic_score" in df.columns
    assert "scenario_tags" in df.columns
    assert "retention_proxy_score" in df.columns
    assert "competition_pressure_score" in df.columns
    assert "profile_tags" in df.columns
    assert df["heuristic_score"].between(0, 1).all()
    assert df["retention_proxy_score"].between(0, 1).all()
    assert df["competition_pressure_score"].between(0, 1).all()
    assert len(df) > 100
