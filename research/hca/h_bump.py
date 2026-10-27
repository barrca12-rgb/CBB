"""Home-court weight test (pre-registered in LOG.md).

    python -m research.hca.h_bump
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.originator.d_common import clv, frames, mae, oriented_openers, walk_forward

OUT = os.path.join(os.path.dirname(__file__), "out")
BUMPS = [0.0, 0.5, 1.0, 1.5]


def picks(w: pd.DataFrame, seasons) -> pd.DataFrame:
    d = w[w["season"].isin(list(seasons))]
    d = d[~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))].dropna(subset=["open_home_spread"])
    e = d["final_margin"] + d["open_home_spread"]
    s = d[e.abs() >= 2.5].assign(home_pick=e[e.abs() >= 2.5] > 0)
    s["m"] = (s["home_pts"] - s["away_pts"] + s["open_home_spread"]) * np.where(s["home_pick"], 1, -1)
    return s[s["m"] != 0]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    base = oriented_openers(walk_forward(train, pred))
    nn = base[~base["neutral"].astype(bool)]
    diag = nn.assign(model_res=(nn["home_pts"] - nn["away_pts"]) - nn["final_margin"],
                     market_res=(nn["home_pts"] - nn["away_pts"]) + nn["home_spread"]).groupby("season").agg(
        games=("game_id", "size"), model_home_resid=("model_res", "mean"), market_home_resid=("market_res", "mean"))
    rows = []
    for b in BUMPS:
        w = base.copy()
        w.loc[~w["neutral"].astype(bool), "final_margin"] += b
        r = {"home bump": b, "margin MAE 2020-26": round(mae(w, range(2020, 2027))["margin MAE"], 4),
             "spread CLV dev": round(clv(w, range(2014, 2018))["spread CLV"], 3),
             "spread CLV conf": round(clv(w, range(2024, 2027))["spread CLV"], 3)}
        for tag, ss in (("dev", [2014, 2015, 2016, 2017, 2024]), ("holdout", [2025, 2026])):
            p = picks(w, ss)
            r[f"win% {tag}"] = round(100 * (p["m"] > 0).mean(), 2)
            r[f"n {tag}"] = len(p)
            r[f"home picks win% {tag}"] = f"{100 * (p.loc[p['home_pick'], 'm'] > 0).mean():.1f} ({p['home_pick'].sum()})"
            r[f"away picks win% {tag}"] = f"{100 * (p.loc[~p['home_pick'], 'm'] > 0).mean():.1f} ({(~p['home_pick']).sum()})"
        rows.append(r)
    t = pd.DataFrame(rows).set_index("home bump")
    f = t.loc[0.0]
    t["verdict"] = ["" if b == 0 else ("PASS" if (t.loc[b, "spread CLV dev"] - f["spread CLV dev"] >= 0.05 and
                                                  t.loc[b, "spread CLV conf"] - f["spread CLV conf"] >= 0.05 and
                                                  t.loc[b, "win% holdout"] >= f["win% holdout"]) else "KILL") for b in t.index]
    diag.to_csv(os.path.join(OUT, "h_diag.csv"))
    t.to_csv(os.path.join(OUT, "h_result.csv"))
    pd.set_option("display.width", 250)
    print(diag.round(2).to_string())
    print(t.T.to_string())


if __name__ == "__main__":
    main()
