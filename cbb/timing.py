"""Bet timing: when books post, how fast lines move after the opener, and how much edge our bets keep.

Historical (opener and close only, 2014-2017 and 2024-2026), from the backtest: spread plays at 3+ saw the line move
our way 65-77% of the time, about 1.2-1.3 points on average, and won 58.7% at the open vs 55.0% for the same bets at
the close (2024-2026). Totals at 4+: 60.1% vs 55.0%. Every point of move is worth about 3-4 points of win rate.

What the opener and close can't show is WHEN the move happens. The live logs can: lines/openers.csv (first_seen
per game and book), lines/moves.csv (every change, every 30-minute check) and bets/bets.csv (logged_at). report()
answers:

  1. Posting: what time (ET) each book first posts a game, and how far ahead of tip.
  2. Speed: for games we bet, how much of the opener-to-close move had happened 1, 2, 4, 8 and 12 hours after the
     opener posted.
  3. Our timing: hours from the line posting to our BET being logged, and the closing line value we got.

    python -m cbb.timing
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import odds, tracker

HOURS = [1, 2, 4, 8, 12]


def _load():
    op = pd.read_csv(os.path.join(odds.LINES, "openers.csv"))
    mv = pd.read_csv(odds.MOVES) if os.path.exists(odds.MOVES) else pd.DataFrame()
    cl = pd.read_csv(os.path.join(odds.LINES, "closing.csv"))
    for d, c in ((op, "first_seen"), (mv, "pulled_at"), (cl, "pulled_at")):
        if len(d):
            d[c] = pd.to_datetime(d[c], utc=True, format="ISO8601")
    cl["start"] = pd.to_datetime(cl["start"], utc=True, format="ISO8601")
    cl["game_key"] = odds.game_key(cl)
    return op, mv, cl


def posting(op: pd.DataFrame, cl: pd.DataFrame) -> pd.DataFrame:
    """Per book: games, median hour posted (ET), median hours before tip."""
    d = op.merge(cl[["game_key", "book", "start"]].drop_duplicates(["game_key", "book"]), on=["game_key", "book"])
    d["hour_et"] = d["first_seen"].dt.tz_convert("America/New_York").dt.hour
    d["ahead_h"] = (d["start"] - d["first_seen"]).dt.total_seconds() / 3600
    return d.groupby("book").agg(games=("game_key", "nunique"), median_hour_et=("hour_et", "median"),
                                 median_hours_before_tip=("ahead_h", "median"))


def speed(mv: pd.DataFrame, game_keys: set | None = None) -> pd.DataFrame:
    """Share of each (game, book)'s total opener-to-close spread move done N hours after the first number."""
    if not len(mv):
        return pd.DataFrame()
    m = mv.dropna(subset=["spread"]).sort_values("pulled_at")
    if game_keys is not None:
        m = m[m["game_key"].isin(game_keys)]
    rows = []
    for (gk, bk), g in m.groupby(["game_key", "book"]):
        o, c = g["spread"].iloc[0], g["spread"].iloc[-1]
        if o == c:
            continue
        t0 = g["pulled_at"].iloc[0]
        r = {"game_key": gk, "book": bk, "total_move": abs(c - o)}
        for h in HOURS:
            at = g[g["pulled_at"] <= t0 + pd.Timedelta(hours=h)]["spread"].iloc[-1]
            r[f"done_{h}h"] = (at - o) / (c - o)
        rows.append(r)
    return pd.DataFrame(rows)


def our_timing(op: pd.DataFrame) -> pd.DataFrame:
    """Each logged bet: hours from that book's first number to the bet being logged, and its CLV."""
    b = tracker.load()
    if not len(b):
        return b
    b["logged_at"] = pd.to_datetime(b["logged_at"], utc=True, format="ISO8601")
    lo = np.minimum(b["home_id"], b["away_id"]).astype(int).astype(str)
    hi = np.maximum(b["home_id"], b["away_id"]).astype(int).astype(str)
    b["game_key"] = b["date"] + "|" + lo + "|" + hi
    first = op.groupby(["game_key", "book"])["first_seen"].min().rename("posted")
    b = b.merge(first, left_on=["game_key", "book"], right_index=True, how="left")
    b["hours_after_post"] = (b["logged_at"] - b["posted"]).dt.total_seconds() / 3600
    return b[["date", "market", "pick", "book", "posted", "logged_at", "hours_after_post", "clv_pts", "result"]]


def report() -> str:
    op, mv, cl = _load()
    out = ["Posting (when each book first had the game):", posting(op, cl).round(1).to_string()]
    bets = our_timing(op)
    sp = speed(mv)
    if len(sp):
        cols = [f"done_{h}h" for h in HOURS]
        out += ["", f"Speed: share of the opener-to-close spread move done N hours after posting ({len(sp)} game-books "
                    "that moved):", sp[cols].median().round(2).to_string()]
    else:
        out += ["", "Speed: no moves logged yet."]
    if len(bets):
        out += ["", "Our bets:", bets.to_string(index=False)]
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
