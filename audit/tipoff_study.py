"""How far ESPN's play-by-play wall clock can be trusted as the actual tip (audit/CLV_VERIFICATION.md, section 2).

Read only, offline: the cached play-by-play (cbb/cache/pbp/play_by_play_<season>.parquet, ESPN via sportsdataverse)
and schedules (cbb/cache/mbb_schedule_<season>.parquet). For every completed Division I vs Division I game it applies
cbb/tipoff.classify (the same rule the live check uses) and measures:

  coverage      games with play-by-play, with a wall clock, and with a usable tip, by season and by reason excluded
  reliability   wall clocks in sequence order; wall-clock time never running faster than the game clock over the
                first plays; the tip's distance from the scheduled start; the game's length on the wall clock
  thresholds    actual tip minus scheduled start (what the 30-minute near-tip limit would call "early"), and the
                share of closes the 60-second buffer would fail if the last quote arrived 0-180 s before the
                scheduled start (the 3-minute targeted polls)

    python -m audit.tipoff_study            # -> audit/tipoff_study.md, audit/tipoff_study_games.csv.gz
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import tipoff

CACHE = os.path.join(os.path.dirname(__file__), "..", "cbb", "cache")
OUT = os.path.dirname(__file__)
SEASONS = range(2021, 2027)   # the 2014-2020 caches were saved without the wallclock column (says nothing about ESPN)
COLS = ["game_id", "sequence_number", "period_number", "clock_display_value", "type_text", "text", "wallclock",
        "game_spread_available"]


def season(s: int) -> pd.DataFrame:
    sch = pd.read_parquet(os.path.join(CACHE, f"mbb_schedule_{s}.parquet"),
                          columns=["game_id", "start_date", "time_valid", "status_type_completed", "home_id", "away_id"])
    d1 = set(pd.read_csv(os.path.join(CACHE, "..", "..", "data", "teams.csv"))["espn_id"].astype(int))
    sch = sch[sch["status_type_completed"].astype(bool) & sch["home_id"].astype(int).isin(d1) &
              sch["away_id"].astype(int).isin(d1)].copy()
    sch["game_id"] = sch["game_id"].astype(int)
    sch["scheduled"] = pd.to_datetime(sch["start_date"], utc=True, errors="coerce")
    f = os.path.join(CACHE, "pbp", f"play_by_play_{s}.parquet")
    p = pd.read_parquet(f, columns=COLS) if os.path.exists(f) else pd.DataFrame(columns=COLS)
    p = p[p["game_id"].astype(int).isin(set(sch["game_id"]))]
    p["game_id"] = p["game_id"].astype(int)
    market = p.groupby("game_id")["game_spread_available"].max() if len(p) else pd.Series(dtype=bool)
    rows = []
    by = dict(tuple(p.groupby("game_id"))) if len(p) else {}
    for _, g in sch.iterrows():
        plays = by.get(g["game_id"])
        r = tipoff.classify(plays, g["scheduled"] if bool(g["time_valid"]) else None)
        r.setdefault("first_clock", None)
        r.update(game_id=g["game_id"], season=s, scheduled=g["scheduled"], time_valid=bool(g["time_valid"]),
                 in_pbp=plays is not None, market=bool(market.get(g["game_id"], False)))
        rows.append(r)
    return pd.DataFrame(rows)


def report(d: pd.DataFrame) -> str:
    L = ["# ESPN wall clock as the actual tip: coverage and reliability\n",
         f"Generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC by `python -m audit.tipoff_study` from the cached "
         "play-by-play and schedules (completed Division I vs Division I games). Rule: `cbb/tipoff.classify`.\n"]
    L.append("## Coverage by season\n")
    L.append("| Season | Games | With play-by-play | With a wall clock | Usable tip |")
    L.append("|---|---:|---:|---:|---:|")
    for s_, g in d.groupby("season"):
        L.append(f"| {s_ - 1}-{str(s_)[2:]} | {len(g)} | {g['in_pbp'].mean():.1%} | {g['has_wallclock'].mean():.1%} | "
                 f"{(g['quality'] == 'jump ball').mean():.1%} |")
    L.append("\n## Why games are excluded (all seasons)\n")
    L.append("| Reason | Games | Share |\n|---|---:|---:|")
    for k, n in d.loc[d["quality"] != "jump ball", "reason"].value_counts().items():
        L.append(f"| {k} | {n} | {n / len(d):.2%} |")
    L.append("\nLast season (2025-26), the format the live check will see:\n")
    L.append("| Reason | Games | Share |\n|---|---:|---:|")
    last = d[d["season"] == d["season"].max()]
    for k, n in last.loc[last["quality"] != "jump ball", "reason"].value_counts().items():
        L.append(f"| {k} | {n} | {n / len(last):.2%} |")
    u = d[d["quality"] == "jump ball"]
    recent = d[d["season"] >= 2024]
    L.append(f"\nUsable: {len(u)} of {len(d)} ({len(u) / len(d):.1%}); last three seasons "
             f"{(recent['quality'] == 'jump ball').mean():.1%} of {len(recent)}. Excluded games are listed in "
             "`audit/tipoff_study_games.csv.gz` (`quality`, `reason`).\n")

    L.append("## Reliability, usable games\n")
    delay = (u["tip"] - u["scheduled"]).dt.total_seconds() / 60
    delay = delay[u["time_valid"]]
    q = delay.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    L.append("Actual tip minus scheduled start (minutes): " + ", ".join(f"p{int(k * 100)} {v:+.1f}" for k, v in q.items()))
    L.append(f"\n- Tip before the scheduled start: {(delay < 0).mean():.2%}; more than 1 min before: {(delay < -1).mean():.2%}; "
             f"more than 5 min before: {(delay < -5).mean():.2%}.")
    L.append(f"- Tip more than 30 min after the scheduled start: {(delay > 30).mean():.2%} "
             f"(more than 15: {(delay > 15).mean():.2%}; more than 60: {(delay > 60).mean():.2%}).")
    L.append(f"- Start-of-game stamp to the jump-ball stamp (where both exist): median "
             f"{u['start_to_jump_s'].median():.0f} s, p95 {u['start_to_jump_s'].quantile(0.95):.0f} s.")
    L.append(f"- Wall clock running faster than the game clock over the first plays (wall-clock gap shorter than the "
             f"game-clock gap): worst case per game median {u['min_slack_s'].median():.0f} s, p1 "
             f"{u['min_slack_s'].quantile(0.01):.0f} s (negative = stamps are not play times).")
    L.append(f"- Game length on the wall clock: median {u['length_min'].median():.0f} min, p1 "
             f"{u['length_min'].quantile(0.01):.0f}, p99 {u['length_min'].quantile(0.99):.0f}.\n")

    L.append("## Effect of the proposed thresholds\n")
    L.append("Near-tip limit (cutoff = scheduled start, assumed correct): share of usable games whose actual tip is "
             "more than N minutes after the scheduled start, i.e. would be called \"early\":\n")
    L.append("| N (min) | 10 | 15 | 20 | 30 | 45 | 60 |\n|---|---:|---:|---:|---:|---:|---:|")
    L.append("| early | " + " | ".join(f"{(delay > n).mean():.2%}" for n in (10, 15, 20, 30, 45, 60)) + " |")
    L.append("\nUncertainty buffer: share of closes failing \"last quote at least B seconds before the actual tip\" "
             "when the last quote arrives uniformly 0-180 s before the scheduled start:\n")
    rng = np.random.default_rng(0)
    u_s = rng.uniform(0, 180, size=len(delay))
    gap = delay.to_numpy() * 60 + u_s                      # seconds from the last quote to the actual tip
    L.append("| B (s) | 0 | 30 | 60 | 120 | 300 |\n|---|---:|---:|---:|---:|---:|")
    L.append("| fail | " + " | ".join(f"{(gap < b).mean():.2%}" for b in (0, 30, 60, 120, 300)) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    d = pd.concat([season(s) for s in SEASONS], ignore_index=True)
    d.to_csv(os.path.join(OUT, "tipoff_study_games.csv.gz"), index=False,
             compression={"method": "gzip", "mtime": 0})
    with open(os.path.join(OUT, "tipoff_study.md"), "w") as fh:
        fh.write(report(d))
    print(report(d))


if __name__ == "__main__":
    main()
