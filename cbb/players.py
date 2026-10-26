"""Player availability from hoopR player box scores: a pregame stand-in for injuries.

For each team-game, `missing` = share of the team's season-to-date minutes played by players who did not play in
the team's previous game (players with 3+ games so far). A team whose 35-minute starter sat out last game starts
the next one with missing ~0.17. Only information from before the game is used.

Backtest 2014-2026: per 1.0 of excess missing (vs the team's own usual), the team does ~3 points worse than the
closing line expects, so the market under-reacts to absences.
"""
from __future__ import annotations

import pandas as pd

from . import data

GAME_SCORE = {"points": 1.0, "field_goals_made": 0.4, "field_goals_attempted": -0.7, "offensive_rebounds": 0.7,
              "defensive_rebounds": 0.3, "steals": 1.0, "assists": 0.7, "blocks": 0.7, "fouls": -0.4, "turnovers": -1.0}


def availability(season: int, upcoming: bool = False, refresh: bool = False) -> pd.DataFrame:
    """Per team-game `missing` (share of the team's minutes so far from players who missed its last game) and
    `missing_value` (the same, weighted by each player's production: his share of the team's Game Score so far,
    Hollinger's box-score summary). upcoming=True adds one row per team with game_id 0: the state going into its
    next game, for live runs."""
    p = data.fetch("player_box", season, refresh)
    p = p[p["athlete_id"].notna()].copy()
    p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
    p["played"] = (p["min"] > 0) & ~p["did_not_play"].fillna(False).astype(bool)
    p["date"] = pd.to_datetime(p["game_date"])
    num = {c: pd.to_numeric(p[c], errors="coerce").fillna(0) for c in list(GAME_SCORE) + ["free_throws_attempted", "free_throws_made"]}
    p["gmsc"] = sum(w * num[c] for c, w in GAME_SCORE.items()) - 0.4 * (num["free_throws_attempted"] - num["free_throws_made"])
    p = p.sort_values(["team_id", "date", "game_id"])
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        cum_min: dict = {}
        cum_val: dict = {}
        cum_games: dict = {}
        team_min = 0.0
        last_played: set = set()

        def state():
            regulars = [a for a in cum_min if cum_games.get(a, 0) >= 3]
            tot_val = sum(max(cum_val[a], 0.0) for a in cum_val)
            missing = sum(cum_min[a] / team_min for a in regulars if a not in last_played) if team_min > 0 and last_played else 0.0
            value = sum(max(cum_val[a], 0.0) / tot_val for a in regulars if a not in last_played) if tot_val > 0 and last_played else 0.0
            return missing, value

        for gid, g in tg.groupby("game_id", sort=False):
            out.append((int(gid), int(team), *state()))
            pl = g[g["played"]]
            for a, m, v in zip(pl["athlete_id"], pl["min"], pl["gmsc"]):
                cum_min[a] = cum_min.get(a, 0.0) + m
                cum_val[a] = cum_val.get(a, 0.0) + v
                cum_games[a] = cum_games.get(a, 0) + 1
            team_min += pl["min"].sum()
            last_played = set(pl["athlete_id"])
        if upcoming:
            out.append((0, int(team), *state()))
    return pd.DataFrame(out, columns=["game_id", "team_id", "missing", "missing_value"])


def next_excess_missing(season: int) -> pd.DataFrame:
    """excess_missing going into each team's next game (team_id, excess_missing), from the latest box scores.
    Empty before the season's first games."""
    try:
        a = availability(season, upcoming=True, refresh=True)
    except Exception:
        return pd.DataFrame(columns=["team_id", "excess_missing"])
    played = a[a["game_id"] != 0]
    typical = played.groupby("team_id")["missing"].mean()
    nxt = a[a["game_id"] == 0].set_index("team_id")["missing"]
    return (nxt - typical.reindex(nxt.index).fillna(0.06)).rename("excess_missing").reset_index()


def load(seasons) -> pd.DataFrame:
    """Availability for each season, cached in cbb/cache/availability_<season>.parquet (about 20s per season)."""
    import os
    parts = []
    for s in seasons:
        path = os.path.join(data.CACHE, f"availability_{s}.parquet")
        if not os.path.exists(path) or "missing_value" not in pd.read_parquet(path).columns:
            availability(s).to_parquet(path)
        parts.append(pd.read_parquet(path))
    return pd.concat(parts, ignore_index=True)


def excess_missing(seasons, games: pd.DataFrame) -> pd.DataFrame:
    """`missing` minus the team's own average so far this season: ratings already reflect a team's usual absences,
    so only the extra matters. games: needs game_id and date."""
    a = load(seasons).merge(games[["game_id", "season", "date"]].drop_duplicates(), on="game_id").sort_values("date")
    grp = a.groupby(["team_id", "season"])
    a["excess_missing"] = a["missing"] - grp["missing"].transform(lambda x: x.shift().expanding().mean()).fillna(0.06)
    a["excess_value"] = a["missing_value"] - grp["missing_value"].transform(lambda x: x.shift().expanding().mean()).fillna(0.05)
    return a[["game_id", "team_id", "missing", "excess_missing", "missing_value", "excess_value"]]


def roster_features(season: int) -> pd.DataFrame:
    """Continuity and experience for each team-game, from games before it (like KenPom's, but as of game day).

    continuity  share of the team's minutes so far this season played by players who also played for it last season
    experience  minutes-weighted average number of earlier seasons each player appeared in D-I box scores (any
                team). Box scores start in 2013, so experience is capped for seasons before ~2017.
    Before a team's first game both use its roster from that first game's box score (weighted equally).
    """
    import os
    path = os.path.join(data.CACHE, f"roster_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    seen: dict = {}            # athlete -> set of earlier seasons
    last_team: dict = {}       # athlete -> set of team ids last season
    for s in range(2013, season):
        q = data.fetch("player_box", s)
        q = q[pd.to_numeric(q["minutes"], errors="coerce").fillna(0) > 0]
        for a, t in zip(q["athlete_id"], q["team_id"]):
            seen.setdefault(a, set()).add(s)
            if s == season - 1:
                last_team.setdefault(a, set()).add(t)
    p = data.fetch("player_box", season)
    p = p[p["athlete_id"].notna()].copy()
    p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
    p["date"] = pd.to_datetime(p["game_date"])
    p = p[p["min"] > 0].sort_values(["team_id", "date", "game_id"])
    p["ret"] = [t in last_team.get(a, ()) for a, t in zip(p["athlete_id"], p["team_id"])]
    p["exp"] = [len(seen.get(a, ())) for a in p["athlete_id"]]
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        mins = ret = exp = 0.0
        first = None
        for gid, g in tg.groupby("game_id", sort=False):
            if first is None:
                first = (g["ret"].mean(), g["exp"].mean())
            if mins > 0:
                out.append((int(gid), int(team), ret / mins, exp / mins))
            else:
                out.append((int(gid), int(team), first[0], first[1]))
            mins += g["min"].sum()
            ret += (g["min"] * g["ret"]).sum()
            exp += (g["min"] * g["exp"]).sum()
    df = pd.DataFrame(out, columns=["game_id", "team_id", "continuity", "experience"])
    df.to_parquet(path)
    return df
