"""Step 1: verify and reproduce the frozen baseline (research/quant/LOG.md).

    python -m research.quant.baseline
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import walk_forward
from research.quant.common import CONF, DEV, OUT, SEASONS, base_frames, boot, fit_predict, plays, scorecard


def main() -> None:
    train, pred = base_frames()
    L = []
    # 1. the research walk-forward equals the production walk_forward and d_common.walk_forward
    w = fit_predict(train, pred)
    wf = walk_forward(train, pred)
    wf = wf[wf["season"].isin(SEASONS)].set_index("game_id")
    a = w.set_index("game_id")
    L.append(f"max |fit_predict - d_common.walk_forward|: margin {np.abs(a['final_margin'] - wf['final_margin']).max():.2e}, "
             f"total {np.abs(a['final_total'] - wf['final_total']).max():.2e}")
    # 2. refit on 2013-2026 reproduces the live coefficients in data/projection.json
    live = json.load(open(os.path.join("data", "projection.json")))
    c = projection.coefficients(train, 2027)
    dm = max(abs(c.loc[k, "margin"] - v) for k, v in live["margin"].items())
    dt = max(abs(c.loc[k, "total"] - v) for k, v in live["total"].items())
    L.append(f"max |refit 2013-26 coefficient - live projection.json|: margin {dm:.2e}, total {dt:.2e}")
    # ridge lambda 1 vs OLS on ~70k rows: is the penalty doing anything?
    w0 = fit_predict(train, pred, lam=1e-9)
    L.append(f"max |lambda 1 - OLS| prediction: margin {np.abs(w['final_margin'] - w0['final_margin']).max():.4f}, "
             f"total {np.abs(w['final_total'] - w0['final_total']).max():.4f}")
    # 3. scorecards by season and by era
    rows = [scorecard(w, [s], "frozen") for s in SEASONS]
    rows += [scorecard(w, DEV, "frozen"), scorecard(w, CONF, "frozen"), scorecard(w, range(2020, 2027), "frozen")]
    sc = pd.DataFrame(rows)
    # the closing line's own MAE, same games
    for i, r in sc.iterrows():
        lo, hi = map(int, r["seasons"].split("-"))
        d = w[w["season"].between(lo, hi)].dropna(subset=["home_spread", "total"])
        sc.loc[i, "close margin MAE"] = float((d["margin"] + d["home_spread"]).abs().mean())
        sc.loc[i, "close total MAE"] = float((d["points"] - d["total"]).abs().mean())
        sc.loc[i, "model margin MAE (close games)"] = float((d["margin"] - d["final_margin"]).abs().mean())
        sc.loc[i, "model total MAE (close games)"] = float((d["points"] - d["final_total"]).abs().mean())
    # 4. calibration: slope of result on prediction, and on prediction-minus-line
    cal = []
    for s0, s1 in ((2014, 2019), (2020, 2026)):
        d = w[w["season"].between(s0, s1)].dropna(subset=["home_spread", "total"])
        d = d[~d["swapped"]]
        for mk, y, f, ln in (("margin", d["margin"], d["final_margin"], -d["home_spread"]),
                             ("total", d["points"], d["final_total"], d["total"])):
            b1 = np.polyfit(f, y, 1)[0]
            b2 = np.polyfit(f - ln, y - ln, 1)[0]
            cal.append({"period": f"{s0}-{s1}", "market": mk, "slope result~model": round(b1, 3),
                        "slope (result-close)~(model-close)": round(b2, 3), "mean resid": round(float((y - f).mean()), 3)})
    # 5. opener plays with intervals
    iv = []
    for era, ss in (("dev 2015-17", DEV), ("conf 2024-26", CONF)):
        for mk in ("spread", "total"):
            p = plays(w[w["season"].isin(ss)], mk).dropna(subset=["win"])
            m, lo, hi = boot(p["win"] * 100, p["date"])
            c_, clo, chi = boot(p["clv"], p["date"])
            iv.append({"era": era, "market": mk, "plays": len(p), "win%": round(m, 2), "win% 95%": f"[{lo:.1f}, {hi:.1f}]",
                       "CLV": round(c_, 3), "CLV 95%": f"[{clo:.2f}, {chi:.2f}]"})
    pd.set_option("display.width", 250)
    txt = "\n".join(L) + "\n\n" + sc.round(3).to_string(index=False) + "\n\n" + pd.DataFrame(cal).to_string(index=False) + \
        "\n\n" + pd.DataFrame(iv).to_string(index=False) + "\n"
    open(os.path.join(OUT, "baseline_run.txt"), "w").write(txt)
    sc.to_csv(os.path.join(OUT, "baseline_by_season.csv"), index=False)
    w[["game_id", "season", "date", "final_margin", "final_total"]].to_csv(os.path.join(OUT, "baseline_preds.csv.gz"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
