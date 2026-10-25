"""SportsGameOdds (api.sportsgameodds.com/v2): live NCAAB lines by bookmaker, with betslip deep links.

Auth: set SGO_API_KEY (sent as the x-api-key header); a session proxy may add it instead.

  events(...)   raw v2 events for league NCAAB, following the cursor across pages
  lines(...)    one row per game x bookmaker x market (spread, total, moneyline) for full-game odds:
                home/away/over/under prices (American), the line, and the bookmaker's deep link.

Odds ids look like `points-home-game-sp-home` (stat-entity-period-betType-side); full-game spreads are
`points-home-game-sp-home`, totals `points-all-game-ou-over`, moneylines `points-home-game-ml-home`.
Not yet run against the live API: no key had been set when this was written.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

from . import net, teams

URL = "https://api.sportsgameodds.com/v2"
MARKETS = {  # market -> (odd id of the home/over side, odd id of the away/under side)
    "spread": ("points-home-game-sp-home", "points-away-game-sp-away"),
    "total": ("points-all-game-ou-over", "points-all-game-ou-under"),
    "moneyline": ("points-home-game-ml-home", "points-away-game-ml-away"),
}


def _get(path: str, **params) -> dict:
    key = os.environ.get("SGO_API_KEY")
    req = urllib.request.Request(f"{URL}/{path}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": net.UA, **({"x-api-key": key} if key else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if not body.get("success", True):
        raise RuntimeError(f"SportsGameOdds {path}: {body.get('error')}")
    return body


def events(starts_after=None, starts_before=None, odds_available: bool = True, league: str = "NCAAB") -> list[dict]:
    params = {"leagueID": league, "limit": 100}
    if odds_available:
        params["oddsAvailable"] = "true"
    if starts_after is not None:
        params["startsAfter"] = pd.Timestamp(starts_after).isoformat()
    if starts_before is not None:
        params["startsBefore"] = pd.Timestamp(starts_before).isoformat()
    out, cursor = [], None
    while True:
        body = _get("events", **params, **({"cursor": cursor} if cursor else {}))
        out += body.get("data", [])
        cursor = body.get("nextCursor")
        if not cursor:
            return out


def usage() -> dict:
    return _get("account/usage").get("data", {})


def _team_id(team: dict, ids: dict[str, int]):
    names = team.get("names", {})
    for n in (names.get("long"), names.get("medium"), names.get("short")):
        if n and teams.norm(n) in ids:
            return ids[teams.norm(n)]
    return None


def lines(evts: list[dict] | None = None, **kw) -> pd.DataFrame:
    evts = events(**kw) if evts is None else evts
    t = teams.load()
    ids = dict(teams.id_lookup("kenpom"))
    for col in ("espn_location", "espn_name"):
        ids.update({teams.norm(n): int(i) for n, i in zip(t[col], t["espn_id"])})
    rows = []
    for e in evts:
        home, away = e.get("teams", {}).get("home", {}), e.get("teams", {}).get("away", {})
        base = {
            "event_id": e.get("eventID"),
            "starts": pd.to_datetime(e.get("status", {}).get("startsAt"), utc=True),
            "home": home.get("names", {}).get("long"), "away": away.get("names", {}).get("long"),
            "home_id": _team_id(home, ids), "away_id": _team_id(away, ids),
        }
        odds = e.get("odds", {})
        for market, (a_id, b_id) in MARKETS.items():
            a, b = odds.get(a_id, {}), odds.get(b_id, {})
            for book in set(a.get("byBookmaker", {})) | set(b.get("byBookmaker", {})):
                x, y = a.get("byBookmaker", {}).get(book, {}), b.get("byBookmaker", {}).get(book, {})
                if not (x.get("available", True) and y.get("available", True)):
                    continue
                line = x.get("spread") if market == "spread" else x.get("overUnder") if market == "total" else None
                rows.append({**base, "book": book, "market": market,
                             "line": pd.to_numeric(line, errors="coerce"),
                             "price_a": pd.to_numeric(x.get("odds"), errors="coerce"),   # home or over
                             "price_b": pd.to_numeric(y.get("odds"), errors="coerce"),   # away or under
                             "link_a": x.get("deeplink"), "link_b": y.get("deeplink"),
                             "updated": x.get("lastUpdatedAt")})
    df = pd.DataFrame(rows)
    if len(df):
        df[["home_id", "away_id"]] = df[["home_id", "away_id"]].astype("Int64")
    return df
