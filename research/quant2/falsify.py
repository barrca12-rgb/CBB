"""Cheap falsification tests (PLAN.md), 2014-2019 only.

    python -m research.quant2.falsify       # -> out/falsify.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.quant2.common import OUT, VAR_FEATS, frame


def main() -> None:
    w = frame()
    d = w[w["season"].between(2014, 2019) & ~w["swapped"]].dropna(subset=["home_spread", "total"]).copy()
    L = []
    # C1: does a pre-game variance model predict |result - close| out of sample (fit 2014-17, test 2018-19)?
    d["r_m"] = (d["margin"] + d["home_spread"]).abs()
    d["r_t"] = (d["points"] - d["total"]).abs()
    tr, te = d[d["season"] <= 2017], d[d["season"] >= 2018]
    L.append("C1 variance model, fit 2014-17, test 2018-19:")
    for mk, y in (("spread", "r_m"), ("total", "r_t")):
        X = np.column_stack([np.ones(len(tr)), tr[VAR_FEATS].to_numpy(float)])
        b, *_ = np.linalg.lstsq(X, tr[y].to_numpy(float), rcond=None)
        s = np.column_stack([np.ones(len(te)), te[VAR_FEATS].to_numpy(float)]) @ b
        q = np.quantile(s, [0.1, 0.9])
        c = np.corrcoef(s, te[y])[0, 1]
        L.append(f"  {mk}: corr(sigma_hat, |result - close|) {c:.3f}; P90/P10 of sigma_hat {q[1] / q[0]:.3f}; "
                 f"coefs " + ", ".join(f"{k} {v:+.3f}" for k, v in zip(VAR_FEATS, b[1:])) +
                 f" -> {'PASS' if c >= 0.03 and q[1] / q[0] >= 1.10 else 'STOP'}")
    # C2: are v1 residuals skewed (median far from mean) by decile of the prediction?
    L.append("\nC2 residual median vs mean by decile, 2014-19:")
    for mk, y, f in (("margin", "margin", "final_margin"), ("total", "points", "final_total")):
        r = d[y] - d[f]
        g = r.groupby(pd.qcut(d[f], 10, labels=False))
        t = pd.DataFrame({"mean": g.mean(), "median": g.median()})
        t["gap"] = t["median"] - t["mean"]
        ok = (t["gap"].abs().max() >= 0.20) or (abs(r.median()) >= 0.10)
        L.append(f"  {mk}: overall mean {r.mean():+.2f}, median {r.median():+.2f}; max |median-mean| by decile "
                 f"{t['gap'].abs().max():.2f} -> {'PASS' if ok else 'STOP'}\n" + t.round(2).to_string())
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "falsify.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
