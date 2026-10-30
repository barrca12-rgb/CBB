"""Season scan for the bad-quote guards (Chad, Oct 30): every logged bet so far, v1 and band B, checked against the
three guards with the books' quotes as the card saw them when it logged the bet (lines/closing.csv at the commit that
first added the bet to bets/bets.csv). Read-only.

    python -m audit.guard_scan        # -> audit/out/guard_scan.csv
"""
from __future__ import annotations

import io
import os
import subprocess

import numpy as np
import pandas as pd

from cbb import run_day, tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")


def git(*a) -> str:
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, check=True).stdout


def first_commit(bet_id: str) -> str:
    """The oldest commit whose bets/bets.csv contains bet_id."""
    for c in reversed(git("log", "--format=%H", "-S", bet_id, "--", "bets/bets.csv").split()):
        if bet_id in git("show", f"{c}:bets/bets.csv"):
            return c
    raise LookupError(bet_id)


def scan() -> pd.DataFrame:
    b = tracker.load("all")
    rows = []
    for _, r in b.iterrows():
        c = first_commit(r["bet_id"])
        try:
            lines = pd.read_csv(io.StringIO(git("show", f"{c}:lines/closing.csv")))
        except subprocess.CalledProcessError:
            lines = pd.DataFrame()
        h, a = int(r["home_id"]), int(r["away_id"])
        same = lines[(lines["home_id"] == h) & (lines["away_id"] == a)] if len(lines) else lines
        flip = lines[(lines["home_id"] == a) & (lines["away_id"] == h)] if len(lines) else lines
        l = same if len(same) else flip.assign(home_spread=-flip["home_spread"]) if len(flip) else same
        col = "home_spread" if r["market"] == "spread" else "total"
        off = run_day._off_market(l, col) if len(l) else pd.DataFrame()
        bk = off[off["book"] == r["book"]] if len(off) else off
        edge = float(r["edge"])
        g1 = pd.isna(r["odds"])
        g2 = len(bk) > 0
        g3 = edge > run_day.MAX_EDGE[r["market"]]
        rows.append({"bet_id": r["bet_id"], "type": r.get("bet_type") if isinstance(r.get("bet_type"), str) else "v1",
                     "status": r["status"], "placed": r.get("placed"), "pick": r["pick"], "book": r["book"],
                     "odds": r["odds"], "edge": edge, "logged_at": r["logged_at"], "commit": c[:8],
                     "books_quoting": int(l[col].notna().sum()) if len(l) else 0,
                     "median_others": float(bk["median_others"].iloc[0]) if g2 else np.nan,
                     "g1_no_price": g1, "g2_off_market": g2, "g3_review": g3, "caught": g1 or g2 or g3})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    s = scan()
    os.makedirs(os.path.join(ROOT, "audit", "out"), exist_ok=True)
    s.to_csv(os.path.join(ROOT, "audit", "out", "guard_scan.csv"), index=False)
    pd.set_option("display.width", 220)
    print(s[["bet_id", "type", "status", "placed", "book", "odds", "edge", "books_quoting", "g1_no_price", "g2_off_market", "g3_review"]].to_string(index=False))
    print(f"\n{len(s)} bets scanned; caught by any guard: {int(s['caught'].sum())}")
