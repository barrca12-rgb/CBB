"""New head coaches: early-season residuals vs the model, the close and the opener (PLAN.md, pre-registered).

    python -m research.new_coach.study        # -> research/new_coach/out/result.csv, run.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.calibration.common import base, boot_ratio
from research.originator.d2_tiers import HIGH, MID

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
POOLS = {"2025-26": [2026], "2021-25": [2022, 2023, 2024, 2025], "2014-20": [2015, 2016, 2017, 2018, 2019, 2020]}
WINDOWS = {"1-10": (1, 10), "1-5": (1, 5), "6-10": (6, 10), "11-20": (11, 20), "21+": (21, 99)}


def team_games() -> pd.DataFrame:
    w = base()
    w = w[w["final_margin"].notna()]
    rows = []
    for side, sign in (("home", 1), ("away", -1)):
        opp = "away" if side == "home" else "home"
        rows.append(pd.DataFrame({
            "game_id": w["game_id"], "season": w["season"], "date": w["date"],
            "team_id": w[f"{side}_id"], "opp_id": w[f"{opp}_id"],
            "margin": sign * w["margin"],
            "vs_model": sign * w["res"],
            "vs_close": sign * (w["margin"] + w["home_spread"]),
            "vs_open": sign * (w["margin"] + w["open_home_spread"])}))
    t = pd.concat(rows, ignore_index=True).sort_values(["team_id", "season", "date", "game_id"], kind="mergesort")
    t["n"] = t.groupby(["team_id", "season"]).cumcount() + 1
    co = pd.read_csv(os.path.join(ROOT, "data", "research", "coaches.csv"))
    new = set(zip(co.loc[co["new"].astype(bool), "team_id"], co.loc[co["new"].astype(bool), "season"]))
    t["new"] = [(a, s) in new for a, s in zip(t["team_id"], t["season"])]
    t["opp_new"] = [(a, s) in new for a, s in zip(t["opp_id"], t["season"])]
    t = t[~(t["new"] & t["opp_new"])]
    conf = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    t["tier"] = t["team_id"].map(conf).map(lambda x: "high" if x in HIGH else ("mid" if x in MID else "low"))
    last = t.groupby(["team_id", "season"])["margin"].mean().rename("last_margin").reset_index()
    last["season"] += 1
    t = t.merge(last, on=["team_id", "season"], how="left")
    t["was_bad"] = t["last_margin"] < 0
    return t


def diff(t: pd.DataFrame, col: str) -> dict:
    """New-coach mean minus everyone else's mean, date-clustered bootstrap interval."""
    x = t[t[col].notna()]
    a, b = x[x["new"]], x[~x["new"]]
    if len(a) < 20:
        return {"n_new": len(a), "diff": np.nan, "lo": np.nan, "hi": np.nan, "new_mean": np.nan}
    d = np.where(x["new"], x[col] / len(a), -x[col] / len(b)) * len(x)
    est, lo, hi = boot_ratio(d, np.ones(len(d)), x["date"])
    return {"n_new": int(len(a)), "teams": int(a.groupby(["team_id", "season"]).ngroups), "new_mean": a[col].mean(),
            "rest_mean": b[col].mean(), "diff": est, "lo": lo, "hi": hi}


def main() -> None:
    t = team_games()
    out = []
    for pool, seasons in POOLS.items():
        p = t[t["season"].isin(seasons)]
        for wn, (a, b) in WINDOWS.items():
            q = p[p["n"].between(a, b)]
            for col in ("vs_model", "vs_close", "vs_open"):
                out.append({"pool": pool, "window": wn, "split": "all", "outcome": col, **diff(q, col)})
            q = q.copy()
            if wn == "1-10":
                for name, mask in (("tier", "tier"), ("last season", "was_bad")):
                    for v, g in q.groupby(mask):
                        rest = q[~q["new"]]
                        for col in ("vs_model", "vs_close"):
                            out.append({"pool": pool, "window": wn, "split": f"{name}={v}", "outcome": col,
                                        **diff(pd.concat([g[g["new"]], rest]), col)})
    pooled = t[t["season"].isin([2022, 2023, 2024, 2025, 2026]) & t["n"].between(1, 10)]
    for col in ("vs_model", "vs_close"):
        out.append({"pool": "2021-26", "window": "1-10", "split": "all", "outcome": col, **diff(pooled, col)})
    r = pd.DataFrame(out)
    os.makedirs(OUT, exist_ok=True)
    r.to_csv(os.path.join(OUT, "result.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 500):
        txt = r.round(2).to_string(index=False)
    open(os.path.join(OUT, "run.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
