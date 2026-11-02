"""Opener rule (Nov 2): does the first-quote store (lines/moves.csv) hold each book's first quote for every game on
the card? Compared with lines/openers.csv (each book's first number and first_seen, no price), game by game.

    python -m research.linemove.coverage      # -> research/linemove/out/coverage.txt
"""
from __future__ import annotations

import json
import os

import pandas as pd

from cbb import odds, run_day

OUT = os.path.join(os.path.dirname(__file__), "out")
REPORTS = os.path.join(os.path.dirname(__file__), "..", "..", "reports")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    days = json.load(open(os.path.join(REPORTS, "days.json")))
    moves = pd.read_csv(odds.MOVES)
    first = moves.sort_values("pulled_at").drop_duplicates(["game_key", "book"], keep="first")
    op = pd.read_csv(os.path.join(odds.LINES, "openers.csv"))
    fq = run_day.first_quotes()
    L, rows = [], []
    for d in days["days"]:
        if d < days["current"]:
            continue
        p = os.path.join(REPORTS, f"cbb_{d}.csv")
        if not os.path.exists(p):
            continue
        c = pd.read_csv(p)
        c = c[c["n_books"] > 0]
        for _, g in c.iterrows():
            lo, hi = min(g["home_id"], g["away_id"]), max(g["home_id"], g["away_id"])
            fm = first[(first["lo_id"] == lo) & (first["hi_id"] == hi)]
            o = op[op["game_key"].astype(str).str.endswith(f"|{lo}|{hi}")]
            q = fq[(fq["lo_id"] == lo) & (fq["hi_id"] == hi)]
            priced = q.dropna(subset=["price"])
            late = []
            for _, x in o.iterrows():
                mm = fm[fm["book"] == x["book"]]
                if not len(mm):
                    late.append(f"{x['book']}: not in moves.csv")
                elif pd.Timestamp(mm["pulled_at"].iloc[0]) - pd.Timestamp(x["first_seen"]) > pd.Timedelta(minutes=15):
                    late.append(f"{x['book']}: first in moves.csv {mm['pulled_at'].iloc[0][:16]}, first seen {str(x['first_seen'])[:16]}")
            rows.append({"date": d, "game": f"{g['away']} at {g['home']}", "books_now": int(g["n_books"]),
                         "books_with_first_quote": fm["book"].nunique(), "priced_first_quotes": priced["book"].nunique(),
                         "first_quote_from": fm["pulled_at"].min()[:16] if len(fm) else None, "gaps": "; ".join(late)})
    t = pd.DataFrame(rows)
    gaps = t[(t["gaps"] != "") | (t["books_with_first_quote"] == 0)]
    L.append(f"Games on the card with lines (today and later): {len(t)}; with a first quote in lines/moves.csv for "
             f"every book openers.csv has: {len(t) - len(gaps)}; with a gap: {len(gaps)}.")
    L.append(f"Earliest first quote in moves.csv: {moves['pulled_at'].min()} (the log started Oct 26, 12:32 UTC); "
             f"the card's first lines for any game: {op['first_seen'].min()}.")
    if len(gaps):
        L.append("\nGames with a gap (the gate skips a book with no first quote; this run's quote stands for a book "
                 "it has never seen):")
        L.append(gaps.to_string(index=False))
    txt = "\n".join(L)
    open(os.path.join(OUT, "coverage.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
