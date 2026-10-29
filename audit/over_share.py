"""Totals over/under mix, season to date (Chad, Oct 29: watch v1's lean to overs; option 1 of research/quant3/LOG.md).

Read only. Two views:
  model   every totals play v1 would make at the opener (edge 3+), from the card's own files
          (research/quant/e2_shadow.build, reused read-only); win% on finished games, pushes dropped
  logged  totals bets in bets/bets.csv (void excluded): count, record and average CLV at the primary close
          (bets/clv_primary.csv, the same CLV the site shows) by side

History at the opener, edge 3+: overs were 87% of plays in 2023-24, 78% in 2024-25 and 53% in 2025-26; both sides
won about 55-56%. Describe only; no change to the card follows from this line.

    python -m audit.over_share
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")


def model_line() -> str:
    from research.quant.e2_shadow import _days, build
    if not _days():
        return "model at the opener: no 2026-27 games yet"
    d = build().dropna(subset=["open_total"])
    e = d["v1_total"] - d["open_total"]
    p = d[e.abs() >= 3].assign(edge=e[e.abs() >= 3])
    if not len(p):
        return "model at the opener: no edge 3+ plays yet"
    o, u = p[p["edge"] > 0], p[p["edge"] < 0]

    def rec(x):
        x = x.dropna(subset=["points"])
        c = np.sign(x["edge"]) * (x["points"] - x["open_total"])
        w, l = int((c > 0).sum()), int((c < 0).sum())
        return f"{w}-{l}" + (f" ({100 * w / (w + l):.1f}%)" if w + l else "")
    return (f"model at the opener (edge 3+): {len(p)} plays, overs {100 * len(o) / len(p):.0f}%; "
            f"overs {rec(o)}, unders {rec(u)}")


def logged_line() -> str:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(b["market"] == "total") & (b["status"] != "void")]
    cp = os.path.join(ROOT, "bets", "clv_primary.csv")
    clv_of = pd.read_csv(cp).set_index("bet_id")["clv_primary"] if os.path.exists(cp) else pd.Series(dtype=float)
    if not len(b):
        return "logged totals: none yet"
    parts = []
    for side in ("over", "under"):
        x = b[b["side"].str.lower() == side]
        r = x["result"].astype(str)
        clv = pd.to_numeric(x["bet_id"].map(clv_of), errors="coerce")
        parts.append(f"{side}s {len(x)} ({(r == 'W').sum()}-{(r == 'L').sum()}"
                     + (f", CLV {clv.mean():+.2f}" if clv.notna().any() else "") + ")")
    return f"logged totals: {len(b)}, overs {100 * (b['side'].str.lower() == 'over').mean():.0f}%; " + ", ".join(parts)


def main() -> None:
    print(model_line())
    print(logged_line())


if __name__ == "__main__":
    main()
