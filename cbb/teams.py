"""Team names across sources, keyed by ESPN team id (the id hoopR uses).

data/teams.csv starts from hoopR's team crosswalk (ESPN -> KenPom names) for the 2025-26 Division I field,
plus teams that left or joined D-I since 2012, with manual fixes marked source=manual. `kenpom_id` is KenPom's
TeamID, which stays the same through renames. data/team_aliases.csv holds the older KenPom names of renamed teams
(Detroit -> Detroit Mercy, IPFW -> Purdue Fort Wayne, ...), built from KenPom's team lists for 2012-2027.
Barttorvik uses the same names as KenPom, so one lookup serves both. Every model table uses ESPN ids; names only
matter at the edges, when joining an outside source.
"""
from __future__ import annotations

import functools
import os
import re

import pandas as pd

PATH = os.path.join(os.path.dirname(__file__), "..", "data", "teams.csv")
ALIASES = os.path.join(os.path.dirname(__file__), "..", "data", "team_aliases.csv")


def load() -> pd.DataFrame:
    return pd.read_csv(PATH)


def norm(name: str) -> str:
    """Loose key for matching names across sources: 'St. John's (NY)' -> 'stjohnsny'."""
    s = str(name).lower().replace("&", "and")
    s = re.sub(r"\bstate\b", "st", s)
    s = re.sub(r"\bsaint\b", "st", s)
    return re.sub(r"[^a-z0-9]", "", s)


@functools.lru_cache
def id_lookup(column: str) -> dict[str, int]:
    """Normalized name in `column` (e.g. 'kenpom') -> ESPN id, including the older names in team_aliases.csv."""
    t = load().dropna(subset=[column])
    a = pd.read_csv(ALIASES)
    ids = {norm(n): int(i) for n, i in zip(a["name"], a["espn_id"])}
    ids.update({norm(n): int(i) for n, i in zip(t[column], t["espn_id"])})
    return ids
