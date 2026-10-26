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

from . import quotelog, teams

API = "https://api.sportsgameodds.com/v2/events"
LINES = os.path.join(os.path.dirname(__file__), "..", "lines")
# The books we bet; plays and the board use only these.
BOOKS = {"fanduel": "FanDuel", "draftkings": "DraftKings", "betmgm": "BetMGM", "caesars": "Caesars", "fanatics": "Fanatics",
         "bet365": "bet365", "espnbet": "theScore Bet"}
ODDS = {"points-home-game-sp-home": ("home_spread", "home_spread_odds", "home_spread_link"),
        "points-away-game-sp-away": (None, "away_spread_odds", "away_spread_link"),
        "points-all-game-ou-over": ("total", "over_odds", "over_link"),
        "points-all-game-ou-under": (None, "under_odds", "under_link"),
        "points-home-game-ml-home": (None, "home_ml", "home_ml_link"),
        "points-away-game-ml-away": (None, "away_ml", "away_ml_link")}
MAX_AGE = pd.Timedelta(hours=12)   # ignore a book's price it hasn't touched in this long (stale feed)
# Quotes recorded for the forward-test log (moneylines are not part of the test)
OBS_SIDES = {"points-home-game-sp-home": ("spread", "home"), "points-away-game-sp-away": ("spread", "away"),
             "points-all-game-ou-over": ("total", "over"), "points-all-game-ou-under": ("total", "under")}


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


BUDGET_STOP = 0.95   # skip pulls once the month's entity use passes this share of the plan's allowance


def usage(api_key: str | None = None) -> dict:
    """This month's SportsGameOdds entity use: {"used", "max"} (empty if the account endpoint can't be read)."""
    api_key = api_key or os.environ.get("SGO_API_KEY", "")
    try:
        req = urllib.request.Request("https://api.sportsgameodds.com/v2/account/usage",
                                     headers={"User-Agent": "cbb-model", "X-Api-Key": api_key})
        with urllib.request.urlopen(req, timeout=30) as r:
            m = json.load(r)["data"]["rateLimits"]["per-month"]
        return {"used": int(m["current-entities"]), "max": int(m["max-entities"])}
    except Exception:
        return {}


def fetch(api_key: str | None = None, max_events: int = 1500) -> pd.DataFrame:
    api_key = api_key or os.environ.get("SGO_API_KEY", "")
    u = usage(api_key)
    fetch.usage = u
    if u and u["used"] >= BUDGET_STOP * u["max"]:
        raise RuntimeError(f"SGO monthly allowance nearly used ({u['used']:,} of {u['max']:,} entities)")
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
    obs = []   # forward-test log (quotelog.py): every quote seen, including unavailable and stale ones
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
                if bk in BOOKS and odd_id in OBS_SIDES:
                    upd0 = pd.to_datetime(o.get("lastUpdatedAt"), utc=True, errors="coerce")
                    status = "unavailable" if o.get("available") is False else \
                        "stale" if pd.notna(upd0) and now - upd0 > MAX_AGE else "available"
                    mk, side = OBS_SIDES[odd_id]
                    obs.append(quotelog.observation("sgo", ev.get("eventID"), st.get("startsAt"), h, a, BOOKS[bk], mk,
                                                    side, _num(o.get("spread") if mk == "spread" else o.get("overUnder")),
                                                    _num(o.get("odds")), o.get("lastUpdatedAt"), now, status))
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
    fetch.observations, fetch.observed_at = obs, now
    base = ["book", "sgo_event", "start", "home_id", "away_id", "home_spread", "total"]
    return pd.DataFrame(rows).reindex(columns=list(dict.fromkeys(base + [c for r in rows for c in r])))


def game_key(d: pd.DataFrame) -> pd.Series:
    """Source-independent game id: ET date and the two team ids in sorted order (sources can disagree on which team
    is home at a neutral site)."""
    date = pd.to_datetime(d["start"], utc=True, format="ISO8601").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    lo = np.minimum(d["home_id"].astype(int), d["away_id"].astype(int)).astype(str)
    hi = np.maximum(d["home_id"].astype(int), d["away_id"].astype(int)).astype(str)
    return date + "|" + lo + "|" + hi


def _flip(d: pd.DataFrame) -> pd.DataFrame:
    """Same lines from the other team's side (home and away swapped)."""
    sw = {"home_id": "away_id", "home_spread_odds": "away_spread_odds", "home_ml": "away_ml",
          "home_spread_link": "away_spread_link", "home_ml_link": "away_ml_link"}
    sw.update({v: k for k, v in sw.items()})
    d = d.rename(columns={k: v for k, v in sw.items() if k in d})
    d["home_spread"] = -d["home_spread"]
    return d


def _merge_second_source(l: pd.DataFrame, extra: pd.DataFrame, cl_path: str) -> pd.DataFrame:
    """Add The Odds API rows for (game, book) pairs SGO doesn't have, oriented like SGO (or like the game's earlier
    rows in closing.csv) so every source agrees on which team is home."""
    if not len(extra):
        return l
    extra = extra.assign(gk=game_key(extra))
    have = set(game_key(l) + "|" + l["book"]) if len(l) else set()
    extra = extra[~(extra["gk"] + "|" + extra["book"]).isin(have)]
    ref = {}
    if os.path.exists(cl_path):
        old = pd.read_csv(cl_path)
        if len(old):
            ref.update(dict(zip(game_key(old), old["home_id"])))
    if len(l):
        ref.update(dict(zip(game_key(l), l["home_id"])))
    want = extra["gk"].map(ref)
    flip = want.notna() & (want != extra["home_id"])
    extra = pd.concat([extra[~flip], _flip(extra[flip])], ignore_index=True).drop(columns="gk")
    return pd.concat([l, extra], ignore_index=True) if len(l) else extra


MOVES = os.path.join(LINES, "moves.csv")
MOVE_COLS = ["spread", "spread_odds_lo", "spread_odds_hi", "total", "over_odds", "under_odds"]


def _log_moves(cur: pd.DataFrame) -> int:
    """Append each (game, book) whose number or price changed since its last logged row to lines/moves.csv: when
    books post, how fast lines move, and whether injury news came before a move. Spreads are stored for the team
    with the lower ESPN id (lo_id), so rows from sources that disagree on home and away compare cleanly."""
    c = cur.assign(game_key=game_key(cur))
    lo = np.minimum(c["home_id"], c["away_id"])
    home_lo = c["home_id"] == lo
    c["lo_id"], c["hi_id"] = lo, np.maximum(c["home_id"], c["away_id"])
    c["spread"] = np.where(home_lo, c["home_spread"], -c["home_spread"])
    c["spread_odds_lo"] = np.where(home_lo, c["home_spread_odds"], c["away_spread_odds"])
    c["spread_odds_hi"] = np.where(home_lo, c["away_spread_odds"], c["home_spread_odds"])
    c = c[["pulled_at", "date", "game_key", "book", "lo_id", "hi_id"] + MOVE_COLS]
    if os.path.exists(MOVES):
        old = pd.read_csv(MOVES)
        last = old.drop_duplicates(["game_key", "book"], keep="last").set_index(["game_key", "book"])[MOVE_COLS]
        prev = last.reindex(pd.MultiIndex.from_frame(c[["game_key", "book"]]))
        same = (prev.to_numpy() == c[MOVE_COLS].to_numpy()) | (prev.isna().to_numpy() & c[MOVE_COLS].isna().to_numpy())
        c = c[~same.all(axis=1)]
        c = pd.concat([old, c], ignore_index=True)
    c.to_csv(MOVES, index=False)
    return len(c)


SGO_MIN_GAP = pd.Timedelta(minutes=25)
SGO_LAST = os.path.join(LINES, "sgo_last_pull.txt")


def _sgo_last() -> pd.Timestamp | None:
    try:
        with open(SGO_LAST) as fh:
            return pd.Timestamp(fh.read().strip())
    except (OSError, ValueError):
        return None


def pull(api_key: str | None = None) -> pd.DataFrame:
    """Fetch, save a timestamped snapshot, and update lines/openers.csv. Returns the lines with open_home_spread and
    open_total (first number seen at that book) added. SGO first; The Odds API (odds_api.py) fills games and books
    SGO doesn't have, on the runs it's due."""
    from . import odds_api
    os.makedirs(LINES, exist_ok=True)
    cl_path = os.path.join(LINES, "closing.csv")
    empty = pd.DataFrame(columns=["book", "sgo_event", "start", "home_id", "away_id", "home_spread", "total"])
    pending_obs = []   # (observations, poll_id, observed_at): logged after openers.csv, so new games are watched
    last = _sgo_last()
    if odds_api.due() and last is not None and pd.Timestamp.now(tz="UTC") - last < SGO_MIN_GAP:
        l = empty   # runs every 10 minutes; SGO's monthly allowance (shared with the NFL model) gets every third
        quotelog.poll("sgo", "skipped", quotelog.now(), error="less than 25 minutes since the last SGO pull")
    else:
        try:
            l = fetch(api_key)
            with open(SGO_LAST, "w") as fh:
                fh.write(pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"))
            u = getattr(fetch, "usage", {}) or {}
            pid = quotelog.poll("sgo", "ok", fetch.observed_at, events=fetch.events, quotes=len(fetch.observations),
                                cost=fetch.events, remaining=(u["max"] - u["used"] - fetch.events) if u else None)
            pending_obs.append((fetch.observations, pid, fetch.observed_at))
        except Exception as e:
            quotelog.poll("sgo", "error", quotelog.now(), error=e)
            if not odds_api.due():
                raise
            print(f"SportsGameOdds failed ({e}); using The Odds API only.")
            l = empty
    n_sgo = len(l)
    if odds_api.due():
        try:
            l = _merge_second_source(l, odds_api.fetch(), cl_path)
            oa = odds_api.fetch
            pid = quotelog.poll("oddsapi", "ok", oa.observed_at, events=oa.events, quotes=len(oa.observations),
                                cost=oa.last_cost, remaining=(oa.usage or {}).get("remaining"))
            pending_obs.append((oa.observations, pid, oa.observed_at))
        except Exception as e:
            quotelog.poll("oddsapi", "error", quotelog.now(), error=e)
            print(f"The Odds API failed ({e}); SGO lines only.")
    else:
        quotelog.poll("oddsapi", "skipped", quotelog.now(), error="not due on this run")
    ts = pd.Timestamp.now(tz="UTC")
    if len(l):
        cur = l.reindex(columns=["sgo_event", "book", "start", "home_id", "away_id", "home_spread", "home_spread_odds",
                                 "away_spread_odds", "total", "over_odds", "under_odds"]).copy()
        cur["date"] = pd.to_datetime(cur["start"], utc=True, format="ISO8601").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        cur["pulled_at"] = ts.isoformat(timespec="seconds")
        old = pd.read_csv(cl_path) if os.path.exists(cl_path) else cur.iloc[:0]
        key = lambda d: game_key(d) + "|" + d["book"].astype(str)
        pd.concat([old[~key(old).isin(set(key(cur)))], cur], ignore_index=True).to_csv(cl_path, index=False)
        _log_moves(cur)
    op_path = os.path.join(LINES, "openers.csv")
    op = pd.read_csv(op_path) if os.path.exists(op_path) else pd.DataFrame(
        columns=["sgo_event", "book", "home_id", "away_id", "open_home_spread", "open_total", "first_seen"])
    if "game_key" not in op and len(op):   # older file keyed by SGO event: look the games up in closing.csv
        c = pd.read_csv(cl_path)
        op["game_key"] = op["sgo_event"].map(dict(zip(c["sgo_event"], game_key(c))))
    op = op.reindex(columns=["game_key", "sgo_event", "book", "home_id", "away_id", "open_home_spread", "open_total",
                             "first_seen"])
    if len(l):
        l = l.assign(game_key=game_key(l))
        new = l[["game_key", "sgo_event", "book", "home_id", "away_id", "home_spread", "total"]].rename(
            columns={"home_spread": "open_home_spread", "total": "open_total"}).assign(first_seen=ts.isoformat())
        key = set(op["game_key"].astype(str) + "|" + op["book"].astype(str))
        new = new[~(new["game_key"] + "|" + new["book"]).isin(key)]
        op = pd.concat([op, new], ignore_index=True) if len(op) else new
        op.to_csv(op_path, index=False)
        m = op[["game_key", "book", "home_id", "open_home_spread", "open_total"]].rename(columns={"home_id": "op_home"})
        l = l.merge(m, on=["game_key", "book"], how="left")
        flipped = l["op_home"].notna() & (l["op_home"] != l["home_id"])
        l.loc[flipped, "open_home_spread"] = -l.loc[flipped, "open_home_spread"]
        l = l.drop(columns=["op_home", "game_key"])
    pull.pulled_at = ts.isoformat(timespec="seconds")   # the lines this run's signals were built on (quotelog)
    pull.observations = pending_obs   # the generating pull's quotes, for each new signal's quote record (quotelog)
    for obs, pid, at in pending_obs:
        quotelog.observations(obs, pid, at)
    quotelog.compact()
    oa = getattr(odds_api.fetch, "usage", None)
    with open(os.path.join(LINES, "last_pull.txt"), "w") as f:
        f.write(f"{ts:%Y-%m-%d %H:%M} UTC  events {getattr(fetch, 'events', 0)}  book-game rows {len(l)} "
                f"({n_sgo} SGO, {len(l) - n_sgo} The Odds API)  "
                f"unmatched teams: {', '.join(sorted(set(getattr(fetch, 'unmatched', [])) | set(getattr(odds_api.fetch, 'unmatched', [])))) or 'none'}"
                + (f"  SGO month: {u['used']:,} of {u['max']:,} entities" if (u := getattr(fetch, "usage", {})) else "")
                + (f"  The Odds API credits left: {oa['remaining']}" if oa and oa.get("remaining") is not None else "")
                + "\n")
    return l
