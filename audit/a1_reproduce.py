"""Audit step 1: reproduce the reported rows from bet-level records and check the records for duplicates and gaps.

    python -m audit.a1_reproduce
Writes audit/out/bets_reported.csv (every play behind every reported row) and prints the reconciliation.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import OUT, bets, frame, record

REPORTED = [  # (row, market, vs, seasons, threshold, reported win %, reported count, reported line value)
    ("Spreads vs opener 2024-26", "spread", "open", (2024, 2026), 2.5, 57.8, 2221, 1.07),
    ("Totals vs opener 2024-26", "total", "open", (2024, 2026), 3.0, 57.4, 4241, 1.45),
    ("Spreads vs opener 2015-17", "spread", "open", (2015, 2017), 2.5, 57.6, 1935, 1.26),
    ("Totals vs opener 2015-17", "total", "open", (2015, 2017), 3.0, 58.4, 3763, 1.22),
    ("Spreads vs close 2020-26", "spread", "close", (2020, 2026), 2.5, 52.4, 5520, None),
    ("Totals vs close 2020-26", "total", "close", (2020, 2026), 3.0, 53.1, 11219, None),
    ("Spreads vs close 2024-26", "spread", "close", (2024, 2026), 2.5, 52.2, 2569, None),
    ("Totals vs close 2024-26", "total", "close", (2024, 2026), 3.0, 51.9, 4729, None),
]

if __name__ == "__main__":
    w = frame()
    print("frame rows", len(w), "| duplicate game_ids:", int(w["game_id"].duplicated().sum()),
          "| seasons", w["season"].min(), "-", w["season"].max())
    allb, rows = [], []
    for name, mk, vs, ss, thr, rw, rn, rclv in REPORTED:
        b = bets(w, mk, vs, thr, ss)
        r = record(b)
        dec = r["W"] + r["L"]
        rows.append({"row": name, "plays": r["plays"], "W": r["W"], "L": r["L"], "P": r["P"], "decided": dec,
                     "win%": round(r["win%"], 2), "reported win%": rw, "reported n": rn,
                     "n matches decided": dec == rn,
                     "line value (all plays)": round(b["clv"].mean(), 3) if vs == "open" else None,
                     "reported line value": rclv, "units@-110": r["units@-110"], "ROI%@-110": r["ROI%"],
                     "games": b["game_id"].nunique(), "dates": b["date"].nunique()})
        allb.append(b.assign(row=name)[["row", "game_id", "season", "date", "home_id", "away_id", "market", "vs",
                                        "side", "line", "close", "edge", "res", "res_at_close", "clv"]])
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    b = pd.concat(allb)
    b.to_csv(os.path.join(OUT, "bets_reported.csv"), index=False)
    print("plays with more than one bet on the same game in a row:", int(b.duplicated(["row", "game_id"]).sum()))
    sg = b[b["vs"] == "open"].groupby(["season", "game_id"])["market"].nunique()
    print("opener games with both a spread and a total play:", int((sg > 1).sum()), "of", len(sg))
