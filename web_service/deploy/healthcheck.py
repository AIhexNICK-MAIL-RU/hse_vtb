#!/usr/bin/env python3
"""Docker HEALTHCHECK: быстрый GET; короткий таймаут на запрос — укладываемся в HEALTHCHECK --timeout Docker."""
from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Один запуск CMD не должен превышать HEALTHCHECK --timeout в Dockerfile.
_REQ_TIMEOUT = 3


def _parse_port(raw: str | None) -> int | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s.isdigit():
        p = int(s)
        return p if 1 <= p <= 65535 else None
    m = re.search(r"(\d{2,5})", s)
    if not m:
        return None
    p = int(m.group(1))
    return p if 1 <= p <= 65535 else None


def _candidate_ports() -> list[int]:
    """8080 первым — EXPOSE и Timeweb."""
    out: list[int] = []

    def add(p: int | None) -> None:
        if p is None:
            return
        if p not in out:
            out.append(p)

    add(8080)
    marker = Path("/tmp/.geoatm_listen_port")
    if marker.is_file():
        add(_parse_port(marker.read_text()))
    add(_parse_port(os.environ.get("PORT")))
    return out


def _candidate_hosts() -> list[str]:
    # Сначала 127.0.0.1 (надёжно с bind 0.0.0.0), затем localhost как в гайде Timeweb.
    return ["127.0.0.1", "localhost"]


def _ok_code(code: int) -> bool:
    return 200 <= code < 300


def _probe_get(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_REQ_TIMEOUT) as resp:
            code = int(resp.getcode())
            if not _ok_code(code):
                return False
            resp.read(4096)
            return True
    except urllib.error.HTTPError as e:
        return _ok_code(int(e.code))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False


def main() -> int:
    ports = _candidate_ports()
    hosts = _candidate_hosts()
    paths = ("/health", "/")
    errs: list[str] = []
    for port in ports:
        for host in hosts:
            for path in paths:
                url = f"http://{host}:{port}{path}"
                if _probe_get(url):
                    return 0
                errs.append(f"{url}: no 2xx")
    for line in errs[-8:]:
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
