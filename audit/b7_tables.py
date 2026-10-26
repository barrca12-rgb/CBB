"""Audit follow-up, item 3: one consolidated table, every variant, with selections, wins, losses, pushes, voids and
unsettled as separate columns, ROI on a stated convention, and date-clustered intervals. Read-only.

ROI convention: flat 1 unit per selection; pushes return the stake (0 units) and stay in the denominator; win % =
W / (W + L); price -110 ASSUMED (no historical spread or total price exists). Voids and unsettled: the backtest
universe is completed games only (data.season_games), so both are 0 by construction; postponed or cancelled games
are absent rather than voided, which cannot be checked from the stored data.

    python -m audit.b7_tables
"""
from __future__ import annotations

import os

import pandas as pd

from audit.a4_robustness import cluster_ci
from audit.b2_opener_cleaning import apply, raw_openers
from audit.common import OUT, bets, frame, record

if __name__ == "__main__":
    v = {"production backtest": frame(tag="base"),
         "live-like approximation": pd.read_pickle(os.path.join(OUT, "wf_live_approx.pkl")),
         "production, crews 0 at open (referee fix)": pd.read_pickle(os.path.join(OUT, "wf_refs_zero_at_open.pkl")),
         "conservative (safe_lag1)": frame(tag="safe_lag1"),
         "conservative, no Barttorvik": frame(tag="safe_lag1_nobt")}
    s = v["conservative (safe_lag1)"]
    v["conservative, no close-based opener rule"] = apply(s, raw_openers(sorted(s["season"].unique())), "none", None)[0]
    rows = []
    for name, w in v.items():
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            for ss in ((2015, 2017), (2024, 2026)):
                b = bets(w, mk, "open", thr, ss)
                r = record(b)
                ci_w, ci_r = cluster_ci(b)
                rows.append({"variant": name, "market": mk, "seasons": f"{ss[0]}-{ss[1]}", "selections": r["plays"],
                             "W": r["W"], "L": r["L"], "P": r["P"], "voids": 0, "unsettled": 0,
                             "win%": round(r["win%"], 2), "win% 95% CI": ci_w, "ROI% (-110 assumed)": r["ROI%"],
                             "ROI 95% CI": ci_r, "line value": round(b["clv"].mean(), 2),
                             "same selections at close, win%": round(record(b, "res_at_close")["win%"], 2)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "consolidated_table.csv"), index=False)
    pd.set_option("display.width", 260)
    print(t.to_string(index=False))
