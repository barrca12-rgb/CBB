"""Follow-up: are the 5+ point spread edges real or bad openers? (pre-registered in LOG.md)

    python -m research.edges.e5_big_edges
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import lines_hist
from research.edges.common import HOLDOUT, OUT, frame, open_meta, opener_plays, record

SEASONS = [2014, 2015, 2016, 2017, 2024, 2025, 2026]


def opener_status() -> pd.DataFrame:
    """Per game: whether the oriented opener was corrected (a book's opener disagreed with its moneyline), or is
    uncheckable residue only, and how many books' openers stood behind it."""
    out = []
    for s in SEASONS:
        l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{s}.csv"))
        m = open_meta(s)
        f = lines_hist.consensus(l, "flip", m).set_index("game_id")["open_home_spread"]
        d = lines_hist.consensus(l, "drop", m).set_index("game_id")["open_home_spread"]
        r = lines_hist.consensus(l, "drop_residue", m).set_index("game_id")["open_home_spread"]
        books = l[~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})].groupby("game_id")["open_home_spread"].count()
        st = pd.DataFrame({"flip": f, "drop": d, "drop_residue": r})
        st["corrected"] = st["flip"].notna() & ((st["drop"].isna()) | (st["drop"] != st["flip"]))
        st["residue only"] = st["flip"].notna() & st["drop_residue"].isna()
        st["opener books"] = books.reindex(st.index).fillna(0).astype(int)
        st["opener source"] = "Opening pseudo-book" if s <= 2017 else ("multi-book median" if s == 2024 else "single book")
        out.append(st.reset_index())
    return pd.concat(out, ignore_index=True)


def main() -> None:
    p = opener_plays(frame())
    p = p[(p["market"] == "spread") & p["season"].isin(SEASONS)].merge(opener_status(), on="game_id", how="left")
    p["band"] = pd.cut(p["edge"], [2.5, 3.5, 5, 7, 99], right=False, labels=["2.5-3.5", "3.5-5", "5-7", "7+"]).astype(str)
    p["big"] = p["edge"] >= 5
    p["move"] = (p["home_spread"] - p["open_home_spread"]).abs()          # opener -> consensus close, points
    # same side graded at the close, and the model's edge against the close
    cl = np.where(p["side"] == "home", p["home_spread"], -p["home_spread"])
    mg = np.where(p["side"] == "home", p["home_pts"] - p["away_pts"], p["away_pts"] - p["home_pts"]) + cl
    p["res_close"] = np.where(np.isnan(cl), None, np.where(mg > 0, "W", np.where(mg < 0, "L", "P")))
    p["u_close"] = np.where(p["res_close"] == "W", 100 / 110, np.where(p["res_close"] == "L", -1.0, 0.0))
    p["edge_close"] = np.where(p["side"] == "home", p["final_margin"] + p["home_spread"], -(p["final_margin"] + p["home_spread"]))
    p["month"] = pd.to_datetime(p["date"]).dt.month
    rows = []

    def add(label, d):
        for sp, g in d.groupby("split"):
            rows.append({"check": label, "split": sp, **record(g["res"], g["u"], g["date"])})

    big = p[p["big"]]
    for b, g in p.groupby("band"):
        add(f"edge band {b}", g)
    add("5+: all", big)
    add("5+: excluding uncheckable (residue-only) openers", big[~big["residue only"].fillna(False).astype(bool)])
    add("5+: excluding opener-to-close moves of 5+", big[big["move"] < 5])
    add("5+: excluding November", big[big["month"] != 11])
    add("5+: excluding all three", big[~big["residue only"].fillna(False).astype(bool) & (big["move"] < 5) & (big["month"] != 11)])
    c = big.dropna(subset=["home_spread"])
    for sp, g in c.groupby("split"):
        rows.append({"check": "5+: same plays graded at the CLOSE", "split": sp, **record(g["res_close"], g["u_close"], g["date"])})
    c2 = c[c["edge_close"] >= 5]
    for sp, g in c2.groupby("split"):
        rows.append({"check": "5+: model still 5+ against the close, graded at the close", "split": sp,
                     **record(g["res_close"], g["u_close"], g["date"])})
    for s, g in big.groupby("season"):
        rows.append({"check": f"5+: season {s}", "split": "holdout" if s in HOLDOUT else "development", **record(g["res"], g["u"], g["date"])})
    t = pd.DataFrame(rows)
    # profile of the 5+ plays vs the rest
    prof = p.groupby("big").agg(plays=("edge", "size"), corrected=("corrected", "mean"), residue_only=("residue only", "mean"),
                                move_median=("move", "median"), move_5plus=("move", lambda x: float((x >= 5).mean())),
                                november=("month", lambda x: float((x == 11).mean())),
                                abs_open_spread_median=("open_home_spread", lambda x: float(x.abs().median())))
    src = p.groupby(["big", "opener source"]).size().unstack(fill_value=0)
    # calibration: development logistic fit of win on edge, checked on the holdout
    dec = p[p["res"] != "P"]
    dv = dec[dec["split"] == "development"]
    X = np.column_stack([np.ones(len(dv)), dv["edge"].to_numpy(float)])
    y = (dv["res"] == "W").to_numpy(float)
    b = np.zeros(2)
    for _ in range(50):
        pr = 1 / (1 + np.exp(-X @ b))
        b = b + np.linalg.solve(X.T @ (X * (pr * (1 - pr))[:, None]), X.T @ (y - pr))
    cal = []
    for bd, g in dec.groupby("band"):
        e = g["edge"].to_numpy(float)
        for sp, gg in g.groupby("split"):
            ee = gg["edge"].to_numpy(float)
            cal.append({"band": bd, "split": sp, "plays": len(gg), "actual win%": 100 * (gg["res"] == "W").mean(),
                        "live table win%": 100 * np.mean(np.minimum(np.maximum(0.5 + 0.0255 * ee, 0.5), 0.58)),
                        "dev logistic fit win%": 100 * np.mean(1 / (1 + np.exp(-(b[0] + b[1] * ee))))})
    cal = pd.DataFrame(cal)
    for name, df in (("e5_checks", t), ("e5_calibration", cal)):
        df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string(index=False))
    print("\nprofile (big = edge 5+):\n", prof.round(3).to_string())
    print("\nopener source:\n", src.to_string())
    print(f"\ndevelopment logistic: win prob = 1/(1+exp(-({b[0]:.3f} + {b[1]:.4f} x edge)))")
    print(cal.round(1).to_string(index=False))
    print("\nlargest 5+ edges (top 15 by edge):")
    print(big.sort_values("edge", ascending=False).head(15)[["season", "date", "home_id", "away_id", "open_home_spread", "home_spread",
                                                              "final_margin", "edge", "side", "res", "corrected", "residue only", "opener source"]].to_string(index=False))


if __name__ == "__main__":
    main()
