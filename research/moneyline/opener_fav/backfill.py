"""Rebuild the opener-favorite signals the live recorder missed (Oct 30 20:30 UTC to Nov 1 02:30 UTC: it failed on a
missing scipy on the card's runner; the price log kept writing). Same rule as the recorder (PLAN.md): each book's FIRST
priced moneyline on a game after the price log started, the favorite, p = Phi(m / 11) with m the card's projected margin
from the card committed at that run, EV +5% or more. Rows are appended to lines/ml/opener_fav.csv once, marked in
research/moneyline/opener_fav/out/backfill.txt.

    python -m research.moneyline.opener_fav.backfill
"""
from __future__ import annotations

import io
import math
import os
import subprocess

import pandas as pd

from cbb import card_features
from research.moneyline.shadow.run import price_log

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
UNTIL = pd.Timestamp("2026-11-01T02:30:00Z")          # the fixed recorder is live from the next run


def git(*a) -> str:
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, check=True).stdout


def card_at(date: str, t: pd.Timestamp, memo: dict) -> pd.DataFrame | None:
    """The card for `date` as committed at or just after run time t (the run's own commit)."""
    key = (date, t.floor("min"))
    if key not in memo:
        c = git("log", "--after", (t - pd.Timedelta(minutes=1)).isoformat(), "--reverse", "--format=%H", "--", f"reports/cbb_{date}.csv").split()
        memo[key] = pd.read_csv(io.StringIO(git("show", f"{c[0]}:reports/cbb_{date}.csv"))) if c else None
    return memo[key]


def main() -> None:
    log = price_log()
    start = log["observed_at"].min()
    ok = log[(log["status"] == "ok") & (log["observed_at"] > start) & (log["observed_at"] < UNTIL)]
    first_any = log[log["status"] == "ok"].sort_values("observed_at").drop_duplicates(["home_id", "away_id", "book"])
    first = first_any[(first_any["observed_at"] > start) & (first_any["observed_at"] < UNTIL)]
    rows, memo = [], {}
    for _, r in first.iterrows():
        c = card_at(str(r["date"]), r["observed_at"], memo) if pd.notna(r.get("date")) else None
        if c is None:
            continue
        g = c[((c["home_id"] == r["home_id"]) & (c["away_id"] == r["away_id"])) | ((c["home_id"] == r["away_id"]) & (c["away_id"] == r["home_id"]))]
        if not len(g) or pd.isna(g["model_margin"].iloc[0]):
            continue
        g = g.iloc[0]
        m_home = float(g["model_margin"]) * (1 if int(g["home_id"]) == int(r["home_id"]) else -1)
        for team, opp, price, opp_price, m in ((r["home_id"], r["away_id"], r["home_ml"], r["away_ml"], m_home),
                                               (r["away_id"], r["home_id"], r["away_ml"], r["home_ml"], -m_home)):
            if not (price < 0 and price < opp_price):
                continue                                 # favorites only: the more negative price
            p = 0.5 * (1 + math.erf(m / card_features.OPENER_SIGMA / math.sqrt(2)))
            ev = p * (100 / -price) - (1 - p)
            if ev >= card_features.OPENER_EV:
                rows.append({"run_at": r["observed_at"].isoformat(timespec="seconds"), "date": r["date"], "game_id": g["game_id"],
                             "start": r["start"], "book": r["book"], "team_id": int(team), "opp_id": int(opp), "price": price,
                             "opp_price": opp_price, "p_model": round(p, 4), "ev": round(ev, 4), "model_margin": round(m, 2)})
    out = pd.DataFrame(rows, columns=card_features.OPENER_COLS)
    path = card_features.OPENER_FAV
    if os.path.exists(path):
        have = pd.read_csv(path)
        key = ["game_id", "book", "team_id"]
        out = out[~out.set_index(key).index.isin(have.set_index(key).index)]
    if len(out):
        out.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
    msg = (f"Backfill (recorder down Oct 30 20:30 to Nov 1 02:30 UTC): {len(first)} first priced moneylines in the window; "
           f"{len(rows)} qualifying favorites; {len(out)} appended to lines/ml/opener_fav.csv")
    open(os.path.join(os.path.dirname(__file__), "out", "backfill.txt"), "w").write(msg + "\n")
    print(msg)


if __name__ == "__main__":
    main()
