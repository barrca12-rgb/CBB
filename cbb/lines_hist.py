"""Historical pregame spreads and totals from ESPN game summaries (`pickcenter`), for the backtest.

ESPN keeps the final pregame line from one or more providers (consensus, teamrankings, numberfire, and in
2026 DraftKings). Coverage from a 50-game sample per season: 2013-2018 about 65-80% of games, 2019-2023 about
100%, 2026 about 80%; nothing for 2012, 2024 or 2025. These are closing-style numbers: ESPN shows the last
line before tipoff, not the opener.

    python -m cbb.lines_hist --start 2013 --end 2026      # writes data/lines/espn_<season>.csv

Columns: game_id, provider, home_spread (sportsbook convention, -3 = home favored by 3), total.
One row per (game, provider); games with no line get a row with provider empty so reruns skip them.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import data

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={}"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "lines")
# Preferred provider when a game has several (ESPN's consensus first, then the sportsbook).
PROVIDER_ORDER = ["consensus", "DraftKings", "teamrankings", "numberfire"]


def game_lines(game_id: int) -> list[dict]:
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL.format(game_id), headers={"User-Agent": "cbb-model"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    rows = []
    for p in d.get("pickcenter") or []:
        if p.get("spread") is None and p.get("overUnder") is None:
            continue
        rows.append({"game_id": game_id, "provider": p.get("provider", {}).get("name", ""),
                     "home_spread": p.get("spread"), "total": p.get("overUnder")})
    return rows or [{"game_id": game_id, "provider": "", "home_spread": None, "total": None}]


def season_lines(season: int, workers: int = 8) -> pd.DataFrame:
    path = os.path.join(OUT, f"espn_{season}.csv")
    done = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=["game_id"])
    g, _ = data.season_games(season)
    todo = sorted(set(g["game_id"]) - set(done["game_id"]))
    if todo:
        with ThreadPoolExecutor(workers) as ex:
            new = [r for rows in ex.map(game_lines, todo) for r in rows]
        done = pd.concat([done, pd.DataFrame(new)], ignore_index=True)
        os.makedirs(OUT, exist_ok=True)
        done.sort_values(["game_id", "provider"]).to_csv(path, index=False)
    return done


def best(lines: pd.DataFrame) -> pd.DataFrame:
    """One line per game, from the preferred provider that has one."""
    l = lines.dropna(subset=["home_spread"]).copy()
    rank = {p: i for i, p in enumerate(PROVIDER_ORDER)}
    l["rank"] = l["provider"].map(rank).fillna(len(rank))
    return l.sort_values(["game_id", "rank"]).drop_duplicates("game_id").drop(columns="rank")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    for s in range(a.start, a.end + 1):
        l = season_lines(s)
        b = best(l)
        print(f"{s}: {l['game_id'].nunique()} games checked, {len(b)} with a spread", flush=True)


if __name__ == "__main__":
    main()
