"""Barttorvik T-Rank ratings as of any date (time machine archive, 2015 season on).

barttorvik.com/timemachine/team_results/<YYYYMMDD>_team_results.json.gz holds every team's adjusted offense,
defense and tempo on that date. Games on date D use the file for D-1, so nothing from game day leaks in.
Only the columns the model uses are kept, cached in cbb/cache/barttorvik/<YYYYMMDD>.parquet.
"""
from __future__ import annotations

import gzip
import json
import os
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from . import teams

URL = "https://barttorvik.com/timemachine/team_results/{}_team_results.json.gz"
# Barttorvik refuses some non-browser clients (403 from GitHub's runners with a plain user agent).
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
CACHE = os.path.join(os.path.dirname(__file__), "cache", "barttorvik")
FIRST_SEASON = 2015


def snapshot(day) -> pd.DataFrame | None:
    """Ratings file for one date (None if Barttorvik has no file that day)."""
    d = pd.Timestamp(day).strftime("%Y%m%d")
    path = os.path.join(CACHE, d + ".parquet")
    if os.path.exists(path):
        t = pd.read_parquet(path)
        return t if len(t) else None
    req = urllib.request.Request(URL.format(d), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None          # refused or down: treat as missing (not cached), projection falls back to KenPom
        rows = []
    except OSError:
        return None
    else:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        rows = json.loads(raw)
    t = pd.DataFrame([(r[1], r[4], r[6], r[44]) for r in rows], columns=["team", "adj_oe", "adj_de", "adj_tempo"])
    ids = teams.id_lookup("kenpom")  # Barttorvik uses KenPom-style names
    t["espn_id"] = t["team"].map(lambda n: ids.get(teams.norm(n))).astype("Int64")
    os.makedirs(CACHE, exist_ok=True)
    t.to_parquet(path)
    return t if len(t) else None


def before(day) -> pd.DataFrame | None:
    """Most recent ratings published before `day` (looks back up to a week)."""
    for k in range(1, 8):
        t = snapshot(pd.Timestamp(day) - pd.Timedelta(days=k))
        if t is not None:
            return t
    return None


def predict(games: pd.DataFrame, live_season: int | None = None) -> pd.DataFrame:
    """Barttorvik-implied home margin and total for each game (game_id, date, home_id, away_id, neutral).
    live_season: fall back to the live ratings file when the archive has nothing for the day before."""
    out = []
    for day, g in games.groupby("date"):
        t = before(day)
        if t is None and live_season:
            t = current(live_season)
        if t is None:
            continue
        t = t.dropna(subset=["espn_id"]).drop_duplicates("espn_id").set_index("espn_id")
        avg_e = t["adj_oe"].mean()
        avg_t = t["adj_tempo"].mean()
        h = t.reindex(g["home_id"].to_numpy())
        a = t.reindex(g["away_id"].to_numpy())
        poss = h["adj_tempo"].to_numpy() * a["adj_tempo"].to_numpy() / avg_t
        hp = poss * h["adj_oe"].to_numpy() * a["adj_de"].to_numpy() / avg_e / 100
        ap = poss * a["adj_oe"].to_numpy() * h["adj_de"].to_numpy() / avg_e / 100
        out.append(pd.DataFrame({"game_id": g["game_id"].to_numpy(), "bt_margin": hp - ap, "bt_total": hp + ap}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["game_id", "bt_margin", "bt_total"])


def current(season: int) -> pd.DataFrame | None:
    """Barttorvik's live ratings for `season` (barttorvik.com/<season>_team_results.json), for today's games
    when the time machine has no file yet (e.g. preseason). Not cached."""
    req = urllib.request.Request(f"https://barttorvik.com/{season}_team_results.json", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = json.load(r)
    except Exception:
        return None
    t = pd.DataFrame([(r[1], r[4], r[6], r[44]) for r in rows], columns=["team", "adj_oe", "adj_de", "adj_tempo"])
    ids = teams.id_lookup("kenpom")
    t["espn_id"] = t["team"].map(lambda n: ids.get(teams.norm(n))).astype("Int64")
    return t
