"""KenPom API (kenpom.com/api.php), cached in cbb/cache/kenpom/.

Endpoints used (all checked back to 2012):
  ratings       season ratings: AdjEM/AdjOE/AdjDE/AdjTempo, luck, SOS. Current season = live, past = final.
  archive       ratings as of a date (d=YYYY-MM-DD), or preseason (preseason=true&y=season). Each row also
                carries the end-of-season values (AdjEMFinal...). This is the point-in-time prior for backtests.
  fanmatch      KenPom's game predictions for a date: predicted scores, home win %, tempo. The benchmark.
  four-factors, height, teams   season team stats, experience/continuity, KenPom team ids and arenas.

Auth: the session proxy adds the key for kenpom.com. Elsewhere set KENPOM_API_KEY (sent as a Bearer token).
Every frame gets an `espn_id` column from data/teams.csv so it joins the hoopR games.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse

import pandas as pd

from . import net, teams

URL = "https://kenpom.com/api.php"
LIVE = 6 * 3600  # re-download current-season data after 6 hours


def _headers() -> dict:
    key = os.environ.get("KENPOM_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


def get(endpoint: str, live: bool = False, refresh: bool = False, **params) -> pd.DataFrame:
    q = {"endpoint": endpoint, **params}
    name = "_".join([endpoint] + [f"{k}-{v}" for k, v in params.items()]) + ".json"
    path = net.get(f"{URL}?{urllib.parse.urlencode(q)}", os.path.join("kenpom", name), refresh=refresh,
                   max_age=LIVE if live else None, headers=_headers())
    with open(path) as f:
        rows = json.load(f)
    if isinstance(rows, dict):                       # error payloads come back as an object
        os.remove(path)
        raise RuntimeError(f"KenPom {endpoint} {params}: {rows}")
    df = pd.DataFrame(rows)
    if "TeamName" in df:
        df.insert(0, "espn_id", df["TeamName"].map(lambda n: _ids().get(teams.norm(n))).astype("Int64"))
    return df


def _ids() -> dict[str, int]:
    return teams.id_lookup("kenpom")


def ratings(season: int, refresh: bool = False) -> pd.DataFrame:
    return get("ratings", live=season >= net.current_season(), refresh=refresh, y=season)


def archive(day, refresh: bool = False) -> pd.DataFrame:
    """Ratings as they stood on `day` (before that day's games)."""
    day = pd.Timestamp(day).date()
    return get("archive", live=day >= dt.date.today(), refresh=refresh, d=day.isoformat())


def preseason(season: int, refresh: bool = False) -> pd.DataFrame:
    return get("archive", refresh=refresh, preseason="true", y=season)


def fanmatch(day, refresh: bool = False) -> pd.DataFrame:
    """KenPom predictions for every game on `day`, with `home_id`/`away_id` ESPN ids."""
    day = pd.Timestamp(day).date()
    df = get("fanmatch", live=day >= dt.date.today() - dt.timedelta(days=1), refresh=refresh, d=day.isoformat())
    if len(df):
        ids = _ids()
        df.insert(0, "away_id", df["Visitor"].map(lambda n: ids.get(teams.norm(n))).astype("Int64"))
        df.insert(0, "home_id", df["Home"].map(lambda n: ids.get(teams.norm(n))).astype("Int64"))
    return df


def four_factors(season: int, refresh: bool = False) -> pd.DataFrame:
    return get("four-factors", live=season >= net.current_season(), refresh=refresh, y=season)


def height(season: int, refresh: bool = False) -> pd.DataFrame:
    return get("height", live=season >= net.current_season(), refresh=refresh, y=season)


def team_list(season: int, refresh: bool = False) -> pd.DataFrame:
    return get("teams", live=season >= net.current_season(), refresh=refresh, y=season)


def match_games(fm: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Add hoopR `game_id` to FanMatch rows (same date and teams; KenPom's home is ESPN's away at some neutral
    sites, so either order counts). Unmatched rows get <NA>."""
    g = games[["game_id", "date", "home_id", "away_id"]]
    keys = pd.concat([g, g.rename(columns={"home_id": "away_id", "away_id": "home_id"})])
    keys = keys.assign(date=keys["date"].dt.date).drop_duplicates(["date", "home_id", "away_id"])
    fm = fm.assign(date=pd.to_datetime(fm["DateOfGame"]).dt.date)
    out = fm.merge(keys.astype({"home_id": "Int64", "away_id": "Int64"}), on=["date", "home_id", "away_id"],
                   how="left")
    out["game_id"] = out["game_id"].astype("Int64")
    return out.drop(columns="date")
