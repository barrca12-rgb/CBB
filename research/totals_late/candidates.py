"""Part 2 (PLAN.md): the four pre-registered totals adjustments against the frozen model. Choose on dev (2014-17 +
2023-24), confirm on holdout (2024-25 + 2025-26). Kill rule in PLAN.md.

    python -m research.totals_late.candidates
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.originator.d_common import frames, oriented_openers, walk_forward
from research.totals_late.diag import OUT, plays

ERAS = {"dev": [2014, 2015, 2016, 2017, 2024], "holdout": [2025, 2026]}


def rule(p: pd.DataFrame, late_thr: float = 3.0, late_under_thr: float = 3.0) -> pd.DataFrame:
    """Keep plays clearing the threshold for their half and side (early stays 3)."""
    thr = np.where(p["half"] == "Jan-Mar", np.where(p["side"] == "under", np.maximum(late_thr, late_under_thr), late_thr), 3.0)
    return p[p["edge"].abs() >= thr]


def score(p: pd.DataFrame) -> dict:
    out = {}
    for h in ("Nov-Dec", "Jan-Mar"):
        g = p[p["half"] == h]
        dec = g["res_open"][g["res_open"] != 0]
        win = 100 * (dec > 0).mean() if len(dec) else np.nan
        c = g["clv"].to_numpy(float)
        dev = pd.Series(c - c.mean()).groupby(g["date"].to_numpy()).sum().to_numpy()
        out.update({f"{h} plays": len(g), f"{h} win%": win, f"{h} ROI%": win * 100 / 110 / 100 * 100 - (100 - win),
                    f"{h} CLV": c.mean(), f"{h} CLV se": np.sqrt((dev ** 2).sum()) / len(c)})
    return out


def main() -> None:
    train, pred = frames()
    base_w = pd.read_pickle(os.path.join(OUT, "frozen_wf.pkl"))
    reg = oriented_openers(walk_forward(train, pred, regimes=True))
    rec = oriented_openers(walk_forward(train, pred, half_life=2))
    swap = lambda w: base_w.drop(columns=["final_total"]).merge(w[["game_id", "final_total"]], on="game_id")
    variants = {"frozen": plays(base_w),
                "(a) late threshold 4": rule(plays(base_w), late_thr=4),
                "(b) two-regime totals fit": plays(swap(reg)),
                "(c) recency weights h=2 (totals)": plays(swap(rec)),
                "(d) late unders threshold 4": rule(plays(base_w), late_under_thr=4)}
    rows = []
    for k, p in variants.items():
        for era, ss in ERAS.items():
            rows.append({"variant": k, "era": era, **score(p[p["season"].isin(ss)])})
    t = pd.DataFrame(rows)
    f = t[t["variant"] == "frozen"].set_index("era")
    for c in ("Jan-Mar win%", "Jan-Mar CLV", "Nov-Dec win%", "Nov-Dec CLV", "Jan-Mar plays"):
        t[f"d {c}"] = t.apply(lambda r: r[c] - f.loc[r["era"], c], axis=1)
    t["late plays kept"] = t.apply(lambda r: r["Jan-Mar plays"] / f.loc[r["era"], "Jan-Mar plays"], axis=1)

    def passes(v):
        x = t[t["variant"] == v].set_index("era")
        ok = all((x.loc[e, "d Jan-Mar win%"] >= 1.0) and (x.loc[e, "d Jan-Mar CLV"] > -0.1)
                 and (x.loc[e, "d Nov-Dec CLV"] > -0.1) and (x.loc[e, "d Nov-Dec win%"] > -1.0) for e in ERAS)
        if v.startswith(("(a)", "(d)")):
            ok = ok and all(x.loc[e, "late plays kept"] >= 0.6 for e in ERAS)
        return "SURVIVES" if ok else "KILL"
    verdict = {v: passes(v) for v in variants if v != "frozen"}
    pd.set_option("display.width", 250)
    cols = ["variant", "era", "Jan-Mar plays", "Jan-Mar win%", "Jan-Mar ROI%", "Jan-Mar CLV", "Jan-Mar CLV se",
            "Nov-Dec plays", "Nov-Dec win%", "Nov-Dec CLV", "d Jan-Mar win%", "d Jan-Mar CLV", "d Nov-Dec win%",
            "d Nov-Dec CLV", "late plays kept"]
    txt = t[cols].round(3).to_string(index=False) + "\n\nVerdicts: " + "; ".join(f"{k}: {v}" for k, v in verdict.items())
    open(os.path.join(OUT, "candidates.txt"), "w").write(txt)
    t.to_csv(os.path.join(OUT, "candidates.csv"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
