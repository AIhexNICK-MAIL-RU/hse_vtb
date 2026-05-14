#!/usr/bin/env python3
"""Проверка для Docker HEALTHCHECK: Timeweb («/») и запасной «/health»."""
from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


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
    found: list[int] = []
    marker = Path("/tmp/.geoatm_listen_port")
    if marker.is_file():
        p = _parse_port(marker.read_text())
        if p is not None:
            found.append(p)
    p = _parse_port(os.environ.get("PORT"))
    if p is not None and p not in found:
        found.append(p)
    if 8080 not in found:
        found.append(8080)
    return found


def _ok_code(code: int) -> bool:
    return 200 <= code < 300


def _probe_once(url: str, *, use_head: bool) -> bool:
    method = "HEAD" if use_head else "GET"
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = int(resp.getcode())
            if not _ok_code(code):
                return False
            if not use_head:
                resp.read(8192)
            return True
    except urllib.error.HTTPError as e:
        if use_head and e.code == 405:
            return _probe_once(url, use_head=False)
        return _ok_code(int(e.code))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False


def _probe(url: str) -> bool:
    if _probe_once(url, use_head=True):
        return True
    return _probe_once(url, use_head=False)


def main() -> int:
    ports = _candidate_ports()
    paths = ("/", "/health")
    errs: list[str] = []
    for port in ports:
        for path in paths:
            url = f"http://127.0.0.1:{port}{path}"
            if _probe(url):
                return 0
            errs.append(f"{url}: no 2xx")
    for line in errs[-8:]:
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
