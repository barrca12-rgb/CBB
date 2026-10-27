"""Source-weighting variants of the stage-2 walk-forward (pre-registered in LOG.md).

    python -m research.weights.w_sources
"""
from __future__ import annotations

import os

import pandas as pd

from cbb import projection
from research.originator import d_common
from research.originator.d_common import clv, frames, mae, oriented_openers, walk_forward
from research.pbp.p_features import win_pct

OUT = os.path.join(os.path.dirname(__file__), "out")
KP_M, KP_T = ["kp_margin", "kp_margin_x_early"], ["kp_total", "kp_total_x_early"]
BT_M, BT_T = ["bt_margin"], ["bt_total"]
MK_M, MK_T = ["mkt_m"], ["mkt_t"]
VARIANTS = {"frozen": ([], [], 1.0), "V1 no KenPom": (KP_M, KP_T, 1.0), "V2 no Barttorvik": (BT_M, BT_T, 1.0),
            "V3 no KenPom, no Barttorvik": (KP_M + BT_M, KP_T + BT_T, 1.0), "V4 no market ratings": (MK_M, MK_T, 1.0),
            "V5 own ratings + context": (KP_M + BT_M + MK_M, KP_T + BT_T + MK_T, 1.0),
            "V6 ridge 100": ([], [], 100.0), "V7 ridge 1000": ([], [], 1000.0)}
DEV, HOLD = [2014, 2015, 2016, 2017, 2024], [2025, 2026]


def fit(train, pred, drop_m, drop_t, lam):
    mf, tf, rw = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES, d_common.ridge_w
    try:
        projection.MARGIN_FEATURES = [c for c in mf if c not in drop_m]
        projection.TOTAL_FEATURES = [c for c in tf if c not in drop_t]
        d_common.ridge_w = lambda X, y, w, lam_=lam: rw(X, y, w, lam_)
        return walk_forward(train, pred)
    finally:
        projection.MARGIN_FEATURES, projection.TOTAL_FEATURES, d_common.ridge_w = mf, tf, rw


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    rows = []
    for tag, (dm, dt, lam) in VARIANTS.items():
        w = oriented_openers(fit(train, pred, dm, dt, lam))
        wd, wh = win_pct(w, DEV), win_pct(w, HOLD)
        cd, cc = clv(w, range(2014, 2018)), clv(w, range(2024, 2027))
        m = mae(w, range(2020, 2027))
        rows.append({"variant": tag, "margin MAE": round(m["margin MAE"], 4), "total MAE": round(m["total MAE"], 4),
                     "spread win% dev": round(wd["spread win%"], 2), "spread win% hold": round(wh["spread win%"], 2),
                     "spread n dev/hold": f"{wd['spread n']}/{wh['spread n']}",
                     "spread CLV dev/conf": f"{cd['spread CLV']:.3f}/{cc['spread CLV']:.3f}",
                     "total win% dev": round(wd["total win%"], 2), "total win% hold": round(wh["total win%"], 2),
                     "total n dev/hold": f"{wd['total n']}/{wh['total n']}",
                     "total CLV dev/conf": f"{cd['total CLV']:.3f}/{cc['total CLV']:.3f}"})
        print(tag, "done", flush=True)
    t = pd.DataFrame(rows).set_index("variant")
    f = t.loc["frozen"]
    verdict = {}
    for mk in ("spread", "total"):
        ch = t.drop(index="frozen")[f"{mk} win% dev"].idxmax()
        x = t.loc[ch]
        cdx, ccx = (float(v) for v in x[f"{mk} CLV dev/conf"].split("/"))
        cdf, ccf = (float(v) for v in f[f"{mk} CLV dev/conf"].split("/"))
        ok = (x[f"{mk} win% dev"] - f[f"{mk} win% dev"] >= 0.5 and x[f"{mk} win% hold"] - f[f"{mk} win% hold"] >= 1.0
              and cdx - cdf >= 0.05 and ccx - ccf >= 0.05)
        verdict[mk] = f"{ch}: {'PASS' if ok else 'KILL'}"
    t.to_csv(os.path.join(OUT, "w_result.csv"))
    pd.set_option("display.width", 250)
    print(t.T.to_string())
    print("chosen on development, verdict:", verdict)


if __name__ == "__main__":
    main()
