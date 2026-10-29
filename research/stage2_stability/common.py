"""Shared pieces for the stage-2 stability study (PLAN.md). Research only; the live model is untouched.

Frames are the frozen live-like benchmark (research/quant/common.base_frames): training frame with referee crews as
recorded, prediction frame with crews 0 and KenPom from the day before. R0 differs from frozen v1 only in
season_avg_total, recomputed here from games on earlier dates (the frozen feature also counts earlier rows of the
same date).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.quant.common import base_frames, plays
from research.quant3.study import opening_week

OUT = os.path.join(os.path.dirname(__file__), "out")
TF, MF = projection.TOTAL_FEATURES, projection.MARGIN_FEATURES
TEST = list(range(2015, 2027))
PRIMARY = [2024, 2025, 2026]
GROUPS_T = {"level": ["pred_total", "pred_total_x_early", "kp_total", "kp_total_x_early", "bt_total", "season_avg_total"],
            "four factors": ["efg_sum", "tov_rate_sum", "orb_rate_sum", "ft_rate_sum"],
            "referees": ["ref_fouls", "ref_pts"], "other": ["rest_sum", "mkt_t", "altitude"]}
GROUPS_M = {"level": ["pred_margin", "pred_margin_x_early", "kp_margin", "kp_margin_x_early", "bt_margin", "mkt_m"],
            "four factors": ["efg_diff", "tov_rate_diff", "orb_rate_diff", "ft_rate_diff"],
            "venue/rest/injury": ["venue", "team_hca", "rest_diff", "b2b_diff", "miss_diff", "altitude"]}


def clean_season_avg(b: pd.DataFrame) -> pd.Series:
    """season_avg_total from games on earlier dates only; same rule otherwise (200 games, else last season's
    average, else the season's mean pred_total)."""
    pts = b["home_pts"] + b["away_pts"]
    d = pd.DataFrame({"season": b["season"], "date": pd.to_datetime(b["date"]), "pts": pts})
    day = d.groupby(["season", "date"])["pts"].agg(["sum", "count"]).sort_index()
    g = day.groupby(level=0)
    prior_sum, prior_n = g["sum"].cumsum() - day["sum"], g["count"].cumsum() - day["count"]
    avg = (prior_sum / prior_n.clip(lower=1)).where(prior_n >= 200)
    key = pd.MultiIndex.from_arrays([d["season"], d["date"]])
    out = pd.Series(avg.reindex(key).to_numpy(), index=b.index)
    prev = pts.groupby(b["season"]).mean()
    out = out.fillna(b["season"].map(prev.shift()))
    return out.fillna(b["pred_total"].groupby(b["season"]).transform("mean"))


def frames(clean: bool = True):
    """(train, pred); with clean=True season_avg_total is leak-free in both."""
    train, pred = base_frames()
    train, pred = train.copy(), pred.copy()
    if clean:
        train["season_avg_total"] = clean_season_avg(train)
        pred["season_avg_total"] = clean_season_avg(pred)
    return train, pred


def ridge(X, y, pen):
    """Ridge with an unpenalized intercept; pen is a scalar or a per-feature vector."""
    X1 = np.column_stack([np.ones(len(X)), X])
    p = np.concatenate([[0.0], np.broadcast_to(np.asarray(pen, float), (X.shape[1],))])
    return np.linalg.solve(X1.T @ X1 + np.diag(p), X1.T @ y)


def fit(tr: pd.DataFrame, feats, target: str, lam=1.0, standardize: bool = False, pen_vec=None):
    """Coefficients on the raw scale (intercept first). standardize: penalty applied to features scaled by the
    training SD (learned from `tr` only); pen_vec overrides lam per feature (standardized units)."""
    X, y = tr[feats].to_numpy(float), tr[target].to_numpy(float)
    if not standardize:
        return ridge(X, y, lam if pen_vec is None else pen_vec)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    c = ridge((X - mu) / sd, y, (lam if pen_vec is None else pen_vec) * len(X))
    beta = c[1:] / sd
    return np.concatenate([[c[0] - mu @ beta], beta])


def predict(c, d, feats):
    return c[0] + d[feats].to_numpy(float) @ c[1:]


def walk(train, pred, tf=None, mf=None, ow: bool = True, seasons=TEST, train_from: int = 2013, **kw):
    """Walk-forward: season s from coefficients fit on train_from..s-1. Returns pred rows of `seasons` with
    final_total / final_margin (live opening-week totals rule applied when ow)."""
    tf, mf = tf or TF, mf or MF
    out = pred[pred["season"].isin(seasons)].copy()
    for s in seasons:
        tr = train[(train["season"] < s) & (train["season"] >= train_from)]
        te = out["season"] == s
        out.loc[te, "final_total"] = predict(fit(tr, tf, "points", **kw), out[te], tf)
        out.loc[te, "final_margin"] = predict(fit(tr, mf, "margin", **kw), out[te], mf)
    return opening_week(out) if ow else out


def boot(v, groups, n=2000, seed=20261029):
    """Mean, 95% and 98.3% intervals and SE from a bootstrap over date clusters."""
    v, groups = np.asarray(v, float), np.asarray(groups)
    u, inv = np.unique(groups, return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(v.mean()), np.quantile(r, [.025, .975]), np.quantile(r, [.0085, .9915]), float(r.std())


__all__ = ["plays"]
