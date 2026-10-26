"""Audit step 4: freeze the opener-selected plays (side, number, edge from the opener comparison) and grade the same
plays at the consensus close. No reselection, no re-prediction.

    python -m audit.a3_same_bets
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from audit.common import bets, frame, record

KEY_SPREAD = [1, 2, 3, 4, 5, 6, 7, 10]   # check which crossings matter instead of assuming equal points

if __name__ == "__main__":
    w = frame()
    pd.set_option("display.width", 250)
    rows = []
    for mk, thr in (("spread", 2.5), ("total", 3.0)):
        for ss in ((2015, 2017), (2024, 2026)):
            b = bets(w, mk, "open", thr, ss)
            o, c = record(b, "res"), record(b, "res_at_close")
            q = b["clv"].quantile([.1, .25, .5, .75, .9]).round(1).tolist()
            rows.append({"cohort": f"{mk} {ss[0]}-{ss[1]} (opener-selected)", "plays": len(b),
                         "win% at opener": round(o["win%"], 2), "ROI%@-110 opener": o["ROI%"],
                         "win% same plays at close": round(c["win%"], 2), "ROI%@-110 close": c["ROI%"],
                         "pushes open/close": f"{o['P']}/{c['P']}",
                         "line moved our way %": round(100 * (b["clv"] > 0).mean(), 1),
                         "unchanged %": round(100 * (b["clv"] == 0).mean(), 1),
                         "against %": round(100 * (b["clv"] < 0).mean(), 1),
                         "mean move": round(b["clv"].mean(), 2), "p10/25/50/75/90": q})
    print(pd.DataFrame(rows).to_string(index=False))

    # spreads: does the value of a move depend on the numbers crossed? win% at close by move size
    for ss in ((2015, 2017), (2024, 2026)):
        b = bets(w, "spread", "open", 2.5, ss)
        b = b.assign(mv=b["clv"].clip(-3, 3).round())
        t = b.groupby("mv").apply(lambda x: pd.Series({"plays": len(x), "win% at opener": 100 * (x.res > 0).sum() / max((x.res != 0).sum(), 1),
                                                       "win% at close": 100 * (x.res_at_close > 0).sum() / max((x.res_at_close != 0).sum(), 1)}))
        print(f"\nSpreads {ss}: by line move (points our way, clipped at 3)\n", t.round(1).to_string())
        # empirical push/landing frequency of final margins on key numbers (for the record)
    m = w.dropna(subset=["home_spread"])
    land = (m["margin"].abs().value_counts(normalize=True).sort_index() * 100).loc[1:10].round(1)
    print("\nShare of games decided by exactly N points (all seasons):", land.to_dict())
