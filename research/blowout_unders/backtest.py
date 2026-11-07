"""Unders in big mismatches (PLAN.md). Research only.

    python -m research.blowout_unders.backtest      # -> REPORT numbers in out/results.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import bets, frame, record

OUT = os.path.join(os.path.dirname(__file__), "out")
PERIODS = {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}
BINS, LABELS = [0, 10, 15, 20, 99], ["<10", "10-15", "15-20", "20+"]
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def size(d: pd.DataFrame) -> pd.Series:
    sp = d["open_home_spread"].fillna(d["home_spread"]).abs()
    return pd.cut(sp, BINS, labels=LABELS, right=False)


def main() -> None:
    w = frame(tag="base")
    rows, games = [], []
    for per, ss in PERIODS.items():
        for nov in (False, True):
            b = bets(w, "total", "open", 3.0, ss)
            b = b.assign(sz=size(b), under=b["side"] if "side" in b else None)
            b["under"] = (b["final_total"] - b["line"]) < 0
            if nov:
                b = b[pd.to_datetime(b["date"]).dt.month == 11]
            for (u, sz), g in b.groupby(["under", "sz"], observed=True):
                r = record(g)
                rows.append({"period": per, "nov only": nov, "side": "Under" if u else "Over", "|spread|": sz,
                             "plays": r["plays"], "win%": round(r["win%"], 1), "ROI%": r["ROI%"],
                             "move to us": round(g["clv"].mean(), 2)})
            d = w[w["season"].between(*ss)].dropna(subset=["total", "points"])
            if nov:
                d = d[pd.to_datetime(d["date"]).dt.month == 11]
            d = d.assign(sz=size(d))
            for sz, g in d.groupby("sz", observed=True):
                games.append({"period": per, "nov only": nov, "|spread|": sz, "games": len(g),
                              "actual - close": round((g["points"] - g["total"]).mean(), 2),
                              "actual - model": round((g["points"] - g["final_total"]).mean(), 2),
                              "model - close": round((g["final_total"] - g["total"]).mean(), 2)})
    P, G = pd.DataFrame(rows), pd.DataFrame(games)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    say("Opener total plays (edge 3+), by side and |spread|:\n" + P.to_string(index=False))
    say("\nAll games, totals by |spread|:\n" + G.to_string(index=False))
    u = P[(P["side"] == "Under") & (~P["nov only"])]
    checks = []
    for per in PERIODS:
        x = u[u["period"] == per]
        big = x[x["|spread|"].isin(["15-20", "20+"])]
        small = x[x["|spread|"].isin(["<10", "10-15"])]
        wb = (big["win%"] * big["plays"]).sum() / big["plays"].sum()
        ws = (small["win%"] * small["plays"]).sum() / small["plays"].sum()
        mb = (big["move to us"] * big["plays"]).sum() / big["plays"].sum()
        checks.append((per, round(wb, 1), round(ws, 1), round(mb, 2), wb < 50 and wb < ws and mb <= 0))
        say(f"\n{per}: Unders |spread| 15+ win {wb:.1f}% ({int(big['plays'].sum())} plays), under 15 {ws:.1f}%; "
            f"move to us on 15+ {mb:+.2f}")
    say(f"\nDecision rule (PLAN.md): {'PASS -> test a change' if all(c[-1] for c in checks) else 'no'}")
    os.makedirs(OUT, exist_ok=True)
    P.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    G.to_csv(os.path.join(OUT, "games.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
