"""Shared pieces for the edge search: the frozen model's live-like frame with moneyline-oriented openers, the
development / holdout split, and the date-clustered bootstrap."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import lines_hist

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
DEV = list(range(2014, 2025))
HOLDOUT = [2025, 2026]
N_BOOT, SEED = 5000, 20261026


def open_meta(season: int) -> pd.DataFrame | None:
    p = os.path.join(ROOT, "audit", "out", f"espn_open_meta_{season}.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def frame() -> pd.DataFrame:
    """Live-like walk-forward frame; openers replaced by the moneyline-oriented consensus ("flip")."""
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    parts = []
    for s in sorted(w["season"].unique()):
        p = os.path.join(lines_hist.OUT, f"espn_{s}.csv")
        if os.path.exists(p):
            c = lines_hist.consensus(pd.read_csv(p), "flip", open_meta(int(s)))
            parts.append(c[["game_id", "open_home_spread", "open_total"]])
    op = pd.concat(parts, ignore_index=True).drop_duplicates("game_id")
    return w.drop(columns=["open_home_spread", "open_total"]).merge(op, on="game_id", how="left")


def boot(v, dates) -> dict:
    d = pd.DataFrame({"v": np.asarray(v, float), "d": np.asarray(dates)}).dropna()
    if d["d"].nunique() < 2:
        return {"n": len(d), "mean": float(d["v"].mean()) if len(d) else np.nan, "se": np.nan}
    g = d.groupby("d")["v"].agg(["sum", "count"]).to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(g), size=(N_BOOT, len(g)))
    s = g[idx].sum(axis=1)
    draws = s[:, 0] / s[:, 1]
    return {"n": len(d), "mean": float(d["v"].mean()), "se": float(draws.std(ddof=1))}


def record(res: pd.Series, units: pd.Series, dates: pd.Series) -> dict:
    """Win % (pushes out) and ROI with date-clustered SEs."""
    dec = res != "P"
    wb = boot((res[dec] == "W").astype(float), dates[dec])
    ub = boot(units, dates)
    return {"bets": int(len(res)), "win%": 100 * wb["mean"], "win% se": 100 * wb["se"],
            "ROI%": 100 * ub["mean"], "ROI% se": 100 * ub["se"]}


def opener_plays(w: pd.DataFrame, total_col: str = "final_total") -> pd.DataFrame:
    """The frozen rule against the opener: spread edge 2.5+, total edge 3+; graded on the opener; -110 assumed."""
    rows = []
    sp = w.dropna(subset=["open_home_spread", "final_margin"])
    sp = sp.assign(edge_signed=sp["final_margin"] + sp["open_home_spread"])
    s = sp[sp["edge_signed"].abs() >= 2.5].copy()
    s["edge"], s["side"], s["market"] = s["edge_signed"].abs(), np.where(s["edge_signed"] > 0, "home", "away"), "spread"
    s["line"] = np.where(s["side"] == "home", s["open_home_spread"], -s["open_home_spread"])
    m = np.where(s["side"] == "home", s["home_pts"] - s["away_pts"], s["away_pts"] - s["home_pts"]) + s["line"]
    rows.append(s.assign(res=np.where(m > 0, "W", np.where(m < 0, "L", "P"))))
    to = w.dropna(subset=["open_total", total_col])
    to = to.assign(edge_signed=to[total_col] - to["open_total"])
    t = to[to["edge_signed"].abs() >= 3.0].copy()
    t["edge"], t["side"], t["market"] = t["edge_signed"].abs(), np.where(t["edge_signed"] > 0, "over", "under"), "total"
    t["line"] = t["open_total"]
    m = np.where(t["side"] == "over", t["home_pts"] + t["away_pts"] - t["line"], t["line"] - t["home_pts"] - t["away_pts"])
    rows.append(t.assign(res=np.where(m > 0, "W", np.where(m < 0, "L", "P"))))
    p = pd.concat(rows, ignore_index=True)
    p["u"] = np.where(p["res"] == "W", 100 / 110, np.where(p["res"] == "L", -1.0, 0.0))
    p["split"] = np.where(p["season"].isin(HOLDOUT), "holdout", "development")
    return p
