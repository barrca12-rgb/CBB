"""Crew pass (PLAN.md).   python -m research.crew_pass.backtest"""
import os
import pandas as pd
from audit.a2_timing import no_refs
from audit.common import bets, frame, record
from cbb import projection as P


def main():
    base = P.blowout(frame(tag="base"))
    nr = P.blowout(frame(tag="no_refs", features=no_refs))
    L = []
    for per, ss in {"2015-17": (2015, 2017), "2024-26": (2024, 2026)}.items():
        o = bets(nr, "total", "open", 3.0, ss)
        c = bets(base, "total", "close", 3.0, ss)
        new = c[~c["game_id"].isin(o["game_id"])]
        r = record(new)
        crew = new[(new["ref_pts"].abs() > 0) | (new["ref_fouls"].abs() > 0)] if "ref_pts" in new else new
        rc = record(crew)
        L.append(f"{per}: opener plays (no crew) {len(o)}; close plays (crew) {len(c)}; NEW {r['plays']} at "
                 f"{r['win%']:.2f}% (units {r['units@-110']}); new with a crew shift {rc['plays']} at {rc['win%']:.2f}%")
    print("\n".join(L))
    os.makedirs("research/crew_pass/out", exist_ok=True)
    open("research/crew_pass/out/results.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
