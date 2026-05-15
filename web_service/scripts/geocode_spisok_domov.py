#!/usr/bin/env python3
"""Заполнить screens/spisok_domov_geocoded.csv для адресов из spisok_domov.csv."""
from __future__ import annotations

import sys
from pathlib import Path

WEB_SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_SERVICE / "backend"))

from app.config import settings  # noqa: E402
from app.services.developments import normalize_spisok_domov  # noqa: E402
from app.services.developments_geocode import (  # noqa: E402
    default_geocode_cache_path,
    default_spisok_path,
    ensure_geocoded_addresses,
)
from app.services.features import _read_table  # noqa: E402


def main() -> int:
    spisok = default_spisok_path()
    if not spisok.is_file():
        print(f"error: нет {spisok}", file=sys.stderr)
        return 1
    raw = _read_table(spisok)
    norm = normalize_spisok_domov(raw)
    addresses = norm["address"].astype(str).tolist()
    cache = default_geocode_cache_path()
    print(f"Адресов: {len(addresses)}, кэш: {cache}")
    found, errors = ensure_geocoded_addresses(addresses, cache, allow_network=True)
    ok = sum(1 for a in addresses if a.strip() in found)
    print(f"Геокодировано: {ok}/{len(addresses)}")
    if errors:
        print("Ошибки/пропуски:")
        for e in errors[:30]:
            print(f"  {e}")
        if len(errors) > 30:
            print(f"  … ещё {len(errors) - 30}")
    return 0 if ok >= len(addresses) * 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(main())
