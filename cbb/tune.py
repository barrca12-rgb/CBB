"""Tuning on the training seasons only (2014-2019); 2020-2026 stay untouched for checking.

    OMP_NUM_THREADS=1 python -m cbb.tune grid   # rating settings: decay half-life x preseason prior strength
                                               # (one thread per worker; otherwise the 4 workers fight)
"""
from __future__ import annotations

import itertools
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import backtest, ratings

TRAIN = list(range(2014, 2020))
TEST = list(range(2020, 2027))


def _run(args):
    season, kw = args
    b = backtest.season(season, ratings.RatingConfig(fit_factors=False, **kw))
    m = b["home_pts"] - b["away_pts"]
    p = b["home_pts"] + b["away_pts"]
    return {**kw, "season": season, "n": len(b),
            "margin_ae": (b["pred_margin"] - m).abs().sum(), "total_ae": (b["pred_total"] - p).abs().sum()}


def grid(seasons=TRAIN, half_lives=(30, 60, 120), priors=(3, 6, 12)):
    jobs = [(s, {"half_life": h, "prior_games": p, "pace_prior_games": p})
            for s, h, p in itertools.product(seasons, half_lives, priors)]
    with Pool(4) as pool:
        r = pd.DataFrame(pool.map(_run, jobs))
    g = r.groupby(["half_life", "prior_games"])[["n", "margin_ae", "total_ae"]].sum()
    g["margin_mae"] = g["margin_ae"] / g["n"]
    g["total_mae"] = g["total_ae"] / g["n"]
    return g[["margin_mae", "total_mae"]].sort_values("margin_mae")


if __name__ == "__main__":
    if sys.argv[1:] == ["grid"]:
        print(grid().round(3).to_string())
