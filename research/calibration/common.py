"""Shared pieces for the calibration checks (LOG.md): the frozen live-like benchmark and clustered statistics."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.originator.d_common import frames, oriented_openers, walk_forward

OUT = os.path.join(os.path.dirname(__file__), "out")
TEST = list(range(2020, 2027))


def base() -> pd.DataFrame:
    """Benchmark predictions with oriented openers and a swapped-record flag (cached)."""
    path = os.path.join(OUT, "base.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    w = oriented_openers(walk_forward(train, pred))
    w["swapped"] = evaluate.swapped(w.assign(pred_margin=w["final_margin"]))
    w["margin"] = w["home_pts"] - w["away_pts"]
    w["points"] = w["home_pts"] + w["away_pts"]
    w["res"] = w["margin"] - w["final_margin"]
    w.to_pickle(path)
    return w


def cluster_ols(X, y, groups):
    """OLS with an intercept; returns (coefs, date-clustered standard errors)."""
    X = np.column_stack([np.ones(len(X)), np.asarray(X, float).reshape(len(y), -1)])
    y = np.asarray(y, float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    br = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(np.asarray(groups)).sum().to_numpy()
    return b, np.sqrt(np.diag(br @ (s.T @ s) @ br))


def boot_ratio(num, den, groups, n=2000, seed=20261027):
    """mean(num)/mean(den) with a bootstrap interval over date clusters."""
    num, den, groups = np.asarray(num, float), np.asarray(den, float), np.asarray(groups)
    u, inv = np.unique(groups, return_inverse=True)
    sn, sd, c = np.bincount(inv, num), np.bincount(inv, den), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sn[i].sum(1) / sd[i].sum(1)
    return float(num.sum() / den.sum()), float(np.quantile(r, .025)), float(np.quantile(r, .975))


def boot_mean(v, groups, n=2000, seed=20261027):
    v = np.asarray(v, float)
    return boot_ratio(v, np.ones(len(v)), groups, n, seed)


def mae(x) -> float:
    return float(np.abs(np.asarray(x, float)).mean())
