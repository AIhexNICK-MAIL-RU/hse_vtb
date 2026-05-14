import math

import pandas as pd
import pytest

from app.services.poi_distances import build_placement_payload, haversine_m, nearest_poi, poi_layer_df


def test_haversine_moscow_order():
    lat0, lon0 = 55.75, 37.62
    lat = pd.Series([55.7505, 55.9])
    lon = pd.Series([37.62, 37.62])
    d = haversine_m(lat0, lon0, lat.to_numpy(), lon.to_numpy())
    assert float(d[0]) < 200
    assert float(d[1]) > 10_000


def test_poi_layer_df_no_bool_on_nonempty_dataframe():
    df = pd.DataFrame({"lat": [55.0], "lon": [37.0], "name": ["A"]})
    poi = {"metro": df}
    assert len(poi_layer_df(poi, "metro")) == 1
    assert poi_layer_df(poi, "missing").empty


def test_build_placement_with_nonempty_layers():
    metro = pd.DataFrame({"lat": [55.751], "lon": [37.621], "station": ["Тестовая"]})
    comp = pd.DataFrame({"lat": [55.752], "lon": [37.622], "name": ["Сбер"]})
    poi = {"metro": metro, "competitor_atms": comp, "malls": pd.DataFrame(), "universities": pd.DataFrame(), "offices": pd.DataFrame(), "vtb_atms": pd.DataFrame(), "markets": pd.DataFrame(), "hardware_stores": pd.DataFrame()}
    out = build_placement_payload(55.75, 37.62, "89118180927ffff", poi, radius_m=400, ml_score=0.9, heuristic_score=0.1, scenario_tags=["competitor"])
    assert out["nearest_metro"] is not None
    assert out["nearest_competitor_atm"] is not None
    assert out["competitors_in_radius"] >= 1
    df = pd.DataFrame(
        {
            "name": ["A", "B"],
            "lat": [55.751, 55.900],
            "lon": [37.621, 37.621],
        }
    )
    n = nearest_poi(55.75, 37.62, df, fallback_name="x")
    assert n is not None
    assert n["name"] == "A"
    assert n["distance_m"] < 500
    assert math.isfinite(n["lat"])
