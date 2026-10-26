"""Audit summary numbers for the conservative ('safe_lag1') timing variant: clustered CIs, prices, slippage,
drawdown, and the same plays at the close. Requires audit/out/wf_safe_lag1.pkl from a2_timing.

    python -m audit.a6_adjusted
"""
from __future__ import annotations

import os

import pandas as pd

from audit.a4_robustness import cluster_ci, drawdown, regrade, units
from audit.common import OUT, bets, frame, record

if __name__ == "__main__":
    rows = []
    for tag in ("base", "safe_lag1"):
        w = frame(tag=tag)
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            for ss in ((2015, 2017), (2024, 2026)):
                b = bets(w, mk, "open", thr, ss)
                ci_w, ci_r = cluster_ci(b)
                cw, cr = cluster_ci(b, res="res_at_close")
                rows.append({"variant": tag, "cohort": f"{mk} {ss[0]}-{ss[1]}", "plays": len(b),
                             "win% open": round(record(b)["win%"], 1), "CI": ci_w, "ROI% open -110": record(b)["ROI%"], "ROI CI": ci_r,
                             "ROI% -115": round(units(b["res"].to_numpy(), -115).mean() * 100, 1),
                             "ROI% 1pt worse": round(units(regrade(b, 1.0, mk)["res"].to_numpy()).mean() * 100, 1),
                             "same plays at close win%": round(record(b, "res_at_close")["win%"], 1), "close CI": cw,
                             "ROI% at close -110": record(b, "res_at_close")["ROI%"], "drawdown u": drawdown(b)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "adjusted_summary.csv"), index=False)
    pd.set_option("display.width", 260)
    print(t.to_string(index=False))
