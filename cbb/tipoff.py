"""Actual tip times, for the pregame validity check on the CLV close (audit/CLV_VERIFICATION.md, section 2).

The protocol's cutoff is a scheduled start; neither odds feed reports when the ball actually went up. ESPN's game
summary (play-by-play) stamps each play with a wall-clock time, so the first play of period 1 (the jump ball) gives
the actual tip. Cached in lines/tipoffs.csv: game_id, actual_tip (UTC; empty if ESPN had no timed play), source,
fetched_at. Read only for the model: nothing here feeds predictions, selection, staking, grading or the protocol's
close; clv_primary uses it to label a close "pregame verified" or not.

    python -m cbb.tipoff 401920982
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, "lines", "tipoffs.csv")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={}"
COLS = ["game_id", "actual_tip", "source", "fetched_at"]
RETRY = pd.Timedelta(hours=1)        # a game with no timed play yet is asked again after this long


def load() -> dict:
    """game_id -> actual tip (UTC Timestamp) from the cache; games without one are left out."""
    if not os.path.exists(CACHE):
        return {}
    c = pd.read_csv(CACHE)
    t = pd.to_datetime(c["actual_tip"], utc=True, errors="coerce", format="ISO8601")
    return {int(g): x for g, x in zip(c["game_id"], t) if pd.notna(x)}


def first_play(summary: dict) -> pd.Timestamp | None:
    """Wall-clock time of the first play of period 1 (ESPN lists the jump ball first), or None."""
    ts = [pd.Timestamp(p["wallclock"]) for p in summary.get("plays") or []
          if p.get("wallclock") and (p.get("period") or {}).get("number") == 1]
    return min(ts) if ts else None


def fetch(game_id: int) -> pd.Timestamp | None:
    with urllib.request.urlopen(urllib.request.Request(SUMMARY.format(game_id), headers={"User-Agent": "cbb-model"}),
                                timeout=30) as r:
        return first_play(json.load(r))


def refresh(b: pd.DataFrame, now: pd.Timestamp | None = None) -> int:
    """Fetch the actual tip of every settled bet's game not yet cached (or cached without one more than RETRY ago).
    Never raises; returns how many games were asked."""
    now = now or pd.Timestamp.now(tz="UTC")
    try:
        c = pd.read_csv(CACHE) if os.path.exists(CACHE) else pd.DataFrame(columns=COLS)
        done = set(c.loc[c["actual_tip"].notna(), "game_id"].astype(int))
        last = c.groupby("game_id")["fetched_at"].max().map(lambda x: pd.Timestamp(x)).to_dict() if len(c) else {}
        want = {int(g) for g in b.loc[b["status"] == "settled", "game_id"]} - done
        want = {g for g in want if g not in last or now - last[g] >= RETRY}
        rows = []
        for g in sorted(want):
            try:
                t = fetch(g)
            except Exception as e:
                print(f"tipoff {g}: {e}")
                continue
            rows.append({"game_id": g, "actual_tip": t.isoformat() if t is not None else None,
                         "source": "espn play-by-play first play", "fetched_at": now.isoformat(timespec="seconds")})
        if rows:
            c = pd.concat([c[~c["game_id"].isin([r["game_id"] for r in rows])], pd.DataFrame(rows)], ignore_index=True)
            c[COLS].to_csv(CACHE, index=False)
        return len(rows)
    except Exception as e:
        print(f"tipoff.refresh failed ({e}); continuing.")
        return 0


if __name__ == "__main__":
    print(fetch(int(sys.argv[1])))
