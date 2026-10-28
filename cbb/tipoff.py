"""Actual tip times, for the pregame validity check on the CLV close (audit/CLV_VERIFICATION.md, section 2).

The protocol's cutoff is a scheduled start; neither odds feed reports when the ball actually went up. ESPN's game
summary (play-by-play) stamps each play with a wall-clock time; classify() takes the earliest period-1 play stamped at
20:00 on the game clock as the actual tip, and rejects records that are missing or not trustworthy (coverage and
reliability measured in audit/tipoff_study.md). Cached in lines/tipoffs.csv: game_id, actual_tip (UTC; empty unless
usable), quality, reason, source, fetched_at. Read only for the model: nothing here feeds predictions, selection, staking, grading or the protocol's
close; clv_primary uses it to label a close "pregame verified" or not.

    python -m cbb.tipoff 401920982
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, "lines", "tipoffs.csv")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={}"
COLS = ["game_id", "actual_tip", "quality", "reason", "source", "fetched_at"]
RETRY = pd.Timedelta(hours=1)        # a game with no timed play yet is asked again after this long


def load() -> dict:
    """game_id -> actual tip (UTC Timestamp) from the cache; games without one are left out."""
    if not os.path.exists(CACHE):
        return {}
    c = pd.read_csv(CACHE)
    t = pd.to_datetime(c["actual_tip"], utc=True, errors="coerce", format="ISO8601")
    return {int(g): x for g, x in zip(c["game_id"], t) if pd.notna(x)}


def _secs(clock) -> float | None:
    try:
        m, sec = str(clock).split(":")
        return int(m) * 60 + float(sec)
    except (ValueError, AttributeError):
        return None


def classify(plays: pd.DataFrame | None, scheduled: pd.Timestamp | None = None) -> dict:
    """The actual tip from one game's play-by-play, or why there is none. plays: sequence_number, period_number,
    clock_display_value, type_text, text, wallclock (the cached play-by-play's columns; summary() converts the live
    feed). quality: "jump ball" (usable), "ambiguous" or "missing"; only "jump ball" is ever used as the tip.

    Tip = the earliest wall clock among period-1 plays stamped at 20:00 on the game clock (ESPN's "Start game" or the
    jump ball). It is the earliest plausible tip in the record, so a quote checked against it errs toward "not
    pregame". Not usable: no play-by-play or no wall clock ("missing"); no period-1 play at 20:00 (a later first play
    only bounds the tip from above, which cannot show a quote was pregame); wall clocks out of order by more than
    5 s or running more than 30 s faster than the game clock over the first 30 plays (stamps are entry times, not play
    times); no scheduled start, or a tip more than 30 min before or 60 min after it (in the 2024-25 records about one
    game in five carries a whole-hour offset, a time-zone error in the stamps); a game shorter than 60 or longer than
    300 minutes on the wall clock ("ambiguous"). A real delay of over an hour is therefore "unverified", never
    "verified"."""
    out = {"quality": "missing", "reason": "no play-by-play", "tip": None, "has_wallclock": False,
           "start_to_jump_s": np.nan, "min_slack_s": np.nan, "length_min": np.nan}
    if plays is None or not len(plays):
        return out
    p = plays.assign(_w=pd.to_datetime(plays["wallclock"], utc=True, errors="coerce"),
                     _seq=pd.to_numeric(plays["sequence_number"], errors="coerce"),
                     _c=plays["clock_display_value"].map(_secs)).sort_values("_seq", kind="mergesort")
    p1 = p[(pd.to_numeric(p["period_number"], errors="coerce") == 1) & p["_w"].notna()]
    if not len(p1):
        out["reason"] = "no wall clock on period-1 plays"
        return out
    out["has_wallclock"] = True
    out["quality"] = "ambiguous"
    open_ = p1[p1["_c"] == 1200]
    if not len(open_):
        out["reason"] = "no period-1 play stamped at 20:00"
        out["first_clock"] = p1["clock_display_value"].iloc[0]
        return out
    tip = open_["_w"].min()
    jump = p1[p1["type_text"].astype(str).str.contains("jump", case=False) &
              p1["text"].astype(str).str.contains("won", case=False)]
    out["start_to_jump_s"] = (jump["_w"].iloc[0] - tip).total_seconds() if len(jump) else np.nan
    f = p1[p1["_c"].notna()].head(30)
    dw = f["_w"].diff().dt.total_seconds()
    dc = -f["_c"].diff()
    slack = (dw - dc).dropna()
    out["min_slack_s"] = float(slack.min()) if len(slack) else np.nan
    out["length_min"] = (p["_w"].max() - tip).total_seconds() / 60
    if (dw.dropna() < -5).any():
        out["reason"] = "wall clocks out of order (more than 5 s backwards)"
    elif len(slack) and slack.min() < -30:
        out["reason"] = "wall clock runs more than 30 s faster than the game clock (entry times, not play times)"
    elif scheduled is None or pd.isna(scheduled):
        out["reason"] = "no scheduled start to check the wall clock against"
    elif not (-30 <= (tip - scheduled).total_seconds() / 60 <= 60):
        late = (tip - scheduled).total_seconds() / 3600
        out["reason"] = ("tip more than 30 min before or 60 min after the scheduled start"
                         + (" (a whole-hour offset: a time-zone error in the stamps)" if late >= 0.9 and
                            abs(late - round(late)) <= 10 / 60 else ""))
    elif not 60 <= out["length_min"] <= 300:
        out["reason"] = "game length on the wall clock outside 60-300 min"
    else:
        out.update(quality="jump ball", reason="", tip=tip)
    return out


def summary_plays(summary: dict) -> pd.DataFrame:
    """The live summary's plays in the cached play-by-play's columns."""
    return pd.DataFrame([{"sequence_number": x.get("sequenceNumber"), "period_number": (x.get("period") or {}).get("number"),
                          "clock_display_value": (x.get("clock") or {}).get("displayValue"),
                          "type_text": (x.get("type") or {}).get("text"), "text": x.get("text"),
                          "wallclock": x.get("wallclock")} for x in summary.get("plays") or []],
                        columns=["sequence_number", "period_number", "clock_display_value", "type_text", "text", "wallclock"])


def first_play(summary: dict) -> pd.Timestamp | None:
    """The usable actual tip from a live summary, or None (see classify)."""
    return fetch_summary(summary)["tip"]


def fetch_summary(summary: dict) -> dict:
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    sched = pd.to_datetime(comp.get("date"), utc=True, errors="coerce")
    return classify(summary_plays(summary), sched if pd.notna(sched) else None)


def fetch(game_id: int) -> dict:
    with urllib.request.urlopen(urllib.request.Request(SUMMARY.format(game_id), headers={"User-Agent": "cbb-model"}),
                                timeout=30) as r:
        return fetch_summary(json.load(r))


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
                c_ = fetch(g)
            except Exception as e:
                print(f"tipoff {g}: {e}")
                continue
            t = c_["tip"]
            rows.append({"game_id": g, "actual_tip": t.isoformat() if t is not None else None,
                         "quality": c_["quality"], "reason": c_["reason"],
                         "source": "espn play-by-play, earliest period-1 play at 20:00",
                         "fetched_at": now.isoformat(timespec="seconds")})
        if rows:
            c = pd.concat([c[~c["game_id"].isin([r["game_id"] for r in rows])], pd.DataFrame(rows)], ignore_index=True)
            c[COLS].to_csv(CACHE, index=False)
        return len(rows)
    except Exception as e:
        print(f"tipoff.refresh failed ({e}); continuing.")
        return 0


if __name__ == "__main__":
    print(fetch(int(sys.argv[1])))
