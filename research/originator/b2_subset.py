"""Part B subset pass: games with a rotation value change of 2+ points for either team (LOG.md, pre-registered).

    python -m research.originator.b2_subset
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb.evaluate import swapped
from research.originator.b_rotation import cluster_ols
from research.originator.d_common import OUT, ROOT, oriented_openers


def main() -> None:
    adj = pd.read_csv(os.path.join(OUT, "b_adjustments.csv.gz")).drop(columns="season")
    adj["v"] = adj["adj_off"] + adj["adj_def"]
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["final_margin"])
    w = w.merge(adj[["game_id", "team_id", "v"]].rename(columns={"team_id": "home_id", "v": "hv"}), on=["game_id", "home_id"]) \
         .merge(adj[["game_id", "team_id", "v"]].rename(columns={"team_id": "away_id", "v": "av"}), on=["game_id", "away_id"])
    w["adj"] = w["hv"] - w["av"]
    w["res"] = (w["home_pts"] - w["away_pts"]) - w["final_margin"]
    w["sub"] = (w["hv"].abs() >= 2) | (w["av"].abs() >= 2)
    s = w[w["sub"]]
    per = w.groupby("season").agg(games=("sub", "size"), subset=("sub", "sum"))
    rows = []
    for era, ss in (("fit 2014-19", range(2014, 2020)), ("test 2020-26", range(2020, 2027))):
        x = s[s["season"].isin(list(ss))]
        b, se = cluster_ols(x[["adj"]].to_numpy(float), x["res"].to_numpy(float), x["date"].to_numpy())
        signed = (x["res"] * np.sign(x["adj"])).mean()
        rows.append({"era": era, "subset games": len(x), "games per season": len(x) / len(ss),
                     "mean |adjustment| (pts)": x["adj"].abs().mean(),
                     "mean residual in the adjustment's direction (pts)": signed,
                     "coef": b[1], "95% CI": f"[{b[1] - 1.96 * se[1]:.2f}, {b[1] + 1.96 * se[1]:.2f}]",
                     "0.42 x mean |adj|": 0.42 * x["adj"].abs().mean()})
    t = pd.DataFrame(rows)
    # opener CLV of the frozen rule's spread plays in the subset, by whether the play is on the adjustment's side
    o = oriented_openers(w)
    o = o[~swapped(o.assign(pred_margin=o["final_margin"]))].dropna(subset=["open_home_spread", "home_spread"])
    e = o["final_margin"] + o["open_home_spread"]
    p = o[e.abs() >= 2.5].copy()
    side = np.sign(e[e.abs() >= 2.5])
    p["lv"] = np.where(side > 0, p["open_home_spread"] - p["home_spread"], p["home_spread"] - p["open_home_spread"])
    p["with_adj"] = np.sign(p["adj"]) == side
    cl = []
    for lab, q in (("all spread plays", p), ("subset", p[p["sub"]]), ("subset, play on the adjustment's side", p[p["sub"] & p["with_adj"]]),
                   ("subset, play against the adjustment", p[p["sub"] & ~p["with_adj"]])):
        b, se = cluster_ols(np.zeros((len(q), 0)), q["lv"].to_numpy(float), q["date"].to_numpy()) if len(q) > 1 else ([np.nan], [np.nan])
        cl.append({"plays": lab, "n": len(q), "opener CLV (pts)": b[0], "95% CI": f"[{b[0] - 1.96 * se[0]:.2f}, {b[0] + 1.96 * se[0]:.2f}]"})
    c = pd.DataFrame(cl)
    t.to_csv(os.path.join(OUT, "b2_subset.csv"), index=False)
    c.to_csv(os.path.join(OUT, "b2_subset_clv.csv"), index=False)
    pd.set_option("display.width", 220)
    print(per.T.to_string())
    print(t.round(3).to_string(index=False))
    print(c.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
