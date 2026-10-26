"""One-off check: does The Odds API carry college basketball second-half lines (spreads_h2, totals_h2) at our books?

1. Upcoming games: the event-markets endpoint lists every market key each book currently has for one event.
2. Last season: historical event odds at halftime (tip + 55 minutes) for a few 2025-26 games, high and low major,
   asking for second-half and first-half spreads and totals. Shows whether the books posted second-half lines in game
   and whether the API archived them.

Writes data/research/h2_check.json. Stops at CAP credits. Runs on GitHub (research_h2.yml), where ODDS_API_KEY is.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from . import data, odds_api, teams

API = "https://api.the-odds-api.com/v4"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "research", "h2_check.json")
CAP = 150
MARKETS = "spreads_h2,totals_h2,spreads_h1,totals_h1"
spent = {"credits": 0, "remaining": None}


def get(path: str, **params):
    params["apiKey"] = os.environ["ODDS_API_KEY"]
    req = urllib.request.Request(f"{API}{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "cbb-model"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            spent["credits"] += int(float(r.headers.get("x-requests-last", 0) or 0))
            spent["remaining"] = r.headers.get("x-requests-remaining")
            return json.load(r), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:300].decode(errors='ignore')}"


def books_markets(ev: dict) -> dict:
    return {b["key"]: sorted(m["key"] for m in b.get("markets") or []) for b in ev.get("bookmakers") or []}


def main():
    out = {"upcoming": [], "historical": []}
    books = ",".join(odds_api.BOOKS)
    evs, err = get("/sports/basketball_ncaab/events")
    out["events_error"] = err
    for ev in (evs or [])[:3]:   # 1. what markets exist on upcoming games right now
        if spent["credits"] >= CAP:
            break
        m, err = get(f"/sports/basketball_ncaab/events/{ev['id']}/markets", regions="us", bookmakers=books)
        out["upcoming"].append({"game": f"{ev.get('away_team')} at {ev.get('home_team')}", "start": ev.get("commence_time"),
                                "markets_by_book": books_markets(m) if m else None, "error": err})
    # 2. halftime snapshots from last season
    s = data.fetch("schedule", 2026)
    s = s[s["home_score"].notna()].copy()
    s["start"] = pd.to_datetime(s["date"], utc=True)
    hi = set(teams.load().query("kenpom_conf in ['B10','SEC','ACC','B12','BE']")["espn_id"])
    sat = s[s["start"].dt.strftime("%Y-%m-%d").isin(["2026-02-15", "2026-02-22"])]   # Saturday night games (UTC date)
    picks = pd.concat([sat[sat["home_id"].astype(int).isin(hi)].head(3), sat[~sat["home_id"].astype(int).isin(hi)].head(1)])
    look = odds_api._lookup()
    for _, g in picks.iterrows():
        if spent["credits"] >= CAP:
            break
        at = (g["start"] + pd.Timedelta(minutes=55)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ev, err = get("/historical/sports/basketball_ncaab/events", date=(g["start"] - pd.Timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        hit = None
        for e in ((ev or {}).get("data") or []):
            ids = {look.get(teams.norm(e.get("home_team", ""))), look.get(teams.norm(e.get("away_team", "")))}
            if ids == {int(g["home_id"]), int(g["away_id"])}:
                hit = e
        row = {"game": f"{g['away_display_name']} at {g['home_display_name']}", "tip": str(g["start"]), "snapshot": at,
               "event_found": hit is not None, "error": err}
        if hit:
            od, err = get(f"/historical/sports/basketball_ncaab/events/{hit['id']}/odds", date=at, regions="us",
                          markets=MARKETS, oddsFormat="american", bookmakers=books)
            d = (od or {}).get("data") or {}
            row.update(markets_by_book=books_markets(d), sample=[
                {"book": b["key"], "market": m["key"], "outcomes": [(o.get("name"), o.get("point"), o.get("price")) for o in m.get("outcomes", [])],
                 "last_update": m.get("last_update")}
                for b in d.get("bookmakers") or [] for m in b.get("markets") or []][:8], error=err)
        out["historical"].append(row)
    out["credits_spent"], out["credits_remaining"] = spent["credits"], spent["remaining"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
