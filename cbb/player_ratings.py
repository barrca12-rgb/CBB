"""Player ratings: a box-score plus-minus (the idea behind Basketball-Reference's BPM), relative to the player's team.

1. Stat weights: Game Score's (WEIGHTS). A regression of team margin on team box scores gave wrong-signed weights
   (shot attempts positive, turnovers positive) because team stats move together, so fixed weights it is.
2. A player's value in a game = weights . his box score. His rate = value per 100 team possessions while he was on
   the floor (team possessions x his minutes / 200).
3. Relative rating = his rate minus his team's rate, season to date before each game, shrunk toward the team
   average with REL_PRIOR possessions. Opponent strength cancels out (the team ratings handle it), which is what an
   absence needs: how much better or worse than the rest of the roster the missing player is.

absences() turns that into a per-team-game input: the minutes share times relative rating of regulars (3+ games)
who sat out the team's previous game, summed. Positive = the team is missing better-than-average players.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import data

# Game Score style weights, in points (Hollinger's, with the shot terms written as makes and misses).
WEIGHTS = pd.Series({"points": 1.0, "missed_fg": -0.7, "missed_ft": -0.4, "offensive_rebounds": 0.7,
                     "defensive_rebounds": 0.3, "assists": 0.7, "steals": 1.0, "blocks": 0.7, "turnovers": -1.0,
                     "fouls": -0.4})
REL_PRIOR = 150.0     # possessions of shrinkage toward the team average


def player_games(season: int, refresh: bool = False) -> pd.DataFrame:
    """Player-game rows with value (weights . box) and on-floor team possessions."""
    p = data.fetch("player_box", season, refresh)
    p = p[p["athlete_id"].notna()].copy()
    p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
    p = p[p["min"] > 0]
    num = lambda c: pd.to_numeric(p[c], errors="coerce").fillna(0)
    p["missed_fg"] = num("field_goals_attempted") - num("field_goals_made")
    p["missed_ft"] = num("free_throws_attempted") - num("free_throws_made")
    for c in WEIGHTS.index:
        p[c] = num(c)
    p["value"] = p[WEIGHTS.index].to_numpy(float) @ WEIGHTS.to_numpy(float)
    try:
        _, t = data.season_games(season, refresh)
        p = p.merge(t[["game_id", "team_id", "poss"]], on=["game_id", "team_id"], how="inner")
    except Exception:
        p["poss"] = 68.0
    p["on_poss"] = p["poss"] * p["min"] / 200
    p["date"] = pd.to_datetime(p["game_date"])
    return p.sort_values(["team_id", "date", "game_id"])


def absences(season: int, upcoming: bool = False, refresh: bool = False) -> pd.DataFrame:
    """Per team-game: miss_rel = sum over regulars who missed the team's last game of (minutes share x relative
    rating), from games before this one. upcoming=True adds a game_id 0 row per team (going into its next game) and
    returns the current relative rating of every player as well (for the injury report)."""
    p = player_games(season, refresh)
    out, current = [], []
    for team, tg in p.groupby("team_id", sort=False):
        v: dict = {}
        ps: dict = {}
        mins: dict = {}
        games: dict = {}
        team_v = team_ps = team_min = 0.0
        last: set = set()

        def rel(a):
            rate = 100 * team_v / team_ps if team_ps else 0.0
            return (100 * v[a] + rate * REL_PRIOR) / (ps[a] + REL_PRIOR) - rate

        def state():
            if not team_min or not last:
                return 0.0
            return sum(mins[a] / team_min * rel(a) for a in mins if games.get(a, 0) >= 3 and a not in last)

        for gid, g in tg.groupby("game_id", sort=False):
            out.append((int(gid), int(team), state()))
            for a, val, pp, m in zip(g["athlete_id"], g["value"], g["on_poss"], g["min"]):
                v[a] = v.get(a, 0.0) + val
                ps[a] = ps.get(a, 0.0) + pp
                mins[a] = mins.get(a, 0.0) + m
                games[a] = games.get(a, 0) + 1
            team_v += g["value"].sum()
            team_ps += g["on_poss"].sum()
            team_min += g["min"].sum()
            last = set(g["athlete_id"])
        if upcoming:
            out.append((0, int(team), state()))
            current += [(int(team), a, rel(a), mins[a] / team_min if team_min else 0.0) for a in mins]
    res = pd.DataFrame(out, columns=["game_id", "team_id", "miss_rel"])
    if upcoming:
        res.attrs["players"] = pd.DataFrame(current, columns=["team_id", "athlete_id", "rel", "share"])
    return res


def load_absences(seasons) -> pd.DataFrame:
    parts = []
    for s in seasons:
        path = os.path.join(data.CACHE, f"player_abs_{s}.parquet")
        if not os.path.exists(path):
            absences(s).to_parquet(path)
        parts.append(pd.read_parquet(path))
    return pd.concat(parts, ignore_index=True)


def season_rates(season: int) -> pd.Series:
    """Each player's value per 100 on-floor possessions over a whole season, shrunk toward the league rate."""
    p = player_games(season)
    g = p.groupby("athlete_id")[["value", "on_poss"]].sum()
    lg = 100 * g["value"].sum() / g["on_poss"].sum()
    return (100 * g["value"] + lg * REL_PRIOR) / (g["on_poss"] + REL_PRIOR)


def roster_strength(season: int) -> pd.DataFrame:
    """Per team-game: the minutes-weighted last-season rating of the players the team has used so far this season
    (mean over its earlier games). Transfers count with the rating they earned at their old school; players with no
    D-I minutes last season get NEWCOMER below the league rate. game_id 0 = going into the next game."""
    prev = season_rates(season - 1)
    lg = float(prev.median())
    p = player_games(season)
    p["prev"] = p["athlete_id"].map(prev).fillna(lg - NEWCOMER)
    p["w"] = p["prev"] * p["min"] / 200
    by = p.groupby(["team_id", "game_id"], sort=False).agg(date=("date", "first"), s=("w", "sum")).reset_index()
    by = by.sort_values(["team_id", "date", "game_id"])
    by["roster"] = by.groupby("team_id")["s"].transform(lambda x: x.shift().expanding().mean()) - lg
    nxt = by.groupby("team_id").agg(roster=("s", "mean")).reset_index().assign(game_id=0)
    nxt["roster"] -= lg
    return pd.concat([by[["game_id", "team_id", "roster"]], nxt[["game_id", "team_id", "roster"]]], ignore_index=True)


NEWCOMER = 6.0     # newcomers (freshmen, non-D-I transfers) rate about this far below the median player (2025: 80 vs 86)


def load_roster(seasons) -> pd.DataFrame:
    parts = []
    for s in seasons:
        path = os.path.join(data.CACHE, f"player_roster_{s}.parquet")
        if not os.path.exists(path):
            roster_strength(s).to_parquet(path)
        parts.append(pd.read_parquet(path))
    return pd.concat(parts, ignore_index=True)
