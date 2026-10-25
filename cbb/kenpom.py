"""KenPom API: ratings as of any date, preseason ratings and FanMatch game predictions.

Needs KENPOM_API_KEY (sent as `Authorization: Bearer`), or a network secret for kenpom.com that adds it.
Every response is cached in cbb/cache/kenpom/, since past dates never change.

    archive(date)       ratings as published on that date (2012 on): what was known before that day's games
    preseason(season)   preseason ratings for a season
    ratings(season)     current (or final) ratings for a season
    fanmatch(date)      KenPom's predicted score for every game on that date

Each table gets an `espn_id` column from data/teams.csv so it joins to the hoopR games.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

from . import teams

API = "https://kenpom.com/api.php"
CACHE = os.path.join(os.path.dirname(__file__), "cache", "kenpom")


def get(endpoint: str, cache: bool = True, **params) -> list[dict]:
    q = {"endpoint": endpoint, **params}
    key = "_".join(f"{k}-{v}" for k, v in q.items())
    path = os.path.join(CACHE, key + ".json")
    if cache and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    headers = {"User-Agent": "cbb-model"}
    if os.environ.get("KENPOM_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["KENPOM_API_KEY"]
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if cache:
        os.makedirs(CACHE, exist_ok=True)
        with open(path + ".tmp", "w") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)
    return data


def _table(rows: list[dict], *name_cols: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    ids = teams.id_lookup("kenpom")
    for c in name_cols:
        if c in df:
            df[("espn_id" if c == "TeamName" else c.lower() + "_espn_id")] = df[c].map(
                lambda n: ids.get(teams.norm(n))).astype("Int64")
    return df


def archive(date: str) -> pd.DataFrame:
    return _table(get("archive", d=str(date)[:10]), "TeamName")


def preseason(season: int) -> pd.DataFrame:
    return _table(get("archive", preseason="true", y=season), "TeamName")


def ratings(season: int, cache: bool = True) -> pd.DataFrame:
    return _table(get("ratings", cache=cache, y=season), "TeamName")


def fanmatch(date: str) -> pd.DataFrame:
    return _table(get("fanmatch", d=str(date)[:10]), "Home", "Visitor")
