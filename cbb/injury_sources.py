"""Multi-source injury logger: which outlet reports a college basketball injury first, and does it beat the line?

Sources (each pulled on every card run, about every 30 minutes):

    espn      site.api.espn.com league-wide injuries feed (the model's input today, see injuries.py)
    rotowire  rotowire.com/cbasketball injury report (the JSON table behind the page)
    covers    covers.com/sport/basketball/ncaab/injuries
    cbs       cbssports.com/college-basketball/injuries/
    action    actionnetwork.com/ncaab/injury-report (the page's embedded __NEXT_DATA__ JSON)

Files in injuries/sources/:

    first_seen.csv  one row per (source, team, player, status) the first run a source shows it, plus a "cleared" row
                    the first run a listed player drops off that source's report. first_seen is the poll time, so
                    timing is good to one run (30 minutes); source_date is what the outlet itself says.
    current.csv     each source's report as of its last successful pull (to spot players dropping off).
    health.csv      every pull: rows parsed, teams and players matched, error. A source that breaks shows up here
                    and is skipped; it never stops the card.
    raw/<source>    a copy of a page that parsed to 0 rows (at most once a day), to fix a parser offline.
    timing.md       the scoreboard: for each injury that matters (Out/Doubtful/Questionable, 10%+ of minutes, before
                    tip) which sources had it, how far behind the first one, and whether they had it before the
                    spread moved against the team (lines/moves.csv).
    choice.json     which source feeds the model (injuries.py). ESPN until the switch rule below fires.

Switch rule (set before any data, so the choice can't be fit to noise): after 7 game days with 30+ material injuries
matched to a line move, or after 14 game days with 10+, pick the source that reported before the move most often
(ties within 2 points go to ESPN, then to the bigger median lead). A source also needs 85%+ of its players matched
to ESPN athlete ids, or switching would quietly drop injuries from the projection. The pick is made once and kept;
edit choice.json to override. Only where the injury input comes from changes: P(miss) by status, the missing-minutes
weight and every bet rule stay as they are.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

import numpy as np
import pandas as pd

from . import data, teams

DIR = os.path.join(os.path.dirname(__file__), "..", "injuries", "sources")
FIRST = os.path.join(DIR, "first_seen.csv")
CURRENT = os.path.join(DIR, "current.csv")
HEALTH = os.path.join(DIR, "health.csv")
TIMING = os.path.join(DIR, "timing.md")
CHOICE = os.path.join(DIR, "choice.json")
LINES = os.path.join(os.path.dirname(__file__), "..", "lines")

URLS = {
    "espn": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/injuries",
    "rotowire": "https://www.rotowire.com/cbasketball/tables/injury-report.php?team=ALL&pos=ALL",
    "covers": "https://www.covers.com/sport/basketball/ncaab/injuries",
    "cbs": "https://www.cbssports.com/college-basketball/injuries/",
    "action": "https://www.actionnetwork.com/ncaab/injury-report",
}
SOURCES = list(URLS)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
COLS = ["source", "team", "team_id", "player", "player_key", "athlete_id", "status", "status_raw", "comment",
        "source_date"]

# switch rule (see the module docstring)
MATERIAL_STATUS = {"out", "doubtful", "questionable"}
MATERIAL_SHARE = 0.10
MOVE_PTS = 1.0                 # spread move against the team, at any book, that counts as "the market reacted"
MOVE_LOOKBACK = pd.Timedelta(hours=12)   # a move up to 12h before the first report still counts (everyone was late)
SAME_RUN = pd.Timedelta(minutes=10)      # a report in the same run as the move did not beat it
MIN_DAYS, MIN_EVENTS = 7, 30
MAX_DAYS, MIN_EVENTS_LATE = 14, 10
TIE_PTS, MIN_MATCH = 0.02, 0.85

_RUN: dict[str, pd.DataFrame] = {}       # this run's parsed reports, so injuries.py doesn't fetch twice


# ---------------------------------------------------------------- statuses and names

def norm_status(s: str) -> str:
    """Map each outlet's wording onto injuries.P_MISS's keys: out, doubtful, questionable, day-to-day, probable. The
    leading label wins ("Questionable - could be out" is questionable); free text falls back to keywords."""
    s = " ".join(str(s or "").lower().split())
    for label, key in (("out", "out"), ("o", "out"), ("doubtful", "doubtful"), ("d", "doubtful"),
                       ("questionable", "questionable"), ("q", "questionable"), ("game-time", "questionable"),
                       ("game time", "questionable"), ("gtd", "questionable"), ("day-to-day", "day-to-day"),
                       ("day to day", "day-to-day"), ("dtd", "day-to-day"), ("probable", "probable"), ("p", "probable"),
                       ("suspended", "out"), ("inactive", "out"), ("unavailable", "out"), ("redshirt", "out")):
        if re.match(rf"{re.escape(label)}\b", s):
            return key
    if re.search(r"\bout\b|season|indefinite|suspend|redshirt|inactive|unavailable|not expected|ruled out", s):
        return "out"
    for word, key in (("doubt", "doubtful"), ("question", "questionable"), ("game-time", "questionable"),
                      ("day-to-day", "day-to-day"), ("probable", "probable"), ("expected to play", "probable")):
        if word in s:
            return key
    return s or "unknown"


def player_key(name: str) -> str:
    """'D.J. Wagner Jr.' -> 'djwagner'; 'Wagner, D.J.' -> 'djwagner'."""
    s = str(name or "")
    if "," in s and not re.search(r",\s*(jr|sr|ii|iii|iv)\.?$", s, re.I):
        last, first = s.split(",", 1)
        s = f"{first} {last}"
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s.lower())
    return re.sub(r"[^a-z]", "", s)


def _team_lookup() -> dict[str, int]:
    """Every name we know a team by (location, full name, abbreviation, KenPom, line sources, each outlet's aliases in
    data/team_aliases.csv) -> ESPN id. Add an alias row with source=<outlet> for a name health.csv reports unmatched."""
    t = teams.load()
    out: dict[str, int] = {}
    for col in ("kenpom", "espn_abbr", "espn_name", "espn_location"):   # later columns win on collisions
        out.update({teams.norm(n): int(i) for n, i in zip(t[col], t["espn_id"]) if isinstance(n, str)})
    for src in ["sgo", "oddsapi"] + SOURCES:
        out.update(teams.id_lookup(src))
    return out


def _team_id(name, lookup: dict[str, int]):
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return None
    # exact names only (no guessing by dropping words: "Southern California" is not Southern); a leading rank goes
    return lookup.get(teams.norm(re.sub(r"^\s*(#\d+|\(\d+\))\s*", "", str(name))))


_ROSTER: dict[tuple[int, str], float] | None = None


def _roster() -> dict[tuple[int, str], float]:
    """(team_id, player_key) -> ESPN athlete id from this and last season's box scores."""
    global _ROSTER
    if _ROSTER is None:
        _ROSTER = {}
        now = pd.Timestamp.now(tz="America/New_York")
        season = now.year + 1 if now.month >= 8 else now.year
        for s in (season - 1, season):
            try:
                p = data.fetch("player_box", s, refresh=s == season)
            except Exception:
                continue
            p = p[p["athlete_id"].notna()]
            name = p["athlete_display_name"] if "athlete_display_name" in p else p.get("athlete_name")
            if name is None:
                continue
            for t, n, a in zip(p["team_id"], name, p["athlete_id"]):
                _ROSTER[(int(t), player_key(n))] = float(a)
    return _ROSTER


# ---------------------------------------------------------------- fetching and parsing

def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                                               "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _row(team, player, status, comment="", source_date="", athlete_id=None, team_id=None) -> dict:
    return {"team": team, "team_id": team_id, "player": " ".join(str(player or "").split()), "status_raw": status,
            "comment": " ".join(str(comment or "").split())[:200], "source_date": str(source_date or ""),
            "athlete_id": athlete_id}


def parse_espn(text: str) -> list[dict]:
    d = json.loads(text)
    out = []
    for t in d.get("injuries") or []:
        for i in t.get("injuries") or []:
            a = i.get("athlete") or {}
            href = next((l.get("href", "") for l in a.get("links") or [] if "/id/" in l.get("href", "")), "")
            m = re.search(r"/id/(\d+)", href)
            out.append(_row(t.get("displayName"), a.get("displayName"), i.get("status"), i.get("shortComment"),
                            i.get("date"), float(m.group(1)) if m else None, int(t["id"])))
    return out


def parse_rotowire(text: str) -> list[dict]:
    d = json.loads(text)
    d = d.get("data", d) if isinstance(d, dict) else d
    out = []
    for r in d or []:
        name = r.get("player") or f"{r.get('firstname', '')} {r.get('lastname', '')}".strip()
        out.append(_row(r.get("team") or r.get("teamName"), name, r.get("status"),
                        " ".join(str(r.get(k) or "") for k in ("injury", "rDate")).strip(),
                        r.get("date") or r.get("rDate")))
    return out


def _cell_text(td) -> str:
    """Prefer the long player name where a cell carries both (CBS: 'J. Smith' and 'John Smith')."""
    long = td.select_one("[class*='long'], [class*='Long']")
    return (long or td).get_text(" ", strip=True)


def parse_tables(html: str) -> list[dict]:
    """Generic HTML injury tables (CBS, Covers): any table with a player column and a status column, the team taken
    from the nearest heading or team-name element above it."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    teamish = lambda tag: (tag.name in ("h2", "h3", "h4", "caption") or any(
        re.search(r"team.?name|TeamName|TableBase-title|team-title|covers-CoversMatchups-teamName", c)
        for c in tag.get("class") or []))
    out = []
    for tb in soup.find_all("table"):
        heads = [th.get_text(" ", strip=True).lower() for th in tb.select("thead th")] or \
                [c.get_text(" ", strip=True).lower() for c in (tb.find("tr").find_all(["th", "td"]) if tb.find("tr") else [])]
        ip = next((i for i, h in enumerate(heads) if "player" in h or h == "name"), None)
        ist = next((i for i, h in enumerate(heads) if "status" in h), None)
        if ip is None or ist is None:
            continue
        iinj = next((i for i, h in enumerate(heads) if h in ("injury", "injury type") or "description" in h), None)
        idate = next((i for i, h in enumerate(heads) if "updated" in h or h == "date"), None)
        cap = tb.find("caption")
        th = cap if cap else tb.find_previous(teamish)
        team = th.get_text(" ", strip=True) if th else None
        rows = tb.select("tbody tr") or tb.find_all("tr")[1:]
        for tr in rows:
            td = tr.find_all(["td", "th"])
            if len(td) <= max(ip, ist):
                continue
            pick = lambda i: td[i].get_text(" ", strip=True) if i is not None and i < len(td) else ""
            out.append(_row(team, _cell_text(td[ip]), pick(ist), pick(iinj), pick(idate)))
    return out


def parse_action(html: str) -> list[dict]:
    """Action Network's page embeds its data as Next.js JSON. Walk it: dicts with a status and a player are injuries,
    their team from an enclosing team dict or a team id in the page's team list."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return parse_tables(html)
    root = json.loads(m.group(1))
    team_names: dict = {}
    out: list[dict] = []

    def tname(d):
        return d.get("full_name") or d.get("display_name") or d.get("location") or d.get("name")

    def collect(o):
        if isinstance(o, dict):
            if "id" in o and ("abbr" in o or "location" in o) and tname(o):
                team_names[o["id"]] = tname(o)
            for v in o.values():
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    def walk(o, team=None):
        if isinstance(o, dict):
            if "id" in o and ("abbr" in o or "location" in o) and tname(o) and \
                    any(isinstance(v, list) for v in o.values()):
                team = tname(o)
            p = o.get("player")
            name = (p.get("full_name") or p.get("name") or tname(p)) if isinstance(p, dict) else \
                (o.get("player_name") or (o.get("full_name") if "status" in o and "injury" in str(o).lower() else None))
            if "status" in o and isinstance(o.get("status"), str) and name:
                tid = o.get("team_id") or (p.get("team_id") if isinstance(p, dict) else None)
                out.append(_row(team_names.get(tid, team), name, o["status"],
                                o.get("description") or o.get("injury") or o.get("short_description") or "",
                                o.get("updated_at") or o.get("date") or ""))
                return
            for v in o.values():
                walk(v, team)
        elif isinstance(o, list):
            for v in o:
                walk(v, team)

    collect(root)
    walk(root)
    return out


PARSERS = {"espn": parse_espn, "rotowire": parse_rotowire, "covers": parse_tables, "cbs": parse_tables,
           "action": parse_action}


def fetch(source: str) -> tuple[pd.DataFrame, str]:
    """(report, raw text) for one source: team_id, player_key and athlete_id attached, status normalized."""
    text = _get(URLS[source])
    df = pd.DataFrame(PARSERS[source](text), columns=["team", "team_id", "player", "status_raw", "comment",
                                                      "source_date", "athlete_id"])
    df = df[df["player"].astype(str).str.strip().ne("")].copy()
    lookup = _team_lookup()
    df["team_id"] = [t if pd.notna(t) else _team_id(n, lookup) for t, n in zip(df["team_id"], df["team"])]
    df["player_key"] = df["player"].map(player_key)
    ro = _roster()
    df["athlete_id"] = [a if pd.notna(a) else (ro.get((int(t), k)) if pd.notna(t) else None)
                        for a, t, k in zip(df["athlete_id"], df["team_id"], df["player_key"])]
    df["status"] = df["status_raw"].map(norm_status)
    df["source"] = source
    df = df.drop_duplicates(["team", "player_key"], keep="first")
    return df[COLS], text


# ---------------------------------------------------------------- logging

def _append(path: str, df: pd.DataFrame):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def _save_raw(source: str, text: str, now: pd.Timestamp):
    """Keep a page that parsed to nothing (once a day per source) so the parser can be fixed offline. The save time is
    the file's first line (a fresh checkout resets file times)."""
    path = os.path.join(DIR, "raw", f"{source}.txt")
    try:
        with open(path) as fh:
            if now - pd.Timestamp(fh.readline().split("saved ")[-1].strip()) < pd.Timedelta(days=1):
                return
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f"# {URLS[source]} saved {now.isoformat()}\n" + text[:400_000])


def log_all(now: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:
    """Pull every source once, log new statuses and drop-offs, refresh timing.md and the switch decision. Never
    raises: a broken source is recorded in health.csv and skipped."""
    now = now or pd.Timestamp.now(tz="UTC").floor("s")
    stamp = now.isoformat(timespec="seconds")
    cur_old = pd.read_csv(CURRENT) if os.path.exists(CURRENT) else pd.DataFrame(columns=COLS + ["pulled_at"])
    seen = pd.read_csv(FIRST) if os.path.exists(FIRST) else pd.DataFrame(columns=COLS + ["first_seen"])
    key = lambda d: (d["source"].astype(str) + "|" + pd.to_numeric(d["team_id"]).astype("Int64").astype(str) + "|"
                     + d["player_key"].astype(str))
    last_status = dict(zip(key(seen), seen["status"])) if len(seen) else {}   # later rows win: each one's latest
    health, new_rows, cur_new = [], [], []
    for src in SOURCES:
        t0 = time.time()
        try:
            df, text = fetch(src)
            if not len(df) and len(text) > 5000:
                _save_raw(src, text, now)
            err = ""
        except Exception as e:
            df, err = None, f"{type(e).__name__}: {e}"[:300]
        h = {"pulled_at": stamp, "source": src, "ok": df is not None, "rows": 0 if df is None else len(df),
             "teams_matched": None, "players_matched": None, "unmatched_teams": "", "error": err,
             "seconds": round(time.time() - t0, 1)}
        if df is not None:
            _RUN[src] = df
            if len(df):
                h["teams_matched"] = round(float(df["team_id"].notna().mean()), 3)
                h["players_matched"] = round(float(df["athlete_id"].notna().mean()), 3)
                h["unmatched_teams"] = "; ".join(sorted(set(df.loc[df["team_id"].isna(), "team"].astype(str))))[:300]
            d = df[df["team_id"].notna()].copy()
            d["team_id"] = d["team_id"].astype(int)
            k = key(d)
            fresh = d[np.array([last_status.get(x) != s for x, s in zip(k, d["status"])], dtype=bool)]
            new_rows.append(fresh.assign(first_seen=stamp))
            # players this source listed last time and no longer does: cleared (back, or the report was trimmed)
            prev = cur_old[(cur_old["source"] == src) & cur_old["team_id"].notna()].copy()
            if len(prev):
                prev["team_id"] = prev["team_id"].astype(int)
                gone = prev[~key(prev).isin(set(k))]
                gone = gone[np.array([last_status.get(x) != "cleared" for x in key(gone)], dtype=bool)]
                new_rows.append(gone[COLS].assign(status="cleared", status_raw="", comment="", source_date="",
                                                  first_seen=stamp))
            cur_new.append(df.assign(pulled_at=stamp))
        else:   # keep the last good report for a source that failed this run
            cur_new.append(cur_old[cur_old["source"] == src])
        health.append(h)
    _append(HEALTH, pd.DataFrame(health))
    new = [r for r in new_rows if len(r)]
    if new:
        _append(FIRST, pd.concat(new, ignore_index=True)[COLS + ["first_seen"]])
    cur = [c for c in cur_new if len(c)]
    os.makedirs(DIR, exist_ok=True)
    (pd.concat(cur, ignore_index=True) if cur else pd.DataFrame(columns=COLS + ["pulled_at"])).to_csv(CURRENT, index=False)
    try:
        timing(now)
    except Exception as e:
        print(f"Injury timing report failed ({e}); continuing.")
    return dict(_RUN)


# ---------------------------------------------------------------- timing vs the line, and the switch

def _games() -> pd.DataFrame:
    """game_key, lo_id, hi_id, start (UTC) for every game with lines."""
    p = os.path.join(LINES, "closing.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["game_key", "lo_id", "hi_id", "start"])
    from .odds import game_key
    c = pd.read_csv(p)
    c = c.assign(game_key=game_key(c), start=pd.to_datetime(c["start"], utc=True, format="ISO8601"),
                 lo_id=np.minimum(c["home_id"], c["away_id"]).astype(int),
                 hi_id=np.maximum(c["home_id"], c["away_id"]).astype(int))
    return c.groupby("game_key", as_index=False).agg(lo_id=("lo_id", "first"), hi_id=("hi_id", "first"),
                                                     start=("start", "min"))


def _shares() -> dict[float, float]:
    """athlete id -> share of team minutes, this season once a team has 3 games, else last season."""
    from .injuries import shares
    now = pd.Timestamp.now(tz="America/New_York")
    s = shares(now.year + 1 if now.month >= 8 else now.year)
    return dict(zip(s["athlete_id"], s["share"]))


def _online(health: pd.DataFrame | None = None) -> pd.Series:
    """source -> start of its current working stretch. A pull is working unless it failed, or came back empty while
    ESPN listed 10+ players (a broken parser)."""
    h = pd.read_csv(HEALTH) if health is None else health
    if not len(h):
        return pd.Series(dtype="datetime64[ns, UTC]")
    h = h.assign(pulled_at=pd.to_datetime(h["pulled_at"], utc=True))
    esp = h[h["source"] == "espn"].set_index("pulled_at")["rows"]
    h["working"] = h["ok"].astype(bool) & ((h["rows"] > 0) | (h["pulled_at"].map(esp).fillna(0) < 10))
    out = {}
    for src, g in h.sort_values("pulled_at").groupby("source"):
        bad = g.loc[~g["working"], "pulled_at"]
        good = g.loc[g["working"] & (g["pulled_at"] > (bad.max() if len(bad) else pd.Timestamp.min.tz_localize("UTC"))),
                     "pulled_at"]
        if len(good):
            out[src] = good.min()
    return pd.Series(out, dtype="datetime64[ns, UTC]")


def events(seen: pd.DataFrame | None = None, games: pd.DataFrame | None = None,
           moves: pd.DataFrame | None = None, share: dict | None = None,
           health: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per material injury report (team, player, status) with each source's first-seen time, the earliest
    report, the team's next game and when the spread first moved 1+ point against the team at any book."""
    seen = pd.read_csv(FIRST) if seen is None else seen
    if not len(seen):
        return pd.DataFrame()
    games = _games() if games is None else games
    if moves is None:
        mp = os.path.join(LINES, "moves.csv")
        moves = pd.read_csv(mp) if os.path.exists(mp) else pd.DataFrame(columns=["pulled_at", "game_key", "book", "spread"])
    seen = seen.assign(first_seen=pd.to_datetime(seen["first_seen"], utc=True))
    start0 = seen["first_seen"].min()
    # each source is scored only on injuries first reported after it was working, and the report it showed on coming
    # back (after an outage or a parser fix) is its backlog, not news
    online = _online(health)
    seen = seen[seen["first_seen"] != seen["source"].map(online)]
    s = seen[seen["status"].isin(MATERIAL_STATUS) & seen["team_id"].notna()].copy()
    s["team_id"] = s["team_id"].astype(int)
    # one athlete id per (team, player) from whichever source matched it
    aid = s.dropna(subset=["athlete_id"]).groupby(["team_id", "player_key"])["athlete_id"].first()
    ev = s.pivot_table(index=["team_id", "player_key", "status"], columns="source", values="first_seen", aggfunc="min")
    ev = ev.reindex(columns=SOURCES).apply(lambda c: pd.to_datetime(c, utc=True))
    if not len(ev):
        return pd.DataFrame()
    ev["t0"] = pd.to_datetime(ev[SOURCES].min(axis=1), utc=True)
    ev = ev.reset_index()
    ev = ev[ev["t0"] > start0]           # already on a report when the logger started: not news
    for src in SOURCES:
        ev[f"on_{src}"] = ev["t0"] >= online.get(src, pd.Timestamp.max.tz_localize("UTC"))
    ev["athlete_id"] = [aid.get((t, k)) for t, k in zip(ev["team_id"], ev["player_key"])]
    if not len(ev):
        return ev.assign(share=[], game_key=[], move_at=pd.to_datetime([], utc=True))
    share = _shares() if share is None else share
    ev["share"] = ev["athlete_id"].map(share).fillna(0.0)
    ev = ev[ev["share"] >= MATERIAL_SHARE]
    if not len(ev) or not len(games):
        return ev.assign(game_key=None, move_at=pd.NaT).astype({"move_at": "datetime64[ns, UTC]"})
    mv = moves.assign(pulled_at=pd.to_datetime(moves["pulled_at"], utc=True)).dropna(subset=["spread"])
    gk, mat = [], []
    for r in ev.itertuples():
        g = games[((games["lo_id"] == r.team_id) | (games["hi_id"] == r.team_id)) & (games["start"] > r.t0)
                  & (games["start"] - r.t0 <= pd.Timedelta(hours=72))].sort_values("start")
        if not len(g):
            gk.append(None)
            mat.append(pd.NaT)
            continue
        g = g.iloc[0]
        gk.append(g["game_key"])
        sign = 1.0 if g["lo_id"] == r.team_id else -1.0     # spread is the lo team's: it rises when lo gets weaker
        m = mv[(mv["game_key"] == g["game_key"]) & (mv["pulled_at"] < g["start"])]
        best = pd.NaT
        for _, b in m.groupby("book"):
            b = b.sort_values("pulled_at")
            base = b[b["pulled_at"] < r.t0 - MOVE_LOOKBACK]
            ref = base["spread"].iloc[-1] if len(base) else b["spread"].iloc[0]
            hit = b[(b["pulled_at"] >= r.t0 - MOVE_LOOKBACK) & (sign * (b["spread"] - ref) >= MOVE_PTS)]
            if len(hit) and (pd.isna(best) or hit["pulled_at"].iloc[0] < best):
                best = hit["pulled_at"].iloc[0]
        mat.append(best)
    return ev.assign(game_key=gk, move_at=pd.to_datetime(pd.Series(mat, index=ev.index, dtype="object"), utc=True))


def scoreboard(ev: pd.DataFrame, match: dict | None = None) -> pd.DataFrame:
    """Per source: coverage, first-or-tied rate, median minutes behind the first report, and the switch score:
    share of line-matched injuries the source had before the move (a miss counts as not before)."""
    rows = []
    for src in SOURCES:
        e = ev[ev[f"on_{src}"]] if len(ev) else ev
        rows.append(_score(src, e, (match or {}).get(src, np.nan)))
    return pd.DataFrame(rows)


def _score(src: str, ev: pd.DataFrame, matched: float) -> dict:
    if not len(ev):
        return {"source": src, "injuries": 0, "coverage": np.nan, "first": np.nan, "median_min_behind": np.nan,
                "matched_moves": 0, "before_move": np.nan, "median_lead_min": np.nan, "players_matched": matched}
    had = ev[src].notna()
    behind = (ev[src] - ev["t0"]).dt.total_seconds().div(60)
    mv = ev[ev["move_at"].notna()]
    before = mv[src] < mv["move_at"] - SAME_RUN          # NaT (source never had it) compares False: a miss
    lead = (mv["move_at"] - mv[src]).dt.total_seconds().div(60)[before]
    return {"source": src, "injuries": int(had.sum()), "coverage": had.mean(),
            "first": (behind[had] <= SAME_RUN.total_seconds() / 60).mean() if had.any() else np.nan,
            "median_min_behind": behind[had].median() if had.any() else np.nan,
            "matched_moves": len(mv), "before_move": before.mean() if len(mv) else np.nan,
            "median_lead_min": lead.median() if len(lead) else np.nan, "players_matched": matched}


def match_rates(health: pd.DataFrame | None = None) -> dict[str, float]:
    """Each source's share of listed players matched to an ESPN athlete id, over its last week of pulls with rows."""
    h = pd.read_csv(HEALTH) if health is None else health
    h = h[h["rows"] > 0].assign(pulled_at=lambda x: pd.to_datetime(x["pulled_at"], utc=True))
    h = h[h["pulled_at"] >= h["pulled_at"].max() - pd.Timedelta(days=7)] if len(h) else h
    return {s: float(np.average(g["players_matched"].fillna(0), weights=g["rows"])) for s, g in h.groupby("source")}


def choice() -> str:
    """The source feeding the model's injury input."""
    try:
        with open(CHOICE) as fh:
            return json.load(fh).get("source", "espn")
    except (OSError, ValueError):
        return "espn"


def decide(board: pd.DataFrame, game_days: int) -> dict | None:
    """The one-time switch (module docstring). None until there is enough data."""
    n = int(board["matched_moves"].max()) if len(board) else 0
    if not ((game_days >= MIN_DAYS and n >= MIN_EVENTS) or game_days >= MAX_DAYS):
        return None
    base = {"decided_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "game_days": game_days,
            "matched_moves": n}
    if n < MIN_EVENTS_LATE:
        return {**base, "source": "espn", "reason": f"only {n} injuries matched to a line move after {game_days} "
                                                     "game days; staying with ESPN"}
    # ESPN carries its own athlete ids, so the match check applies only to the others
    b = board[(board["source"] == "espn") | (board["players_matched"].fillna(0) >= MIN_MATCH)].copy()
    b["before_move"] = b["before_move"].fillna(0)
    top = b["before_move"].max()
    tied = b[b["before_move"] >= top - TIE_PTS]
    if "espn" in set(tied["source"]) or top <= 0:
        pick = "espn"
    else:
        pick = tied.sort_values("median_lead_min", ascending=False, na_position="last")["source"].iloc[0]
    r = b.set_index("source")
    esp = f"{r.loc['espn', 'before_move']:.0%}" if "espn" in r.index else "n/a"
    return {**base, "source": pick,
            "reason": f"{pick} had {r.loc[pick, 'before_move']:.0%} of {n} line-matched injuries before the spread "
                      f"moved (ESPN {esp})",
            "scores": {s: round(float(v), 3) for s, v in r["before_move"].items()}}


def timing(now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Rewrite timing.md, and make the switch decision once the rule's data threshold is met."""
    now = now or pd.Timestamp.now(tz="UTC")
    seen = pd.read_csv(FIRST) if os.path.exists(FIRST) else pd.DataFrame(columns=COLS + ["first_seen"])
    ev = events(seen)
    match = match_rates() if os.path.exists(HEALTH) else {}
    board = scoreboard(ev, match)
    start = (pd.to_datetime(seen["first_seen"], utc=True).min() if len(seen) else now).tz_convert("America/New_York").normalize()
    g = _games()
    played = g[(g["start"] >= start) & (g["start"] <= now)] if len(g) else g
    game_days = int(played["start"].dt.tz_convert("America/New_York").dt.date.nunique()) if len(played) else 0
    current = choice()
    if not os.path.exists(CHOICE):
        d = decide(board, game_days)
        if d is not None:
            with open(CHOICE, "w") as fh:
                json.dump(d, fh, indent=1)
            current = d["source"]
            print(f"Injury source decided: {d['source']} ({d['reason']}).")
    fmt = lambda v, f: "" if pd.isna(v) else format(v, f)
    lines = [
        "# Injury sources: who reports first", "",
        f"Updated {now:%Y-%m-%d %H:%M} UTC by `cbb/injury_sources.py`. Logging since {start:%Y-%m-%d}; "
        f"{game_days} game day(s) so far. Model's injury input: **{current}**"
        + ("" if os.path.exists(CHOICE) else f" (decision after {MIN_DAYS} game days with {MIN_EVENTS}+ "
                                             f"line-matched injuries, or {MAX_DAYS} game days)") + ".", "",
        f"Material injuries: Out / Doubtful / Questionable, player with {MATERIAL_SHARE:.0%}+ of team minutes, first "
        f"reported after logging began and before the team's next game. A line move is the spread moving "
        f"{MOVE_PTS:g}+ point against the team at any book. Times are poll times (one run = 30 minutes).", "",
        "| Source | Injuries | Coverage | First (or same run) | Median min behind first | Before the move | "
        "Median lead on move (min) | Players matched to ESPN ids |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in board.itertuples():
        lines.append(f"| {r.source} | {r.injuries} | {fmt(r.coverage, '.0%')} | {fmt(r.first, '.0%')} | "
                     f"{fmt(r.median_min_behind, '.0f')} | {fmt(r.before_move, '.0%')} | "
                     f"{fmt(r.median_lead_min, '.0f')} | {fmt(r.players_matched, '.0%')} |")
    n = int(board["matched_moves"].max()) if len(board) else 0
    lines += ["", f"{len(ev)} material injuries; {n} matched to a line move."]
    if os.path.exists(HEALTH):
        h = pd.read_csv(HEALTH).groupby("source").tail(1).set_index("source")
        lines += ["", "Last pull per source:", "", "| Source | OK | Rows | Teams matched | Unmatched teams | Error |",
                  "|---|---|---:|---:|---|---|"]
        for s in SOURCES:
            if s in h.index:
                x = h.loc[s]
                lines.append(f"| {s} | {'yes' if x['ok'] else 'no'} | {x['rows']} | {fmt(x['teams_matched'], '.0%')} | "
                             f"{'' if pd.isna(x['unmatched_teams']) else x['unmatched_teams']} | "
                             f"{'' if pd.isna(x['error']) else x['error']} |")
    with open(TIMING, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return board


def report(source: str) -> pd.DataFrame | None:
    """This run's report from `source` (pulled by log_all), or a fresh pull; None if the pull fails."""
    df = _RUN.get(source)
    if df is None:
        try:
            df, _ = fetch(source)
        except Exception as e:
            print(f"Injury source {source} unavailable ({e}).")
            return None
    return df


if __name__ == "__main__":
    for s, d in log_all().items():
        print(f"{s}: {len(d)} listed")
    print(open(TIMING).read())
