"""Moneyline test 2 (PLAN.md): a book's moneyline against the other books' moneylines. Research only.

    python -m research.moneyline.test2      # -> research/moneyline/out/test2.txt, test2_bets.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.moneyline import test1 as t1

DEV, CONFIRM = range(2018, 2021), range(2021, 2025)
MIN_OTHERS = 3
L: list[str] = []
t1.L = L                      # one report: the shared loader's lines go into this file too


def main() -> None:
    os.makedirs(t1.OUT, exist_ok=True)
    d = t1.load(list(DEV) + list(CONFIRM))
    ih, ia = t1.implied(d["home_ml"]), t1.implied(d["away_ml"])
    d["nv_home"] = ih / (ih + ia)                                   # multiplicative vig removal
    g = d.groupby("game_id")["nv_home"]
    d["others"] = g.transform("count") - 1
    d["fair_home"] = g.transform(lambda x: pd.Series(
        [np.median(np.delete(x.to_numpy(), i)) if len(x) > 1 else np.nan for i in range(len(x))], index=x.index))
    d = d[d["others"] >= MIN_OTHERS].copy()
    t1.say(f"Quotes with {MIN_OTHERS}+ other clean books on the game: {len(d):,} on {d['game_id'].nunique():,} games")
    # the book's own spread against the other books' spreads (is an outlier moneyline also an outlier spread?)
    gs = d.groupby("game_id")["home_spread"]
    d["spread_gap"] = (d["home_spread"] - gs.transform(lambda x: pd.Series(
        [np.median(np.delete(x.to_numpy(), i)) for i in range(len(x))], index=x.index))).abs()
    sides = []
    for side, p, ml, won in (("home", d["fair_home"], d["home_ml"], d["home_win"]), ("away", 1 - d["fair_home"], d["away_ml"], 1 - d["home_win"])):
        x = d[["game_id", "date", "season", "book", "home_spread", "spread_gap", "others"]].assign(side=side, p=p, price=ml, won=won)
        x["ev"] = x["p"] * t1.payout(x["price"]) - (1 - x["p"])
        sides.append(x)
    q = pd.concat(sides, ignore_index=True)
    q["profit"] = np.where(q["won"] == 1, t1.payout(q["price"]), -1.0)
    sig = q[q["ev"] >= t1.EV_MIN]
    best = sig.sort_values("ev", ascending=False).drop_duplicates(["game_id", "side"])
    best.to_csv(os.path.join(t1.OUT, "test2_bets.csv"), index=False)
    t1.say(f"Quotes x sides: {len(q):,}; signals (EV >= +3% against the other books' no-vig median): {len(sig):,}; "
           f"best per game and side: {len(best):,}")
    # calibration of the consensus itself (confirm era, home side)
    cc = d[d["season"].isin(CONFIRM)].drop_duplicates("game_id").copy()
    cc["bin"] = pd.qcut(cc["fair_home"], 10, duplicates="drop")
    t1.say("\nCalibration of the other books' no-vig median, confirm era (home side, by decile):")
    t1.say(cc.groupby("bin", observed=True).agg(games=("fair_home", "size"), predicted=("fair_home", "mean"),
                                                actual=("home_win", "mean")).round(3).to_string())
    for era, ss in (("dev 2018-2020", DEV), ("CONFIRM 2021-2024", CONFIRM)):
        t1.say(f"\n== {era} ==")
        for lab, b in (("(ii) best per game/side [primary]", best), ("(i) every signal quote", sig)):
            t1.say(f"{lab}: {t1.summary(b[b['season'].isin(ss)])}")
    cb = best[best["season"].isin(CONFIRM)].copy()
    cb["dog"] = np.where(cb["price"] > 0, "underdog", "favorite")
    cb["band"] = pd.cut(cb["price"], [-1e9, -300, -150, 149.5, 299.5, 1e9],
                        labels=["-300 or shorter", "-299 to -150", "-149 to +149", "+150 to +299", "+300 or longer"])
    cb["own spread vs others"] = pd.cut(cb["spread_gap"], [-0.1, 0.25, 1.0, 2.99], labels=["same (<=0.25)", "0.5-1", "1.5-2.5"])
    cb["ev band"] = pd.cut(cb["ev"], [0.03, 0.05, 0.08, 1e9], labels=["3-5%", "5-8%", "8%+"])
    for col in ("dog", "band", "ev band", "own spread vs others", "book", "season"):
        rows = [{col: k, **t1.summary(v)} for k, v in cb.groupby(col, observed=True)]
        t1.say(f"\nConfirm era by {col}:")
        t1.say(pd.DataFrame(rows).to_string(index=False))
    s = t1.summary(cb)
    dead = s["bets"] < 200 or s["ROI %"] < 1.0 or s["95% lo"] <= 0
    t1.say(f"\nKill rule (confirm, best per game/side): bets {s['bets']} (need 200+), ROI {s['ROI %']}% (need +1%+), "
           f"95% interval [{s['95% lo']}, {s['95% hi']}] (must exclude 0)  =>  {'FAILS: closed' if dead else 'SURVIVES: goes to a live shadow'}")
    open(os.path.join(t1.OUT, "test2.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
