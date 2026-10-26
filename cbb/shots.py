"""Shot quality from play-by-play: what each team-game's shots were worth at league-average accuracy.

Every field-goal attempt in hoopR's play-by-play is typed (layup, dunk, tip, jumper) and marked 2 or 3 points. Shots
are grouped as rim (layup/dunk/tip), mid-range (other 2s) and three; each group is valued at that season's league
make rate. xpts = sum of those values + free-throw attempts at the league FT%. Rim shots and threes are good shots,
mid-range jumpers poor ones, and shot selection is steadier than whether the shots fell. hoopR play-by-play
(ESPN), ~60 MB per season; only the per-team-game summary is cached (cbb/cache/shots_<season>.parquet).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import data

data.FILES.setdefault("pbp", "espn_mens_college_basketball_pbp/play_by_play_{season}.parquet")
RIM = {"LayUpShot", "DunkShot", "TipShot", "Layup Shot", "Dunk Shot", "Tip Shot"}


def season(s: int) -> pd.DataFrame:
    """game_id, team_id, rim_a, rim_m, mid_a, mid_m, three_a, three_m."""
    path = os.path.join(data.CACHE, f"shots_{s}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    raw = os.path.join(data.CACHE, f"play_by_play_{s}.parquet")
    data.fetch("pbp", s)
    p = pd.read_parquet(raw, columns=["game_id", "team_id", "type_text", "shooting_play", "scoring_play",
                                      "points_attempted"])
    os.remove(raw)
    p = p[p["shooting_play"].fillna(False).astype(bool) & p["points_attempted"].isin([2, 3]) & p["team_id"].notna()]
    kind = np.where(p["points_attempted"] == 3, "three", np.where(p["type_text"].isin(RIM), "rim", "mid"))
    p = p.assign(kind=kind, made=p["scoring_play"].fillna(False).astype(int))
    g = p.groupby(["game_id", "team_id", "kind"])["made"].agg(["size", "sum"]).unstack("kind").fillna(0)
    out = pd.DataFrame({f"{k}_{x}": g[(c, k)] if (c, k) in g.columns else 0
                        for k in ("rim", "mid", "three") for x, c in (("a", "size"), ("m", "sum"))}, index=g.index)
    out = out.reset_index().astype({"game_id": int, "team_id": int})
    out.to_parquet(path)
    return out


def xppp(t: pd.DataFrame, s: int) -> pd.Series:
    """Shot-quality points per 100 possessions for the team-games in t (data.season_games), NaN where the
    play-by-play is missing."""
    sh = season(s)
    m = t[["game_id", "team_id", "fta", "poss"]].merge(sh, on=["game_id", "team_id"], how="left")
    rates = {k: sh[f"{k}_m"].sum() / sh[f"{k}_a"].sum() for k in ("rim", "mid", "three")}
    ft = t["ftm"].sum() / t["fta"].sum()
    xp = (m["rim_a"] * 2 * rates["rim"] + m["mid_a"] * 2 * rates["mid"] + m["three_a"] * 3 * rates["three"]
          + m["fta"] * ft)
    # play-by-play sometimes misses shots: only trust games where it logged at least 80% of the box score's FGA
    fga_pbp = m["rim_a"] + m["mid_a"] + m["three_a"]
    ok = fga_pbp >= 0.8 * t["fga"].to_numpy()
    out = pd.Series(np.where(ok, 100 * xp / m["poss"], np.nan), index=t.index)
    return out
