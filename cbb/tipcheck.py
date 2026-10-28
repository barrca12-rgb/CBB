"""Tip-time review before tip (audit/CLV_VERIFICATION.md, section 2). Run on every card run by record_page.write.

For each open, non-void bet whose tip has not passed, the protocol's cutoff (the feed's start carried by the latest
pregame observation) is compared with ESPN's scheduled start and with the feed's latest reported start
(cbb/clv_primary.py: tip_check). A difference over 10 minutes ("review") or of 30 minutes or more ("conflict") sends
one phone alert per bet and per distinct set of times, and every check that finds one is logged to
bets/tip_review.csv. Reads and alerts only: the cutoff, the close, the picks and the stakes are never changed.
"""
from __future__ import annotations

import json
import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG = os.path.join(ROOT, "bets", "tip_review.csv")
SENT = os.path.join(ROOT, "bets", "tip_review_sent.json")


def _et(x) -> str:
    t = pd.to_datetime(x, utc=True, errors="coerce")
    return "unknown" if pd.isna(t) else t.tz_convert("America/New_York").strftime("%a %-I:%M %p ET")


def message(r: pd.Series) -> str:
    """'Tip time CONFLICT: Over 152.5 (Memphis at Iowa State): CLV cutoff Mon 6:00 PM ET (feed), ESPN Mon 7:00 PM ET.'"""
    return (f"Tip time {'CONFLICT' if r['tip_check'] == 'conflict' else 'review'}: {r['pick']} ({r['away']} at {r['home']}): "
            f"CLV cutoff {_et(r['cutoff'])} (feed), ESPN {_et(r['espn_start'])}, feed latest {_et(r['feed_latest_start'])}. "
            f"The close is taken in the 15 minutes before the cutoff.")


def check(now: pd.Timestamp | None = None, alert: bool = True) -> pd.DataFrame:
    """Flagged open bets before tip; alerts once per (bet, times) and logs every finding. Returns the findings."""
    from . import clv_primary, notify, tracker
    now = now or pd.Timestamp.now(tz="UTC")
    b = tracker.load()
    b = b[b["status"] == "open"]
    if not len(b):
        return pd.DataFrame()
    p = clv_primary.primary(b, now=now)
    p = p.merge(b[["bet_id", "pick", "home", "away"]], on="bet_id")
    cut = pd.to_datetime(p["cutoff"], utc=True, errors="coerce", format="ISO8601")
    f = p[p["tip_check"].isin(["review", "conflict"]) & (cut.isna() | (cut > now))].copy()
    if not len(f):
        return f
    sent = set(json.load(open(SENT))) if os.path.exists(SENT) else set()
    f["key"] = f["bet_id"] + "|" + f["cutoff"].astype(str) + "|" + f["espn_start"].astype(str) + "|" + f["feed_latest_start"].astype(str)
    f["alerted"] = False
    for i, r in f.iterrows():
        if alert and r["key"] not in sent and notify.message("CBB tip time " + r["tip_check"], message(r)):
            sent.add(r["key"])
            f.at[i, "alerted"] = True
    with open(SENT, "w") as fh:
        json.dump(sorted(sent), fh)
    f.insert(0, "checked_at", now.isoformat(timespec="seconds"))
    cols = ["checked_at", "bet_id", "pick", "tip_check", "cutoff", "cutoff_source", "espn_start", "start_gap_min",
            "feed_latest_start", "feed_gap_min", "alerted"]
    f[cols].to_csv(LOG, mode="a", header=not os.path.exists(LOG), index=False)
    return f[cols]


if __name__ == "__main__":
    print(check(alert=False).to_string())
