from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.services.developments import (
    completion_date_from_value,
    is_spisok_domov_format,
    load_developments,
    normalize_spisok_domov,
)
from app.services.developments_geocode import load_geocode_cache


def test_spisok_format_detect():
    df = pd.DataFrame([{"Адрес": "ул. Тест, 1", "Количество квартир": 100, "Срок сдачи": 2027}])
    assert is_spisok_domov_format(df)


def test_completion_year_to_july():
    assert completion_date_from_value(2026) == date(2026, 7, 1)
    assert completion_date_from_value("2028") == date(2028, 7, 1)


def test_normalize_spisok_domov():
    df = pd.DataFrame(
        [
            {"Адрес": "Тестовая ул., 1", "Количество квартир": 42, "Срок сдачи": 2026},
            {"Адрес": "", "Количество квартир": 1, "Срок сдачи": 2026},
        ]
    )
    norm = normalize_spisok_domov(df)
    assert len(norm) == 1
    assert norm.iloc[0]["apartments"] == 42
    assert norm.iloc[0]["completion_date"] == "2026-07-01"


def test_load_spisok_with_cache(tmp_path, monkeypatch):
    tcsv = tmp_path / "spisok.csv"
    pd.DataFrame([{"Адрес": "Тестовая ул., 1", "Количество квартир": 10, "Срок сдачи": 2026}]).to_csv(
        tcsv, index=False
    )
    cache = tmp_path / "geo.csv"
    pd.DataFrame([{"address": "Тестовая ул., 1", "lat": 55.75, "lon": 37.62}]).to_csv(cache, index=False)
    monkeypatch.setenv("GEOATM_NEW_BUILDINGS_CSV", str(tcsv))
    monkeypatch.setenv("GEOATM_GEOCODE_NETWORK", "0")
    cfg = {"developments": {"geocode_cache": str(cache)}}
    items, meta = load_developments(tmp_path, cfg)
    assert len(items) == 1
    assert items[0]["apartments"] == 10
    assert meta["format"] == "spisok_domov"


def test_geocode_cache_roundtrip(tmp_path):
    p = tmp_path / "c.csv"
    pd.DataFrame([{"address": "A", "lat": 55.76, "lon": 37.64}]).to_csv(p, index=False)
    m = load_geocode_cache(p)
    assert m["A"] == pytest.approx((55.76, 37.64))
