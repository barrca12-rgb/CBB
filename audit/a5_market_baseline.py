"""Audit: (1) a market-only baseline with the same timing (team ratings fit to earlier games' closing lines, known
before any opener), (2) does the edge depend on suspicious openers (very large opener-to-close moves, the kind a
stale or mis-keyed opener produces)? Read-only.

    python -m audit.a5_market_baseline
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from audit.common import bets, frame, record

if __name__ == "__main__":
    w = frame()
    pd.set_option("display.width", 250)
    rows = []
    m = w[w["mkt_n"] >= 10].copy()   # both teams have 10+ earlier lined games
    for ss in ((2015, 2017), (2024, 2026)):
        for name, col in (("market ratings only", "mkt_margin"), ("final model, same games", "final_margin")):
            b = bets(m, "spread", "open", 2.5, ss, margin_col=col)
            r = record(b)
            rows.append({"spreads, 10+ prior closes": name, "seasons": f"{ss[0]}-{ss[1]}", "plays": r["plays"],
                         "win%": round(r["win%"], 1), "ROI%@-110": r["ROI%"], "mean move": round(b["clv"].mean(), 2)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nOpener plays split by size of the opener-to-close move (|move| >= 4 is the suspicious tail):")
    rows = []
    for mk, thr in (("spread", 2.5), ("total", 3.0)):
        for ss in ((2015, 2017), (2024, 2026)):
            b = bets(w, mk, "open", thr, ss)
            big = (b["line"] - b["close"]).abs() >= 4
            for lab, g in (("|move| < 4", b[~big]), ("|move| >= 4", b[big])):
                r = record(g)
                rows.append({"cohort": f"{mk} {ss[0]}-{ss[1]}", "subset": lab, "plays": r["plays"], "win%": round(r["win%"], 1),
                             "ROI%@-110": r["ROI%"], "same plays at close win%": round(record(g, "res_at_close")["win%"], 1)})
    print(pd.DataFrame(rows).to_string(index=False))
