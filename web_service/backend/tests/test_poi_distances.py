import math

import pandas as pd
import pytest

from app.services.poi_distances import haversine_m, nearest_poi


def test_haversine_moscow_order():
    lat0, lon0 = 55.75, 37.62
    lat = pd.Series([55.7505, 55.9])
    lon = pd.Series([37.62, 37.62])
    d = haversine_m(lat0, lon0, lat.to_numpy(), lon.to_numpy())
    assert float(d[0]) < 200
    assert float(d[1]) > 10_000


def test_nearest_poi_picks_closest():
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
