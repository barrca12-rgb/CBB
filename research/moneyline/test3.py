"""Moneyline test 3 (PLAN.md): the model's win probability against the market. Research only.

    python -m research.moneyline.test3      # -> research/moneyline/out/test3.txt, test3_bets.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import norm

from research.band_b.replay import plays
from research.moneyline import test1 as t1
from research.persistent_disagreement.common import baseline

DEV, CONFIRM = range(2014, 2018), range(2024, 2027)
L: list[str] = []
t1.L = L


def main() -> None:
    os.makedirs(t1.OUT, exist_ok=True)
    live = baseline()
    live = live[~live["swapped"]].copy()
    live["home_win"] = (live["home_pts"] > live["away_pts"]).astype(int)
    q = t1.load(list(DEV) + list(CONFIRM))
    # sigma_m on dev games only: P(home wins) = Phi(final_margin / sigma_m)
    dev = live[live["season"].isin(DEV)]
    m, y = dev["final_margin"].to_numpy(), dev["home_win"].to_numpy()
    nll = lambda s: -np.sum(y * np.log(np.clip(norm.cdf(m / s), 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - norm.cdf(m / s), 1e-9, 1)))
    sigma = float(minimize_scalar(nll, bounds=(5, 25), method="bounded").x)
    t1.say(f"\nModel win probability, fit on 2014-2017 ({len(dev):,} games), frozen: P(home wins) = Phi(model margin / {sigma:.3f})")
    live["p_home"] = norm.cdf(live["final_margin"] / sigma)
    conf = live[live["season"].isin(CONFIRM)].copy()
    conf["bin"] = pd.qcut(conf["p_home"], 10, duplicates="drop")
    t1.say("Calibration, confirm era 2024-2026 (home side, by decile):")
    t1.say(conf.groupby("bin", observed=True).agg(games=("p_home", "size"), predicted=("p_home", "mean"),
                                                 actual=("home_win", "mean")).round(3).to_string())
    # the best clean closing price per game and side across books
    best_px = []
    for side, col in (("home", "home_ml"), ("away", "away_ml")):
        b = q.assign(pay=t1.payout(q[col])).sort_values("pay", ascending=False).drop_duplicates("game_id")
        best_px.append(b[["game_id", "book", col]].rename(columns={col: "price"}).assign(side=side))
    px = pd.concat(best_px, ignore_index=True)
    g = live[["game_id", "date", "season", "p_home", "home_win", "home_spread"]].merge(px, on="game_id")
    g["p"] = np.where(g["side"] == "home", g["p_home"], 1 - g["p_home"])
    g["won"] = np.where(g["side"] == "home", g["home_win"], 1 - g["home_win"])
    g["ev"] = g["p"] * t1.payout(g["price"]) - (1 - g["p"])
    g["profit"] = np.where(g["won"] == 1, t1.payout(g["price"]), -1.0)
    sig = g[g["ev"] >= t1.EV_MIN]
    sig.to_csv(os.path.join(t1.OUT, "test3_bets.csv"), index=False)
    t1.say(f"\nGames with the model and a clean closing moneyline: {g['game_id'].nunique():,}; signals (EV >= +3% at the best price): {len(sig):,}")
    for era, ss in (("dev 2014-2017 (in-sample sigma)", DEV), ("CONFIRM 2024-2026", CONFIRM)):
        t1.say(f"\n== {era} ==  {t1.summary(sig[sig['season'].isin(ss)])}")
    cb = sig[sig["season"].isin(CONFIRM)].copy()
    cb["dog"] = np.where(cb["price"] > 0, "underdog", "favorite")
    cb["band"] = pd.cut(cb["price"], [-1e9, -300, -150, 149.5, 299.5, 1e9],
                        labels=["-300 or shorter", "-299 to -150", "-149 to +149", "+150 to +299", "+300 or longer"])
    cb["ev band"] = pd.cut(cb["ev"], [0.03, 0.05, 0.08, 0.15, 1e9], labels=["3-5%", "5-8%", "8-15%", "15%+"])
    for col in ("dog", "band", "ev band", "season"):
        rows = [{col: k, **t1.summary(v)} for k, v in cb.groupby(col, observed=True)]
        t1.say(f"\nConfirm era by {col}:")
        t1.say(pd.DataFrame(rows).to_string(index=False))
    # v1's underdog spread plays (opener, edge 2.5+): the moneyline on the same dog vs the spread
    sp = plays(live[live["season"].isin(CONFIRM)], "spread")
    sp = sp[sp["edge"] >= 2.5]
    dog_side = np.where(sp["side"] == "home", sp["open_home_spread"] > 0, sp["open_home_spread"] < 0)
    sp = sp[dog_side][["game_id", "side", "cover"]]
    both = sp.merge(g, on=["game_id", "side"])
    if len(both):
        dec = both[both["cover"] != 0]
        spread_roi = float(np.where(dec["cover"] > 0, 100 / 110, -1.0).mean())
        t1.say(f"\nv1 underdog spread plays, confirm era, with a clean moneyline on the same dog: {len(both):,} games")
        t1.say(f"  spread at the opener, -110 assumed: ROI {100 * spread_roi:+.2f}% (pushes out, {len(dec):,} decided)")
        t1.say(f"  moneyline on the same dog at the best closing price: {t1.summary(both)}")
        t1.say(f"  of these, moneyline EV >= +3% at the close: {int((both['ev'] >= t1.EV_MIN).sum())}")
    s = t1.summary(cb)
    dead = s["bets"] < 200 or s["ROI %"] < 1.0 or s["95% lo"] <= 0
    t1.say(f"\nKill rule (confirm): bets {s['bets']} (need 200+), ROI {s['ROI %']}% (need +1%+), "
           f"95% interval [{s['95% lo']}, {s['95% hi']}] (must exclude 0)  =>  {'FAILS: closed' if dead else 'SURVIVES: goes to a live shadow'}")
    open(os.path.join(t1.OUT, "test3.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
