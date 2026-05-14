#!/usr/bin/env python3
"""Проверка для Docker HEALTHCHECK: «/» (Timeweb) или запасной «/health»."""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path


def _listen_port() -> int:
    marker = Path("/tmp/.geoatm_listen_port")
    if marker.is_file():
        raw = marker.read_text().strip()
    else:
        raw = (os.environ.get("PORT") or "8080").strip()
    return int(raw) if raw.isdigit() else 8080


def main() -> int:
    port = _listen_port()
    for path in ("/", "/health"):
        url = f"http://127.0.0.1:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                if resp.status == 200:
                    resp.read(65536)
                    return 0
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
