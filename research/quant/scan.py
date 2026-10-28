"""Step 2: where the frozen baseline misses predictably (research/quant/LOG.md). Development seasons 2014-2019 only.

For each pre-game quantity: mean residual vs the model (result - prediction) by bucket, and the slope of
(result - close) on the quantity with the model's own edge vs the close as a control (does the close already have it?).

    python -m research.quant.scan
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.quant.common import OUT, base_frames, fit_predict


def ols(X, y, g):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    br = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(np.asarray(g)).sum().to_numpy()
    return b, np.sqrt(np.diag(br @ (s.T @ s) @ br))


def main() -> None:
    train, pred = base_frames()
    w = fit_predict(train, pred)
    d = w[w["season"].between(2014, 2019) & ~w["swapped"]].copy()
    d["res_m"], d["res_t"] = d["margin"] - d["final_margin"], d["points"] - d["final_total"]
    d["absm"] = d["final_margin"].abs()
    d["gb"] = d["games_before"]
    feats = {"absm": [0, 2, 4, 6, 9, 13, 18, 25, 60], "final_margin": [-60, -15, -8, -3, 0, 3, 8, 15, 60],
             "final_total": [0, 125, 132, 138, 144, 150, 157, 250], "pred_poss": [0, 63, 66, 68, 70, 72, 75, 99],
             "gb": [-1, 2, 5, 9, 14, 20, 40], "month": [0, 1, 2, 3, 4, 10, 11, 12]}
    L = []
    for f, bins in feats.items():
        g = d.groupby(pd.cut(d[f], bins), observed=True)
        t = g.agg(n=("res_t", "size"), res_margin=("res_m", "mean"), res_total=("res_t", "mean"),
                  abs_res_margin=("res_m", lambda x: x.abs().mean()))
        L.append(f"--- {f}\n" + t.round(2).to_string())
    c = d.dropna(subset=["home_spread", "total"])
    rows = []
    for f in ["absm", "pred_poss", "final_total", "gb", "neutral", "conf_game", "miss_diff"]:
        x = c[f].astype(float).to_numpy()
        for mk, y, edge in (("margin", (c["margin"] + c["home_spread"]).to_numpy(), (c["final_margin"] + c["home_spread"]).to_numpy()),
                            ("total", (c["points"] - c["total"]).to_numpy(), (c["final_total"] - c["total"]).to_numpy())):
            b, se = ols(np.column_stack([x, edge]), y, c["date"])
            rows.append({"feature": f, "market": mk, "coef vs close": round(b[1], 4), "se": round(se[1], 4),
                         "t": round(b[1] / se[1], 1)})
    L.append("--- (result - close) ~ feature + model edge, 2014-19\n" + pd.DataFrame(rows).to_string(index=False))
    txt = "\n\n".join(L) + "\n"
    open(os.path.join(OUT, "scan_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
