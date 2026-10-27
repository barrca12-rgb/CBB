"""Check 3: home edge by season (LOG.md).

    python -m research.calibration.c3_home
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.calibration.common import OUT, TEST, base, boot_mean, mae
from research.originator.d_common import clv, frames, walk_forward


def main() -> None:
    w = base()
    train, pred = frames()
    nohome = walk_forward(train, pred.assign(venue=0.0, team_hca=0.0))[["game_id", "final_margin"]].rename(columns={"final_margin": "fm0"})
    w = w.merge(nohome, on="game_id", how="left")
    nn = w[~w["neutral"].astype(bool) & w["season"].between(2014, 2026)].dropna(subset=["res"])
    rows = []
    for s, g in nn.groupby("season"):
        m, lo, hi = boot_mean(g["res"], g["date"].astype(str))
        rows.append({"season": s, "games": len(g), "home residual": round(m, 3), "interval": f"[{lo:.3f}, {hi:.3f}]",
                     "realized home margin": round(g["margin"].mean(), 2), "predicted home margin": round(g["final_margin"].mean(), 2),
                     "stage-2 home terms (venue + team_hca)": round((g["final_margin"] - g["fm0"]).mean(), 2),
                     "outside +-0.3": abs(m) > 0.3})
    t = pd.DataFrame(rows)
    killed = not t["outside +-0.3"].any()
    res = {"killed (no season outside +-0.3)": killed}
    if not killed:
        # in-season home term: from each season's 301st non-neutral game, add the mean residual of its earlier ones
        w = w.sort_values(["date", "game_id"]).copy()
        w["adj"] = 0.0
        for s, g in w[~w["neutral"].astype(bool)].groupby("season"):
            r = g["res"].fillna(0.0)
            # games the same day aren't known yet: use residuals of earlier dates only
            day = g.groupby("date")["res"].agg(["sum", "count"]).cumsum().shift().fillna(0)
            mean_prev = (day["sum"] / day["count"].replace(0, np.nan)).where(day["count"] >= 300, 0.0).fillna(0.0)
            w.loc[g.index, "adj"] = g["date"].map(mean_prev).to_numpy()
        w["fm_adj"] = w["final_margin"] + w["adj"]
        t_ = w[w["season"].isin(TEST)]
        res["margin MAE 2020-26 benchmark / with in-season home term"] = (round(mae(t_["margin"] - t_["final_margin"]), 4), round(mae(t_["margin"] - t_["fm_adj"]), 4))
        a = w.assign(final_margin=w["fm_adj"])
        for era, ss in (("2014-17", range(2014, 2018)), ("2024-26", range(2024, 2027))):
            res[f"spread CLV {era} benchmark / with term"] = (round(clv(w, ss)["spread CLV"], 3), round(clv(a, ss)["spread CLV"], 3))
        res["mean |adjustment| applied 2020-26 (pts)"] = round(t_.loc[~t_["neutral"].astype(bool), "adj"].abs().mean(), 3)
    t.to_csv(os.path.join(OUT, "c3_result.csv"), index=False)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    for k, v in res.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
