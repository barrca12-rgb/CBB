"""Part 1 diagnostics (PLAN.md): why totals are weaker in 2025-26 and from January. Descriptive only.

    python -m research.totals_late.diag
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.originator.d_common import frames, oriented_openers, walk_forward

OUT = os.path.join(os.path.dirname(__file__), "out")
ERAS = {"dev 2014-17": [2014, 2015, 2016, 2017], "2023-24": [2024], "2024-25": [2025], "2025-26": [2026]}


def plays(w: pd.DataFrame) -> pd.DataFrame:
    """The frozen totals rule's plays (edge 3+ against the opener), with side, CLV and results vs opener and close."""
    d = w[~evaluate.swapped(w.assign(pred_margin=w["final_margin"]))].dropna(subset=["open_total", "total"]).copy()
    d["actual"] = d["home_pts"] + d["away_pts"]
    d["edge"] = d["final_total"] - d["open_total"]
    d = d[d["edge"].abs() >= 3].copy()
    d["sgn"] = np.sign(d["edge"])
    d["side"] = np.where(d["sgn"] > 0, "over", "under")
    d["clv"] = (d["total"] - d["open_total"]) * d["sgn"]
    d["res_open"] = (d["actual"] - d["open_total"]) * d["sgn"]
    d["res_close"] = (d["actual"] - d["total"]) * d["sgn"]
    m = pd.to_datetime(d["date"]).dt.month
    d["half"] = np.where(m.isin([11, 12]), "Nov-Dec", "Jan-Mar")
    d["month"] = m
    return d


def summ(g: pd.DataFrame) -> pd.Series:
    wo, wc = g["res_open"][g["res_open"] != 0], g["res_close"][g["res_close"] != 0]
    return pd.Series({"plays": len(g), "win% open": 100 * (wo > 0).mean(), "win% close": 100 * (wc > 0).mean(),
                      "CLV": g["clv"].mean(), "edge": g["edge"].abs().mean(),
                      "CLV/edge": g["clv"].mean() / g["edge"].abs().mean()})


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    w = oriented_openers(walk_forward(train, pred))
    w.to_pickle(os.path.join(OUT, "frozen_wf.pkl"))
    p = plays(w)
    era = {s: k for k, ss in ERAS.items() for s in ss}
    p["era"] = p["season"].map(era)
    p = p.dropna(subset=["era"])
    pd.set_option("display.width", 250, "display.max_rows", 200)
    txt = []

    def show(title, df):
        txt.append(f"\n## {title}\n" + df.round(2).to_string())

    show("Overall by era and half", p.groupby(["era", "half"]).apply(summ))
    show("1. Side", p.groupby(["era", "half", "side"]).apply(summ))
    p["band"] = pd.cut(p["edge"].abs(), [3, 4, 6, 99], right=False, labels=["3-4", "4-6", "6+"])
    show("4. Edge size", p.groupby(["era", "half", "band"], observed=True).apply(summ))
    p["gtype"] = np.where(p["month"] == 3, "March", np.where(p["conf_game"].astype(bool), "conference", "non-conference"))
    show("5a. Game type", p.groupby(["era", "half", "gtype"]).apply(summ))
    p["level"] = pd.cut(p["open_total"], [0, 140, 150, 999], right=False, labels=["<140", "140-150", "150+"])
    show("5b. Opener total level", p.groupby(["era", "half", "level"], observed=True).apply(summ))

    # 2 and 6: bias of model, opener and close against the actual total, all games with lines, by month
    a = w.dropna(subset=["open_total", "total"]).copy()
    a["era"] = a["season"].map(era)
    a = a.dropna(subset=["era"])
    a["actual"] = a["home_pts"] + a["away_pts"]
    a["month"] = pd.to_datetime(a["date"]).dt.month
    b = a.groupby(["era", "month"]).apply(lambda g: pd.Series({
        "games": len(g), "actual": g["actual"].mean(),
        "model - actual": (g["final_total"] - g["actual"]).mean(),
        "opener - actual": (g["open_total"] - g["actual"]).mean(),
        "close - actual": (g["total"] - g["actual"]).mean(),
        "model - opener": (g["final_total"] - g["open_total"]).mean(),
        "model MAE": (g["final_total"] - g["actual"]).abs().mean(),
        "opener MAE": (g["open_total"] - g["actual"]).abs().mean(),
        "close MAE": (g["total"] - g["actual"]).abs().mean()}))
    show("2/6. Bias and accuracy by month (all games with lines)", b)
    out = "\n".join(txt)
    open(os.path.join(OUT, "diag.txt"), "w").write(out)
    p.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    print(out)


if __name__ == "__main__":
    main()
