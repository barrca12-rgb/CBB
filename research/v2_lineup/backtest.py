"""Lineup v2 backtest: v1 vs v2 spread plays at the opener (PLAN.md).

    python -m research.v2_lineup.backtest
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb.evaluate import swapped
from research.edges.common import record
from research.originator.d_common import oriented_openers

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")


def frame() -> pd.DataFrame:
    adj = pd.read_csv(os.path.join(ROOT, "research", "originator", "out", "b_adjustments.csv.gz")).drop(columns="season")
    adj["v"] = adj["adj_off"] + adj["adj_def"]
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["final_margin"])
    a = adj[["game_id", "team_id", "v"]]
    w = w.merge(a.rename(columns={"team_id": "home_id", "v": "hv"}), on=["game_id", "home_id"], how="left") \
         .merge(a.rename(columns={"team_id": "away_id", "v": "av"}), on=["game_id", "away_id"], how="left")
    w["adj"] = (w["hv"].fillna(0) - w["av"].fillna(0))
    w["res"] = (w["home_pts"] - w["away_pts"]) - w["final_margin"]
    # walk-forward beta: fit on seasons before each season
    w["beta"] = np.nan
    for s in range(2015, 2027):
        tr = w[w["season"] < s]
        x, y = tr["adj"].to_numpy(float), tr["res"].to_numpy(float)
        b = np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), y, rcond=None)[0][1]
        w.loc[w["season"] == s, "beta"] = b
    w["v2_margin"] = w["final_margin"] + w["beta"] * w["adj"]
    return w[w["season"] >= 2015]


def plays(w: pd.DataFrame, col: str) -> pd.DataFrame:
    d = w.dropna(subset=["open_home_spread", "home_spread"])
    e = d[col] + d["open_home_spread"]
    p = d[e.abs() >= 2.5].copy()
    e = e[e.abs() >= 2.5]
    p["side"] = np.where(e > 0, "home", "away")
    line = np.where(p["side"] == "home", p["open_home_spread"], -p["open_home_spread"])
    m = np.where(p["side"] == "home", p["home_pts"] - p["away_pts"], p["away_pts"] - p["home_pts"]) + line
    p["res"] = np.where(m > 0, "W", np.where(m < 0, "L", "P"))
    p["u"] = np.where(p["res"] == "W", 100 / 110, np.where(p["res"] == "L", -1.0, 0.0))
    p["lv"] = np.where(p["side"] == "home", p["open_home_spread"] - p["home_spread"], p["home_spread"] - p["open_home_spread"])
    p["key"] = p["game_id"].astype(str) + "|" + p["side"]
    return p


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = oriented_openers(frame())
    w = w[~swapped(w.assign(pred_margin=w["final_margin"]))]
    w = w[w["season"].isin([2015, 2016, 2017, 2024, 2025, 2026])]
    w["split"] = np.where(w["season"] >= 2025, "holdout 2025-26", "development 2015-17, 2024")
    p1, p2 = plays(w, "final_margin"), plays(w, "v2_margin")
    k1, k2 = set(p1["key"]), set(p2["key"])
    sets = {"v1 (all)": p1, "v2 (all)": p2, "both": p1[p1["key"].isin(k2)], "v1 only": p1[~p1["key"].isin(k2)],
            "v2 only": p2[~p2["key"].isin(k1)]}
    rows = []
    for name, p in sets.items():
        for sp, g in p.groupby("split"):
            r = record(g["res"], g["u"], g["date"])
            rows.append({"set": name, "split": sp, **r, "opener CLV (pts)": g["lv"].mean()})
    t = pd.DataFrame(rows)
    betas = w.groupby("season")["beta"].first()
    full = np.linalg.lstsq(np.column_stack([np.ones(len(w)), w["adj"]]), w["res"], rcond=None)[0][1]
    allw = frame()
    beta_live = np.linalg.lstsq(np.column_stack([np.ones(len(allw)), allw["adj"]]), allw["res"].to_numpy(float), rcond=None)[0][1]
    t.to_csv(os.path.join(OUT, "backtest.csv"), index=False)
    pd.set_option("display.width", 200)
    print(t.round(3).to_string(index=False))
    print("walk-forward beta by season:", betas.round(3).to_dict())
    print(f"beta for the live shadow (all games 2015-2026, frozen residual on adjustment): {beta_live:.4f}")
    print("margin MAE 2020-26 v1 vs v2:", round(float((allw[allw.season >= 2020]["res"]).abs().mean()), 4),
          round(float((allw[allw.season >= 2020]["home_pts"] - allw[allw.season >= 2020]["away_pts"] - allw[allw.season >= 2020]["v2_margin"]).abs().mean()), 4))


if __name__ == "__main__":
    main()
