"""Shared helpers for the backtest audit. Read-only with respect to production: frames are rebuilt through the
production code (evaluate.load -> projection.add_features -> projection.walk_forward) from a stage-1 file and cached
under audit/out/.

Bet rows follow the reported analysis exactly: a play is the model's side when |model - line| >= threshold, where the
line is the ESPN consensus opener (lines_hist.consensus) or close; graded against the final score on that same number;
pushes are counted separately and excluded from win %.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate, projection

OUT = os.path.join(os.path.dirname(__file__), "out")
STAGE1 = os.path.join(os.path.dirname(__file__), "..", "cbb", "output", "backtest_2013_2026.csv")


def frame(stage1: str = STAGE1, tag: str = "base", features=None, refresh: bool = False) -> pd.DataFrame:
    """Walk-forward frame (final_margin / final_total) from a stage-1 csv. features: optional callable applied to
    the add_features() output before walk_forward (used for the timing variants)."""
    path = os.path.join(OUT, f"wf_{tag}.pkl")
    if os.path.exists(path) and not refresh:
        return pd.read_pickle(path)
    d = os.path.dirname(os.path.abspath(stage1))
    name = os.path.basename(stage1)
    old = evaluate.OUT_DIR
    try:   # evaluate.load reads <OUT_DIR>/backtest_<start>_<end>.csv; point it at the file under test
        tmp = os.path.join(OUT, f"_stage1_{tag}")
        os.makedirs(tmp, exist_ok=True)
        dst = os.path.join(tmp, "backtest_2013_2026.csv")
        if os.path.abspath(stage1) != os.path.abspath(dst):
            if os.path.lexists(dst):
                os.remove(dst)
            os.symlink(os.path.abspath(stage1), dst)
        evaluate.OUT_DIR = tmp
        b = projection.add_features(evaluate.load(2013, 2026))
    finally:
        evaluate.OUT_DIR = old
    if features is not None:
        b = features(b)
    w = projection.walk_forward(b).dropna(subset=["final_margin"])
    os.makedirs(OUT, exist_ok=True)
    w.to_pickle(path)
    return w


def bets(w: pd.DataFrame, market: str, vs: str, thr: float, seasons=None, margin_col="final_margin",
         total_col="final_total") -> pd.DataFrame:
    """One row per play. vs: 'open' or 'close' (the line the edge is measured against and graded on)."""
    d = w if seasons is None else w[w["season"].between(*seasons)]
    if market == "spread":
        line = d["open_home_spread"] if vs == "open" else d["home_spread"]
        d = d.assign(line=line).dropna(subset=["line"])
        if vs == "open":
            d = d.dropna(subset=["home_spread"])
        e = d[margin_col] + d["line"]                       # home edge in points
        side = np.sign(e)
        res = np.sign(d["margin"] + d["line"]) * side         # +1 win, -1 loss, 0 push (on the line bet)
        res_close = np.sign(d["margin"] + d["home_spread"]) * side
        move = (d["line"] - d["home_spread"]) * side          # + = close moved toward our side
        out = d.assign(edge=e.abs(), side=np.where(side > 0, "home", "away"), res=res, res_at_close=res_close,
                       clv=move, close=d["home_spread"])
    else:
        line = d["open_total"] if vs == "open" else d["total"]
        d = d.assign(line=line).dropna(subset=["line"])
        if vs == "open":
            d = d.dropna(subset=["total"])
        e = d[total_col] - d["line"]
        side = np.sign(e)
        res = np.sign(d["points"] - d["line"]) * side
        res_close = np.sign(d["points"] - d["total"]) * side
        move = (d["total"] - d["line"]) * side
        out = d.assign(edge=e.abs(), side=np.where(side > 0, "over", "under"), res=res, res_at_close=res_close,
                       clv=move, close=d["total"])
    out = out[(out["edge"] >= thr) & (side.loc[out.index] != 0)]
    return out.assign(market=market, vs=vs)


def record(b: pd.DataFrame, res: str = "res", odds: float = -110) -> dict:
    w, l, p = int((b[res] > 0).sum()), int((b[res] < 0).sum()), int((b[res] == 0).sum())
    pay = 100 / -odds if odds < 0 else odds / 100
    units = w * pay - l
    return {"plays": len(b), "W": w, "L": l, "P": p, "win%": 100 * w / (w + l) if w + l else np.nan,
            "units@-110": round(units, 1), "ROI%": round(100 * units / len(b), 2) if len(b) else np.nan}
