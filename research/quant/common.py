"""Shared pieces for the quant-lead experiments (research/quant/LOG.md). Research only; the live model is untouched.

Everything here reuses the frozen live-like benchmark (research/originator/d_common.py): the stage-2 training frame
as recorded and the prediction frame with referee crews zeroed and KenPom from the day before, the frozen 17/16
features, ridge lambda 1, one fit per season on all earlier seasons (2013 on).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate, projection
from research.originator.d_common import frames, oriented_openers, ridge_w

OUT = os.path.join(os.path.dirname(__file__), "out")
SEASONS = list(range(2014, 2027))
DEV = [2015, 2016, 2017]          # openers exist (ESPN "Opening" line)
CONF = [2024, 2025, 2026]         # openers exist (ESPN open/close)
EDGE = {"spread": 2.5, "total": 3.0}


def base_frames():
    """(train, pred) with margin/points, opener columns and the swapped-record flag."""
    path = os.path.join(OUT, "frames.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    train, pred = frames()
    for b in (train, pred):
        b["margin"] = b["home_pts"] - b["away_pts"]
        b["points"] = b["home_pts"] + b["away_pts"]
    pred = oriented_openers(pred)
    pred["swapped"] = evaluate.swapped(pred.assign(pred_margin=pred["pred_margin"]))
    pd.to_pickle((train, pred), path)
    return train, pred


def fit_predict(train, pred, mf=None, tf=None, extra_train=None, lam=1.0, target_m="margin", target_t="points"):
    """Walk-forward stage 2: season s predicted from coefficients fit on seasons 2013..s-1 of `train`."""
    mf, tf = mf or projection.MARGIN_FEATURES, tf or projection.TOTAL_FEATURES
    out = pred.copy()
    out["final_margin"], out["final_total"] = np.nan, np.nan
    for s in SEASONS:
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        te = out["season"] == s
        w = np.ones(len(tr))
        cm = ridge_w(tr[mf].to_numpy(float), tr[target_m].to_numpy(float), w, lam)
        ct = ridge_w(tr[tf].to_numpy(float), tr[target_t].to_numpy(float), w, lam)
        out.loc[te, "final_margin"] = cm[0] + out.loc[te, mf].to_numpy(float) @ cm[1:]
        out.loc[te, "final_total"] = ct[0] + out.loc[te, tf].to_numpy(float) @ ct[1:]
    return out[out["season"].isin(SEASONS)]


def boot(v, groups, n=2000, seed=20261028):
    """Mean with a 95% interval from a bootstrap over date clusters."""
    v, groups = np.asarray(v, float), np.asarray(groups)
    u, inv = np.unique(groups, return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(v.mean()), float(np.quantile(r, .025)), float(np.quantile(r, .975))


def plays(w: pd.DataFrame, market: str, line: str = "open") -> pd.DataFrame:
    """Frozen-rule plays against the opener (or close): edge, side, result vs that line, CLV vs the close.
    Swapped records excluded; pushes dropped from win rates."""
    d = w[~w["swapped"]].copy()
    if market == "spread":
        col = "open_home_spread" if line == "open" else "home_spread"
        d = d.dropna(subset=[col])
        e = d["final_margin"] + d[col]
        d = d[e.abs() >= EDGE["spread"]].assign(edge=e[e.abs() >= EDGE["spread"]])
        sgn = np.sign(d["edge"])
        d["cover"] = sgn * (d["margin"] + d[col])
        d["clv"] = sgn * (d[col] - d["home_spread"]) if line == "open" else np.nan
    else:
        col = "open_total" if line == "open" else "total"
        d = d.dropna(subset=[col])
        e = d["final_total"] - d[col]
        d = d[e.abs() >= EDGE["total"]].assign(edge=e[e.abs() >= EDGE["total"]])
        sgn = np.sign(d["edge"])
        d["cover"] = sgn * (d["points"] - d[col])
        d["clv"] = sgn * (d["total"] - d[col]) if line == "open" else np.nan
    d["win"] = np.where(d["cover"] > 0, 1.0, np.where(d["cover"] < 0, 0.0, np.nan))
    return d


def scorecard(w: pd.DataFrame, seasons, tag: str) -> dict:
    d = w[w["season"].isin(list(seasons))]
    r = {"model": tag, "seasons": f"{min(seasons)}-{max(seasons)}"}
    r["margin MAE"] = float((d["margin"] - d["final_margin"]).abs().mean())
    r["total MAE"] = float((d["points"] - d["final_total"]).abs().mean())
    r["games"] = len(d)
    for mk in ("spread", "total"):
        p = plays(d, mk, "open")
        x = p.dropna(subset=["win"])
        r[f"{mk} open n"] = len(x)
        r[f"{mk} open win%"] = 100 * float(x["win"].mean()) if len(x) else np.nan
        r[f"{mk} open CLV"] = float(p["clv"].dropna().mean()) if len(p) else np.nan
        c = plays(d, mk, "close").dropna(subset=["win"])
        r[f"{mk} close n"], r[f"{mk} close win%"] = len(c), 100 * float(c["win"].mean()) if len(c) else np.nan
    return r
