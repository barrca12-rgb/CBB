"""Second line source: The Odds API (the-odds-api.com/v4), for games SportsGameOdds hasn't loaded yet.

SGO can lag the books by days (opening week 2026: DraftKings had dozens of Nov 2 games up, SGO two). odds.pull()
calls fetch() and keeps a row from here only where SGO has no line for that game and book. Same columns as odds.py,
with sgo_event = "oa:<event id>".

Needs ODDS_API_KEY (repository secret). Each pull costs 3 credits (spreads, totals, moneylines; our four books count
as one region). The free plan's 500 credits a month cover the pulls in PULL_HOURS (about 4 a day); set
ODDS_API_EVERY_RUN=1 on a paid plan to pull on every run. Manual runs (the Update button) always pull. Usage is kept
in lines/odds_api_usage.json; pulls stop when fewer than MIN_LEFT credits remain.

Credit reserve (Chad, Oct 30): the live system (card pulls here and the targeted quote polls, cbb/poll_targets.py)
may spend down to MIN_LEFT = 10,000 credits and stops below it; one phone alert goes out the first time the balance
falls below ALERT_AT = 20,000 (lines/odds_api_alert.json). The 50,000 floor belongs to research pulls only (their own
workflows), whose pulls are all scheduled after the Nov 25 renewal.

Show-only books (Chad, Oct 30, option 2): DISPLAY_BOOKS (Novig, a no-vig exchange) come in the same card call at no
extra credit (up to 10 books cost one region) but never enter the card's lines, the quote log or any close, so no pick,
price or CLV changes. Their latest prices go to lines/novig_latest.csv for the card and the phone alert to show beside
each play, and every change is appended to lines/novig_log.csv for the Jan 15 read.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from . import quotelog, teams

API = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars",
         "fanatics": "Fanatics", "bet365": "bet365", "espnbet": "theScore Bet"}   # up to 10 books cost one region
CORE = ["draftkings", "fanduel", "betmgm", "williamhill_us"]
DISPLAY_BOOKS = {"novig": "Novig"}   # show-only: never in the card's lines, the quote log or a close
NOVIG_LATEST = os.path.join(os.path.dirname(__file__), "..", "lines", "novig_latest.csv")
NOVIG_LOG = os.path.join(os.path.dirname(__file__), "..", "lines", "novig_log.csv")
DISPLAY_COLS = ["book", "event_id", "start", "home_id", "away_id", "home_spread", "home_spread_odds", "away_spread_odds",
                "total", "over_odds", "under_odds", "last_update", "pulled_at"]
# Book keys the API refused (wrong or not offered), found once by trying each extra book alone and then skipped
REFUSED = os.path.join(os.path.dirname(__file__), "..", "lines", "odds_api_refused_books.json")
PULL_HOURS = {7, 12, 18, 23}     # ET hours of the scheduled runs that pull (7:37 am, 12:37, 6:07 pm, 11:37 pm)
MIN_LEFT = 10_000                 # live reserve: card pulls and targeted polls stop below this (Chad, Oct 30)
ALERT_AT = 20_000                 # one phone alert the first time the balance falls below this
ALERTED = os.path.join(os.path.dirname(__file__), "..", "lines", "odds_api_alert.json")
MAX_AGE = pd.Timedelta(hours=12)
USAGE = os.path.join(os.path.dirname(__file__), "..", "lines", "odds_api_usage.json")


def budget_ok() -> bool:
    """False once the last recorded balance is below the live reserve (MIN_LEFT)."""
    u = json.load(open(USAGE)) if os.path.exists(USAGE) else {}
    return u.get("remaining") is None or u["remaining"] >= MIN_LEFT


def _alert_low(remaining) -> None:
    """One phone alert the first time the balance falls below ALERT_AT (re-armed once it is back above)."""
    if remaining is None:
        return
    st = json.load(open(ALERTED)) if os.path.exists(ALERTED) else {}
    if remaining >= ALERT_AT:
        if st.get("sent"):
            json.dump({"sent": False}, open(ALERTED, "w"))
        return
    if st.get("sent"):
        return
    try:
        from . import notify
        ok = notify.message("CBB: Odds API credits low",
                            f"{remaining:,} credits left (alert below {ALERT_AT:,}). Card pulls and targeted quote polls "
                            f"stop below {MIN_LEFT:,}. The plan renews Nov 25.")
    except Exception as e:
        print(f"Low-credit alert failed ({e}); continuing.")
        ok = False
    if ok:
        json.dump({"sent": True, "remaining": int(remaining), "at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")},
                  open(ALERTED, "w"))


def due() -> bool:
    """Pull on this run? Manual runs, a paid plan (ODDS_API_EVERY_RUN), the first run ever, or a PULL_HOURS run."""
    if not os.environ.get("ODDS_API_KEY"):
        return False
    u = json.load(open(USAGE)) if os.path.exists(USAGE) else {}
    if u.get("remaining") is not None and u["remaining"] < MIN_LEFT:
        return False
    if os.environ.get("ODDS_API_EVERY_RUN") or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or not u:
        return True
    return pd.Timestamp.now(tz="America/New_York").hour in PULL_HOURS


def _lookup() -> dict:
    t = teams.load()
    out = {}
    for col in ("espn_name", "espn_location", "kenpom"):
        out.update({teams.norm(n): int(i) for n, i in zip(t[col], t["espn_id"]) if isinstance(n, str)})
    out.update(teams.id_lookup("oddsapi"))
    return out


def _get(params: dict) -> tuple[list, dict]:
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r), {k.lower(): v for k, v in r.headers.items()}


def parse(events: list, lookup: dict | None = None) -> tuple[pd.DataFrame, list]:
    """Rows in odds.py's format from The Odds API's event list; also the team names that didn't match."""
    lookup = lookup or _lookup()
    now = pd.Timestamp.now(tz="UTC")
    rows, unmatched = [], set()
    obs = []   # forward-test log (quotelog.py): every quote seen at our books, stale ones included
    for ev in events:
        # a game past the feed's start is never priced on the card; its quotes are still passed to the forward-test
        # log, which keeps them only inside a watch window (a tip-time conflict's window before ESPN's start) and
        # which the protocol's close excludes (observed at or after the quote's own reported start)
        started = pd.to_datetime(ev.get("commence_time"), utc=True) <= now
        hn, an = ev.get("home_team"), ev.get("away_team")
        h, a = lookup.get(teams.norm(hn or "")), lookup.get(teams.norm(an or ""))
        if h is None or a is None:
            if not started:
                unmatched.update(n for n, i in ((hn, h), (an, a)) if i is None)
            continue
        for bk in ev.get("bookmakers") or []:
            if bk.get("key") not in BOOKS:
                continue
            for m in bk.get("markets") or []:
                if m.get("key") not in ("spreads", "totals"):
                    continue
                mu = m.get("last_update") or bk.get("last_update")
                mut = pd.to_datetime(mu, utc=True, errors="coerce")
                status = "stale" if pd.notna(mut) and now - mut > MAX_AGE else "available"
                for o in m.get("outcomes") or []:
                    nm = o.get("name")
                    side = ("home" if nm == hn else "away" if nm == an else None) if m["key"] == "spreads" else str(nm).lower()
                    if side in ("home", "away", "over", "under"):
                        obs.append(quotelog.observation("oddsapi", f"oa:{ev.get('id')}", ev.get("commence_time"), h, a,
                                                        BOOKS[bk["key"]], "spread" if m["key"] == "spreads" else "total",
                                                        side, o.get("point"), o.get("price"), mu, now, status))
            upd = pd.to_datetime(bk.get("last_update"), utc=True, errors="coerce")
            if started or (pd.notna(upd) and now - upd > MAX_AGE):
                continue
            r = {"book": BOOKS[bk["key"]], "sgo_event": f"oa:{ev.get('id')}", "start": ev.get("commence_time"),
                 "home_id": h, "away_id": a}
            for m in bk.get("markets") or []:
                for o in m.get("outcomes") or []:
                    name, price, link = o.get("name"), o.get("price"), o.get("link")
                    if m["key"] == "spreads":
                        side = "home" if name == hn else "away" if name == an else None
                        if side:
                            r[f"{side}_spread_odds"] = price
                            if link:
                                r[f"{side}_spread_link"] = link
                            if side == "home":
                                r["home_spread"] = o.get("point")
                    elif m["key"] == "totals":
                        side = str(name).lower()
                        if side in ("over", "under"):
                            r[f"{side}_odds"] = price
                            r["total"] = o.get("point")
                            if link:
                                r[f"{side}_link"] = link
                    elif m["key"] == "h2h":
                        side = "home" if name == hn else "away" if name == an else None
                        if side:
                            r[f"{side}_ml"] = price
                            if link:
                                r[f"{side}_ml_link"] = link
            rows.append(r)
    parse.observations, parse.observed_at = obs, now
    base = ["book", "sgo_event", "start", "home_id", "away_id", "home_spread", "total"]
    df = pd.DataFrame(rows).reindex(columns=list(dict.fromkeys(base + [c for r in rows for c in r])))
    for c in df.columns:
        if c.endswith(("_odds", "_ml", "spread")) or c == "total":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, sorted(unmatched)


def parse_display(events: list, lookup: dict | None = None) -> pd.DataFrame:
    """One row per game for each show-only book (DISPLAY_BOOKS), pregame and fresher than MAX_AGE, oriented to our
    home and away ids. Kept apart from parse(), so these books never reach the card's lines or the quote log."""
    lookup = lookup or _lookup()
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for ev in events:
        if pd.to_datetime(ev.get("commence_time"), utc=True) <= now:
            continue
        hn, an = ev.get("home_team"), ev.get("away_team")
        h, a = lookup.get(teams.norm(hn or "")), lookup.get(teams.norm(an or ""))
        if h is None or a is None:
            continue
        for bk in ev.get("bookmakers") or []:
            if bk.get("key") not in DISPLAY_BOOKS:
                continue
            upd = pd.to_datetime(bk.get("last_update"), utc=True, errors="coerce")
            if pd.notna(upd) and now - upd > MAX_AGE:
                continue
            r = {"book": DISPLAY_BOOKS[bk["key"]], "event_id": ev.get("id"), "start": ev.get("commence_time"),
                 "home_id": h, "away_id": a, "last_update": bk.get("last_update"),
                 "pulled_at": now.isoformat(timespec="seconds")}
            for m in bk.get("markets") or []:
                for o in m.get("outcomes") or []:
                    name, price = o.get("name"), o.get("price")
                    if m.get("key") == "spreads":
                        side = "home" if name == hn else "away" if name == an else None
                        if side:
                            r[f"{side}_spread_odds"] = price
                            if side == "home":
                                r["home_spread"] = o.get("point")
                    elif m.get("key") == "totals" and str(name).lower() in ("over", "under"):
                        r[f"{str(name).lower()}_odds"] = price
                        r["total"] = o.get("point")
            rows.append(r)
    return pd.DataFrame(rows).reindex(columns=DISPLAY_COLS)


def save_display(d: pd.DataFrame) -> None:
    """Latest show-only prices (overwritten each pull) and a change-only log for the Jan 15 read."""
    d.to_csv(NOVIG_LATEST, index=False)
    if not len(d):
        return
    key = ["book", "home_id", "away_id", "home_spread", "home_spread_odds", "away_spread_odds", "total", "over_odds",
           "under_odds"]
    def sig(x: pd.DataFrame) -> pd.Series:   # numbers compared as floats, so -110 and -110.0 match
        y = x[key].copy()
        for c in key[1:]:
            y[c] = pd.to_numeric(y[c], errors="coerce").astype(float)
        return y.astype(str).agg("|".join, axis=1)
    new = d
    if os.path.exists(NOVIG_LOG):
        last = pd.read_csv(NOVIG_LOG).drop_duplicates(["book", "home_id", "away_id"], keep="last")
        new = d[~sig(d).isin(set(sig(last)))]
    if len(new):
        new.to_csv(NOVIG_LOG, mode="a", header=not os.path.exists(NOVIG_LOG), index=False)


def display_quote(home_id: int, away_id: int, d: pd.DataFrame | None = None, max_age_h: float = 2.0) -> dict | None:
    """The latest show-only (Novig) prices for a game, oriented to the given home and away ids (the feed may list
    a neutral-site game the other way round). None when there is no row or the pull is older than max_age_h."""
    if d is None:
        if not os.path.exists(NOVIG_LATEST):
            return None
        d = pd.read_csv(NOVIG_LATEST)
    if not len(d):
        return None
    for flip in (False, True):
        h, a = (away_id, home_id) if flip else (home_id, away_id)
        m = d[(d["home_id"] == h) & (d["away_id"] == a)]
        if not len(m):
            continue
        r = m.iloc[-1]
        if pd.Timestamp.now(tz="UTC") - pd.to_datetime(r["pulled_at"], utc=True) > pd.Timedelta(hours=max_age_h):
            return None
        num = lambda c: float(r[c]) if pd.notna(r.get(c)) else None
        q = {"book": r["book"], "home_spread": num("home_spread"), "home_spread_odds": num("home_spread_odds"),
             "away_spread_odds": num("away_spread_odds"), "total": num("total"), "over_odds": num("over_odds"),
             "under_odds": num("under_odds"), "pulled_at": r["pulled_at"]}
        if flip:
            q.update(home_spread=-q["home_spread"] if q["home_spread"] is not None else None,
                     home_spread_odds=q["away_spread_odds"], away_spread_odds=q["home_spread_odds"])
        return q
    return None


def display_side(q: dict | None, market: str, side: str) -> tuple[float, float] | None:
    """(number, price) of a show-only quote on one side: spread line from that side, or the total."""
    if not q:
        return None
    if market == "spread":
        if q["home_spread"] is None or q.get(f"{side}_spread_odds") is None:
            return None
        return (q["home_spread"] if side == "home" else -q["home_spread"]), q[f"{side}_spread_odds"]
    if q["total"] is None or q.get(f"{side}_odds") is None:
        return None
    return q["total"], q[f"{side}_odds"]


def fetch_quotes(api_key: str | None = None) -> tuple[list, dict]:
    """Targeted poll for the forward-test log (poll_targets.py): spreads and totals only, no links, every book in the
    frozen set. Costs 2 credits per call however many games it returns. Returns (observations, info)."""
    api_key = api_key or os.environ.get("ODDS_API_KEY", "")
    refused = set(json.load(open(REFUSED))) if os.path.exists(REFUSED) else set()
    events, hdr = _get({"apiKey": api_key, "regions": "us", "markets": "spreads,totals", "oddsFormat": "american",
                        "bookmakers": ",".join(b for b in BOOKS if b not in refused)})
    parse(events)
    left = hdr.get("x-requests-remaining")
    return parse.observations, {"observed_at": parse.observed_at, "events": len(events),
                                "cost": int(float(hdr["x-requests-last"])) if hdr.get("x-requests-last") else None,
                                "remaining": int(float(left)) if left else None}


def fetch(api_key: str | None = None) -> pd.DataFrame:
    api_key = api_key or os.environ.get("ODDS_API_KEY", "")
    refused = set(json.load(open(REFUSED))) if os.path.exists(REFUSED) else set()
    books = [b for b in list(BOOKS) + list(DISPLAY_BOOKS) if b not in refused]   # show-only books ride the same call
    params = {"apiKey": api_key, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american",
              "bookmakers": ",".join(books), "includeLinks": "true"}
    try:
        events, hdr = _get(params)
    except urllib.error.HTTPError as e:
        if e.code not in (400, 422):
            raise
        # an extra book's key was refused: find which by trying each alone with the core books, remember it, and
        # pull with the rest (if the core books alone fail, links are the problem: pull without them)
        bad = []
        for b in [b for b in books if b not in CORE]:
            try:
                _get(dict(params, bookmakers=",".join(CORE + [b]), markets="spreads"))
            except urllib.error.HTTPError:
                bad.append(b)
        if bad:
            with open(REFUSED, "w") as fh:
                json.dump(sorted(refused | set(bad)), fh)
            print(f"The Odds API refused book keys {bad}; skipping them from now on.")
        ok = [b for b in books if b not in bad]
        try:
            events, hdr = _get(dict(params, bookmakers=",".join(ok)))
        except urllib.error.HTTPError:
            params.pop("includeLinks")
            events, hdr = _get(dict(params, bookmakers=",".join(ok)))
    df, fetch.unmatched = parse(events)
    try:   # show-only prices (Novig): their own files; a failure never touches the card
        save_display(parse_display(events))
    except Exception as e:
        print(f"Show-only prices failed ({e}); continuing.")
    fetch.events = len(events)
    fetch.observations, fetch.observed_at = parse.observations, parse.observed_at
    fetch.last_cost = int(float(hdr["x-requests-last"])) if hdr.get("x-requests-last") else None
    u = {"remaining": int(float(hdr.get("x-requests-remaining", "nan"))) if hdr.get("x-requests-remaining") else None,
         "used": int(float(hdr.get("x-requests-used", 0) or 0)), "at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(USAGE), exist_ok=True)
    with open(USAGE, "w") as f:
        json.dump(u, f)
    fetch.usage = u
    _alert_low(u["remaining"])
    return df
