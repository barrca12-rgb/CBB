"""B2 data: AP rank at game time and TV networks for every game in the frozen frames, from ESPN's public scoreboard
(one call per game date, cached). Output research/frontier/out/b2_espn.csv.gz: game_id, home/away AP rank (curatedRank,
99 = unranked), and the broadcast names with their market (national / regional / unknown).

    python -m research.frontier.b2_fetch
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

import pandas as pd

from research.originator.d_common import frames

HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, "out", "espn_sb")
OUT = os.path.join(HERE, "out", "b2_espn.csv.gz")
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={}&groups=50&limit=500"


def day(d: str) -> list[dict]:
    path = os.path.join(CACHE, f"{d}.json")
    if os.path.exists(path):
        return json.load(open(path))
    for i in range(4):
        try:
            req = urllib.request.Request(URL.format(d), headers={"User-Agent": "cbb-research"})
            with urllib.request.urlopen(req, timeout=40) as r:
                ev = json.load(r).get("events") or []
            break
        except Exception:
            time.sleep(2 ** (i + 1))
    else:
        return []
    rows = []
    for e in ev:
        c = e["competitions"][0]
        side = {t.get("homeAway"): t for t in c.get("competitors", [])}
        rk = lambda t: int(((t or {}).get("curatedRank") or {}).get("current") or 99)
        bro = [f"{b.get('market')}:{n}" for b in c.get("broadcasts") or [] for n in b.get("names") or []]
        rows.append({"game_id": int(e["id"]), "home_rank": rk(side.get("home")), "away_rank": rk(side.get("away")),
                     "broadcasts": "|".join(bro)})
    os.makedirs(CACHE, exist_ok=True)
    json.dump(rows, open(path, "w"))
    return rows


def main() -> None:
    train, _ = frames()
    dates = sorted(pd.to_datetime(train.loc[train["season"] >= 2014, "date"]).dt.strftime("%Y%m%d").unique())
    rows = []
    for i, d in enumerate(dates):
        rows += day(d)
        if i % 100 == 0:
            print(i, len(dates), d, len(rows), flush=True)
    out = pd.DataFrame(rows).drop_duplicates("game_id")
    out.to_csv(OUT, index=False)
    print("games", len(out), "matched to frames", out["game_id"].isin(train["game_id"]).sum())


if __name__ == "__main__":
    main()
