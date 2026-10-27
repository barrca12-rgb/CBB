"""Record a placed bet from the card's Placed button (.github/workflows/placed.yml).

Marks the bet placed in bets/bets.csv and records what was actually taken (book, line, odds, stake, time) in
bets/accepted.csv, the forward test's cohort C (FORWARD_TEST_PROTOCOL.md section 6). One accepted row per bet: a
second press for the same bet replaces it. Never changes a pick, line, edge, stake or result in the bet log.

    python -m cbb.placed --bet-id "2026-11-02|401906769|total|over" --book Fanatics --line 159.5 --odds -110 --stake 1
"""
from __future__ import annotations

import argparse
import csv
import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
BETS = os.path.join(ROOT, "bets", "bets.csv")
ACCEPTED = os.path.join(ROOT, "bets", "accepted.csv")
ACC_COLS = ["bet_id", "book", "placed_at", "line", "odds", "stake", "source"]


def tip_time(bet_id: str) -> pd.Timestamp | None:
    """The game's start from that day's card (reports/cbb_<date>.csv); None if the card has no start for it."""
    d, gid = bet_id.split("|")[:2]
    path = os.path.join(ROOT, "reports", f"cbb_{d}.csv")
    if not os.path.exists(path):
        return None
    c = pd.read_csv(path, usecols=["game_id", "start"])
    m = c[c["game_id"].astype(str) == gid]["start"]
    t = pd.to_datetime(m.iloc[0], utc=True, errors="coerce") if len(m) else pd.NaT
    return None if pd.isna(t) else t


def record(bet_id: str, book: str, line: float, odds: float, stake: float, placed_at: str | None = None,
           source: str = "card button") -> None:
    if not book.strip():
        raise ValueError("book is required")
    if not (abs(odds) >= 100):
        raise ValueError(f"odds {odds} are not American odds")
    if not (0 < stake <= 20):
        raise ValueError(f"stake {stake} is outside 0-20 units")
    rows = list(csv.reader(open(BETS, newline="")))
    h = rows[0]
    hit = [r for r in rows[1:] if r[h.index("bet_id")] == bet_id]
    if len(hit) != 1:
        raise ValueError(f"bet_id {bet_id!r} found {len(hit)} times in bets/bets.csv")
    start = tip_time(bet_id)
    if start is not None and pd.Timestamp.now(tz="UTC") >= start:
        raise ValueError(f"{bet_id} tipped off at {start:%Y-%m-%d %H:%M} UTC; a bet can only be marked placed before "
                         "tip (the record counts placed bets only). Ask in the session to record a late one by hand.")
    hit[0][h.index("placed")] = "yes"
    with open(BETS, "w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    acc = pd.read_csv(ACCEPTED, dtype=str) if os.path.exists(ACCEPTED) else pd.DataFrame(columns=ACC_COLS)
    acc = acc[acc["bet_id"] != bet_id]
    row = {"bet_id": bet_id, "book": book.strip(), "placed_at": placed_at or pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
           "line": f"{line:g}", "odds": f"{odds:g}", "stake": f"{stake:g}", "source": source}
    pd.concat([acc, pd.DataFrame([row])], ignore_index=True)[ACC_COLS].to_csv(ACCEPTED, index=False)
    print(f"Placed: {bet_id} at {row['book']} {row['line']} ({row['odds']}), {row['stake']}u, {row['placed_at']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bet-id", required=True)
    ap.add_argument("--book", required=True)
    ap.add_argument("--line", type=float, required=True)
    ap.add_argument("--odds", type=float, required=True)
    ap.add_argument("--stake", type=float, required=True)
    ap.add_argument("--placed-at")
    a = ap.parse_args()
    record(a.bet_id, a.book, a.line, a.odds, a.stake, a.placed_at)
