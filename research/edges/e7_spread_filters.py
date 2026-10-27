"""Spread agreement and situation filters (pre-registered in LOG.md).

    python -m research.edges.e7_spread_filters
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb.evaluate import swapped
from research.edges.common import OUT, frame, opener_plays, record


def main() -> None:
    w = frame()
    w = w[~swapped(w.assign(pred_margin=w["final_margin"]))]
    p = opener_plays(w)
    p = p[(p["market"] == "spread") & p["season"].isin([2014, 2015, 2016, 2017, 2024, 2025, 2026])].copy()
    sgn = np.where(p["side"] == "home", 1, -1)
    dev = p["split"] == "development"
    for src in ("kp_margin", "bt_margin", "mkt_margin"):
        off = float((p.loc[dev, src] + p.loc[dev, "open_home_spread"]).mean())   # source's average offset vs the line
        p[f"{src}_edge"] = sgn * (p[src] + p["open_home_spread"] - off)
    f = {
        "A. KenPom agrees (1+)": p["kp_margin_edge"] >= 1,
        "B. Barttorvik agrees (1+)": p["bt_margin_edge"] >= 1,
        "C. KenPom and Barttorvik agree": (p["kp_margin_edge"] >= 1) & (p["bt_margin_edge"] >= 1),
        "D. market ratings agree (1+)": (p["mkt_margin_edge"] >= 1).where(p["mkt_m"] != 0),
        "E. rest favours our side": pd.Series(sgn * p["rest_diff"] > 0, index=p.index),
        "F. conference game": p["conf_game"].astype(bool),
        "G. injury-driven (|missing value diff| >= 0.1)": p["miss_value_diff"].abs() >= 0.1,
    }
    base = {sp: record(g["res"], g["u"], g["date"]) for sp, g in p.groupby("split")}
    rows = [{"filter": "ALL", "part": "", "split": sp, **r} for sp, r in base.items()]
    for name, mask in f.items():
        m = mask.dropna().astype(bool)
        for part, sub in (("keep", p.loc[m.index[m]]), ("drop", p.loc[m.index[~m]])):
            for sp, g in sub.groupby("split"):
                rows.append({"filter": name, "part": part, "split": sp, **record(g["res"], g["u"], g["date"])})
    t = pd.DataFrame(rows)
    t["diff vs all"] = t["win%"] - t["split"].map({k: v["win%"] for k, v in base.items()})
    t.to_csv(os.path.join(OUT, "e7_spread_filters.csv"), index=False)
    pd.set_option("display.width", 200)
    print(t.round(2).to_string(index=False))
    d = t[(t["split"] == "development") & (t["part"] == "keep")]
    fl = d[d["diff vs all"] >= 2 * d["win% se"]]
    print("\nflagged (keep side 2+ SE above all, development):", fl["filter"].tolist())


if __name__ == "__main__":
    main()
