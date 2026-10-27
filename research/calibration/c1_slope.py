"""Check 1: calibration slope by edge size (LOG.md).

    python -m research.calibration.c1_slope
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.calibration.common import OUT, TEST, base, boot_ratio, cluster_ols, mae

BUCKETS = [(0, 2.5), (2.5, 4), (4, 6), (6, 99)]
OPEN_S = [2014, 2015, 2016, 2017, 2024, 2025, 2026]


def sides(w: pd.DataFrame, mk: str, line: str, seasons) -> pd.DataFrame:
    """Per game: predicted edge and realized edge from the model's side against `line`."""
    d = w[w["season"].isin(seasons) & ~w["swapped"]].dropna(subset=[line])
    if mk == "spread":
        e = d["final_margin"] + d[line]
        real = (d["margin"] + d[line]) * np.sign(e)
    else:
        e = d["final_total"] - d[line]
        real = (d["points"] - d[line]) * np.sign(e)
    return pd.DataFrame({"date": d["date"].astype(str), "season": d["season"], "pe": e.abs(), "re": real})


def main() -> None:
    w = base()
    rows, out = [], {}
    t = w[w["season"].isin(TEST)]
    for mk, a, p in (("spread", "margin", "final_margin"), ("total", "points", "final_total")):
        b, se = cluster_ols(t[p], t[a], t["date"].astype(str))
        rows.append({"check": f"1 overall {mk}", "metric": "slope of actual on predicted 2020-26", "value": round(b[1], 4),
                     "interval": f"[{b[1]-1.96*se[1]:.4f}, {b[1]+1.96*se[1]:.4f}]", "intercept": round(b[0], 3)})
        # walk-forward calibration of the prediction
        cal = []
        for s in TEST:
            tr = w[w["season"].between(2014, s - 1)]
            bb = np.polyfit(tr[p], tr[a], 1)
            te = w[w["season"] == s]
            cal.append(te[a] - (bb[1] + bb[0] * te[p]))
        cal = pd.concat(cal)
        out[f"{mk} MAE change from walk-forward calibration"] = round(mae(cal) - mae(t[a] - t[p]), 4)
        for line, seasons in ((("home_spread" if mk == "spread" else "total"), TEST), (("open_home_spread" if mk == "spread" else "open_total"), OPEN_S)):
            s = sides(w, mk, line, seasons)
            for lo, hi in BUCKETS:
                x = s[(s["pe"] >= lo) & (s["pe"] < hi)]
                r, l, h = boot_ratio(x["re"], x["pe"], x["date"])
                dec = x[x["re"] != 0]
                rows.append({"check": f"1 {mk} vs {'close' if 'open' not in line else 'opener'}", "metric": f"edge {lo}-{hi if hi < 99 else '+'}",
                             "value": round(r, 3), "interval": f"[{l:.3f}, {h:.3f}]", "games": len(x),
                             "mean predicted edge": round(x["pe"].mean(), 2), "mean realized edge": round(x["re"].mean(), 2),
                             "win%": round(100 * (dec["re"] > 0).mean(), 1)})
    # win-chance rule: p = 0.5 + k x edge; fit k on earlier seasons' cover rates, check later; 5+ at the opener
    sp = sides(w, "spread", "open_home_spread", OPEN_S)
    sp = sp[sp["re"] != 0]
    fit = sp[sp["season"] <= 2017]
    k = float(np.sum((fit["re"] > 0).astype(float).values - 0.5) / np.sum(fit["pe"].clip(upper=8)))   # least-squares through 0.5 is messy; use mean-ratio form
    ks = np.linalg.lstsq(fit[["pe"]].clip(upper=8).to_numpy(float), ((fit["re"] > 0).astype(float) - 0.5).to_numpy(), rcond=None)[0][0]
    later = sp[sp["season"] >= 2024]
    tab = later.assign(b=pd.cut(later["pe"], [2.5, 3, 4, 5, 6, 99], right=False)).groupby("b", observed=True).apply(
        lambda g: pd.Series({"games": len(g), "realized win%": round(100 * (g["re"] > 0).mean(), 1),
                             "rule p (0.0255, cap 0.58)": round(100 * np.minimum(0.5 + 0.0255 * g["pe"], 0.58).mean(), 1),
                             "refit p (2014-17 slope)": round(100 * (0.5 + ks * g["pe"]).mean(), 1)}))
    five = sp[sp["pe"] >= 5]
    out["refit win-chance slope per point (2014-17, through 50%)"] = round(float(ks), 4)
    out["5+ edges at the opener, all opener seasons: realized win%"] = f"{100 * (five['re'] > 0).mean():.1f}% of {len(five)}"
    out["EV rule at -110 binds below edge"] = round((0.5238 + 0.02 / 1.909 - 0.5) / 0.0255, 2)
    t1 = pd.DataFrame(rows)
    t1.to_csv(os.path.join(OUT, "c1_result.csv"), index=False)
    tab.to_csv(os.path.join(OUT, "c1_winrule.csv"))
    pd.set_option("display.width", 250)
    print(t1.to_string(index=False))
    print(tab.to_string())
    for k_, v in out.items():
        print(f"{k_}: {v}")


if __name__ == "__main__":
    main()
