"""Execution timing: which opener picks must be taken at once, and can it be told in advance? (pre-registered in
LOG.md)

    python -m research.edges.e6_timing
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb.evaluate import swapped
from research.edges.common import OUT, ROOT, frame, opener_plays, record

POWER = {"ACC", "B10", "B12", "BE", "SEC", "P12"}
FEATS = ["edge", "is_total", "month_n", "neutral", "power_teams", "abs_open_spread", "kp_edge", "is_over"]


def main() -> None:
    w = frame()
    w = w[~swapped(w.assign(pred_margin=w["final_margin"]))]
    p = opener_plays(w)
    p = p[p["season"].isin([2014, 2015, 2016, 2017, 2024, 2025, 2026])].copy()
    sp = p["market"] == "spread"
    close = np.where(sp, np.where(p["side"] == "home", p["home_spread"], -p["home_spread"]), p["total"])
    p["close"] = close
    p = p.dropna(subset=["close"])
    sp = p["market"] == "spread"
    p["lv"] = np.where(sp, p["line"] - p["close"], np.where(p["side"] == "over", p["close"] - p["line"], p["line"] - p["close"]))
    m = np.where(sp, np.where(p["side"] == "home", p["home_pts"] - p["away_pts"], p["away_pts"] - p["home_pts"]) + p["close"],
                 np.where(p["side"] == "over", p["home_pts"] + p["away_pts"] - p["close"], p["close"] - p["home_pts"] - p["away_pts"]))
    p["res_close"] = np.where(m > 0, "W", np.where(m < 0, "L", "P"))
    p["u_close"] = np.where(p["res_close"] == "W", 100 / 110, np.where(p["res_close"] == "L", -1.0, 0.0))
    p["cls"] = np.where(p["lv"] >= 1, "chased", np.where(p["lv"] <= -1, "faded", "stable"))
    t = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    p["power_teams"] = p["home_id"].map(t).isin(POWER).astype(int) + p["away_id"].map(t).isin(POWER).astype(int)
    p["month_n"] = (pd.to_datetime(p["date"]).dt.month - 11) % 12          # Nov 0 ... Mar 4
    p["neutral"] = p["neutral"].astype(float)
    p["is_total"] = (~sp).astype(float)
    p["is_over"] = (p["side"] == "over").astype(float)
    p["abs_open_spread"] = p["open_home_spread"].abs()
    kp_e = np.where(sp, np.where(p["side"] == "home", p["kp_margin"] + p["open_home_spread"], -(p["kp_margin"] + p["open_home_spread"])),
                    np.where(p["side"] == "over", p["kp_total"] - p["open_total"], p["open_total"] - p["kp_total"]))
    p["kp_edge"] = kp_e
    p = p.dropna(subset=FEATS)
    rows = []
    for mk in ("spread", "total"):
        for cls_, g in p[p["market"] == mk].groupby("cls"):
            for spl, gg in g.groupby("split"):
                a, b = record(gg["res"], gg["u"], gg["date"]), record(gg["res_close"], gg["u_close"], gg["date"])
                rows.append({"market": mk, "class": cls_, "split": spl, "share": len(gg) / ((p["market"] == mk) & (p["split"] == spl)).sum(),
                             "plays": a["bets"], "win% at opener": a["win%"], "win% at close": b["win%"],
                             "ROI% at opener": a["ROI%"], "ROI% at close": b["ROI%"]})
    cls_t = pd.DataFrame(rows)
    # predict "chased" from pick-time information
    dv, ho = p[p["split"] == "development"], p[p["split"] == "holdout"]
    mu, sd = dv[FEATS].mean(), dv[FEATS].std().replace(0, 1)
    X = lambda d: np.column_stack([np.ones(len(d)), ((d[FEATS] - mu) / sd).to_numpy(float)])
    y = (dv["cls"] == "chased").to_numpy(float)
    b = np.zeros(len(FEATS) + 1)
    for _ in range(60):
        pr = 1 / (1 + np.exp(-X(dv) @ b))
        b = b + np.linalg.solve(X(dv).T @ (X(dv) * (pr * (1 - pr))[:, None]) + 1e-6 * np.eye(len(b)), X(dv).T @ (y - pr))
    pr_dv = 1 / (1 + np.exp(-X(dv) @ b))
    se = np.sqrt(np.diag(np.linalg.inv(X(dv).T @ (X(dv) * (pr_dv * (1 - pr_dv))[:, None]))))
    coef = pd.DataFrame({"feature": ["intercept"] + FEATS, "coef (per SD)": b, "z": b / se})

    def auc(score, lab):
        r = pd.Series(score).rank().to_numpy()
        n1 = lab.sum(); n0 = len(lab) - n1
        return float((r[lab == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
    ho = ho.assign(pchase=1 / (1 + np.exp(-X(ho) @ b)))
    a_dv, a_ho = auc(pr_dv, y), auc(ho["pchase"].to_numpy(), (ho["cls"] == "chased").to_numpy(int))
    ho["tercile"] = pd.qcut(ho["pchase"], 3, labels=["least likely chased", "middle", "most likely chased"]).astype(str)
    ter = []
    for tc, g in ho.groupby("tercile"):
        a, c = record(g["res"], g["u"], g["date"]), record(g["res_close"], g["u_close"], g["date"])
        ter.append({"holdout tercile": tc, "plays": a["bets"], "actually chased": float((g["cls"] == "chased").mean()),
                    "mean lv": float(g["lv"].mean()), "win% at opener": a["win%"], "win% at close": c["win%"],
                    "ROI% at opener": a["ROI%"], "ROI% at close": c["ROI%"]})
    ter = pd.DataFrame(ter)
    for name, df in (("e6_classes", cls_t), ("e6_coef", coef), ("e6_terciles", ter)):
        df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    pd.set_option("display.width", 220)
    print(cls_t.round(3).to_string(index=False))
    print(coef.round(3).to_string(index=False))
    print(f"AUC predicting 'chased': development {a_dv:.3f}, holdout {a_ho:.3f}")
    print(ter.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
