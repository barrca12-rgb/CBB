"""Barttorvik (barttorvik.com) team ratings, cached in cbb/cache/torvik/. Public files, no key.

  team_results(season)   season ratings, 2008 onward: adjoe/adjde/barthag/adjt, SOS, WAB. Current season = live.
  time_machine(day)      the same table as it stood on a date. Daily from the 2014-15 season (2014-11-20) on,
                         so it is a second point-in-time rating next to KenPom's archive.

The files are JSON arrays without headers; COLUMNS are the headers of the site's CSV export (whose header row is
misaligned for 2012-2021, hence JSON). Team names follow KenPom's, so `espn_id` comes from the same lookup.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os

import pandas as pd

from . import net, teams

URL = "https://barttorvik.com"
LIVE = 6 * 3600
COLUMNS = [
    "rank", "team", "conf", "record", "adjoe", "adjoe_rank", "adjde", "adjde_rank", "barthag", "barthag_rank",
    "proj_w", "proj_l", "proj_conf_w", "proj_conf_l", "conf_record", "sos", "ncsos", "consos", "proj_sos",
    "proj_ncsos", "proj_consos", "elite_sos", "elite_ncsos", "opp_oe", "opp_de", "opp_proj_oe", "opp_proj_de",
    "conf_adjoe", "conf_adjde", "qual_o", "qual_d", "qual_barthag", "qual_games", "fun", "conf_pf", "conf_pa",
    "conf_poss", "conf_oe", "conf_de", "conf_sos_remain", "conf_win_pct", "wab", "wab_rank", "fun_rank", "adjt",
]
FIRST_TIME_MACHINE = dt.date(2014, 11, 20)


def _frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["adjem"] = df["adjoe"] - df["adjde"]
    ids = teams.id_lookup("kenpom")
    df.insert(0, "espn_id", df["team"].map(lambda n: ids.get(teams.norm(n))).astype("Int64"))
    return df


def team_results(season: int, refresh: bool = False) -> pd.DataFrame:
    path = net.get(f"{URL}/{season}_team_results.json", f"torvik/team_results_{season}.json", refresh=refresh,
                   max_age=LIVE if season >= net.current_season() else None)
    with open(path) as f:
        return _frame(json.load(f)).assign(season=season)


def time_machine(day, refresh: bool = False) -> pd.DataFrame:
    """Ratings as of the morning of `day`."""
    day = pd.Timestamp(day).date()
    if day < FIRST_TIME_MACHINE:
        raise ValueError(f"Barttorvik's time machine starts {FIRST_TIME_MACHINE}")
    stamp = day.strftime("%Y%m%d")
    path = net.get(f"{URL}/timemachine/team_results/{stamp}_team_results.json.gz",
                   os.path.join("torvik", f"time_machine_{stamp}.json.gz"), refresh=refresh,
                   max_age=LIVE if day >= dt.date.today() else None)
    with gzip.open(path) as f:
        return _frame(json.loads(f.read())).assign(season=net.season_of(day), date=day)
