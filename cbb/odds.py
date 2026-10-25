"""Live NCAAB lines from SportsGameOdds (api.sportsgameodds.com/v2), one row per (book, game), with betslip links.

Needs SGO_API_KEY (sent as X-Api-Key), or a network secret for api.sportsgameodds.com that adds it. Each pull
updates two files: lines/openers.csv keeps the first number seen for each game and book (the backtest's edge is
against the opener, so the card shows how far each line has moved, and first_seen says when books post), and
lines/closing.csv keeps the last pregame number (started games drop out of the feed, so their row stays as the
close). The tracker grades closing line value against closing.csv.

Columns: book, sgo_event, start, home_id, away_id (ESPN ids), home_spread (-3 = home favored by 3),
home_spread_odds, away_spread_odds, total, over_odds, under_odds, home_ml, away_ml, and *_link betslip URLs.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from . import teams

API = "https://api.sportsgameodds.com/v2/events"
LINES = os.path.join(os.path.dirname(__file__), "..", "lines")
BOOKS = {"fanduel": "FanDuel", "draftkings": "DraftKings", "betmgm": "BetMGM", "caesars": "Caesars",
         "espnbet": "ESPN BET", "fanatics": "Fanatics", "betrivers": "BetRivers", "hardrockbet": "Hard Rock",
         "bet365": "bet365"}
ODDS = {"points-home-game-sp-home": ("home_spread", "home_spread_odds", "home_spread_link"),
        "points-away-game-sp-away": (None, "away_spread_odds", "away_spread_link"),
        "points-all-game-ou-over": ("total", "over_odds", "over_link"),
        "points-all-game-ou-under": (None, "under_odds", "under_link"),
        "points-home-game-ml-home": (None, "home_ml", "home_ml_link"),
        "points-away-game-ml-away": (None, "away_ml", "away_ml_link")}
MAX_AGE = pd.Timedelta(hours=12)   # ignore a book's price it hasn't touched in this long (stale feed)


def _num(x):
    try:
        return float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return np.nan


def _team_id(t: dict, lookup: dict) -> int | None:
    """ESPN id from an SGO team: long name ('Notre Dame Fighting Irish') matches ESPN's display name; medium
    ('Notre Dame') or the teamID ('NOTRE_DAME_NCAAB') usually match the location."""
    names = t.get("names") or {}
    for cand in (names.get("long"), names.get("medium"), str(t.get("teamID", "")).removesuffix("_NCAAB").replace("_", " ")):
        if cand and teams.norm(cand) in lookup:
            return lookup[teams.norm(cand)]
    return None


def _lookup() -> dict:
    t = teams.load()
    out = {}
    for col in ("espn_location", "espn_name", "kenpom"):
        out.update({teams.norm(n): int(i) for n, i in zip(t[col], t["espn_id"]) if isinstance(n, str)})
    out.update(teams.id_lookup("sgo"))
    return out


def fetch(api_key: str | None = None, max_events: int = 1500) -> pd.DataFrame:
    api_key = api_key or os.environ.get("SGO_API_KEY", "")
    events, cursor = [], None
    while len(events) < max_events:
        q = {"leagueID": "NCAAB", "oddsAvailable": "true", "limit": 100, "oddID": ",".join(ODDS)}
        if cursor:
            q["cursor"] = cursor
        headers = {"User-Agent": "cbb-model"}
        if api_key:
            headers["X-Api-Key"] = api_key
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.load(r)
        events += body.get("data") or []
        cursor = body.get("nextCursor")
        if not cursor:
            break
    lookup = _lookup()
    now = pd.Timestamp.now(tz="UTC")
    rows, unmatched = [], set()
    for ev in events:
        st = ev.get("status") or {}
        if st.get("started") or st.get("ended") or st.get("cancelled"):
            continue
        tm = ev.get("teams") or {}
        h, a = _team_id(tm.get("home") or {}, lookup), _team_id(tm.get("away") or {}, lookup)
        if h is None or a is None:
            for side, i in (("home", h), ("away", a)):
                if i is None:
                    unmatched.add(((tm.get(side) or {}).get("names") or {}).get("long", "?"))
            continue
        per_book: dict = {}
        for odd_id, (line_col, price_col, link_col) in ODDS.items():
            for bk, o in ((ev.get("odds") or {}).get(odd_id, {}).get("byBookmaker") or {}).items():
                if bk not in BOOKS or o.get("available") is False:
                    continue
                upd = pd.to_datetime(o.get("lastUpdatedAt"), utc=True, errors="coerce")
                if pd.notna(upd) and now - upd > MAX_AGE:
                    continue
                r = per_book.setdefault(bk, {"book": BOOKS[bk], "sgo_event": ev.get("eventID"),
                                             "start": st.get("startsAt"), "home_id": h, "away_id": a})
                r[price_col] = _num(o.get("odds"))
                if o.get("deeplink"):
                    r[link_col] = o["deeplink"]
                if line_col == "home_spread":
                    r["home_spread"] = _num(o.get("spread"))
                elif line_col == "total":
                    r["total"] = _num(o.get("overUnder"))
        rows += per_book.values()
    fetch.unmatched = sorted(unmatched)
    fetch.events = len(events)
    return pd.DataFrame(rows)


def pull(api_key: str | None = None) -> pd.DataFrame:
    """Fetch, save a timestamped snapshot, and update lines/openers.csv. Returns the lines with open_home_spread and
    open_total (first number seen at that book) added."""
    l = fetch(api_key)
    os.makedirs(LINES, exist_ok=True)
    ts = pd.Timestamp.now(tz="UTC")
    if len(l):
        cl_path = os.path.join(LINES, "closing.csv")
        cur = l[["sgo_event", "book", "start", "home_id", "away_id", "home_spread", "home_spread_odds",
                 "away_spread_odds", "total", "over_odds", "under_odds"]].copy()
        cur["date"] = pd.to_datetime(cur["start"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        cur["pulled_at"] = ts.isoformat(timespec="seconds")
        old = pd.read_csv(cl_path) if os.path.exists(cl_path) else cur.iloc[:0]
        key = lambda d: d["sgo_event"].astype(str) + "|" + d["book"].astype(str)
        pd.concat([old[~key(old).isin(set(key(cur)))], cur], ignore_index=True).to_csv(cl_path, index=False)
    op_path = os.path.join(LINES, "openers.csv")
    op = pd.read_csv(op_path) if os.path.exists(op_path) else pd.DataFrame(
        columns=["sgo_event", "book", "home_id", "away_id", "open_home_spread", "open_total", "first_seen"])
    if len(l):
        new = l[["sgo_event", "book", "home_id", "away_id", "home_spread", "total"]].rename(
            columns={"home_spread": "open_home_spread", "total": "open_total"}).assign(first_seen=ts.isoformat())
        key = op["sgo_event"].astype(str) + "|" + op["book"].astype(str)
        new = new[~(new["sgo_event"].astype(str) + "|" + new["book"]).isin(set(key))]
        op = pd.concat([op, new], ignore_index=True)
        op.to_csv(op_path, index=False)
        l = l.merge(op[["sgo_event", "book", "open_home_spread", "open_total"]], on=["sgo_event", "book"], how="left")
    with open(os.path.join(LINES, "last_pull.txt"), "w") as f:
        f.write(f"{ts:%Y-%m-%d %H:%M} UTC  events {getattr(fetch, 'events', 0)}  book-game rows {len(l)}  "
                f"unmatched teams: {', '.join(getattr(fetch, 'unmatched', [])) or 'none'}\n")
    return l
