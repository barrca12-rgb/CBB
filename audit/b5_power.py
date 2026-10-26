"""Audit follow-up, item 7: power of the forward test, independent and dependence-aware.

Independent: SE of a win rate at n decided plays = sqrt(p(1-p)/n). Dependence-aware: the design effect (variance of
the date-clustered bootstrap / binomial variance) measured on the historical opener cohorts, applied to n. Also the
group-sequential boundary for the predeclared interim read (Lan-DeMets O'Brien-Fleming spending).

    python -m audit.b5_power
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from audit.common import bets, frame

RNG = np.random.default_rng(11)
Z = lambda p: float(pd.Series([p]).pipe(lambda s: s))   # placeholder (not used)


def deff(b: pd.DataFrame, n_boot: int = 3000) -> float:
    d = b[b["res"] != 0].assign(w=lambda x: (x["res"] > 0).astype(int))
    g = d.groupby("date")["w"].agg(["sum", "count"]).to_numpy()
    idx = RNG.integers(0, len(g), size=(n_boot, len(g)))
    s = g[idx].sum(axis=1)
    var_c = np.var(s[:, 0] / s[:, 1])
    p = d["w"].mean()
    return var_c / (p * (1 - p) / len(d))


def phi_inv(q: float) -> float:
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    rows = []
    for tag in ("base", "safe_lag1"):
        w = frame(tag=tag)
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            for ss in ((2015, 2017), (2024, 2026)):
                b = bets(w, mk, "open", thr, ss)
                rows.append({"model": tag, "cohort": f"{mk} {ss[0]}-{ss[1]}", "plays per date": round(len(b) / b["date"].nunique(), 1),
                             "design effect": round(deff(b), 2)})
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    de = float(t["design effect"].median())
    be = 0.524
    print(f"\nmedian design effect {de:.2f} (used below)")
    for n in (300, 600, 1000, 1600):
        se = math.sqrt(be * (1 - be) / n) * 100
        sed = se * math.sqrt(de)
        line = f"n={n}: SE independent {se:.2f} pts, dependence-aware {sed:.2f} pts | z vs 52.4% for true 54/55/57%: "
        line += ", ".join(f"{(p - 52.4) / se:.2f}/{(p - 52.4) / sed:.2f}" for p in (54, 55, 57))
        print(line)
    # O'Brien-Fleming-type spending (Lan-DeMets), two looks, one-sided alpha per market
    for alpha in (0.025, 0.0125):
        for t_frac in (0.3, 0.375, 0.5):
            a1 = 2 - 2 * 0.5 * (1 + math.erf(phi_inv(1 - alpha / 2) / math.sqrt(t_frac) / math.sqrt(2)))
            z1 = phi_inv(1 - a1)
            print(f"one-sided alpha {alpha}: interim at information fraction {t_frac}: spend {a1:.5f}, boundary z >= {z1:.2f}")
