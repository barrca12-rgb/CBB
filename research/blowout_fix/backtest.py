"""Blowout correction (PLAN.md). Research only.

    python -m research.blowout_fix.backtest     # -> out/results.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import bets, frame, record

OUT = os.path.join(os.path.dirname(__file__), "out")
TS, KS = range(16, 30, 2), np.round(np.arange(0, 0.41, 0.02), 2)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def apply(w: pd.DataFrame, T: float, k: float) -> pd.DataFrame:
    M = w["final_margin"].abs()
    x = k * np.maximum(0, M - T)
    s = np.sign(w["final_margin"]).replace(0, 1)
    return w.assign(final_margin=w["final_margin"] + s * x, final_total=w["final_total"] + x)


def fit(tr: pd.DataFrame) -> tuple[float, float]:
    tr = tr.dropna(subset=["margin", "points"])
    best, arg = None, (TS[0], 0.0)
    for T in TS:
        for k in KS:
            a = apply(tr, T, k)
            sse = ((a["margin"] - a["final_margin"]) ** 2).sum() + ((a["points"] - a["final_total"]) ** 2).sum()
            if best is None or sse < best:
                best, arg = sse, (T, k)
    return arg


def main() -> None:
    w = frame(tag="base")
    parts, fits = [], {}
    for s in range(2023, 2027):
        T, k = fit(w[w["season"].between(s - 3, s - 1)])
        fits[s] = (T, k)
        parts.append(apply(w[w["season"] == s], T, k))
    new = pd.concat(parts)
    old = w[w["season"].between(2023, 2026)].loc[new.index]
    say("Walk-forward fits (season: T, k): " + ", ".join(f"{s}: {t}, {k}" for s, (t, k) in fits.items()))
    say(f"Live fit on 2023-2026: T, k = {fit(w[w['season'].between(2023, 2026)])}")
    rows = []
    for lab, m in (("all games", slice(None)), ("model margin 20+", old["final_margin"].abs() >= 20),
                   ("model margin 25+", old["final_margin"].abs() >= 25)):
        for tag, d in (("base", old), ("corrected", new)):
            x = d[m] if lab != "all games" else d
            x = x.dropna(subset=["margin", "points"])
            rows.append({"games": lab, "model": tag, "n": len(x),
                         "margin MAE": round((x["margin"] - x["final_margin"]).abs().mean(), 4),
                         "total MAE": round((x["points"] - x["final_total"]).abs().mean(), 4),
                         "total bias": round((x["points"] - x["final_total"]).mean(), 2)})
    A = pd.DataFrame(rows)
    say("\nAccuracy 2023-2026 (out of sample):\n" + A.to_string(index=False))
    prow = []
    for tag, d in (("base", old), ("corrected", new)):
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            b = bets(d, mk, "open", thr, (2024, 2026))
            big = b[b["open_home_spread"].fillna(b["home_spread"]).abs() >= 20]
            for lab, x in (("all", b), ("|spread| 20+", big)):
                r = record(x)
                prow.append({"model": tag, "market": mk, "plays": lab, "n": r["plays"], "win%": round(r["win%"], 2),
                             "ROI%": r["ROI%"], "move to us": round(x["clv"].mean(), 2)})
    P = pd.DataFrame(prow)
    pd.set_option("display.width", 250)
    say("\nOpener plays 2024-26:\n" + P.to_string(index=False))
    g = lambda lab, tag, col: A[(A.games == lab) & (A.model == tag)][col].iat[0]
    c1 = all(g("model margin 20+", "corrected", c) < g("model margin 20+", "base", c) for c in ("margin MAE", "total MAE"))
    c2 = all(g("all games", "corrected", c) <= g("all games", "base", c) + 0.005 for c in ("margin MAE", "total MAE"))
    pw = lambda tag, mk: P[(P.model == tag) & (P.market == mk) & (P.plays == "all")]["win%"].iat[0]
    c3 = all(pw("corrected", mk) >= pw("base", mk) - 0.3 for mk in ("spread", "total"))
    say(f"\nShip rule: 20+ errors fall {c1}; all-games errors not worse {c2}; opener win % within 0.3 {c3} -> "
        f"{'SHIP' if c1 and c2 and c3 else 'do not ship'}")
    os.makedirs(OUT, exist_ok=True)
    A.to_csv(os.path.join(OUT, "accuracy.csv"), index=False)
    P.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
