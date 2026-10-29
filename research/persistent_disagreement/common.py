"""Shared pieces for the persistent-disagreement study (PLAN.md). Research only.

Frames: the established live-like research frame (research/quant/common.base_frames: training frame as recorded,
prediction frame with referee crews 0 and KenPom from the day before; openers oriented by moneyline, swapped records
flagged). Baseline forecasts: frozen v1 stage-2 walk-forward (fit on 2013..s-1) with the live opening-week totals rule.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.quant.common import base_frames, fit_predict
from research.quant3.study import opening_week

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
NS = {"8": 8, "all": 10_000}
KS = [25.0, 100.0]
LAMS = [10.0, 100.0, 1_000.0, 10_000.0, 100_000.0]
SHRINK_N = 4.0        # S = sum(d) / (n + 4)


def baseline() -> pd.DataFrame:
    """Live-like walk-forward v1 forecasts for 2014-2026 with the opening-week totals rule."""
    train, pred = base_frames()
    w = opening_week(fit_predict(train, pred))
    w["margin"] = w["home_pts"] - w["away_pts"]
    w["points"] = w["home_pts"] + w["away_pts"]
    w["date"] = pd.to_datetime(w["date"])
    return w.reset_index(drop=True)


def history_sums(w: pd.DataFrame, lag_days: int) -> dict:
    """For every game: sums over the union of both teams' prior same-season games (date < game date - lag_days),
    last N per team (N in NS), de-duplicated by game id. Spread quantities are oriented to today's home team; totals
    are unoriented. Returns {N: DataFrame indexed like w with n, sd_s, sdr_s, sdd_s, sd_t, sdr_t, sdd_t}."""
    ok = (~w["swapped"]) & w["home_spread"].notna() & w["total"].notna() & w["final_margin"].notna() & w["final_total"].notna()
    ds = (w["final_margin"] + w["home_spread"]).where(ok)          # home side: model margin - market margin
    rs = (w["margin"] + w["home_spread"]).where(ok)                # home side: result - market margin
    dt = (w["final_total"] - w["total"]).where(ok)
    rt = (w["points"] - w["total"]).where(ok)
    out = {k: {c: np.zeros(len(w)) for c in ("n", "sd_s", "sdr_s", "sdd_s", "sd_t", "sdr_t", "sdd_t")} for k in NS}
    for s, g in w.groupby("season"):
        # per team: chronological list of (date, row index, sign for that team)
        rows = []
        for side, sign in (("home_id", 1.0), ("away_id", -1.0)):
            rows.append(pd.DataFrame({"team": g[side].to_numpy(), "date": g["date"].to_numpy(), "idx": g.index.to_numpy(), "sign": sign}))
        tl = pd.concat(rows).sort_values(["team", "date", "idx"], kind="mergesort")
        tl = tl[ok.loc[tl["idx"]].to_numpy()]                          # only games with lines and forecasts count
        by_team = {t: (x["date"].to_numpy(), x["idx"].to_numpy(), x["sign"].to_numpy()) for t, x in tl.groupby("team")}
        for i, r in g.iterrows():
            cut = r["date"] - pd.Timedelta(days=lag_days)
            for key, N in NS.items():
                used = {}
                for team, orient in ((r["home_id"], 1.0), (r["away_id"], -1.0)):
                    if team not in by_team:
                        continue
                    dts, idx, sg = by_team[team]
                    m = int(np.searchsorted(dts, np.datetime64(cut), side="left"))   # strictly before the cutoff
                    for j in range(max(0, m - N), m):
                        # oriented to today's home team: team-side value * orient; team-side = home-side * sign
                        used[idx[j]] = sg[j] * orient
                if not used:
                    continue
                ii = np.fromiter(used.keys(), int)
                o = np.fromiter(used.values(), float)
                d, rr = ds.to_numpy()[ii] * o, rs.to_numpy()[ii] * o
                td, tr = dt.to_numpy()[ii], rt.to_numpy()[ii]
                o_ = out[key]
                o_["n"][i] = len(ii)
                o_["sd_s"][i], o_["sdr_s"][i], o_["sdd_s"][i] = d.sum(), (d * rr).sum(), (d * d).sum()
                o_["sd_t"][i], o_["sdr_t"][i], o_["sdd_t"][i] = td.sum(), (td * tr).sum(), (td * td).sum()
    return {k: pd.DataFrame(v, index=w.index) for k, v in out.items()}


def feats(h: pd.DataFrame, d0: pd.Series, market: str, k: float) -> pd.DataFrame:
    """S (lean), Sdir (aligned with today's disagreement) and V (track record) from history sums."""
    suf = "_s" if market == "spread" else "_t"
    S = h[f"sd{suf}"] / (h["n"] + SHRINK_N)
    V = h[f"sdr{suf}"] / (h[f"sdd{suf}"] + k)
    return pd.DataFrame({"S": S, "Sdir": np.sign(d0) * S, "V": V}, index=h.index)


def design(d0: np.ndarray, f: pd.DataFrame, mu: pd.Series, sd: pd.Series) -> np.ndarray:
    z = (f[["V", "Sdir", "S"]] - mu) / sd
    return np.column_stack([d0, d0 * z["V"].to_numpy(), d0 * z["Sdir"].to_numpy(), z["S"].to_numpy()])


def fit_candidate(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    pen = np.array([0.0, lam, lam, lam])
    return np.linalg.solve(X.T @ X + np.diag(pen), X.T @ y)


def fit_comparator(d0: np.ndarray, y: np.ndarray) -> float:
    return float((d0 * y).sum() / (d0 * d0).sum())


def payout(o: float) -> float:
    return o / 100 if o > 0 else 100 / -o


def select(edge: np.ndarray, price_pos: np.ndarray, price_neg: np.ndarray, market: str):
    """Fixed live rule: |edge| >= threshold and EV >= +2% at the price of the side the edge points to."""
    slope, cap, thr = (0.0255, 0.58, 2.5) if market == "spread" else (0.014, 0.565, 3.0)
    p = np.minimum(np.maximum(0.5 + slope * np.abs(edge), 0.5), cap)
    price = np.where(edge > 0, price_pos, price_neg)
    ev = p * np.array([payout(o) for o in price]) - (1 - p)
    return (np.abs(edge) >= thr) & (ev >= 0.02), np.where(edge > 0, 1, -1), price


def grade(side: np.ndarray, cover: np.ndarray, price: np.ndarray) -> np.ndarray:
    """cover = result - line from the positive side (home for spreads, over for totals). 1 unit risked."""
    won = np.sign(cover) * side
    return np.where(won > 0, [payout(o) for o in price], np.where(won < 0, -1.0, 0.0))
