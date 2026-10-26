"""Game results and box scores from hoopR (sportsdataverse), cached locally.

hoopR publishes ESPN men's college basketball data as GitHub release assets, one file per season:
  * schedules  (espn_mens_college_basketball_schedules/mbb_schedule_{season}.parquet): venue, neutral site,
    conference game, status, scores
  * team box   (espn_mens_college_basketball_team_boxscores/team_box_{season}.parquet): two rows per game

`season` is the year the season ends: 2025 = the 2024-25 season.

Outputs (both D-I vs D-I, completed games only):
  games       one row per game: date, home/away ESPN ids, neutral, conference game, scores, possessions
  team_games  two rows per game (one per team): offense `team` vs defense `opp`, with points, possessions,
              points per 100 possessions and the Four Factors. This is the input to the ridge ratings.
"""
from __future__ import annotations

import os
import urllib.request

import numpy as np
import pandas as pd

RELEASES = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
FILES = {
    "schedule": "espn_mens_college_basketball_schedules/mbb_schedule_{season}.parquet",
    "team_box": "espn_mens_college_basketball_team_boxscores/team_box_{season}.parquet",
    "player_box": "espn_mens_college_basketball_player_boxscores/player_box_{season}.parquet",
}
CACHE = os.path.join(os.path.dirname(__file__), "cache")

# 3-point luck: share of each team-game's 3-point makes above or below the league rate (given its attempts) that is
# treated as noise and removed from points per 100 (`ppp`). Opponents' 3P% is mostly luck (KenPom); a team's own
# shooting is partly skill. Walk-forward test 2017/19/22/24/25: 0.3-0.4 cut the margin miss 8.843 -> 8.806 and
# the total miss 13.198 -> 13.154; regressing offense and defense separately did no better. `ppp_raw` keeps the
# actual number.
THREE_LUCK = 0.35
# Free-throw weight in the possession estimate (KenPom uses 0.475; Oliver's original is 0.44).
FT_WEIGHT = 0.475


def fetch(kind: str, season: int, refresh: bool = False) -> pd.DataFrame:
    """One season of a hoopR file, downloaded once and cached in cbb/cache/."""
    rel = FILES[kind].format(season=season)
    path = os.path.join(CACHE, os.path.basename(rel))
    if refresh or not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(f"{RELEASES}/{rel}", headers={"User-Agent": "cbb-model"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path + ".tmp", "wb") as f:
            f.write(r.read())
        os.replace(path + ".tmp", path)
    return pd.read_parquet(path)


def possessions(fga, orb, tov, fta):
    return fga - orb + tov + FT_WEIGHT * fta


def season_games(season: int, refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, team_games) for one season."""
    sch = fetch("schedule", season, refresh)
    box = fetch("team_box", season, refresh)

    sch = sch[sch["status_type_completed"].fillna(False).astype(bool)]
    sch = sch.drop_duplicates("game_id")
    g = pd.DataFrame({
        "game_id": sch["game_id"].astype(int),
        "season": season,
        "season_type": sch["season_type"].astype(int),   # 2 = regular season, 3 = postseason
        "date": pd.to_datetime(sch["game_date"]),
        "start": sch["game_date_time"],
        "home_id": sch["home_id"].astype(int),
        "away_id": sch["away_id"].astype(int),
        "home": sch["home_location"],
        "away": sch["away_location"],
        "neutral": sch["neutral_site"].fillna(False).astype(bool),
        "conf_game": sch["conference_competition"].fillna(False).astype(bool),
        "venue_id": sch["venue_id"],
        "venue_state": sch["venue_address_state"],
        "notes": sch["notes_headline"],
        "home_pts": pd.to_numeric(sch["home_score"], errors="coerce"),
        "away_pts": pd.to_numeric(sch["away_score"], errors="coerce"),
        "periods": pd.to_numeric(sch["status_period"], errors="coerce"),
    })

    # Division I = teams ESPN lists with a conference. Non-D-I opponents (NAIA, D-II) have none.
    conf = pd.concat([sch[["home_id", "home_conference_id"]].set_axis(["id", "c"], axis=1),
                      sch[["away_id", "away_conference_id"]].set_axis(["id", "c"], axis=1)])
    d1 = set(conf.dropna()["id"].astype(int))
    g = g[g["home_id"].isin(d1) & g["away_id"].isin(d1)]

    b = box.drop_duplicates(["game_id", "team_id"])
    t = pd.DataFrame({
        "game_id": b["game_id"].astype(int),
        "team_id": b["team_id"].astype(int),
        "opp_id": b["opponent_team_id"].astype(int),
        "pts": b["team_score"],
        "fgm": b["field_goals_made"], "fga": b["field_goals_attempted"],
        "fg3m": b["three_point_field_goals_made"], "fg3a": b["three_point_field_goals_attempted"],
        "ftm": b["free_throws_made"], "fta": b["free_throws_attempted"],
        "orb": b["offensive_rebounds"], "drb": b["defensive_rebounds"],
        "tov": b["total_turnovers"],
    })
    # Opponent's defensive rebounds give each team's OREB%.
    opp = t[["game_id", "team_id", "drb", "orb", "fga", "tov", "fta"]].rename(
        columns={"team_id": "opp_id", "drb": "opp_drb", "orb": "opp_orb", "fga": "opp_fga", "tov": "opp_tov",
                 "fta": "opp_fta"})
    t = t.merge(opp, on=["game_id", "opp_id"], how="inner")
    t = t.merge(g[["game_id", "season", "season_type", "date", "home_id", "neutral", "conf_game", "periods"]],
                on="game_id", how="inner")

    # Possessions: average of the two teams' estimates, per 40 minutes so overtime doesn't inflate pace.
    own = possessions(t["fga"], t["orb"], t["tov"], t["fta"])
    their = possessions(t["opp_fga"], t["opp_orb"], t["opp_tov"], t["opp_fta"])
    t["poss"] = (own + their) / 2
    minutes = 40 + 5 * (t["periods"].fillna(2) - 2).clip(lower=0)
    t["pace"] = t["poss"] * 40 / minutes
    t["ppp_raw"] = 100 * t["pts"] / t["poss"]
    p3 = t["fg3m"].sum() / t["fg3a"].sum()
    t["ppp"] = t["ppp_raw"] - THREE_LUCK * 100 * 3 * (t["fg3m"] - t["fg3a"] * p3) / t["poss"]
    t["efg"] = (t["fgm"] + 0.5 * t["fg3m"]) / t["fga"]
    t["tov_rate"] = t["tov"] / t["poss"]
    t["orb_rate"] = t["orb"] / (t["orb"] + t["opp_drb"])
    t["ft_rate"] = t["ftm"] / t["fga"]
    t["fg3a_rate"] = t["fg3a"] / t["fga"]
    # Venue from this team's point of view: +1 home, -1 away, 0 neutral.
    t["venue"] = np.where(t["neutral"], 0, np.where(t["team_id"] == t["home_id"], 1, -1))
    t = t.drop(columns=["home_id", "opp_drb", "opp_orb", "opp_fga", "opp_tov", "opp_fta"])

    pace = t.groupby("game_id")["pace"].first()
    g = g[g["game_id"].isin(pace.index)].copy()
    g["pace"] = g["game_id"].map(pace)
    return g.reset_index(drop=True), t.reset_index(drop=True)


def load(seasons, refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts = [season_games(s, refresh) for s in seasons]
    return (pd.concat([p[0] for p in parts], ignore_index=True),
            pd.concat([p[1] for p in parts], ignore_index=True))
