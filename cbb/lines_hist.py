"""Historical pregame spreads and totals from ESPN's odds feed, for the backtest.

sports.core.api.espn.com keeps, per game, the last pregame line from every book it tracked. Coverage from a
40-game sample per season:

    2012        none
    2013-2018   about 70% of games (2014-2017 include Pinnacle and an "Opening" line)
    2019-2024   about 100%, 8-13 books per game
    2024-2026   about 100%, with opening and closing lines (one book: ESPN BET, then DraftKings)

    python -m cbb.lines_hist --start 2013 --end 2026      # writes data/lines/espn_<season>.csv

`consensus()` keeps real sportsbooks only (see NOT_BOOKS), which leaves nothing for 2013.

One row per (game, book): home_spread and total (closing, sportsbook convention: -3 = home favored by 3),
home_ml/away_ml, and open_home_spread/open_total where ESPN has the opener. Games with no line get one row
with an empty book so reruns skip them. In-game ("Live Odds") feeds are dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from . import data

URL = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/"
       "events/{0}/competitions/{0}/odds?limit=100")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "lines")
# Projection sites and aggregates, not sportsbooks. numberfire stores 0 for a missing line, and teamrankings tracks
# results more closely than any book (likely updated after the close), so neither is a usable closing line. 2013
# has only these, so the betting backtest starts in 2014.
NOT_BOOKS = {"consensus", "numberfire", "teamrankings"}
COLS = ["game_id", "book", "home_spread", "total", "home_ml", "away_ml", "open_home_spread", "open_total"]


def _num(x):
    try:
        v = float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return np.nan
    return v


def _american(side: dict, when: str, field: str):
    return _num(((side.get(when) or {}).get(field) or {}).get("american"))


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
    for p in d.get("items") or []:
        book = (p.get("provider") or {}).get("name", "")
        if "live" in book.lower():
            continue
        h, a = p.get("homeTeamOdds") or {}, p.get("awayTeamOdds") or {}
        close_sp = _american(h, "close", "pointSpread")
        close_tot = _num(((p.get("close") or {}).get("total") or {}).get("american"))
        r = {
            "game_id": game_id, "book": book,
            "home_spread": close_sp if close_sp == close_sp else _num(p.get("spread")),
            "total": close_tot if close_tot == close_tot else _num(p.get("overUnder")),
            "home_ml": _num(h.get("moneyLine")) or np.nan,
            "away_ml": _num(a.get("moneyLine")) or np.nan,
            "open_home_spread": _american(h, "open", "pointSpread"),
            "open_total": _num(((p.get("open") or {}).get("total") or {}).get("american")),
        }
        if r["home_spread"] == r["home_spread"] or r["total"] == r["total"]:
            rows.append(r)
    return rows or [{"game_id": game_id, "book": ""}]


def season_lines(season: int, workers: int = 8) -> pd.DataFrame:
    path = os.path.join(OUT, f"espn_{season}.csv")
    done = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=COLS)
    g, _ = data.season_games(season)
    todo = sorted(set(g["game_id"]) - set(done["game_id"]))
    if todo:
        with ThreadPoolExecutor(workers) as ex:
            new = [r for rows in ex.map(game_lines, todo) for r in rows]
        done = pd.concat([done, pd.DataFrame(new, columns=COLS)], ignore_index=True)
        os.makedirs(OUT, exist_ok=True)
        done.sort_values(["game_id", "book"]).to_csv(path, index=False)
    return done


def consensus(lines: pd.DataFrame) -> pd.DataFrame:
    """One closing line per game: the median across books (robust to one stale or off-market book)."""
    l = lines[~lines["book"].fillna("").isin(NOT_BOOKS | {"", "Opening"})].copy()
    l.loc[l["total"] <= 0, "total"] = np.nan
    # Drop a book whose spread is far from the others on the same game (side flipped or stale).
    med = l.groupby("game_id")["home_spread"].transform("median")
    l.loc[(l["home_spread"] - med).abs() > 5, "home_spread"] = np.nan
    agg = l.groupby("game_id").agg(home_spread=("home_spread", "median"), total=("total", "median"),
                                   open_home_spread=("open_home_spread", "median"),
                                   open_total=("open_total", "median"), books=("book", "nunique"))
    # ESPN's "Opening" pseudo-book (2014-2017) fills in openers where no book has one.
    op = lines[lines["book"] == "Opening"].drop_duplicates("game_id").set_index("game_id")
    agg["open_home_spread"] = agg["open_home_spread"].fillna(op["home_spread"])
    agg["open_total"] = agg["open_total"].fillna(op["total"])
    return agg.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    for s in range(a.start, a.end + 1):
        c = consensus(season_lines(s))
        print(f"{s}: {c['home_spread'].notna().sum()} games with a spread, {c['open_home_spread'].notna().sum()} "
              f"with an opener", flush=True)


if __name__ == "__main__":
    main()
