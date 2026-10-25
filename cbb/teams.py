"""Team names across sources, keyed by ESPN team id (the id hoopR uses).

data/teams.csv starts from hoopR's team crosswalk (ESPN -> KenPom names) for the 2025-26 Division I field,
with a few manual fixes marked source=manual. data/team_aliases.csv adds the older names a
source used for a team, and teams that have since left Division I. Barttorvik and SportsGameOdds names get added the same way once
those sources are reachable. Every model table uses ESPN ids; names only matter at the edges, when joining an
outside source.
"""
from __future__ import annotations

import os
import re

import pandas as pd

PATH = os.path.join(os.path.dirname(__file__), "..", "data", "teams.csv")
# Older names a source used for a team (e.g. KenPom's "IPFW" for Purdue Fort Wayne), and teams that have left D-I.
ALIASES = os.path.join(os.path.dirname(__file__), "..", "data", "team_aliases.csv")


def load() -> pd.DataFrame:
    return pd.read_csv(PATH)


def norm(name: str) -> str:
    """Loose key for matching names across sources: 'St. John's (NY)' -> 'stjohnsny'."""
    s = str(name).lower().replace("&", "and")
    s = re.sub(r"\bstate\b", "st", s)
    s = re.sub(r"\bsaint\b", "st", s)
    return re.sub(r"[^a-z0-9]", "", s)


def id_lookup(column: str) -> dict[str, int]:
    """Normalized name in `column` (e.g. 'kenpom') -> ESPN id, including that source's older names."""
    t = load()
    t = t.dropna(subset=[column]) if column in t else t.iloc[:0].assign(**{column: []})
    out = {norm(n): int(i) for n, i in zip(t[column], t["espn_id"])}
    a = pd.read_csv(ALIASES)
    a = a[a["source"] == column]
    out.update({norm(n): int(i) for n, i in zip(a["name"], a["espn_id"])})
    return out
