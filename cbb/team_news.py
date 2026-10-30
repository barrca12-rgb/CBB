"""Team news that injury reports miss (eligibility rulings, suspensions, season-ending injuries, players leaving),
plus a manual eligibility watchlist. Information only: nothing here changes a projection, a pick or a stake.

  news scan   ESPN's free per-team news feed for both teams of every play or watch on the card. Articles tagged
              with the team, published in the last LOOKBACK, whose headline or summary matches KEYWORDS.
  watchlist   data/eligibility_watch.csv: teams with a key player whose eligibility (or an announced absence) is
              unresolved, until the row's "until" date. Started from Greg Peterson's 2026-27 preview.

Every flagged article is logged once to injuries/news_log.csv (first time seen), for the Jan 15 miss review. The
result goes on the card as news_flag (shown under the play) and into the play's phone alert. Any failure here is
printed and skipped: it never stops the card.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
WATCH = os.path.join(ROOT, "data", "eligibility_watch.csv")
LOG = os.path.join(ROOT, "injuries", "news_log.csv")
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/news?team={}&limit=50"
LOOKBACK = pd.Timedelta(days=7)
MAX_TEAMS = 4      # ESPN tags league-wide stories (rankings, "eligibility chaos") with 25-65 teams; team news has 1-4
KEYWORDS = re.compile(
    r"\b(eligib\w*|ineligib\w*|ruling|injunction|court|lawsuit|waiver|suspend\w*|dismiss\w*|reinstat\w*|"
    r"out for (?:the )?season|season-ending|torn|tear|surgery|fractur\w*|concussion|indefinitely|"
    r"will not play|won't play|ruled out|sidelined|leaves? (?:the )?(?:team|program)|left the team|"
    r"enter\w* (?:the )?transfer portal|arrest\w*|charged)\b", re.I)
LOG_COLS = ["first_seen", "team_id", "article_id", "published", "headline", "url", "matched"]


def watchlist(today: pd.Timestamp) -> dict:
    """espn_id -> "Team: players (note)" for rows still active on `today`."""
    if not os.path.exists(WATCH):
        return {}
    w = pd.read_csv(WATCH)
    w = w[pd.to_datetime(w["until"]) >= today.tz_localize(None).normalize()]
    return {int(r["espn_id"]): f"{r['team']}: {r['players']} ({r['note']})" for _, r in w.iterrows()}


def team_articles(team_id: int, now: pd.Timestamp) -> list[dict]:
    """Recent articles tagged with this team whose headline or summary matches KEYWORDS."""
    req = urllib.request.Request(URL.format(int(team_id)), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=10) as r:
        arts = json.load(r).get("articles") or []
    out = []
    for a in arts:
        tags = [str(c.get("teamId") or (c.get("team") or {}).get("id")) for c in a.get("categories") or [] if c.get("type") == "team"]
        tagged = str(int(team_id)) in tags
        pub = pd.to_datetime(a.get("published"), utc=True, errors="coerce")
        if not tagged or len(tags) > MAX_TEAMS or pd.isna(pub) or now - pub > LOOKBACK:
            continue
        text = f"{a.get('headline') or ''} {a.get('description') or ''}"
        m = KEYWORDS.findall(text)
        if m:
            out.append({"team_id": int(team_id), "article_id": str(a.get("id") or a.get("headline")), "published": pub.isoformat(),
                        "headline": (a.get("headline") or "").strip(), "url": ((a.get("links") or {}).get("web") or {}).get("href", ""),
                        "matched": ", ".join(sorted({x.lower() for x in m}))})
    return out


def _log(hits: list[dict], now: pd.Timestamp) -> None:
    if not hits:
        return
    old = pd.read_csv(LOG, dtype=str) if os.path.exists(LOG) else pd.DataFrame(columns=LOG_COLS)
    have = set(zip(old["team_id"].astype(str), old["article_id"].astype(str)))
    new = [dict(h, first_seen=now.isoformat(timespec="seconds")) for h in hits
           if (str(h["team_id"]), str(h["article_id"])) not in have]
    if new:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        pd.DataFrame(new)[LOG_COLS].to_csv(LOG, mode="a", header=not os.path.exists(LOG), index=False)


def annotate(card: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Add news_flag (text, or empty) for games with a play or watch."""
    if not len(card):
        return card
    now = now or pd.Timestamp.now(tz="UTC")
    card = card.copy()
    card["news_flag"] = ""
    watch = watchlist(now.tz_convert("America/New_York"))
    names = {}
    try:
        from . import teams
        names = teams.load().drop_duplicates("espn_id").set_index("espn_id")["espn_location"].to_dict()
    except Exception:
        pass
    active = pd.Series(False, index=card.index)
    for mk in ("spread", "total"):
        if f"{mk}_verdict" in card:
            active |= card[f"{mk}_verdict"].isin(["BET", "WATCH"])
    cache, hits, errors = {}, [], 0
    for i, g in card[active].iterrows():
        arts, notes = {}, []                      # one line per article, naming every team of this game it is tagged with
        for tid in (int(g["away_id"]), int(g["home_id"])):
            if tid not in cache:
                try:
                    cache[tid] = team_articles(tid, now)
                    hits += cache[tid]
                except Exception:
                    cache[tid] = []
                    errors += 1
            for a in cache[tid][:2]:
                arts.setdefault(a["article_id"], (a, []))[1].append(names.get(tid, tid))
        for a, who in arts.values():
            d = pd.Timestamp(a["published"]).tz_convert("America/New_York")
            notes.append(f"News ({', '.join(map(str, who))}, {d:%b %-d}): {a['headline']}")
        for tid in (int(g["away_id"]), int(g["home_id"])):
            if tid in watch:
                notes.append("Eligibility watch: " + watch[tid])
        card.loc[i, "news_flag"] = " · ".join(notes)
    try:
        _log(hits, now)
    except Exception as e:
        print(f"News log failed ({e}); continuing.")
    if errors:
        print(f"Team news: {errors} team feed(s) failed this run; skipped.")
    return card


def injury_lines(home_id: int, away_id: int, names: dict | None = None) -> list[str]:
    """Current Out / Doubtful / Questionable players for both teams, across every injury source, for alerts."""
    from . import injury_sources
    if not os.path.exists(injury_sources.CURRENT):
        return []
    c = pd.read_csv(injury_sources.CURRENT)
    c = c[c["team_id"].isin([home_id, away_id]) & c["status"].isin(["out", "doubtful", "questionable"])]
    out = []
    for (tid, player), g in c.groupby(["team_id", "player"]):
        st = g["status"].mode().iloc[0]
        out.append(f"{(names or {}).get(int(tid), g['team'].iloc[0])}: {player} {st} ({', '.join(sorted(g['source'].unique()))})")
    return out
