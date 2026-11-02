"""Opener rule (Nov 2): backtest split of plays that qualify only after an adverse move, by size of the move.

A play "qualifies only after an adverse move" when the frozen walk-forward model's edge against the opener is below
the threshold (2.5 spreads, 3 totals) and its edge against the close, on the same side, is at or above it. It is
graded at the close (the only later number the history has). Move = edge at the close minus edge at the opener, in
points on our side's scale. Plays that qualify at the opener are graded at the opener for comparison. Pushes are
excluded; 95% Wilson intervals. Minutes since open: not in the historical data (opener and close only).

    python -m research.linemove.backtest_split      # -> research/linemove/out/backtest_split.txt
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from research.persistent_disagreement import common

OUT = os.path.join(os.path.dirname(__file__), "out")
ERAS = {"2014-17": range(2014, 2018), "2024-26": range(2024, 2027)}


def wilson(w: int, n: int) -> tuple[float, float]:
    if not n:
        return (np.nan, np.nan)
    p, z = w / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (c - h), 100 * (c + h))


def frame() -> pd.DataFrame:
    d = common.baseline()
    if "swapped" in d:
        d = d[~d["swapped"].fillna(False).astype(bool)]
    out = []
    for mk, thr in (("spread", 2.5), ("total", 3.0)):
        if mk == "spread":
            eo, ec = d["final_margin"] + d["open_home_spread"], d["final_margin"] + d["home_spread"]
            ro, rc = d["margin"] + d["open_home_spread"], d["margin"] + d["home_spread"]
        else:
            eo, ec = d["final_total"] - d["open_total"], d["final_total"] - d["total"]
            ro, rc = d["points"] - d["open_total"], d["points"] - d["total"]
        x = pd.DataFrame({"season": d["season"], "eo": eo, "ec": ec, "ro": ro, "rc": rc, "market": mk, "thr": thr}).dropna()
        out.append(x)
    return pd.concat(out, ignore_index=True)


def row(lab: str, r: pd.Series) -> dict:
    r = r[r != 0]
    w, n = int((r > 0).sum()), len(r)
    lo, hi = wilson(w, n)
    roi = (w * 100 / 110 - (n - w)) / n * 100 if n else np.nan
    return {"group": lab, "plays": n, "win %": round(100 * w / n, 1) if n else None, "95% lo": round(lo, 1),
            "95% hi": round(hi, 1), "ROI % at -110": round(roi, 1) if n else None}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    x = frame()
    L = [__doc__.split("\n\n")[1], ""]
    for mk in ("spread", "total"):
        for era, ss in ERAS.items():
            y = x[(x["market"] == mk) & x["season"].isin(ss)]
            thr = y["thr"].iloc[0]
            at_open = y[y["eo"].abs() >= thr]
            s_o = np.sign(at_open["eo"])
            only_after = y[(y["ec"].abs() >= thr) & ~((y["eo"].abs() >= thr) & (np.sign(y["eo"]) == np.sign(y["ec"])))]
            side = np.sign(only_after["ec"])
            # our side's edge at the opener (can be negative: the model was on the other side at the open)
            move = only_after["ec"].abs() - side * only_after["eo"]
            res = side * only_after["rc"]
            rows = [row("qualified at the opener (bet at the opener)", s_o * at_open["ro"]),
                    row("only after an adverse move, all (bet at the close)", res)]
            for lab, lo, hi in (("  move 0.5-1 pt", 0.5, 1.0), ("  move 1-2 pts", 1.0, 2.0), ("  move 2+ pts", 2.0, 99)):
                rows.append(row(lab, res[(move >= lo) & (move < hi)]))
            rows.append(row("  move under 0.5 pt", res[move < 0.5]))
            L.append(f"{mk}, {era}:")
            L.append(pd.DataFrame(rows).to_string(index=False))
            L.append("")
    L.append("CLV of a play bet at the close is 0 by construction, so the history cannot show positive CLV for any "
             "after-move band; minutes since open are not in the history (opener and close only).")
    txt = "\n".join(L)
    open(os.path.join(OUT, "backtest_split.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
