"""Second line source: The Odds API (the-odds-api.com/v4), for games SportsGameOdds hasn't loaded yet.

SGO can lag the books by days (opening week 2026: DraftKings had dozens of Nov 2 games up, SGO two). odds.pull()
calls fetch() and keeps a row from here only where SGO has no line for that game and book. Same columns as odds.py,
with sgo_event = "oa:<event id>".

Needs ODDS_API_KEY (repository secret). Each pull costs 3 credits (spreads, totals, moneylines; our four books count
as one region). The free plan's 500 credits a month cover the pulls in PULL_HOURS (about 4 a day); set
ODDS_API_EVERY_RUN=1 on a paid plan to pull on every run. Manual runs (the Update button) always pull. Usage is kept
in lines/odds_api_usage.json; pulls stop when fewer than MIN_LEFT credits remain.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from . import teams

API = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars",
         "fanatics": "Fanatics", "bet365": "bet365"}   # up to 10 books cost the same as one region
CORE = ["draftkings", "fanduel", "betmgm", "williamhill_us"]
PULL_HOURS = {7, 12, 18, 23}     # ET hours of the scheduled runs that pull (7:37 am, 12:37, 6:07 pm, 11:37 pm)
MIN_LEFT = 15
MAX_AGE = pd.Timedelta(hours=12)
USAGE = os.path.join(os.path.dirname(__file__), "..", "lines", "odds_api_usage.json")


def due() -> bool:
    """Pull on this run? Manual runs, a paid plan (ODDS_API_EVERY_RUN), the first run ever, or a PULL_HOURS run."""
    if not os.environ.get("ODDS_API_KEY"):
        return False
    u = json.load(open(USAGE)) if os.path.exists(USAGE) else {}
    if u.get("remaining") is not None and u["remaining"] < MIN_LEFT:
        return False
    if os.environ.get("ODDS_API_EVERY_RUN") or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or not u:
        return True
    return pd.Timestamp.now(tz="America/New_York").hour in PULL_HOURS


def _lookup() -> dict:
    t = teams.load()
    out = {}
    for col in ("espn_name", "espn_location", "kenpom"):
        out.update({teams.norm(n): int(i) for n, i in zip(t[col], t["espn_id"]) if isinstance(n, str)})
    out.update(teams.id_lookup("oddsapi"))
    return out


def _get(params: dict) -> tuple[list, dict]:
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r), {k.lower(): v for k, v in r.headers.items()}


def parse(events: list, lookup: dict | None = None) -> tuple[pd.DataFrame, list]:
    """Rows in odds.py's format from The Odds API's event list; also the team names that didn't match."""
    lookup = lookup or _lookup()
    now = pd.Timestamp.now(tz="UTC")
    rows, unmatched = [], set()
    for ev in events:
        if pd.to_datetime(ev.get("commence_time"), utc=True) <= now:
            continue
        hn, an = ev.get("home_team"), ev.get("away_team")
        h, a = lookup.get(teams.norm(hn or "")), lookup.get(teams.norm(an or ""))
        if h is None or a is None:
            unmatched.update(n for n, i in ((hn, h), (an, a)) if i is None)
            continue
        for bk in ev.get("bookmakers") or []:
            if bk.get("key") not in BOOKS:
                continue
            upd = pd.to_datetime(bk.get("last_update"), utc=True, errors="coerce")
            if pd.notna(upd) and now - upd > MAX_AGE:
                continue
            r = {"book": BOOKS[bk["key"]], "sgo_event": f"oa:{ev.get('id')}", "start": ev.get("commence_time"),
                 "home_id": h, "away_id": a}
            for m in bk.get("markets") or []:
                for o in m.get("outcomes") or []:
                    name, price, link = o.get("name"), o.get("price"), o.get("link")
                    if m["key"] == "spreads":
                        side = "home" if name == hn else "away" if name == an else None
                        if side:
                            r[f"{side}_spread_odds"] = price
                            if link:
                                r[f"{side}_spread_link"] = link
                            if side == "home":
                                r["home_spread"] = o.get("point")
                    elif m["key"] == "totals":
                        side = str(name).lower()
                        if side in ("over", "under"):
                            r[f"{side}_odds"] = price
                            r["total"] = o.get("point")
                            if link:
                                r[f"{side}_link"] = link
                    elif m["key"] == "h2h":
                        side = "home" if name == hn else "away" if name == an else None
                        if side:
                            r[f"{side}_ml"] = price
                            if link:
                                r[f"{side}_ml_link"] = link
            rows.append(r)
    base = ["book", "sgo_event", "start", "home_id", "away_id", "home_spread", "total"]
    df = pd.DataFrame(rows).reindex(columns=list(dict.fromkeys(base + [c for r in rows for c in r])))
    for c in df.columns:
        if c.endswith(("_odds", "_ml", "spread")) or c == "total":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, sorted(unmatched)


def fetch(api_key: str | None = None) -> pd.DataFrame:
    api_key = api_key or os.environ.get("ODDS_API_KEY", "")
    params = {"apiKey": api_key, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american",
              "bookmakers": ",".join(BOOKS), "includeLinks": "true"}
    try:
        events, hdr = _get(params)
    except urllib.error.HTTPError as e:
        if e.code not in (400, 422):
            raise
        # a book key the API doesn't know, or links not offered on this plan: retry with the core books, then no links
        try:
            events, hdr = _get(dict(params, bookmakers=",".join(CORE)))
            print(f"The Odds API refused the book list ({e.code}); used {', '.join(CORE)}.")
        except urllib.error.HTTPError:
            params.pop("includeLinks")
            events, hdr = _get(dict(params, bookmakers=",".join(CORE)))
    df, fetch.unmatched = parse(events)
    fetch.events = len(events)
    u = {"remaining": int(float(hdr.get("x-requests-remaining", "nan"))) if hdr.get("x-requests-remaining") else None,
         "used": int(float(hdr.get("x-requests-used", 0) or 0)), "at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(USAGE), exist_ok=True)
    with open(USAGE, "w") as f:
        json.dump(u, f)
    fetch.usage = u
    return df
