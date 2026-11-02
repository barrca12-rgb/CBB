"""Opener rule (Nov 2): rebuild research/linemove/signals.csv rows the live runs wrote but the workflow did not save.

From the first run on the rule (01:07 UTC Nov 2) until the workflow's fix, update.yml committed reports, lines and
bets but not research/linemove, so each run's new rows were lost. This replays every committed card run in that
span, oldest first (research/linemove/replay.py: the run's own model numbers and the quotes as of its time), and
writes each stopped signal once, stamped with that run's time, exactly as run_day.log_linemove would have.

    python -m research.linemove.backfill --since 2026-11-02T01:06:00Z
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

import pandas as pd

from cbb import odds, run_day
from research.linemove import replay


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    a = ap.parse_args()
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    days = json.load(open(os.path.join(root, "reports", "days.json")))["days"]
    moves = pd.read_csv(odds.MOVES)
    runs = []
    for d in days:
        out = subprocess.run(["git", "log", f"--since={a.since}", "--format=%cI", "--", f"reports/cbb_{d}.csv"],
                             capture_output=True, text=True, cwd=root).stdout.split()
        runs += [(t, d) for t in out]
    n = 0
    for t, d in sorted(runs):
        r = replay.run(d, t, moves)
        rows = []
        for g in r["gated"]:
            g = dict(g, seen_at=r["run"])
            if g.get("opener_first_seen"):
                g["minutes_since_open"] = round((pd.Timestamp(r["run"]) - pd.Timestamp(g["opener_first_seen"])).total_seconds() / 60, 1)
            rows.append(g)
        before = len(pd.read_csv(run_day.LINEMOVE_SIGNALS)) if os.path.exists(run_day.LINEMOVE_SIGNALS) else 0
        run_day.log_linemove(rows)
        after = len(pd.read_csv(run_day.LINEMOVE_SIGNALS)) if os.path.exists(run_day.LINEMOVE_SIGNALS) else 0
        n += after - before
    print(f"{len(runs)} card runs replayed since {a.since}; {n} signals written to {run_day.LINEMOVE_SIGNALS}")


if __name__ == "__main__":
    main()
