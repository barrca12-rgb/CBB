"""C2 scoring: stage-1 MAE of each functional form against the frozen additive form, then each form's stage-1 file
through the unchanged stage 2 on the standard scoreboard. Needs c2_forms.py's output.

    python -m research.frontier.c2_score
"""
from __future__ import annotations

import os

import pandas as pd

from research.frontier.common import clv_gains, scoreboard
from research.originator.d_common import AUDIT, frames, walk_forward

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
FILES = {"additive (frozen)": os.path.join(AUDIT, "_stage1_base", "backtest_2013_2026.csv"),
         "mult": os.path.join(OUT, "c2_mult", "backtest_2013_2026.csv"),
         "poisson": os.path.join(OUT, "c2_poisson", "backtest_2013_2026.csv")}


def main() -> None:
    lines, s1 = [], {}
    for k, f in FILES.items():
        b = pd.read_csv(f)
        b["me"] = (b["home_pts"] - b["away_pts"] - b["pred_margin"]).abs()
        b["te"] = (b["home_pts"] + b["away_pts"] - b["pred_total"]).abs()
        s1[k] = b.groupby("season")[["me", "te"]].mean()
        for lab, ss in (("2014-26", range(2014, 2027)), ("2020-26", range(2020, 2027))):
            x = b[b["season"].isin(list(ss))]
            lines.append(f"Stage-1 {k:18s} {lab}: margin MAE {x['me'].mean():.4f}, total MAE {x['te'].mean():.4f}, n {len(x)}")
    per = pd.concat({k: v for k, v in s1.items()}, axis=1).round(4)
    lines.append("\nStage-1 MAE by season:\n" + per.to_string())
    fits = {}
    for k, f in FILES.items():
        tag = "frozen" if k.startswith("additive") else f"c2_{k}"
        tr, pr = frames(None if tag == "frozen" else f, tag)
        fits["frozen" if tag == "frozen" else k] = walk_forward(tr, pr)
    t = scoreboard(fits)
    for k in ("mult", "poisson"):
        g = clv_gains(t, k)
        lines.append(f"{k}: opener CLV gain (dev, conf): " + "; ".join(f"{m} {a:+.3f}, {c:+.3f}" for m, (a, c) in g.items()))
    t.T.to_csv(os.path.join(OUT, "c2_result.csv"))
    txt = "\n".join(lines) + "\n\n" + t.T.to_string()
    open(os.path.join(OUT, "c2_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
