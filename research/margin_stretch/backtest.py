"""Margin stretch (PLAN.md). Research only.   python -m research.margin_stretch.backtest"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from audit.common import bets, frame, record
from cbb import projection as P

OUT = os.path.join(os.path.dirname(__file__), "out")
KS = np.round(np.arange(0.94, 1.201, 0.01), 2)


def fitk(tr):
    tr = tr.dropna(subset=["margin"])
    errs = [(tr["margin"] - k * tr["final_margin"]).abs().mean() for k in KS]
    return float(KS[int(np.argmin(errs))])


def main():
    w = P.blowout(frame(tag="base"))
    parts, ks = [], {}
    for s in sorted(w["season"].unique()):
        tr = w[w["season"].between(s - 3, s - 1)]
        k = fitk(tr) if tr["season"].nunique() >= 2 else 1.0
        ks[int(s)] = k
        parts.append(w[w["season"] == s].assign(final_margin=lambda d: d["final_margin"] * k))
    new = pd.concat(parts).loc[w.index]
    lines = ["k by season (fit on the 3 before): " + ", ".join(f"{s}: {k}" for s, k in ks.items()),
             f"live k (fit on 2024-2026): {fitk(w[w['season'].between(2024, 2026)])}"]
    o, n = w[w["season"].between(2023, 2026)].dropna(subset=["margin"]), new[new["season"].between(2023, 2026)].dropna(subset=["margin"])
    lines.append(f"margin MAE 2023-26: base {(o['margin'] - o['final_margin']).abs().mean():.4f} -> stretched {(n['margin'] - n['final_margin']).abs().mean():.4f}")
    rows = []
    for tag, d in (("base", w), ("stretch", new)):
        for per, ss in {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}.items():
            b = bets(d, "spread", "open", 2.5, ss)
            fav_home = b["open_home_spread"].fillna(b["home_spread"]) < 0
            b["grp"] = np.where((b["side"] == "home") == fav_home, "fav", "dog")
            for lab, x in (("all", b), ("fav", b[b.grp == "fav"]), ("dog", b[b.grp == "dog"])):
                r = record(x)
                rows.append({"model": tag, "period": per, "plays": lab, "n": r["plays"], "win%": round(r["win%"], 2),
                             "units": r["units@-110"], "move": round(x["clv"].mean(), 3)})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    lines.append(t.to_string(index=False))
    g = lambda m, p: t[(t.model == m) & (t.period == p) & (t.plays == "all")]["win%"].iat[0]
    c1 = (n["margin"] - n["final_margin"]).abs().mean() < (o["margin"] - o["final_margin"]).abs().mean()
    d = [g("stretch", p) - g("base", p) for p in ("2015-17", "2024-26")]
    ok = c1 and min(d) >= -0.3 and max(d) > 0
    lines.append(f"Ship rule: margin error lower {c1}; win% change {d[0]:+.2f} / {d[1]:+.2f} -> {'SHIP' if ok else 'do not ship'}")
    print("\n".join(lines))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
