"""Opener rule (Nov 2): which plays already in bets/bets.csv were line-move plays when they were logged.

Each play logged before the rule went live gets the same opener test the card now applies, as of its own
logged_at: the model it was logged with (bets.csv "model"), the first quotes seen up to that moment (lines/moves.csv
and lines/openers.csv as of logged_at), and the quotes then standing as this run's. A play that fails it is a
"line-move, pre-rule" play: it stays in the log as logged and is reported in its own cell, never pooled with v1.
Writes bets/linemove_prerule.csv (read by tracker.load; display and reads only, the bet log is unchanged).

    python -m research.linemove.prerule [--before ISO]
"""
from __future__ import annotations

import argparse
import os
import tempfile

import numpy as np
import pandas as pd

from cbb import odds, run_day, tracker

OUT = os.path.join(tracker.ROOT, "bets", "linemove_prerule.csv")
COLS = ["bet_id", "bet_type", "market", "pick", "logged_at", "opener_line", "opener_price", "opener_book",
        "opener_first_seen", "edge_vs_opener", "edge_logged"]


def classify(before: str) -> pd.DataFrame:
    b = tracker.load("all")
    b = b[(b["status"] != "void") & (pd.to_datetime(b["logged_at"], utc=True) < pd.Timestamp(before))]
    moves = pd.read_csv(odds.MOVES)
    mt = pd.to_datetime(moves["pulled_at"], utc=True, format="ISO8601")
    op = pd.read_csv(os.path.join(odds.LINES, "openers.csv"))
    ot = pd.to_datetime(op["first_seen"], utc=True, format="ISO8601")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        mp, opp = os.path.join(tmp, "m.csv"), os.path.join(tmp, "o.csv")
        cache = {}
        for _, r in b.sort_values("logged_at").iterrows():
            at = pd.Timestamp(r["logged_at"])
            if at not in cache:
                moves[mt <= at].to_csv(mp, index=False)
                op[ot <= at].to_csv(opp, index=False)
                cache = {at: run_day.first_quotes(mp, openers=opp)}
            fq = cache[at]
            h, a = int(r["home_id"]), int(r["away_id"])
            lo = min(h, a)
            m = moves[(mt <= at) & (moves["lo_id"] == lo) & (moves["hi_id"] == max(h, a))]
            m = m.drop_duplicates(["game_key", "book"], keep="last")
            home_lo = h == lo
            cur = pd.DataFrame({"book": m["book"], "home_spread": np.where(home_lo, m["spread"], -m["spread"]),
                                "home_spread_odds": np.where(home_lo, m["spread_odds_lo"], m["spread_odds_hi"]),
                                "away_spread_odds": np.where(home_lo, m["spread_odds_hi"], m["spread_odds_lo"]),
                                "total": m["total"], "over_odds": m["over_odds"], "under_odds": m["under_odds"]})
            kind = "bandB" if r.get("bet_type") == tracker.BAND_B else "v1"
            thr = tracker.BAND_B_RANGE[r["market"]][0] if kind == "bandB" else \
                (run_day.SPREAD_CALLS if r["market"] == "spread" else run_day.TOTAL_CALLS)[0][0]
            start = r["date"] + "T23:00:00Z"
            g = {"home_id": h, "away_id": a, "start": start}
            ok, o = run_day.opener_test(fq, g, r["market"], str(r["side"]).lower(), float(r["model"]), thr, cur,
                                        at.isoformat())
            if not ok:
                rows.append({"bet_id": r["bet_id"], "bet_type": kind, "market": r["market"], "pick": r["pick"],
                             "logged_at": r["logged_at"], "opener_line": o["line"] if o else np.nan,
                             "opener_price": o["price"] if o else np.nan, "opener_book": o["book"] if o else None,
                             "opener_first_seen": o["seen_at"] if o else None,
                             "edge_vs_opener": round(o["edge"], 2) if o else np.nan, "edge_logged": r["edge"]})
    return pd.DataFrame(rows, columns=COLS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=pd.Timestamp.now(tz="UTC").isoformat())
    a = ap.parse_args()
    t = classify(a.before)
    t.to_csv(OUT, index=False)
    print(f"{len(t)} line-move, pre-rule plays (logged before {a.before}):")
    print(t.groupby(["bet_type", "market"]).size().to_string())


if __name__ == "__main__":
    main()
