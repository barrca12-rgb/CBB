"""Idea 1: moneylines at real prices (specification in LOG.md, fixed before running).

    python -m research.edges.e1_moneyline
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from cbb import lines_hist
from research.edges.common import HOLDOUT, OUT, open_meta, record

SIGMA = 11.0                  # run_day: p_home_win = Phi(margin / 11)
THRESHOLDS = [0.05, 0.02, 0.10]   # primary first


def payout(o):
    o = np.asarray(o, float)
    return np.where(o > 0, o / 100, 100 / -np.where(o < 0, o, -1))


def implied(o):
    return np.where(o < 0, -o / (100 - np.minimum(o, 0)), 100 / (np.maximum(o, 0) + 100))


def to_american(p: pd.Series) -> pd.Series:
    p = p.astype(float)
    return pd.Series(np.where(p >= 0.5, -100 * p / (1 - p), 100 * (1 - p) / p), index=p.index)


def clean(x: pd.DataFrame) -> pd.DataFrame:
    x = x.dropna(subset=["hml", "aml"])
    x = x[(x["hml"] != 0) & (x["aml"] != 0) & (x["hml"].abs() >= 100) & (x["aml"].abs() >= 100)]
    s = implied(x["hml"].to_numpy(float)) + implied(x["aml"].to_numpy(float))
    return x[(s >= 1.0) & (s <= 1.12)]


def prices(season: int, era: str) -> pd.DataFrame:
    if era == "close":
        l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{season}.csv"))
        l = l[~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"}) & ~l["book"].fillna("").str.contains("live", case=False)]
        x = l.rename(columns={"home_ml": "hml", "away_ml": "aml"})[["game_id", "book", "hml", "aml"]]
    else:
        m = open_meta(season)
        if m is None:
            return pd.DataFrame(columns=["game_id", "book", "hml", "aml"])
        x = m.rename(columns={"open_home_ml": "hml", "open_away_ml": "aml"})[["game_id", "book", "hml", "aml"]]
    return clean(x)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = pd.read_pickle(os.path.join(os.path.dirname(__file__), "..", "..", "audit", "out", "wf_live_approx.pkl"))
    w = w[["game_id", "season", "date", "home_pts", "away_pts", "final_margin"]].dropna()
    w["p_home"] = [0.5 * (1 + math.erf(m / SIGMA / math.sqrt(2))) for m in w["final_margin"]]
    w["home_won"] = (w["home_pts"] > w["away_pts"]).astype(float)
    w = w[w["home_pts"] != w["away_pts"]]
    rows, cal = [], []
    allbets = []
    for era, seasons in (("close", range(2014, 2027)), ("open", (2024, 2025, 2026))):
        px = pd.concat([prices(s, era) for s in seasons], ignore_index=True)
        g = px.groupby("game_id")
        # median price taken in implied-probability space (a median of American odds is wrong across +-100)
        px = px.assign(ih=implied(px["hml"].to_numpy(float)), ia=implied(px["aml"].to_numpy(float)))
        g = px.groupby("game_id")
        agg = pd.DataFrame({"best_h": g["hml"].max(), "best_a": g["aml"].max(),   # highest American = best price
                            "med_h": to_american(g["ih"].median()), "med_a": to_american(g["ia"].median()),
                            "books": g["book"].nunique()})
        # de-vigged market probability from the median pair
        ih, ia = implied(agg["med_h"].to_numpy(float)), implied(agg["med_a"].to_numpy(float))
        agg["p_mkt"] = ih / (ih + ia)
        d = w.merge(agg.reset_index(), on="game_id")
        for pricing in ("best", "median"):
            ph, pa = d[f"{'best' if pricing == 'best' else 'med'}_h"].to_numpy(float), d[f"{'best' if pricing == 'best' else 'med'}_a"].to_numpy(float)
            ev_h = d["p_home"] * payout(ph) - (1 - d["p_home"])
            ev_a = (1 - d["p_home"]) * payout(pa) - d["p_home"]
            home = ev_h >= ev_a
            ev = np.where(home, ev_h, ev_a)
            price = np.where(home, ph, pa)
            won = np.where(home, d["home_won"], 1 - d["home_won"])
            b = d.assign(side=np.where(home, "home", "away"), ev=ev, price=price,
                         res=np.where(won == 1, "W", "L"), u=np.where(won == 1, payout(price), -1.0),
                         split=np.where(d["season"].isin(HOLDOUT), "holdout", "development"),
                         dog=np.where(price > 0, "underdog", "favourite"))
            for thr in THRESHOLDS:
                q = b[b["ev"] >= thr]
                for split, s_ in q.groupby("split"):
                    rows.append({"era": era, "pricing": pricing, "EV min": thr, "split": split,
                                 "primary": thr == 0.05 and pricing == "best", **record(s_["res"], s_["u"], s_["date"]),
                                 "avg price": float(s_["price"].median())})
                    if thr == 0.05 and pricing == "best":
                        for dg, s2 in s_.groupby("dog"):
                            rows.append({"era": era, "pricing": pricing, "EV min": thr, "split": f"{split}: {dg}s",
                                         "primary": False, **record(s2["res"], s2["u"], s2["date"]),
                                         "avg price": float(s2["price"].median())})
                if thr == 0.05 and pricing == "best":
                    allbets.append(q.assign(era=era))
        # calibration on development games
        dv = d[~d["season"].isin(HOLDOUT)]
        y = dv["home_won"].to_numpy()
        ll = lambda p: float(-np.mean(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1))))
        lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
        X = np.column_stack([np.ones(len(dv)), lg(dv["p_home"].to_numpy()), lg(dv["p_mkt"].to_numpy())])
        bcoef = np.zeros(3)
        for _ in range(50):
            p = 1 / (1 + np.exp(-X @ bcoef))
            H = X.T @ (X * (p * (1 - p))[:, None])
            bcoef = bcoef + np.linalg.solve(H, X.T @ (y - p))
        p = 1 / (1 + np.exp(-X @ bcoef))
        se = np.sqrt(np.diag(np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))))
        cal.append({"era": era, "games": len(dv), "log loss model": ll(dv["p_home"].to_numpy()),
                    "log loss market": ll(dv["p_mkt"].to_numpy()),
                    "weight on model (z)": f"{bcoef[1]:.3f} ({bcoef[1] / se[1]:.1f})",
                    "weight on market (z)": f"{bcoef[2]:.3f} ({bcoef[2] / se[2]:.1f})"})
        print(era, "done", flush=True)
    t = pd.DataFrame(rows)
    c = pd.DataFrame(cal)
    t.to_csv(os.path.join(OUT, "e1_results.csv"), index=False)
    c.to_csv(os.path.join(OUT, "e1_calibration.csv"), index=False)
    pd.concat(allbets).to_csv(os.path.join(OUT, "e1_bets.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string(index=False))
    print(c.to_string(index=False))


if __name__ == "__main__":
    main()
