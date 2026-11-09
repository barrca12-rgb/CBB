"""Prior speed (PLAN.md).   python -m research.prior_speed.backtest"""
import os
import numpy as np
import pandas as pd
from audit.common import bets, frame, record
from cbb import projection as P

ROOT = os.path.join(os.path.dirname(__file__), "..", "originator", "out")
V = {"prior 6 (live)": None, "prior 3 (faster)": "stage1_prior3.csv", "prior 12 (slower)": "stage1_prior12.csv"}


def main():
    L, rows, plays = [], [], []
    for name, f in V.items():
        w = frame(tag="base") if f is None else frame(stage1=os.path.join(ROOT, f), tag="ps_" + f[7:-4])
        w = P.blowout(w)
        d = pd.to_datetime(w["date"])
        start = d.groupby(w["season"]).transform("min")
        early = (d - start).dt.days < 30
        for era, (a, b) in {"2014-19": (2014, 2019), "2020-26": (2020, 2026)}.items():
            x = w[early & w["season"].between(a, b)].dropna(subset=["margin", "points"])
            rows.append({"variant": name, "era": era, "early games": len(x),
                         "margin MAE": round((x["margin"] - x["final_margin"]).abs().mean(), 4),
                         "total MAE": round((x["points"] - x["final_total"]).abs().mean(), 4)})
        for per, ss in {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}.items():
            for mk, th in (("spread", 2.5), ("total", 3.0)):
                r = record(bets(w, mk, "open", th, ss))
                plays.append({"variant": name, "market": mk, "period": per, "plays": r["plays"], "win%": round(r["win%"], 2), "units": r["units@-110"]})
    A, B = pd.DataFrame(rows), pd.DataFrame(plays)
    pd.set_option("display.width", 200)
    L += ["Early season (first 30 days):", A.to_string(index=False), "", "Opener plays:", B.to_string(index=False)]
    base = "prior 6 (live)"
    for v in V:
        if v == base:
            continue
        a = lambda vv, era, c: A[(A.variant == vv) & (A.era == era)][c].iat[0]
        c1 = all(a(v, e, c) < a(base, e, c) for e in ("2014-19", "2020-26") for c in ("margin MAE", "total MAE"))
        dd = [B[(B.variant == v) & (B.market == m) & (B.period == p)]["win%"].iat[0] - B[(B.variant == base) & (B.market == m) & (B.period == p)]["win%"].iat[0]
              for m in ("spread", "total") for p in ("2015-17", "2024-26")]
        ok = c1 and min(dd) >= -0.3 and max(dd) > 0
        L.append(f"{v}: early errors lower in both eras {c1}; win% changes {['%+.2f' % x for x in dd]} -> {'SHIP' if ok else 'no'}")
    print("\n".join(L))
    os.makedirs("research/prior_speed/out", exist_ok=True)
    open("research/prior_speed/out/results.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
