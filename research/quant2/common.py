"""Shared pieces for batch 2 (PLAN.md): v1 walk-forward predictions plus pre-game variance features."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import data
from research.quant.common import SEASONS, base_frames, fit_predict

OUT = os.path.join(os.path.dirname(__file__), "out")


def three_rate() -> pd.DataFrame:
    """Each team's season-to-date 3PA share of FGA from games strictly before each date."""
    path = os.path.join(OUT, "three_rate.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    rows = []
    for s in range(2014, 2027):
        _, t = data.season_games(s)
        t = t[["team_id", "date", "fg3a", "fga"]].copy() if "fg3a" in t else t.assign(fg3a=t["fg3a_rate"] * t["fga"])[["team_id", "date", "fg3a", "fga"]]
        t["date"] = pd.to_datetime(t["date"])
        d = t.groupby(["team_id", "date"])[["fg3a", "fga"]].sum().sort_index()
        cs = d.groupby(level=0).cumsum() - d                     # through the previous date only
        r = ((cs["fg3a"] + 0.36 * 100) / (cs["fga"] + 100)).rename("tpar")   # shrunk to the league share with 100 FGA
        rows.append(r.reset_index().assign(season=s))
    out = pd.concat(rows, ignore_index=True)
    out.to_pickle(path)
    return out


def frame() -> pd.DataFrame:
    """v1 walk-forward predictions 2014-26 with the variance features attached."""
    path = os.path.join(OUT, "frame.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    train, pred = base_frames()
    w = fit_predict(train, pred)
    w["date"] = pd.to_datetime(w["date"])
    tr = three_rate()
    for sd in ("home", "away"):
        w = w.merge(tr.rename(columns={"team_id": f"{sd}_id", "tpar": f"{sd}_tpar"})[[f"{sd}_id", "date", f"{sd}_tpar"]],
                    on=[f"{sd}_id", "date"], how="left")
    w["tpar_sum"] = (w["home_tpar"].fillna(0.36) + w["away_tpar"].fillna(0.36))
    w["absm"] = w["final_margin"].abs()
    w["disagree"] = (w["kp_margin"] - w["pred_margin"]).abs()
    w["gb"] = np.log1p(w["games_before"].clip(lower=0))
    w["neutral_f"] = w["neutral"].astype(float)
    w.to_pickle(path)
    return w


VAR_FEATS = ["pred_poss", "final_total", "absm", "gb", "neutral_f", "disagree", "tpar_sum"]
