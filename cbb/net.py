"""Cached HTTP GETs for the outside sources (hoopR, KenPom, Barttorvik, SportsGameOdds).

Past seasons and past dates never change, so their files are kept for good. Anything that can still change
(the current season, today's games) is re-downloaded once it is older than `max_age` seconds.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(__file__), "cache")
UA = "cbb-model (github.com/barrca12-rgb/CBB)"


def season_of(day: dt.date) -> int:
    """Season (year it ends) a date belongs to: 2026-11-10 -> 2027."""
    return day.year + 1 if day.month >= 7 else day.year


def current_season() -> int:
    return season_of(dt.date.today())


def get(url: str, path: str, refresh: bool = False, max_age: float | None = None,
        headers: dict | None = None, timeout: int = 120) -> str:
    """Download `url` to cbb/cache/`path` unless a usable copy is there; return the local path."""
    full = os.path.join(CACHE, path)
    stale = max_age is not None and os.path.exists(full) and time.time() - os.path.getmtime(full) > max_age
    if refresh or stale or not os.path.exists(full):
        os.makedirs(os.path.dirname(full), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r, open(full + ".tmp", "wb") as f:
            f.write(r.read())
        os.replace(full + ".tmp", full)
    return full
