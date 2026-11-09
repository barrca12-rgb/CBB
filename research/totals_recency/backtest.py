"""Totals with recency weights (PLAN.md).   python -m research.totals_recency.backtest"""
import os
import numpy as np
import pandas as pd
from audit.common import bets, frame, record
from cbb import projection as P
from research.r1000w.backtest import wridge

OUT = os.path.join(os.path.dirname(__file__), "out")


def walk(w, H, seasons):
    parts = []
    for s in seasons:
        tr = w[w["season"] < s].dropna(subset=["points"])
        wt = np.ones(len(tr)) if H is None else 0.5 ** ((s - 1 - tr["season"].to_numpy()) / H)
        ct = wridge(tr[P.TOTAL_FEATURES].to_numpy(float), tr["points"].to_numpy(float), wt / wt.mean(), 1.0)
        te = w[w["season"] == s].copy()
        te["final_total"] = ct[0] + te[P.TOTAL_FEATURES].to_numpy(float) @ ct[1:]
        parts.append(te)
    return P.blowout(pd.concat(parts))


def mae(d):
    d = d.dropna(subset=["points"])
    return float((d["points"] - d["final_total"]).abs().mean())


def main():
    w = frame(tag="base")
    L = []
    sel = {H: mae(walk(w, H, range(2019, 2023))) for H in (None, 1, 2, 3, 5)}
    L.append("2019-22 total error: " + ", ".join(f"H={h}: {v:.4f}" for h, v in sel.items()))
    best = min((h for h in sel if h is not None), key=lambda h: sel[h])
    L.append(f"chosen H = {best}")
    seasons = sorted(w["season"].unique())[1:]
    base, new = walk(w, None, seasons), walk(w, best, seasons)
    hb, hn = mae(base[base.season.between(2023, 2026)]), mae(new[new.season.between(2023, 2026)])
    L.append(f"2023-26 total error: base {hb:.4f} -> recency {hn:.4f}")
    rows = []
    for tag, d in (("base", base), ("recency", new)):
        for per, ss in {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}.items():
            b = bets(d, "total", "open", 3.0, ss)
            r = record(b)
            rows.append({"model": tag, "period": per, "plays": r["plays"], "win%": round(r["win%"], 2), "units": r["units@-110"], "move": round(b["clv"].mean(), 3)})
    t = pd.DataFrame(rows)
    L.append(t.to_string(index=False))
    g = lambda m, p: t[(t.model == m) & (t.period == p)]["win%"].iat[0]
    d = [g("recency", p) - g("base", p) for p in ("2015-17", "2024-26")]
    ok = hn < hb and min(d) >= -0.3 and max(d) > 0
    L.append(f"Ship rule: error lower {hn < hb}; win% change {d[0]:+.2f} / {d[1]:+.2f} -> {'SHIP' if ok else 'do not ship'}")
    print("\n".join(L))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
