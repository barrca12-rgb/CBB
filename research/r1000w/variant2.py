"""Variant 2 (PLAN.md): ridge-1,000 plus the blowout term. Research only.

    python -m research.r1000w.variant2      # -> out/variant2.txt
"""
from __future__ import annotations

import os

import pandas as pd

from audit.common import bets, frame, record
from research.blowout_fix.backtest import apply, fit
from research.r1000w.backtest import OUT, mae, walk

L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def main() -> None:
    w = frame(tag="base")
    base = walk(w, 1000.0, None, range(2020, 2027))
    parts, fits = [], {}
    for s in range(2023, 2027):
        T, k = fit(base[base["season"].between(s - 3, s - 1)])
        fits[s] = (T, k)
        parts.append(apply(base[base["season"] == s], T, k))
    v2 = pd.concat(parts)
    r1 = base[base["season"].between(2023, 2026)]
    live_fit = fit(base[base["season"].between(2023, 2026)])
    say("Fits (season: T, k): " + ", ".join(f"{s}: {t}, {k}" for s, (t, k) in fits.items()) + f"; live fit {live_fit}")
    rows = []
    for name, d in (("ridge-1,000", r1), ("ridge-1,000 + blowout", v2)):
        m, t = mae(d)
        big = d[d["final_margin"].abs() >= 20]
        bm, bt = mae(big)
        row = {"model": name, "2023-26 margin": round(m, 4), "2023-26 total": round(t, 4),
               "20+ margin": round(bm, 4), "20+ total": round(bt, 4)}
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            b = bets(d, mk, "open", thr, (2024, 2026))
            r = record(b)
            row[f"{mk} plays"], row[f"{mk} win%"], row[f"{mk} move"] = r["plays"], round(r["win%"], 2), round(b["clv"].mean(), 3)
        rows.append(row)
    A = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    say(A.to_string(index=False))
    a, b = A.iloc[0], A.iloc[1]
    c1 = b["2023-26 margin"] < a["2023-26 margin"] and b["2023-26 total"] < a["2023-26 total"]
    c2 = b["spread win%"] >= a["spread win%"] - 0.3 and b["total win%"] >= a["total win%"] - 0.3
    say(f"Shadow rule: errors below ridge-1,000 {c1}; opener win % within 0.3 {c2} -> {'RUN AS SHADOW' if c1 and c2 else 'do not run'}")
    os.makedirs(OUT, exist_ok=True)
    A.to_csv(os.path.join(OUT, "variant2.csv"), index=False)
    open(os.path.join(OUT, "variant2.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
