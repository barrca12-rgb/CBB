"""Opener favorite moneylines: grade the live log (PLAN.md). Reads lines/ml/opener_fav.csv (written by the card's
wrapper), the price log and the card reports; writes research/moneyline/opener_fav/out/bets.csv and summary.txt.

    python -m research.moneyline.opener_fav.run [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from research.moneyline import test1 as t1
from research.moneyline.devig_methods import implied, shin
from research.moneyline.shadow.run import BOOKS, price_log

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..", "..")
LOG = os.path.join(ROOT, "lines", "ml", "opener_fav.csv")
REPORTS = os.path.join(ROOT, "reports")
OUT = os.path.join(HERE, "out")


def _fair(ours, theirs) -> np.ndarray:
    return shin(implied(ours), implied(theirs))[0]


def _result(date: str, game_id) -> tuple | None:
    """(home_id, away_id, home_score, away_score) once the card reports the game final."""
    path = os.path.join(REPORTS, f"cbb_{date}.csv")
    if not os.path.exists(path):
        return None
    c = pd.read_csv(path, usecols=lambda k: k in ("game_id", "home_id", "away_id", "home_score", "away_score", "state"))
    r = c[c["game_id"].astype(str) == str(game_id)]
    if not len(r) or r["state"].iloc[0] != "post" or pd.isna(r["home_score"].iloc[0]):
        return None
    r = r.iloc[0]
    return int(r["home_id"]), int(r["away_id"]), float(r["home_score"]), float(r["away_score"])


def build(through: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not os.path.exists(LOG):
        return pd.DataFrame(), pd.DataFrame()
    s = pd.read_csv(LOG)
    if through:
        s = s[s["date"].astype(str) <= through]
    s["profit"], s["won"], s["clv_pp"] = np.nan, np.nan, np.nan
    log = price_log()
    for i, r in s.iterrows():
        res = _result(str(r["date"]), r["game_id"])
        if res is not None:
            h, a, hs, as_ = res
            team_pts, opp_pts = (hs, as_) if int(r["team_id"]) == h else (as_, hs)
            won = team_pts > opp_pts
            s.at[i, "won"] = float(won)
            s.at[i, "profit"] = 100 / -r["price"] if won else -1.0
        if res is not None and len(log) and pd.notna(r["start"]):     # final: the close is complete
            tip = pd.Timestamp(r["start"])
            g = log[(((log["home_id"] == r["team_id"]) & (log["away_id"] == r["opp_id"]))
                     | ((log["home_id"] == r["opp_id"]) & (log["away_id"] == r["team_id"])))
                    & (log["observed_at"] < tip) & (log["status"] == "ok") & log["book"].isin(BOOKS)]
            g = g.sort_values("observed_at").drop_duplicates("book", keep="last")
            if len(g):
                ours = np.where(g["home_id"] == r["team_id"], g["home_ml"], g["away_ml"])
                theirs = np.where(g["home_id"] == r["team_id"], g["away_ml"], g["home_ml"])
                close = float(np.median(_fair(ours, theirs)))
                s.at[i, "clv_pp"] = round(100 * (close - float(_fair([r["price"]], [r["opp_price"]])[0])), 2)
    s["run_at"] = pd.to_datetime(s["run_at"], utc=True)
    s["pay"] = 100 / -s["price"]
    unit = s.sort_values(["run_at", "pay"], ascending=[True, False]).drop_duplicates(["game_id", "team_id"])
    return s, unit


def summary(s: pd.DataFrame, unit: pd.DataFrame) -> str:
    if not len(s):
        return "Opener favorite moneylines: no signals logged yet."
    g = unit.dropna(subset=["profit"])
    L = [f"Opener favorite moneylines (EV +5% at Phi(margin / 11), first price at a book): {len(s)} qualifying quotes, "
         f"{len(unit)} game-sides, {len(g)} graded"]
    if len(g):
        st = t1.summary(g.assign(p=g["p_model"]))
        c = g["clv_pp"].dropna()
        L.append(f"  first qualifying quote per game-side: {st}; mean moneyline CLV {c.mean():+.2f} pp on {len(c)}"
                 if len(c) else f"  first qualifying quote per game-side: {st}")
        sg = s.dropna(subset=["profit"])
        L.append("  every qualifying quote, by book:\n" + pd.DataFrame(
            [{"book": k, **t1.summary(v.assign(p=v["p_model"]))} for k, v in sg.groupby("book")]).to_string(index=False))
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    a = ap.parse_args()
    s, unit = build(a.through)
    os.makedirs(OUT, exist_ok=True)
    if len(unit):
        unit.to_csv(os.path.join(OUT, "bets.csv"), index=False)
    text = summary(s, unit)
    open(os.path.join(OUT, "summary.txt"), "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
