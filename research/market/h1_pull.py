"""First-half test, option A (research/market/LOG.md): first-half spreads and totals at tip - 15 minutes for every
mapped game on the 2025-26 Option B dates, at most 11,700 credits, floor 50,000. Resumable.

    python -m research.market.h1_pull --select   lists the games (local, no API) -> data/h1_a_games.csv
    python -m research.market.h1_pull            pulls (GitHub Actions, research_h1_a.yml, needs ODDS_API_KEY)
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from research.market.h1_pilot import DATA, FLOOR, PER_CALL, get

GAMES = os.path.join(DATA, "h1_a_games.csv")
LINES = os.path.join(DATA, "h1_a_lines.csv")
STATUS = os.path.join(DATA, "h1_a_status.csv")
DATES = ["2025-01-11", "2025-03-01", "2025-11-08", "2026-01-10", "2026-03-07"]
CAP = 11_700


def select() -> None:
    from research.market.s1_sample_report import OUT
    f = pd.read_csv(os.path.join(OUT, "s1_first_quotes.csv.gz"))
    g = f[f["date"].isin(DATES)].drop_duplicates("game_id")
    g[["date", "game_id", "event_id", "tip", "home_team", "away_team", "h", "a", "flip"]].sort_values(["date", "tip", "game_id"]).to_csv(GAMES, index=False)
    print(g.groupby("date").size(), len(g))


def pull() -> None:
    key = os.environ.get("ODDS_API_KEY") or sys.exit("ODDS_API_KEY missing")
    g = pd.read_csv(GAMES)
    old = pd.read_csv(STATUS) if os.path.exists(STATUS) else pd.DataFrame(columns=["game_id"])
    rows = pd.read_csv(LINES).to_dict("records") if os.path.exists(LINES) else []
    status = old.to_dict("records")
    spent, left = 0, None
    for _, r in g[~g["game_id"].isin(old["game_id"])].iterrows():
        if spent + PER_CALL > CAP or (left is not None and int(float(left)) - PER_CALL < FLOOR):
            print(f"Stopping: spent {spent}, {left} left (cap {CAP}, floor {FLOOR})")
            break
        at = (pd.Timestamp(r["tip"]) - pd.Timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        d, cost, rem, err = get(r["event_id"], at, key)
        spent += cost
        left = rem or left
        data = (d or {}).get("data") or {}
        n = 0
        for b in data.get("bookmakers") or []:
            for m in b.get("markets") or []:
                for o in m.get("outcomes") or []:
                    rows.append({"game_id": r["game_id"], "event_id": r["event_id"], "snapshot": (d or {}).get("timestamp"),
                                 "book": b["key"], "market": m["key"], "outcome": o.get("name"), "point": o.get("point"),
                                 "price": o.get("price"), "last_update": m.get("last_update")})
                    n += 1
        status.append({"game_id": r["game_id"], "rows": n, "books": len(data.get("bookmakers") or []), "cost": cost, "error": err})
        if len(status) % 50 == 0:
            pd.DataFrame(rows).to_csv(LINES, index=False)
            pd.DataFrame(status).to_csv(STATUS, index=False)
            print(f"{len(status)} games, spent {spent}, {left} left", flush=True)
    pd.DataFrame(rows).to_csv(LINES, index=False)
    st = pd.DataFrame(status)
    st.to_csv(STATUS, index=False)
    print(f"games {len(st)}, with lines {(st['rows'] > 0).sum()}; spent {spent} this run; {left} left")


if __name__ == "__main__":
    select() if "--select" in sys.argv else pull()
