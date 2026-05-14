"""Встроенная SQLite (scripts/build_embedded_sqlite.py) — дымовая проверка чтения."""

from pathlib import Path

import pytest

from app.services.sqlite_data import (
    embedded_sqlite_default_path,
    load_core_dataset_sqlite,
    load_okrug_reference_sqlite,
    resolve_sqlite_path,
)


def test_embedded_sqlite_exists_and_readable():
    p = embedded_sqlite_default_path()
    if not p.is_file():
        pytest.skip("Нет geoatm.sqlite — выполните: cd web_service && python3 scripts/build_embedded_sqlite.py")
    assert p.suffix == ".sqlite"
    df = load_core_dataset_sqlite(p)
    assert len(df) > 1000
    ok = load_okrug_reference_sqlite(p)
    assert len(ok) >= 1


def test_resolve_prefers_env_over_embedded(monkeypatch, tmp_path):
    db = tmp_path / "custom.sqlite"
    db.write_bytes(b"not sqlite")  # resolve only checks is_file()
    monkeypatch.setenv("GEOATM_SQLITE_PATH", str(db))
    monkeypatch.delenv("GEOATM_USE_SQLITE", raising=False)
    # broken file still "exists" — path returned; actual read would fail
    assert resolve_sqlite_path() == Path(db)
