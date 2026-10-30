"""Ladder share read (PLAN.md): the share of logged plays whose best rung beats the main number by 0.5 points of EV
(gain >= 0.005 per unit), with credits spent. Used for the first-week report and the Nov 23 stop rule. Read-only.

    python -m research.ladder.read [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from cbb import ladder

BAR = 0.005


def read(through: str | None = None) -> str:
    if not os.path.exists(ladder.PLAYS):
        return "No ladder plays logged yet."
    p = pd.read_csv(ladder.PLAYS)
    from cbb import tracker
    void = set(tracker.load("all").query("status == 'void'")["bet_id"])
    p = p[~p["bet_id"].isin(void)]                  # a voided play (e.g. the Oct 30 bad BetMGM quote) is not a play
    if through:
        p = p[p["date"].astype(str) <= through]
    pulls = p.drop_duplicates(["game_id", "pulled_at"])
    cost = pd.to_numeric(pulls["cost"], errors="coerce")
    out = [f"Plays with a ladder row: {len(p)}; pulls {len(pulls)}; credits {cost.sum():.0f} "
           f"({cost.mean():.2f} per pull, {cost.sum() / max(len(p), 1):.2f} per play; {cost.isna().sum()} pulls without a cost header)"]
    have = p[pd.to_numeric(p["rungs"], errors="coerce") > 0]
    out.append(f"Plays with rungs on their side: {len(have)} of {len(p)}")
    for mk, g in [("all", have)] + list(have.groupby("market")):
        gain = pd.to_numeric(g["gain"], errors="coerce")
        n, k = len(g), int((gain >= BAR).sum())
        out.append(f"  {mk}: {k} of {n} ({100 * k / n:.1f}%) have a rung beating the main number by 0.5+ points of EV; "
                   f"median gain {gain.median():+.4f}" if n else f"  {mk}: none")
    if len(have):
        share = (pd.to_numeric(have["gain"], errors="coerce") >= BAR).mean()
        out.append(f"Stop rule (after three weeks): {'switch off' if share < 0.10 else 'keep'} at a {100 * share:.1f}% share (bar 10%)")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    print(read(ap.parse_args().through))
