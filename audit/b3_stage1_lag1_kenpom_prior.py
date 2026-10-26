"""Audit (follow-up, item 2): the conservative stage-1 rebuild (games before D-1, as audit/stage1_lag.py with LAG=1)
but with KenPom's preseason prior alone, i.e. Barttorvik removed from the prior. Writes
audit/out/backtest_lag1_kpprior_2013_2026.csv; the original audit outputs are not touched.

    python -m audit.b3_stage1_lag1_kenpom_prior
"""
from __future__ import annotations

import os
from multiprocessing import Pool

import pandas as pd

from cbb import backtest

backtest.preseason_prior = backtest.kenpom_prior   # this process (and its forked workers) only

import audit.stage1_lag as s1   # noqa: E402  (module-level LAG defaults to 1 when no argument is given)

OUT = os.path.join(os.path.dirname(__file__), "out", "backtest_lag1_kpprior_2013_2026.csv")

if __name__ == "__main__":
    assert s1.LAG == 1
    with Pool(4) as pool:
        b = pd.concat(pool.map(s1.season, range(2013, 2027)))
    b.to_csv(OUT, index=False)
    print("done", len(b))
