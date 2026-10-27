"""First-half line pilot (research/market/LOG.md): historical first-half spreads and totals for 20 games of the
2025-26 Option B dates, at two moments per game, at most 800 credits.

    python -m research.market.h1_pilot --select   picks the games (local, no API) -> data/h1_pilot_games.csv
    python -m research.market.h1_pilot            pulls (GitHub Actions, research_h1_pilot.yml, needs ODDS_API_KEY)

Moments: game day 15:00 UTC (10 or 11 am Eastern) and tip - 15 minutes. Output: data/h1_pilot_lines.csv (one row
per book, market and outcome at each moment) and data/h1_pilot_status.csv (per game and moment: lines found, credits).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
GAMES = os.path.join(DATA, "h1_pilot_games.csv")
API = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/events/{}/odds"
DATES = ["2025-11-08", "2026-01-10", "2026-03-07"]
MARKETS = "spreads_h1,totals_h1"
CAP, FLOOR, PER_CALL = 800, 50_000, 20


def select() -> None:
    from research.market.s1_sample_report import OUT, POWER
    from cbb import teams
    f = pd.read_csv(os.path.join(OUT, "s1_first_quotes.csv.gz"))
    g = f[f["date"].isin(DATES)].drop_duplicates("game_id")[["date", "game_id", "event_id", "tip", "home_team", "away_team", "h", "a"]]
    g["tip"] = pd.to_datetime(g["tip"], utc=True)
    g = g[g["tip"].dt.hour >= 17]       # tip at or after 17:00 UTC, so the 15:00 snapshot is before tip
    conf = teams.load().drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    g["power"] = g["h"].map(conf).isin(POWER) | g["a"].map(conf).isin(POWER)
    rng = np.random.default_rng(20261027)
    pick = pd.concat([x.iloc[rng.permutation(len(x))[:10]] for _, x in g.sort_values("game_id").groupby("power")])
    pick.sort_values(["date", "tip"]).to_csv(GAMES, index=False)
    print(pick.groupby(["date", "power"]).size())


def get(eid: str, at: str, key: str):
    q = urllib.parse.urlencode({"apiKey": key, "regions": "us", "markets": MARKETS, "oddsFormat": "american", "date": at})
    try:
        with urllib.request.urlopen(urllib.request.Request(API.format(eid) + "?" + q, headers={"User-Agent": "cbb-research"}), timeout=60) as r:
            h = {k.lower(): v for k, v in r.headers.items()}
            return json.load(r), int(float(h.get("x-requests-last", 0) or 0)), h.get("x-requests-remaining"), None
    except urllib.error.HTTPError as e:
        return None, 0, None, f"HTTP {e.code}: {e.read()[:200].decode(errors='ignore')}"


def pull() -> None:
    key = os.environ.get("ODDS_API_KEY") or sys.exit("ODDS_API_KEY missing")
    g = pd.read_csv(GAMES)
    rows, status, spent, left = [], [], 0, None
    for _, r in g.iterrows():
        tip = pd.Timestamp(r["tip"])
        for moment, at in (("morning", pd.Timestamp(r["date"] + " 15:00", tz="UTC")), ("tip-15", tip - pd.Timedelta(minutes=15))):
            if spent + PER_CALL > CAP or (left is not None and int(float(left)) - PER_CALL < FLOOR):
                print(f"Stopping: spent {spent}, {left} left (cap {CAP}, floor {FLOOR})")
                break
            d, cost, rem, err = get(r["event_id"], at.strftime("%Y-%m-%dT%H:%M:%SZ"), key)
            spent += cost
            left = rem or left
            data = (d or {}).get("data") or {}
            n = 0
            for b in data.get("bookmakers") or []:
                for m in b.get("markets") or []:
                    for o in m.get("outcomes") or []:
                        rows.append({"game_id": r["game_id"], "event_id": r["event_id"], "moment": moment,
                                     "snapshot": (d or {}).get("timestamp"), "book": b["key"], "market": m["key"],
                                     "outcome": o.get("name"), "point": o.get("point"), "price": o.get("price"),
                                     "last_update": m.get("last_update")})
                        n += 1
            status.append({"game_id": r["game_id"], "power": r["power"], "moment": moment, "rows": n,
                           "books": len(data.get("bookmakers") or []), "cost": cost, "error": err})
    pd.DataFrame(rows).to_csv(os.path.join(DATA, "h1_pilot_lines.csv"), index=False)
    st = pd.DataFrame(status)
    st.to_csv(os.path.join(DATA, "h1_pilot_status.csv"), index=False)
    print(st.groupby(["moment", "power"]).agg(calls=("rows", "size"), with_lines=("rows", lambda x: int((x > 0).sum())),
                                              books=("books", "mean"), credits=("cost", "sum")).to_string())
    print(f"spent {spent} credits; {left} left")


if __name__ == "__main__":
    select() if "--select" in sys.argv else pull()
