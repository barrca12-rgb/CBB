"""Selection cut (PLAN.md). Research only.   python -m research.selection_cut.backtest"""
from __future__ import annotations
import os
import pandas as pd
from audit.common import bets, frame, record
from cbb import projection as P

OUT = os.path.join(os.path.dirname(__file__), "out")
PER = {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}


def main():
    w = P.blowout(frame(tag="base"))
    rows = []
    for per, ss in PER.items():
        for mk, ths in (("spread", (2.5, 3.0, 3.5, 4.0)), ("total", (3.0, 3.5, 4.0, 4.5))):
            for vs in ("open", "close"):
                for th in ths:
                    b = bets(w, mk, vs, th, ss)
                    r = record(b)
                    rows.append({"period": per, "market": mk, "vs": vs, "edge>=": th, "plays": r["plays"],
                                 "win%": round(r["win%"], 2), "units": r["units@-110"], "ROI%": r["ROI%"]})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200); pd.set_option("display.max_rows", 100)
    print(t.to_string(index=False))
    os.makedirs(OUT, exist_ok=True)
    t.to_csv(os.path.join(OUT, "results.csv"), index=False)


if __name__ == "__main__":
    main()
