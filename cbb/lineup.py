"""Lineup adjustment for the v2 shadow test (research/v2_lineup/PLAN.md). Not used by the live card.

For each team, from its completed games only:
  expected minutes  last-5-game weighted average (weights 5,4,3,2,1; missed games count 0), shrunk toward the
                    embedded minutes with 2 games of weight; 0 if the player sat out the team's previous game
  embedded minutes  the player's minutes over the season so far, weighted 0.5^(days/120) (the rating's half-life)
  player value      offensive and defensive box-score value per 100 on-floor possessions relative to the team,
                    season to date, shrunk toward the team average (player_ratings.REL_PRIOR possessions)
  adjustment        sum over players of (expected - embedded minutes)/200 x relative value x team possessions/100

Identical to research/originator/b_rotation.season_adjustments (tested); upcoming=True adds a game_id 0 row per
team: its adjustment going into its next game.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import player_ratings as pr

OFF = ["points", "missed_fg", "missed_ft", "offensive_rebounds", "assists", "turnovers"]
DEF = ["defensive_rebounds", "steals", "blocks", "fouls"]
W5 = np.array([5, 4, 3, 2, 1], float)
BETA = 0.4022    # frozen residual on the adjustment, 2015-2026 (research/v2_lineup/out/backtest_run.txt)


def _state(hist, dates, cum, tv_o, tv_d, tps, poss_hist, d0) -> tuple[float, float]:
    players = set().union(*hist)
    w = np.array([0.5 ** ((d0 - d).days / 120) for d in dates])
    last = hist[-1]
    rate_o, rate_d = (100 * tv_o / tps, 100 * tv_d / tps) if tps else (0.0, 0.0)
    adj_o = adj_d = 0.0
    tposs = float(np.mean(poss_hist[-10:]))
    for a in players:
        mins = np.array([h.get(a, 0.0) for h in hist])
        emb = float((w * mins).sum() / w.sum())
        rec = mins[::-1][:5]
        rw = W5[:len(rec)]
        recent = (float((rw * rec).sum()) + 2 * emb) / (rw.sum() + 2)
        exp = 0.0 if last.get(a, 0.0) == 0 else recent
        o, dv, ps = cum.get(a, (0.0, 0.0, 0.0))
        rel_o = (100 * o + rate_o * pr.REL_PRIOR) / (ps + pr.REL_PRIOR) - rate_o
        rel_d = (100 * dv + rate_d * pr.REL_PRIOR) / (ps + pr.REL_PRIOR) - rate_d
        adj_o += (exp - emb) / 200 * rel_o * tposs / 100
        adj_d += (exp - emb) / 200 * rel_d * tposs / 100
    return adj_o, adj_d


def adjustments(season: int, upcoming: bool = False, asof: pd.Timestamp | None = None, refresh: bool = False) -> pd.DataFrame:
    """Per team-game (game_id, team_id, adj_off, adj_def). upcoming=True adds game_id 0 per team, from games
    before `asof` (default: all completed games)."""
    p = pr.player_games(season, refresh)
    if asof is not None:
        p = p[p["date"] < pd.Timestamp(asof).tz_localize(None).normalize()]
    p["off_v"] = p[OFF].to_numpy(float) @ pr.WEIGHTS[OFF].to_numpy(float)
    p["def_v"] = p[DEF].to_numpy(float) @ pr.WEIGHTS[DEF].to_numpy(float)
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        hist, dates, poss_hist = [], [], []
        cum: dict = {}
        tv_o = tv_d = tps = 0.0
        for gid, g in tg.groupby("game_id", sort=False):
            d0 = g["date"].iloc[0]
            if hist:
                out.append((int(gid), int(team), *_state(hist, dates, cum, tv_o, tv_d, tps, poss_hist, d0)))
            hist.append(dict(zip(g["athlete_id"], g["min"])))
            dates.append(d0)
            for a, o, dv, ps in zip(g["athlete_id"], g["off_v"], g["def_v"], g["on_poss"]):
                c = cum.get(a, (0.0, 0.0, 0.0))
                cum[a] = (c[0] + o, c[1] + dv, c[2] + ps)
            tv_o += g["off_v"].sum()
            tv_d += g["def_v"].sum()
            tps += g["on_poss"].sum()
            poss_hist.append(float(g["poss"].iloc[0]))
        if upcoming and hist:
            d_next = (pd.Timestamp(asof).tz_localize(None).normalize() if asof is not None else dates[-1] + pd.Timedelta(days=1))
            out.append((0, int(team), *_state(hist, dates, cum, tv_o, tv_d, tps, poss_hist, d_next)))
    return pd.DataFrame(out, columns=["game_id", "team_id", "adj_off", "adj_def"])
