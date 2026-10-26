"""Idea 4: totals matchup features (specification in LOG.md, fixed before running).

    python -m research.edges.e4_totals_matchup
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.edges.common import HOLDOUT, OUT, ROOT, frame, opener_plays, record

K = 5.0   # games of league-average prior


def features(season: int) -> pd.DataFrame:
    t = pd.read_parquet(os.path.join(ROOT, "cbb", "cache", f"team_box_{season}.parquet"))
    t = t[["game_id", "game_date", "team_id", "opponent_team_id", "field_goals_attempted", "offensive_rebounds",
           "total_turnovers", "free_throws_attempted", "three_point_field_goals_attempted"]].dropna()
    t["poss"] = t["field_goals_attempted"] - t["offensive_rebounds"] + t["total_turnovers"] + 0.475 * t["free_throws_attempted"]
    t["r3"] = t["three_point_field_goals_attempted"] / t["field_goals_attempted"]
    t["date"] = pd.to_datetime(t["game_date"])
    t = t.sort_values(["date", "game_id"]).reset_index(drop=True)
    lg_poss, lg_r3 = t["poss"].mean(), t["r3"].mean()
    # season-to-date before the game: own tempo and 3PA rate; 3PA rate allowed (as the opponent)
    for col, key in (("poss", "team_id"), ("r3", "team_id")):
        g = t.groupby(key)[col]
        n = g.cumcount()
        t[f"{col}_pre"] = ((g.cumsum() - t[col]) + K * (lg_poss if col == "poss" else lg_r3)) / (n + K)
    g = t.groupby("opponent_team_id")["r3"]
    n = g.cumcount()
    t["r3_allowed_pre"] = ((g.cumsum() - t["r3"]) + K * lg_r3) / (n + K)   # what this row's opponent allowed before
    t["r3_dev"] = t["r3_pre"] - lg_r3
    t["r3a_dev"] = t["r3_allowed_pre"] - lg_r3
    return t.set_index(["game_id", "team_id"])[["poss_pre", "r3_dev", "r3a_dev"]]


def add(w: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for s in sorted(w["season"].unique()):
        f = features(int(s))
        g = w[w["season"] == s]
        h = f.reindex(pd.MultiIndex.from_arrays([g["game_id"], g["home_id"]])).to_numpy()
        a = f.reindex(pd.MultiIndex.from_arrays([g["game_id"], g["away_id"]])).to_numpy()
        # r3a_dev on the home row = what the AWAY team allowed before (the home row's opponent is away)
        parts.append(g.assign(pace_mismatch=np.abs(h[:, 0] - a[:, 0]),
                              three_interplay=h[:, 1] * h[:, 2] + a[:, 1] * a[:, 2]))
    return pd.concat(parts)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = add(frame())
    w["y"] = (w["home_pts"] + w["away_pts"]) - w["total"]
    w["x0"] = w["final_total"] - w["total"]
    fits, adj = [], []
    for s in range(2015, 2027):
        tr = w[(w["season"] < s)].dropna(subset=["y", "x0", "pace_mismatch", "three_interplay"])
        X = np.column_stack([np.ones(len(tr)), tr[["x0", "pace_mismatch", "three_interplay"]].to_numpy(float)])
        beta, *_ = np.linalg.lstsq(X, tr["y"].to_numpy(float), rcond=None)
        res = tr["y"].to_numpy(float) - X @ beta
        # date-clustered sandwich SEs
        Xr = X * res[:, None]
        meat = sum(np.outer(v, v) for v in pd.DataFrame(Xr).groupby(tr["date"].to_numpy()).sum().to_numpy())
        bread = np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(bread @ meat @ bread))
        fits.append({"test season": s, "fit n": len(tr), **{f"{k}": b for k, b in zip(["const", "model-close", "pace mismatch", "3P interplay"], beta)},
                     **{f"{k} z": b / e for k, b, e in zip(["pace mismatch", "3P interplay"], beta[2:], se[2:])}})
        g = w[w["season"] == s].copy()
        g["final_total_adj"] = g["final_total"] + beta[2] * g["pace_mismatch"].fillna(0) + beta[3] * g["three_interplay"].fillna(0)
        adj.append(g)
    f = pd.DataFrame(fits)
    a = pd.concat(adj)
    a = a[a["season"].isin([2015, 2016, 2017, 2024] + HOLDOUT)]
    rows = []
    for name, col in (("frozen model total", "final_total"), ("with matchup features", "final_total_adj")):
        p = opener_plays(a, col)
        p = p[p["market"] == "total"]
        for sp, g in p.groupby("split"):
            rows.append({"version": name, "split": sp, **record(g["res"], g["u"], g["date"])})
    t = pd.DataFrame(rows)
    f.to_csv(os.path.join(OUT, "e4_fits.csv"), index=False)
    t.to_csv(os.path.join(OUT, "e4_results.csv"), index=False)
    pd.set_option("display.width", 220)
    print(f.round(3).to_string(index=False))
    print(t.round(2).to_string(index=False))
    print("feature SDs:", w[["pace_mismatch", "three_interplay"]].std().round(4).to_dict())


if __name__ == "__main__":
    main()
