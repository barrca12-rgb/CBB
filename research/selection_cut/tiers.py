"""Test 3 (PLAN.md): stake by edge.   python -m research.selection_cut.tiers"""
import numpy as np, pandas as pd
from audit.common import bets, frame
from cbb import projection as P
w = P.blowout(frame(tag="base"))
pay = 100 / 110
rows = []
for per, ss in {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}.items():
    for mk, bar in (("spread", 2.5), ("total", 3.0)):
        b = bets(w, mk, "open", bar, ss)
        r = np.where(b["res"] > 0, pay, np.where(b["res"] < 0, -1.0, 0.0))
        for name, st in (("flat 1u", np.ones(len(b))),
                         ("tiers 1/1.5/2", np.where(b["edge"] >= bar + 2, 2.0, np.where(b["edge"] >= bar + 1, 1.5, 1.0)))):
            u = (r * st).sum()
            rows.append({"period": per, "market": mk, "stakes": name, "plays": len(b), "risked": round(st.sum(), 1),
                         "units": round(u, 1), "ROI%": round(100 * u / st.sum(), 2)})
        for lo, hi in ((bar, bar + 1), (bar + 1, bar + 2), (bar + 2, 99)):
            x = b[(b["edge"] >= lo) & (b["edge"] < hi)]
            wins = (x["res"] > 0).sum(); dec = (x["res"] != 0).sum()
            rows.append({"period": per, "market": mk, "stakes": f"edge {lo}-{hi if hi < 99 else '+'}", "plays": len(x),
                         "risked": None, "units": None, "ROI%": round(100 * ((wins * pay - (dec - wins)) / len(x)), 2) if len(x) else None,
                         "win%": round(100 * wins / dec, 1) if dec else None})
t = pd.DataFrame(rows); pd.set_option("display.width", 200); print(t.to_string(index=False))
t.to_csv("research/selection_cut/out/tiers.csv", index=False)
