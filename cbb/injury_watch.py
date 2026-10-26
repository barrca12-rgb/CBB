"""Injury checks between card runs, and a phone alert when news hits a team we have a bet on.

Late scratches mostly come out in the last hour or two before tip. The card runs every 30 minutes; this runs every
10 minutes from a separate cron-job.org job (.github/workflows/injuries.yml) and does real work only when a game
tips within LEAD of now: it pulls every injury source (injury_sources.log_all, so first-seen times get 10-minute
resolution) and, for each newly listed Out / Doubtful / Questionable player on a team in today's open bets, sends
one alert (deduped across sources in injuries/sources/alerted.json). The card run calls check() too.

    python -m cbb.injury_watch
"""
from __future__ import annotations

import json
import os

import pandas as pd

from . import injury_sources, tracker

LEAD = pd.Timedelta(hours=2)
SERIOUS = {"out", "doubtful", "questionable"}
ALERTED = os.path.join(injury_sources.DIR, "alerted.json")


def _open_bets(now: pd.Timestamp) -> pd.DataFrame:
    b = tracker.load()
    today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
    return b[(b["status"] == "open") & (b["date"] >= today)]


def alert_new(stamp: str, now: pd.Timestamp) -> int:
    """Alert on this pull's new serious statuses for teams with open bets. Returns alerts sent."""
    from . import notify
    if not os.path.exists(injury_sources.FIRST):
        return 0
    seen = pd.read_csv(injury_sources.FIRST)
    new = seen[(seen["first_seen"] == stamp) & seen["status"].isin(SERIOUS) & seen["team_id"].notna()]
    bets = _open_bets(now)
    if not len(new) or not len(bets):
        return 0
    done = set(json.load(open(ALERTED))) if os.path.exists(ALERTED) else set()
    sent = 0
    for _, r in new.iterrows():
        tid = int(r["team_id"])
        key = f"{tid}|{r['player_key']}|{r['status']}"
        mine = bets[(bets["home_id"] == tid) | (bets["away_id"] == tid)]
        if key in done or not len(mine):
            continue
        plays = "; ".join(f"{p['pick']} ({p['away']} at {p['home']})" for _, p in mine.iterrows())
        body = f"{r['player']} ({r['team']}) {r['status'].title()} via {r['source']}. Your play: {plays}."
        if notify.message(f"CBB injury: {r['team']}", body):
            sent += 1
        done.add(key)
    with open(ALERTED, "w") as fh:
        json.dump(sorted(done), fh)
    return sent


def check(now: pd.Timestamp | None = None, alert: bool = True) -> int:
    """Pull every source once (log_all) and alert on news for teams we have bets on."""
    now = now or pd.Timestamp.now(tz="UTC").floor("s")
    injury_sources.log_all(now)
    return alert_new(now.isoformat(timespec="seconds"), now) if alert else 0


def games_soon(now: pd.Timestamp) -> bool:
    """Any game today (ET) tipping between now and LEAD from now."""
    from .run_day import slate
    day = pd.Timestamp(now.tz_convert("America/New_York").date())
    g = slate(day)
    if not len(g):
        return False
    start = pd.to_datetime(g["start"], utc=True, format="ISO8601")
    return bool(((start > now) & (start <= now + LEAD)).any())


def main():
    now = pd.Timestamp.now(tz="UTC").floor("s")
    if not games_soon(now):
        print("No game tips in the next 2 hours; nothing to check.")
        return
    print(f"Injury check: {check(now)} alert(s) sent.")


if __name__ == "__main__":
    main()
