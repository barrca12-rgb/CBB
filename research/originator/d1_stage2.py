"""Part D1: recency-weighted and two-regime stage 2 (pre-registered in LOG.md).

    python -m research.originator.d1_stage2
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.originator.d_common import OUT, clv, frames, info_beyond_close, mae, oriented_openers, walk_forward

VARIANTS = {"frozen (refit check)": {}, "recency h=2": {"half_life": 2.0}, "recency h=4": {"half_life": 4.0},
            "two regimes": {"regimes": True}, "two regimes + h=4": {"regimes": True, "half_life": 4.0}}


def main() -> None:
    train, pred = frames()
    bench = pd.read_pickle(os.path.join(os.path.dirname(__file__), "..", "..", "audit", "out", "wf_live_approx.pkl"))
    rows, fits = [], {}
    for name, kw in VARIANTS.items():
        w = oriented_openers(walk_forward(train, pred, **kw))
        fits[name] = w
        r = {"variant": name}
        for era, seasons in (("dev 2014-17", range(2014, 2018)), ("confirm 2024-26", range(2024, 2027))):
            c = clv(w, seasons)
            r.update({f"{era} CLV combined": c["combined CLV"], f"{era} spread CLV": c["spread CLV"],
                      f"{era} total CLV": c["total CLV"], f"{era} plays": c["spread plays"] + c["total plays"]})
        r.update({f"MAE 2020-26 {k}": v for k, v in mae(w, range(2020, 2027)).items()})
        rows.append(r)
        print(name, "done", flush=True)
    t = pd.DataFrame(rows)
    base = fits["frozen (refit check)"]
    chk = base.merge(bench[["game_id", "final_margin"]], on="game_id", suffixes=("", "_bench"))
    print("refit check vs wf_live_approx: max |margin diff| =", float((chk["final_margin"] - chk["final_margin_bench"]).abs().max()))
    for k in ("dev 2014-17 CLV combined", "confirm 2024-26 CLV combined"):
        t[f"{k} gain"] = t[k] - float(t.loc[t["variant"] == "frozen (refit check)", k].iloc[0])
    t["kill (<0.1 gain in either era)"] = (t["dev 2014-17 CLV combined gain"] < 0.1) | (t["confirm 2024-26 CLV combined gain"] < 0.1)
    info = pd.DataFrame([{"variant": n, **info_beyond_close(w, base, range(2020, 2027))} for n, w in fits.items() if n != "frozen (refit check)"])
    t.to_csv(os.path.join(OUT, "d1_results.csv"), index=False)
    info.to_csv(os.path.join(OUT, "d1_info.csv"), index=False)
    pd.set_option("display.width", 250)
    print(t.round(4).to_string(index=False))
    print(info.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
