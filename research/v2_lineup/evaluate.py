"""Lineup v2 shadow vs live v1, spreads (PLAN.md). Read-only; run at Jan 15 (descriptive) and the season-end read.

    python -m research.v2_lineup.evaluate [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from cbb import data

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
FREEZE = pd.Timestamp("2026-10-26T19:20:50Z")


def payout(o):
    return np.where(o > 0, o / 100, 100 / -np.where(o < 0, o, -1))


def close_spread(closing: pd.DataFrame, r) -> float:
    """Median home spread across books observed within 60 minutes before the start, from the signal's side."""
    c = closing[(closing["date"] == r["date"])]
    same = c[(c["home_id"] == r["home_id"]) & (c["away_id"] == r["away_id"])]
    flip = c[(c["home_id"] == r["away_id"]) & (c["away_id"] == r["home_id"])]
    c, sgn = (same, 1) if len(same) else (flip, -1)
    st = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    seen = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    v = c.loc[((st - seen) <= pd.Timedelta(minutes=60)) & (seen < st), "home_spread"].dropna()
    if not len(v):
        return np.nan
    h = sgn * float(v.median())
    return h if r["side"] == "home" else -h


def boot(v, d, n=5000):
    v, d = np.asarray(v, float), np.asarray(d)
    ok = ~np.isnan(v)
    v, d = v[ok], d[ok]
    u = np.unique(d)
    if len(u) < 2:
        return float(v.mean()) if len(v) else np.nan, np.nan
    idx = np.random.default_rng(20261026).integers(0, len(u), (n, len(u)))
    sums = np.array([[v[d == k].sum(), (d == k).sum()] for k in u])
    s = sums[idx].sum(axis=1)
    return float(v.mean()), float((s[:, 0] / s[:, 1]).std(ddof=1))


def main(through: str | None = None) -> pd.DataFrame:
    v2 = pd.read_csv(os.path.join(ROOT, "bets", "shadow_v2", "signals.csv"))
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(pd.to_datetime(b["logged_at"], utc=True, format="ISO8601") >= FREEZE) & (b["market"] == "spread") & (b["status"] != "void")]
    v1 = b[["bet_id", "date", "game_id", "home_id", "away_id", "side", "line", "odds"]].copy()
    if through:
        v1, v2 = v1[v1["date"] <= through], v2[v2["date"] <= through]
    closing = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    parts = []
    for season in sorted({int(d[:4]) + (1 if int(d[5:7]) >= 8 else 0) for d in pd.concat([v1["date"], v2["date"]])}):
        try:
            parts.append(data.season_games(season)[0])
        except Exception:     # no box scores yet: those signals count as unsettled
            pass
    g = pd.concat(parts) if parts else pd.DataFrame(columns=["game_id", "home_pts", "away_pts"])
    score = g.drop_duplicates("game_id").set_index("game_id")[["home_pts", "away_pts"]].astype(float)
    rows = []
    k1, k2 = set(v1["bet_id"]), set(v2["bet_id"])
    for name, df in (("v1 (live)", v1), ("v2 (shadow)", v2), ("both", v1[v1["bet_id"].isin(k2)]),
                     ("v1 only", v1[~v1["bet_id"].isin(k2)]), ("v2 only", v2[~v2["bet_id"].isin(k1)])):
        d = df.copy()
        d["hp"], d["ap"] = d["game_id"].map(score["home_pts"]), d["game_id"].map(score["away_pts"])
        m = np.where(d["side"] == "home", d["hp"] - d["ap"], d["ap"] - d["hp"]) + d["line"]
        d["u"] = np.where(np.isnan(m) | d["odds"].isna(), np.nan, np.where(m > 0, payout(d["odds"].fillna(-110)), np.where(m < 0, -1.0, 0.0)))
        d["close"] = [close_spread(closing, r) for _, r in d.iterrows()]
        d["lv"] = d["line"] - d["close"]
        roi, roi_se = boot(d["u"], d["date"])
        lv, lv_se = boot(d["lv"], d["date"])
        dec = ~np.isnan(m) & (m != 0)
        rows.append({"set": name, "signals": len(d), "settled with price": int(d["u"].notna().sum()),
                     "win%": 100 * float((m[dec] > 0).mean()) if dec.any() else np.nan,
                     "ROI% (recorded prices)": 100 * roi, "ROI se": 100 * roi_se,
                     "line value vs closing.csv (pts)": lv, "lv se": lv_se, "close missing": int(d["close"].isna().sum())})
    t = pd.DataFrame(rows)
    # primary endpoint 1 (PLAN amendment): residual difference on the 2+ point subset
    gp = os.path.join(ROOT, "bets", "shadow_v2", "games_latest.csv")
    if os.path.exists(gp):
        gl = pd.read_csv(gp)
        if through:
            gl = gl[gl["date"] <= through]
        gl = gl[gl["subset"].astype(bool)]
        gl["res"] = gl["game_id"].map(score["home_pts"]) - gl["game_id"].map(score["away_pts"])
        gl = gl.dropna(subset=["res"])
        diff = (gl["res"] - gl["v1_margin"]).abs() - (gl["res"] - gl["v2_margin"]).abs()
        m, se = boot(diff, gl["date"]) if len(gl) else (np.nan, np.nan)
        print(f"subset games settled: {len(gl)}; residual gain v2 over v1 (pts): {m:.3f} (se {se:.3f})")
    pd.set_option("display.width", 200)
    print(t.round(3).to_string(index=False))
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    main(ap.parse_args().through)
