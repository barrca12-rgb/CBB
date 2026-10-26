"""Audit follow-up, item 1: the closest historical approximation of the live card at opener time.

Live (frozen dfb4bc7): stage-2 weights fit WITH referee crews and game-day KenPom (data/projection.json), but at
opener time crews are not posted (0) and KenPom's game-day FanMatch is not out (the card uses KenPom's current
ratings, i.e. through the previous day's games for an opener posted the evening before). Here: walk-forward weights
are fit on the production features exactly as before; predictions are then made with crews set to 0 and KenPom from
its archive dated D-1. Remaining differences from live are listed in audit/AUDIT_v2.md. Read-only.

    python -m audit.b1_live_approx
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.a2_timing import kp_prev, score
from audit.common import OUT, frame
from cbb import evaluate, projection


def walk_forward_split(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """projection.walk_forward, but fit on `train` features and predict from `pred` features (same rows)."""
    out = pred.copy()
    for b in (train, out):
        b["margin"] = b["home_pts"] - b["away_pts"]
        b["points"] = b["home_pts"] + b["away_pts"]
    out["final_margin"] = np.nan
    out["final_total"] = np.nan
    for s in sorted(train["season"].unique()):
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        if tr["season"].nunique() < 1:
            continue
        te = out["season"] == s
        cm = projection.ridge(tr[projection.MARGIN_FEATURES].to_numpy(float), tr["margin"].to_numpy(float))
        ct = projection.ridge(tr[projection.TOTAL_FEATURES].to_numpy(float), tr["points"].to_numpy(float))
        out.loc[te, "final_margin"] = cm[0] + out.loc[te, projection.MARGIN_FEATURES].to_numpy(float) @ cm[1:]
        out.loc[te, "final_total"] = ct[0] + out.loc[te, projection.TOTAL_FEATURES].to_numpy(float) @ ct[1:]
    return out.dropna(subset=["final_margin"])


if __name__ == "__main__":
    path = os.path.join(OUT, "wf_live_approx.pkl")
    if os.path.exists(path):
        w = pd.read_pickle(path)
    else:
        tmp = os.path.join(OUT, "_stage1_base")
        old = evaluate.OUT_DIR
        evaluate.OUT_DIR = tmp
        try:
            train = projection.add_features(evaluate.load(2013, 2026))
        finally:
            evaluate.OUT_DIR = old
        pred = kp_prev(train.assign(ref_fouls=0.0, ref_pts=0.0))
        w = walk_forward_split(train, pred.loc[train.index] if pred.index.equals(train.index) else pred)
        w.to_pickle(path)
    t = pd.DataFrame(score(frame(tag="base"), "production backtest") + score(w, "live-like approximation"))
    t.to_csv(os.path.join(OUT, "live_approx.csv"), index=False)
    pd.set_option("display.width", 200)
    print(t.to_string(index=False))
