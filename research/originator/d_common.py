"""Shared pieces for Part D: the live-like stage-2 training and prediction frames, a configurable walk-forward,
and both scorecards (forecast MAE; information beyond the close and opener CLV)."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate, lines_hist, projection

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
AUDIT = os.path.join(ROOT, "audit", "out")


def frames(stage1_csv: str | None = None, tag: str = "frozen") -> tuple[pd.DataFrame, pd.DataFrame]:
    """(train, pred): stage-2 features from a stage-1 file; train as recorded, pred with crews 0 and KenPom from
    the day before (audit/b1_live_approx). Cached per tag."""
    path = os.path.join(OUT, f"d_frames_{tag}.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    from audit.a2_timing import kp_prev
    src = stage1_csv or os.path.join(AUDIT, "_stage1_base", "backtest_2013_2026.csv")
    tmp = os.path.join(OUT, f"_stage1_{tag}")
    os.makedirs(tmp, exist_ok=True)
    dst = os.path.join(tmp, "backtest_2013_2026.csv")
    if not os.path.lexists(dst):
        os.symlink(os.path.abspath(src), dst)
    old = evaluate.OUT_DIR
    evaluate.OUT_DIR = tmp
    try:
        train = projection.add_features(evaluate.load(2013, 2026))
    finally:
        evaluate.OUT_DIR = old
    pred = kp_prev(train.assign(ref_fouls=0.0, ref_pts=0.0))
    pd.to_pickle((train, pred), path)
    return train, pred


def ridge_w(X, y, w, lam=1.0):
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0
    W = w[:, None]
    return np.linalg.solve(X1.T @ (X1 * W) + np.diag(pen), (X1 * W).T @ y)


def walk_forward(train: pd.DataFrame, pred: pd.DataFrame, half_life: float | None = None,
                 regimes: bool = False) -> pd.DataFrame:
    """The live-like walk-forward with optional season-recency weights 0.5^((s-1-season)/half_life) and optional
    separate November-December / January-on fits."""
    tr_all, out = train.copy(), pred.copy()
    for b in (tr_all, out):
        b["margin"] = b["home_pts"] - b["away_pts"]
        b["points"] = b["home_pts"] + b["away_pts"]
        b["regime"] = np.where(pd.to_datetime(b["date"]).dt.month.isin([11, 12]), "early", "late")
    out["final_margin"], out["final_total"] = np.nan, np.nan
    for s in sorted(tr_all["season"].unique()):
        tr = tr_all[(tr_all["season"] < s) & (tr_all["season"] >= 2013)]
        if not len(tr):
            continue
        groups = ["early", "late"] if regimes else [None]
        for rg in groups:
            t = tr if rg is None else tr[tr["regime"] == rg]
            te = (out["season"] == s) if rg is None else ((out["season"] == s) & (out["regime"] == rg))
            w = np.ones(len(t)) if half_life is None else 0.5 ** ((s - 1 - t["season"].to_numpy(float)) / half_life)
            cm = ridge_w(t[projection.MARGIN_FEATURES].to_numpy(float), t["margin"].to_numpy(float), w)
            ct = ridge_w(t[projection.TOTAL_FEATURES].to_numpy(float), t["points"].to_numpy(float), w)
            out.loc[te, "final_margin"] = cm[0] + out.loc[te, projection.MARGIN_FEATURES].to_numpy(float) @ cm[1:]
            out.loc[te, "final_total"] = ct[0] + out.loc[te, projection.TOTAL_FEATURES].to_numpy(float) @ ct[1:]
    return out.dropna(subset=["final_margin"])


def oriented_openers(w: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for s in sorted(w["season"].unique()):
        p = os.path.join(lines_hist.OUT, f"espn_{s}.csv")
        mp = os.path.join(AUDIT, f"espn_open_meta_{s}.csv")
        if os.path.exists(p):
            c = lines_hist.consensus(pd.read_csv(p), "flip", pd.read_csv(mp) if os.path.exists(mp) else None)
            parts.append(c[["game_id", "open_home_spread", "open_total"]])
    op = pd.concat(parts).drop_duplicates("game_id")
    return w.drop(columns=[c for c in ("open_home_spread", "open_total") if c in w]).merge(op, on="game_id", how="left")


def clv(w: pd.DataFrame, seasons) -> dict:
    """Opener CLV of the frozen rule (spread 2.5+, total 3+): mean points the consensus close moved toward the
    play; swapped records excluded."""
    d = w[w["season"].isin(list(seasons))]
    d = d[~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))]
    sp = d.dropna(subset=["open_home_spread", "home_spread"])
    e = sp["final_margin"] + sp["open_home_spread"]
    s = sp[e.abs() >= 2.5]
    lv_s = np.where(e[e.abs() >= 2.5] > 0, s["open_home_spread"] - s["home_spread"], s["home_spread"] - s["open_home_spread"])
    to = d.dropna(subset=["open_total", "total"])
    e = to["final_total"] - to["open_total"]
    t = to[e.abs() >= 3]
    lv_t = np.where(e[e.abs() >= 3] > 0, t["total"] - t["open_total"], t["open_total"] - t["total"])
    allv = np.concatenate([lv_s, lv_t])
    return {"spread plays": len(lv_s), "spread CLV": float(np.mean(lv_s)), "total plays": len(lv_t),
            "total CLV": float(np.mean(lv_t)), "combined CLV": float(np.mean(allv))}


def mae(w: pd.DataFrame, seasons) -> dict:
    d = w[w["season"].isin(list(seasons))]
    return {"margin MAE": float((d["home_pts"] - d["away_pts"] - d["final_margin"]).abs().mean()),
            "total MAE": float((d["home_pts"] + d["away_pts"] - d["final_total"]).abs().mean())}


def info_beyond_close(ch: pd.DataFrame, base: pd.DataFrame, seasons) -> dict:
    """Scorecard 2a: OLS of (result - close) on the challenger's adjustment (challenger - frozen), with the frozen
    model's edge vs the close as a control; date-clustered SEs. Margin and total."""
    d = base[["game_id", "date", "season", "home_pts", "away_pts", "home_spread", "total", "final_margin", "final_total"]].merge(
        ch[["game_id", "final_margin", "final_total"]], on="game_id", suffixes=("", "_ch"))
    d = d[d["season"].isin(list(seasons))].dropna(subset=["home_spread", "total"])
    out = {}
    for mk, res, adj, ctl in (("margin", (d["home_pts"] - d["away_pts"]) + d["home_spread"], d["final_margin_ch"] - d["final_margin"], d["final_margin"] + d["home_spread"]),
                              ("total", (d["home_pts"] + d["away_pts"]) - d["total"], d["final_total_ch"] - d["final_total"], d["final_total"] - d["total"])):
        X = np.column_stack([np.ones(len(d)), adj, ctl])
        y = res.to_numpy(float)
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ b
        bread = np.linalg.inv(X.T @ X)
        s = pd.DataFrame(X * e[:, None]).groupby(d["date"].to_numpy()).sum().to_numpy()
        se = np.sqrt(np.diag(bread @ (s.T @ s) @ bread))
        out[f"{mk}: adjustment coef (se)"] = f"{b[1]:.3f} ({se[1]:.3f})"
        out[f"{mk}: adjustment SD"] = float(adj.std())
    return out
