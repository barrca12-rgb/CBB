"""Totals edge bands 2-4+ at the opener on the live-like frame (Oct 30; helper doc follow-up 1 on band B).

The Oct 26 band table that lowered the live totals cutoff from 4 to 3 came from the production frame, which uses
inputs the opener never has (the game's referee crew, game-day KenPom). This reports the same bands on the
live-like frame (research/persistent_disagreement baseline: crews unknown, KenPom from the day before), by era, at
an assumed -110, with the +2% EV trim at recorded DraftKings prices on the dated 2025-26 sample. Research only.

    python -m research.band_b.totals_bands      # -> research/band_b/out/totals_bands.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import run_day
from research.band_b.replay import ERAS, plays
from research.persistent_disagreement.common import baseline

OUT = os.path.join(os.path.dirname(__file__), "out")
BANDS = [(2.0, 2.5), (2.5, 3.0), (3.0, 3.5), (3.5, 4.0), (4.0, 99.0), (3.0, 99.0)]


def cell(y: pd.DataFrame, dates: pd.Series) -> dict:
    dec = y[y["cover"] != 0]
    win = (dec["cover"] > 0).astype(float)
    # date-clustered SE of the win rate
    n = len(win)
    se = float(np.sqrt(((win - win.mean()).groupby(dates.reindex(dec.index).to_numpy()).sum() ** 2).sum()) / n) if n > 1 else np.nan
    w = float(win.mean()) if n else np.nan
    return {"plays": len(y), "win %": round(100 * w, 1), "95% ±": round(196 * se, 1),
            "ROI % at -110": round(100 * (w * 100 / 110 - (1 - w)), 1), "CLV": round(float(y["clv"].mean()), 2),
            "pass EV at -110": int((y["ev110"] >= run_day.MIN_EV).sum())}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    w = w[~w["swapped"]]
    rows = []
    for era, ss in list(ERAS.items()) + [("both eras", ERAS["2014-15..2016-17"] + ERAS["2023-24..2025-26"])]:
        d = plays(w[w["season"].isin(ss)], "total")
        for lo, hi in BANDS:
            y = d[(d["edge"] >= lo) & (d["edge"] < hi)]
            for g in ("all", "overs", "unders"):
                yy = y if g == "all" else y[y["group"] == g]
                rows.append({"era": era, "band": f"{lo:g}-{hi:g}" if hi < 99 else f"{lo:g}+", "side": g,
                             **cell(yy, d["date"].astype(str))})
    t = pd.DataFrame(rows)
    lines = ["Totals bands at the ESPN opener, live-like frame (crews unknown, KenPom from the day before), swapped "
             "records out, pushes out of win %; ROI at an assumed -110; 95% ± is date-clustered.", "",
             t.to_string(index=False), ""]
    # EV trim at recorded DraftKings prices (dated 2025-26 sample, same source as replay.py)
    rt = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "rotation_totals", "out", "predictions_A_strict.csv"))
    r = rt[rt["season"] == 2026]
    e = r["model_total"] - r["dk_total"]
    price = np.where(e > 0, r["over_price"], r["under_price"])
    p = np.array([run_day.win_prob("total", x) for x in e.abs()])
    ok = np.array([run_day.ev(pp, o) for pp, o in zip(p, price)]) >= run_day.MIN_EV
    lines.append("EV trim at recorded DraftKings prices (2025-26 dates 2025-11-08, 2026-01-10, 2026-03-07):")
    for lo, hi in BANDS[:5]:
        b = ((e.abs() >= lo) & (e.abs() < hi)).to_numpy()
        lines.append(f"  totals {lo:g}-{hi:g}: {int(b.sum())} edges, {int((b & ok).sum())} pass +2% EV, {int((b & ~ok).sum())} trimmed")
    open(os.path.join(OUT, "totals_bands.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
