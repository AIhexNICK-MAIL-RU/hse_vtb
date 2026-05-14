import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("GEOATM_AUTO_INGEST", "0")
    monkeypatch.setenv("GEOATM_API_PREFIX", "/api")
    monkeypatch.setenv("GEOATM_STATIC_DIR", str(tmp_path / "no_static_here"))
    import app.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_live_get(client):
    r = client.get("/live")
    assert r.status_code == 200
    assert r.text.strip() == "ok"


def test_live_head(client):
    assert client.head("/live").status_code == 200
