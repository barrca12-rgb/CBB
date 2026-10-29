"""Shared pieces for the game-state study (PLAN.md). Research only."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import ridge_w
from research.quant.common import base_frames
from research.quant3.study import opening_week
from research.game_state.stage1 import VARIANTS

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
NAMES = [v[0] for v in VARIANTS]


def deltas(lag: int, seasons) -> pd.DataFrame:
    """Stage-1 forecast changes (adjusted - unadjusted) per game and variant, indexed by game_id."""
    d = pd.concat([pd.read_parquet(os.path.join(OUT, f"s1_lag{lag}_{s}.parquet")) for s in seasons], ignore_index=True)
    return d.set_index("game_id")


def shift(frame: pd.DataFrame, D: pd.DataFrame | None, name: str) -> pd.DataFrame:
    """Frame with the variant's stage-1 change added to pred_margin / pred_total and the early-season interactions
    recomputed. Games without a delta (no play-by-play season, e.g. 2013) are unchanged."""
    f = frame.copy()
    if D is None or name == "none":
        return f
    dm = f["game_id"].map(D[f"dm_{name}"]).fillna(0.0).to_numpy()
    dt = f["game_id"].map(D[f"dt_{name}"]).fillna(0.0).to_numpy()
    f["pred_margin"] = f["pred_margin"] + dm
    f["pred_total"] = f["pred_total"] + dt
    f["pred_margin_x_early"] = f["pred_margin"] * f["early"]
    f["pred_total_x_early"] = f["pred_total"] * f["early"]
    return f


def fit_predict(train: pd.DataFrame, pred: pd.DataFrame, lam: float = 1.0) -> pd.DataFrame:
    """research.quant.common.fit_predict (ridge lambda 1, the frozen 16/17 features, season s fit on train seasons
    2013..s-1), except that seasons with no earlier training rows are left empty instead of failing."""
    mf, tf = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
    out = pred.copy()
    out["final_margin"], out["final_total"] = np.nan, np.nan
    for s in sorted(out["season"].unique()):
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        if not len(tr):
            continue
        te = out["season"] == s
        w = np.ones(len(tr))
        cm = ridge_w(tr[mf].to_numpy(float), tr["margin"].to_numpy(float), w, lam)
        ct = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), w, lam)
        out.loc[te, "final_margin"] = cm[0] + out.loc[te, mf].to_numpy(float) @ cm[1:]
        out.loc[te, "final_total"] = ct[0] + out.loc[te, tf].to_numpy(float) @ ct[1:]
    return out[out["season"].between(2014, 2026)]


def forecast(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """Live-like walk-forward stage 2 plus the live opening-week totals rule."""
    w = opening_week(fit_predict(train, pred))
    w["margin"] = w["home_pts"] - w["away_pts"]
    w["points"] = w["home_pts"] + w["away_pts"]
    w["date"] = pd.to_datetime(w["date"])
    return w.reset_index(drop=True)


def frames():
    return base_frames()


def payout(o: float) -> float:
    return o / 100 if o > 0 else 100 / -o


def select(edge, price_pos, price_neg, market: str):
    """Fixed live rule: |edge| >= threshold and EV >= +2% at the price of the side the edge points to."""
    edge = np.asarray(edge, float)
    slope, cap, thr = (0.0255, 0.58, 2.5) if market == "spread" else (0.014, 0.565, 3.0)
    ok = ~np.isnan(edge)
    e = np.where(ok, edge, 0.0)
    p = np.minimum(np.maximum(0.5 + slope * np.abs(e), 0.5), cap)
    price = np.where(e > 0, price_pos, price_neg)
    ev = p * np.array([payout(o) for o in price]) - (1 - p)
    return ok & (np.abs(e) >= thr) & (ev >= 0.02), np.where(e > 0, 1, -1), price


def grade(side, cover, price) -> np.ndarray:
    """cover = result - line from the positive side (home for spreads, over for totals). 1 unit risked."""
    won = np.sign(cover) * side
    return np.where(won > 0, [payout(o) for o in price], np.where(won < 0, -1.0, 0.0))
