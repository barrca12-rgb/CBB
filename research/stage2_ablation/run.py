"""Stage-2 ablation (pre-registered in PLAN.md): the frozen live-like stage 2 refit without KenPom, without Barttorvik,
and without both; opener CLV (date-clustered SE), opener win % and MAE per market, era and half of the season.

    python -m research.stage2_ablation.run
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate, projection
from research.originator.d_common import frames, oriented_openers, walk_forward

OUT = os.path.join(os.path.dirname(__file__), "out")
KP = ["kp_margin", "kp_margin_x_early", "kp_total", "kp_total_x_early"]
BT = ["bt_margin", "bt_total"]
VARIANTS = {"frozen": [], "(a) no KenPom": KP, "(b) no Barttorvik": BT, "(c) neither": KP + BT}
ERAS = {"dev 2014-17": range(2014, 2018), "conf 2024-26": range(2024, 2027)}
HALVES = {"all": None, "Nov-Dec": (11, 12), "Jan-Mar": (1, 2, 3, 4)}


def fit_without(train, pred, drop):
    mf, tf = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
    try:
        projection.MARGIN_FEATURES = [f for f in mf if f not in drop]
        projection.TOTAL_FEATURES = [f for f in tf if f not in drop]
        return walk_forward(train, pred)
    finally:
        projection.MARGIN_FEATURES, projection.TOTAL_FEATURES = mf, tf


def _clustered(v: np.ndarray, dates: np.ndarray) -> tuple[float, float]:
    if len(v) < 2:
        return (float(v.mean()) if len(v) else np.nan), np.nan
    m = float(v.mean())
    g = pd.Series(v - m).groupby(dates).sum().to_numpy()
    return m, float(np.sqrt((g ** 2).sum()) / len(v))


def cell(w: pd.DataFrame, seasons, months) -> dict:
    """Opener CLV (mean, clustered SE, n) and opener win % of the frozen rule, plus MAE, for one era/half."""
    d = w[w["season"].isin(list(seasons))]
    if months:
        d = d[pd.to_datetime(d["date"]).dt.month.isin(months)]
    out = {"margin MAE": float((d["home_pts"] - d["away_pts"] - d["final_margin"]).abs().mean()),
           "total MAE": float((d["home_pts"] + d["away_pts"] - d["final_total"]).abs().mean())}
    d = d[~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))]
    sp = d.dropna(subset=["open_home_spread", "home_spread"])
    e = sp["final_margin"] + sp["open_home_spread"]
    s, side = sp[e.abs() >= 2.5], np.sign(e[e.abs() >= 2.5])
    lv = ((s["open_home_spread"] - s["home_spread"]) * side).to_numpy(float)
    res = ((s["home_pts"] - s["away_pts"] + s["open_home_spread"]) * side).to_numpy(float)
    to = d.dropna(subset=["open_total", "total"])
    e = to["final_total"] - to["open_total"]
    t, tside = to[e.abs() >= 3], np.sign(e[e.abs() >= 3])
    lvt = ((t["total"] - t["open_total"]) * tside).to_numpy(float)
    rest = ((t["home_pts"] + t["away_pts"] - t["open_total"]) * tside).to_numpy(float)
    for mk, v, r, dd in (("spread", lv, res, s["date"].to_numpy()), ("total", lvt, rest, t["date"].to_numpy())):
        m, se = _clustered(v, dd)
        dec = r[r != 0]
        out[f"{mk} CLV"], out[f"{mk} CLV se"], out[f"{mk} n"] = m, se, len(v)
        out[f"{mk} win%"] = 100 * float((dec > 0).mean()) if len(dec) else np.nan
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    fits = {k: oriented_openers(fit_without(train, pred, drop)) for k, drop in VARIANTS.items()}
    rows = []
    for k, w in fits.items():
        for era, ss in ERAS.items():
            for half, months in HALVES.items():
                rows.append({"variant": k, "era": era, "half": half, **cell(w, ss, months)})
    t = pd.DataFrame(rows)
    f = t[t["variant"] == "frozen"].set_index(["era", "half"])
    for c in ("spread CLV", "total CLV", "margin MAE", "spread win%", "total win%"):
        t[f"d {c}"] = t.apply(lambda r: r[c] - f.loc[(r["era"], r["half"]), c], axis=1)
    t.to_csv(os.path.join(OUT, "ablation.csv"), index=False)
    a = t[(t["variant"] == "(a) no KenPom") & (t["half"] != "all")]
    breach = a[(a["d spread CLV"].abs() >= 0.1) | (a["d total CLV"].abs() >= 0.1) | (a["d margin MAE"].abs() >= 0.02)]
    pd.set_option("display.width", 250, "display.max_rows", 100)
    show = t[["variant", "era", "half", "spread CLV", "spread CLV se", "spread n", "spread win%", "total CLV", "total CLV se",
              "total n", "total win%", "margin MAE", "d spread CLV", "d total CLV", "d margin MAE"]].round(3)
    txt = show.to_string(index=False) + "\n\nKill-rule breaches for (a) (|dCLV| >= 0.1 or |dMAE| >= 0.02, by era and half):\n" + \
        (breach[["era", "half", "d spread CLV", "d total CLV", "d margin MAE"]].round(3).to_string(index=False) if len(breach) else "none")
    open(os.path.join(OUT, "run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
