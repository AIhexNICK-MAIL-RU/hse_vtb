"""Геокодирование адресов из spisok_domov.csv (Nominatim + локальный кэш)."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

_MOSCOW_LAT = (55.55, 55.92)
_MOSCOW_LON = (37.35, 37.95)
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_PHOTON_URL = "https://photon.komoot.io/api/"
_USER_AGENT = "VTB-GeoATM-HSE/1.0 (educational; contact: local)"


def web_service_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_spisok_path() -> Path:
    return web_service_root() / "screens" / "spisok_domov.csv"


def default_geocode_cache_path() -> Path:
    return web_service_root() / "screens" / "spisok_domov_geocoded.csv"


def _in_moscow_bbox(lat: float, lon: float) -> bool:
    return _MOSCOW_LAT[0] <= lat <= _MOSCOW_LAT[1] and _MOSCOW_LON[0] <= lon <= _MOSCOW_LON[1]


def _query_variants(address: str) -> list[str]:
    """Несколько формулировок: полный адрес, улица без з/у и подзон."""
    import re

    a = address.strip()
    if not a:
        return []
    variants: list[str] = []
    seen: set[str] = set()

    def add(q: str) -> None:
        q = re.sub(r"\s+", " ", q).strip(" ,")
        if q and q not in seen:
            seen.add(q)
            variants.append(q)

    add(f"Москва, {a}")
    head = re.sub(r"\s*\([^)]*\)", "", a.split(",")[0]).strip()
    add(f"Москва, {head}")
    no_plot = re.sub(r",?\s*з/у.*", "", a, flags=re.IGNORECASE).strip(" ,")
    if no_plot != a:
        add(f"Москва, {no_plot}")
        head2 = re.sub(r"\s*\([^)]*\)", "", no_plot.split(",")[0]).strip()
        add(f"Москва, {head2}")
    no_bld = re.sub(r",?\s*влд\.?\s*[^,]+", "", head, flags=re.IGNORECASE).strip(" ,")
    if no_bld and no_bld != head:
        add(f"Москва, {no_bld}")
    return variants


def _fetch_nominatim(q: str, *, delay_s: float) -> tuple[float, float] | None:
    params = urllib.parse.urlencode(
        {
            "q": q,
            "format": "json",
            "limit": 1,
            "countrycodes": "ru",
            "viewbox": "37.35,55.92,37.95,55.55",
            "bounded": 1,
        }
    )
    req = urllib.request.Request(f"{_NOMINATIM_URL}?{params}", headers={"User-Agent": _USER_AGENT})
    time.sleep(delay_s)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    if not _in_moscow_bbox(lat, lon):
        return None
    return lat, lon


def _fetch_photon(q: str) -> tuple[float, float] | None:
    params = urllib.parse.urlencode({"q": q, "limit": 1, "lang": "ru", "osm_tag": "!place:country"})
    req = urllib.request.Request(f"{_PHOTON_URL}?{params}", headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    feats = data.get("features") or []
    if not feats:
        return None
    coords = feats[0].get("geometry", {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    lon, lat = float(coords[0]), float(coords[1])
    if not _in_moscow_bbox(lat, lon):
        return None
    return lat, lon


def geocode_query(address: str, *, delay_s: float = 1.05) -> tuple[float, float] | None:
    """Nominatim + Photon по нескольким вариантам строки адреса."""
    for i, q in enumerate(_query_variants(address)):
        try:
            pt = _fetch_nominatim(q, delay_s=delay_s if i == 0 else 1.05)
            if pt:
                return pt
        except Exception:  # noqa: BLE001
            pass
    for q in _query_variants(address)[:3]:
        try:
            pt = _fetch_photon(q)
            if pt:
                return pt
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.25)
    return None


def load_geocode_cache(path: Path) -> dict[str, tuple[float, float]]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    if df.empty:
        return {}
    df.columns = [str(c).strip() for c in df.columns]
    out: dict[str, tuple[float, float]] = {}
    for _, r in df.iterrows():
        addr = str(r.get("address", r.get("Адрес", ""))).strip()
        if not addr:
            continue
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if _in_moscow_bbox(lat, lon):
            out[addr] = (lat, lon)
    return out


def save_geocode_cache(path: Path, mapping: dict[str, tuple[float, float]]) -> None:
    rows = [{"address": a, "lat": lat, "lon": lon} for a, (lat, lon) in sorted(mapping.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def ensure_geocoded_addresses(
    addresses: list[str],
    cache_path: Path | None = None,
    *,
    allow_network: bool = True,
) -> tuple[dict[str, tuple[float, float]], list[str]]:
    """
    Возвращает (address -> (lat, lon), errors).
    Сначала кэш; недостающие — Nominatim, если allow_network.
    """
    cache_path = cache_path or default_geocode_cache_path()
    found = load_geocode_cache(cache_path)
    errors: list[str] = []
    missing = [a for a in addresses if a.strip() and a.strip() not in found]

    if missing and allow_network:
        for addr in missing:
            key = addr.strip()
            try:
                pt = geocode_query(key)
            except Exception as e:  # noqa: BLE001
                errors.append(f"geocode_fail:{key[:80]}:{e}")
                continue
            if pt is None:
                errors.append(f"geocode_miss:{key[:80]}")
                continue
            found[key] = pt
        if found:
            save_geocode_cache(cache_path, found)

    for addr in addresses:
        key = addr.strip()
        if key and key not in found:
            errors.append(f"no_coords:{key[:80]}")

    return found, errors
