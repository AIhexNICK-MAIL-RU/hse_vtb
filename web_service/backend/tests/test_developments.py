import pandas as pd

from app.services.developments import delivery_score_and_tier, load_developments


def test_delivery_score_buckets():
    cfg = {"developments": {"buckets": {"months_urgent": 3, "score_at_12m": 0.82}}}
    ref = __import__("datetime").date(2026, 1, 1)
    s1, t1 = delivery_score_and_tier(__import__("datetime").date(2026, 2, 1), ref=ref, cfg=cfg)
    assert s1 == 1.0 and t1 == "urgent_0_3m"
    s2, t2 = delivery_score_and_tier(__import__("datetime").date(2026, 7, 1), ref=ref, cfg=cfg)
    assert 0.79 < s2 < 0.99 and t2 == "high_3_12m"
    s3, _ = delivery_score_and_tier(__import__("datetime").date(2027, 7, 1), ref=ref, cfg=cfg)
    assert 0.45 < s3 < 0.75
    s4, _ = delivery_score_and_tier(__import__("datetime").date(2029, 1, 1), ref=ref, cfg=cfg)
    assert s4 < 0.45


def test_load_developments_from_example(tmp_path, monkeypatch):
    root = tmp_path
    df = pd.DataFrame(
        [
            {"building_id": "a", "name": "A", "lat": 55.0, "lon": 37.0, "completion_date": "2026-06-01"},
            {"building_id": "b", "name": "B", "lat": 55.1, "lon": 37.1, "completion_date": "bad"},
        ]
    )
    p = root / "new_buildings.csv"
    df.to_csv(p, index=False)
    monkeypatch.setenv("GEOATM_NEW_BUILDINGS_CSV", str(p))
    items, meta = load_developments(root, {"developments": {"csv_filename": "new_buildings.csv"}})
    assert len(items) == 1
    assert meta["rows"] == 1
    assert "delivery_score" in items[0]
