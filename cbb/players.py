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

data.FILES["player_box"] = "espn_mens_college_basketball_player_boxscores/player_box_{season}.parquet"


def availability(season: int, upcoming: bool = False, refresh: bool = False) -> pd.DataFrame:
    """Per team-game `missing`. upcoming=True adds one row per team with game_id 0: the state going into its next
    game (who missed its most recent one), for live runs."""
    p = data.fetch("player_box", season, refresh)
    p = p[p["athlete_id"].notna()].copy()
    p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
    p["played"] = (p["min"] > 0) & ~p["did_not_play"].fillna(False).astype(bool)
    p["date"] = pd.to_datetime(p["game_date"])
    p = p.sort_values(["team_id", "date", "game_id"])
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        cum_min: dict = {}
        cum_games: dict = {}
        team_min = 0.0
        last_played: set = set()
        for gid, g in tg.groupby("game_id", sort=False):
            missing = 0.0
            if team_min > 0 and last_played:
                for a, m in cum_min.items():
                    if cum_games.get(a, 0) >= 3 and a not in last_played:
                        missing += m / team_min
            out.append((int(gid), int(team), missing))
            pl = g[g["played"]]
            for a, m in zip(pl["athlete_id"], pl["min"]):
                cum_min[a] = cum_min.get(a, 0.0) + m
                cum_games[a] = cum_games.get(a, 0) + 1
            team_min += pl["min"].sum()
            last_played = set(pl["athlete_id"])
        if upcoming:
            missing = sum(m / team_min for a, m in cum_min.items()
                          if team_min > 0 and cum_games.get(a, 0) >= 3 and a not in last_played)
            out.append((0, int(team), missing))
    return pd.DataFrame(out, columns=["game_id", "team_id", "missing"])


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
        if not os.path.exists(path):
            availability(s).to_parquet(path)
        parts.append(pd.read_parquet(path))
    return pd.concat(parts, ignore_index=True)


def excess_missing(seasons, games: pd.DataFrame) -> pd.DataFrame:
    """`missing` minus the team's own average so far this season: ratings already reflect a team's usual absences,
    so only the extra matters. games: needs game_id and date."""
    a = load(seasons).merge(games[["game_id", "season", "date"]].drop_duplicates(), on="game_id").sort_values("date")
    typical = a.groupby(["team_id", "season"])["missing"].transform(lambda x: x.shift().expanding().mean())
    a["excess_missing"] = a["missing"] - typical.fillna(0.06)
    return a[["game_id", "team_id", "missing", "excess_missing"]]


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
