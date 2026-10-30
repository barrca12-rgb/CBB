"""Band B read (FORWARD_TEST_PROTOCOL.md Appendix B): band B's own record, and the games where a band B play was
later joined by a v1 bet on the same game and market, reported as their own cell (helper note, Oct 30).

A band B play stands when the game later reaches v1's cutoff and v1 logs it too, so the same side can carry 0.5 + 1
units. This lists those games: count, combined stake, and v1's record and Alert CLV on them against v1's record
overall (plus the opposite-side case, a hedge). Read-only.

    python -m audit.band_b_read [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from cbb import clv_primary, tracker


def _rec(x: pd.DataFrame) -> dict:
    s = x[x["status"] == "settled"]
    w, l, p = int((s["result"] == "W").sum()), int((s["result"] == "L").sum()), int((s["result"] == "P").sum())
    c = pd.to_numeric(s.get("clv_pts"), errors="coerce").dropna() if len(s) else pd.Series(dtype=float)
    staked = float(s["stake"].astype(float).sum())
    return {"plays": int(len(x)), "settled": int(len(s)), "W-L-P": f"{w}-{l}-{p}", "win %": round(100 * w / (w + l), 1) if w + l else None,
            "units": round(float(s["profit"].astype(float).sum()), 2), "ROI %": round(100 * float(s["profit"].astype(float).sum()) / staked, 1) if staked else None,
            "Alert CLV": round(float(c.mean()), 2) if len(c) else None, "with close": int(len(c))}


def overlaps(b: pd.DataFrame) -> pd.DataFrame:
    """One row per band B play that a later v1 bet joined on the same game and market (non-void)."""
    b = b[b["status"] != "void"]
    band = b[b["bet_type"].fillna("") == tracker.BAND_B]
    v1 = b[b["bet_type"].fillna("") != tracker.BAND_B]
    m = band.merge(v1, on=["game_id", "market"], suffixes=("_b", "_v1"))
    m = m[pd.to_datetime(m["logged_at_v1"], utc=True, format="ISO8601") > pd.to_datetime(m["logged_at_b"], utc=True, format="ISO8601")]
    m["same_side"] = m["side_b"].astype(str).str.lower() == m["side_v1"].astype(str).str.lower()
    m["combined_stake"] = np.where(m["same_side"], m["stake_b"].astype(float) + m["stake_v1"].astype(float), np.nan)
    return m


def read(through: str | None = None) -> dict:
    b = tracker.load("all")
    if through:
        b = b[b["date"] <= through]
    b = clv_primary.attach(b) if len(b) else b
    b = b[b["status"] != "void"]
    band = b[b["bet_type"].fillna("") == tracker.BAND_B]
    v1 = b[b["bet_type"].fillna("") != tracker.BAND_B]
    m = overlaps(b)
    out = {"through": through or "all", "band B (spreads only)": _rec(band), "v1, all plays": _rec(v1)}
    for lab, sub in (("same side (0.5 + 1 units on one side)", m[m["same_side"]]), ("opposite side (hedge)", m[~m["same_side"]])):
        v = v1[v1["bet_id"].isin(sub["bet_id_v1"])]
        out[f"band B games later bet by v1, {lab}"] = {
            "games": int(len(sub)), "combined stake (units)": float(sub["combined_stake"].sum()) if len(sub) else 0.0,
            "v1 on these games": _rec(v), "band B on these games": _rec(band[band["bet_id"].isin(sub["bet_id_b"])])}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    print(json.dumps(read(ap.parse_args().through), indent=1, default=str))
