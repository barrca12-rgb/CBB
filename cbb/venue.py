"""Venue check for the neutral flag (reads and displays only; Chad's Oct 30 brief, item 1).

ESPN's neutral flag decides whether home court enters a projection (about 3 points), and it is unreliable in
November's multi-team events. This compares each game's flag with its venue: the arena ESPN lists for the game
against each team's own home arena(s) on file (data/home_arenas.csv).

  confirmed  the flag agrees with the venue: neutral at an arena belonging to neither team, or a home game at the
             listed home team's arena
  conflict   the flag disagrees: neutral at one team's arena, or a home game at the other team's arena or at
             neither's
  unknown    no venue, or the venue matches neither team and a team has no arena on file

Two edge cases are flagged on top: "home city" (neutral, in a team's home city but not at its arena; or a home game
at another venue in the home team's own city) and "reversed" (the listed home team is the visitor at the venue: the
arena is the listed away team's).

The model's flag is never changed here. The card, the phone alert and Discord show the state; cached per date in
reports/venue_<date>.csv.
"""
from __future__ import annotations

import json
import os
import urllib.request

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
ARENAS = os.path.join(ROOT, "data", "home_arenas.csv")
CACHE = os.path.join(ROOT, "reports", "venue_{}.csv")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
              "?dates={}&groups=50&limit=500")
COLS = ["game_id", "date", "home_id", "away_id", "neutral", "venue_id", "venue", "city", "state", "event",
        "home_venue_id", "away_venue_id", "venue_state", "reason", "edge"]


def arenas() -> pd.DataFrame:
    a = pd.read_csv(ARENAS) if os.path.exists(ARENAS) else pd.DataFrame(columns=["espn_id", "venue_id", "alt_venue_ids", "city"])
    return a


def _venue_sets(a: pd.DataFrame) -> tuple[dict, dict]:
    """team -> set of its home venue ids (primary plus alternates); team -> primary arena city."""
    sets, city = {}, {}
    for _, r in a.iterrows():
        s = set()
        if pd.notna(r.get("venue_id")):
            s.add(int(r["venue_id"]))
        for v in str(r.get("alt_venue_ids") or "").split(";"):
            if v.strip().isdigit():
                s.add(int(v))
        sets[int(r["espn_id"])] = s
        if isinstance(r.get("city"), str):
            city[int(r["espn_id"])] = r["city"].strip().lower()
    return sets, city


def classify(neutral: bool, venue_id, venue_city, home_id: int, away_id: int, sets: dict, city: dict,
             home_team_venue=None, away_team_venue=None) -> tuple[str, str, str]:
    """(state, reason, edge). home_team_venue / away_team_venue: the team's current arena id from the same feed,
    added to the team's set when given."""
    if venue_id is None or pd.isna(venue_id):
        return "unknown", "no venue listed", ""
    v = int(venue_id)
    hs, as_ = set(sets.get(home_id, set())), set(sets.get(away_id, set()))
    if home_team_venue is not None and pd.notna(home_team_venue):
        hs.add(int(home_team_venue))
    if away_team_venue is not None and pd.notna(away_team_venue):
        as_.add(int(away_team_venue))
    if v in hs:
        return ("conflict", "flagged neutral at the home team's arena", "") if neutral else ("confirmed", "home team's arena", "")
    if v in as_:
        return ("conflict", "flagged neutral at the away team's arena", "") if neutral else \
            ("conflict", "home game at the listed away team's arena", "reversed")
    if not hs or not as_:
        return "unknown", "venue matches neither team and a team has no arena on file", ""
    vc = str(venue_city or "").strip().lower()
    edge = "home city" if neutral and vc and vc in (city.get(home_id), city.get(away_id)) else ""
    if neutral:
        return "confirmed", "neutral, arena belongs to neither team", edge
    # a home game at another venue in the home team's own city (an old gym, a downtown arena) stays a conflict by
    # definition, labelled so the mark says which kind
    return "conflict", "home game at an arena belonging to neither team", "home city" if vc and vc == city.get(home_id) else ""


def fetch_day(day: pd.Timestamp) -> pd.DataFrame:
    """ESPN's scoreboard for one date, every D-I game with its venue, classified."""
    req = urllib.request.Request(SCOREBOARD.format(pd.Timestamp(day).strftime("%Y%m%d")), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    sets, city = _venue_sets(arenas())
    rows = []
    for ev in d.get("events") or []:
        c = (ev.get("competitions") or [{}])[0]
        side = {t.get("homeAway"): t for t in c.get("competitors") or []}
        if "home" not in side or "away" not in side:
            continue
        ven = c.get("venue") or {}
        h, a = int(side["home"]["team"]["id"]), int(side["away"]["team"]["id"])
        hv = (side["home"]["team"].get("venue") or {}).get("id")
        av = (side["away"]["team"].get("venue") or {}).get("id")
        neutral = bool(c.get("neutralSite"))
        vid = int(ven["id"]) if str(ven.get("id", "")).isdigit() else None
        st, why, edge = classify(neutral, vid, (ven.get("address") or {}).get("city"), h, a, sets, city,
                                 int(hv) if str(hv or "").isdigit() else None, int(av) if str(av or "").isdigit() else None)
        rows.append({"game_id": int(ev["id"]), "date": pd.Timestamp(day).strftime("%Y-%m-%d"), "home_id": h, "away_id": a,
                     "neutral": neutral, "venue_id": vid, "venue": ven.get("fullName"),
                     "city": (ven.get("address") or {}).get("city"), "state": (ven.get("address") or {}).get("state"),
                     "event": "; ".join(n.get("headline", "") for n in c.get("notes") or [] if n.get("headline")),
                     "home_venue_id": hv, "away_venue_id": av, "venue_state": st, "reason": why, "edge": edge})
    return pd.DataFrame(rows).reindex(columns=COLS)


def day_table(day, refresh: bool = False) -> pd.DataFrame:
    """The cached venue check for a date: fetched when missing, or when refresh and the cache is over 3 hours old."""
    path = CACHE.format(pd.Timestamp(day).strftime("%Y-%m-%d"))
    fresh = os.path.exists(path) and pd.Timestamp.now().timestamp() - os.path.getmtime(path) < 3 * 3600
    if os.path.exists(path) and (fresh or not refresh):
        return pd.read_csv(path)
    t = fetch_day(day)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t.to_csv(path, index=False)
    return t


def lookup(day, game_id, refresh: bool = True) -> dict | None:
    """{state, venue, city, reason, edge} for one game, or None. Never raises."""
    try:
        t = day_table(day, refresh)
        m = t[t["game_id"].astype(str) == str(game_id)]
        if not len(m):
            return None
        r = m.iloc[0]
        val = lambda k: r[k] if pd.notna(r[k]) else ""
        return {"state": r["venue_state"], "venue": val("venue"), "city": val("city"), "reason": val("reason"), "edge": val("edge")}
    except Exception as e:
        print(f"Venue check failed ({e}); continuing.")
        return None


def word(v: dict | None) -> str:
    """The one-line mark for alerts: 'Venue: conflict (flagged neutral at the home team's arena), Arena, City'."""
    if not v:
        return "Venue: unknown"
    place = ", ".join(x for x in (v.get("venue"), v.get("city")) if x)
    extra = v["reason"] if v["state"] != "confirmed" else ""
    if v.get("edge"):
        extra = (extra + "; " if extra else "") + v["edge"]
    return f"Venue: {v['state']}" + (f" ({extra})" if extra else "") + (f", {place}" if place else "")
