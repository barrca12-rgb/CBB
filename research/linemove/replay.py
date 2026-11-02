"""Opener rule (Nov 2): replay past live card runs with the rule off and on.

Each run is rebuilt from the repo's own history: the model's numbers from that run's committed card
(reports/cbb_<date>.csv), the lines and every first quote from lines/moves.csv as of that run's time. The v1 output
(every BET and band B play: game, market, side, line, book, price, edge, units) is compared rule-off vs rule-on.

    python -m research.linemove.replay      # -> research/linemove/out/replay.txt
"""
from __future__ import annotations

import io
import os
import subprocess

import numpy as np
import pandas as pd

from cbb import odds, run_day

OUT = os.path.join(os.path.dirname(__file__), "out")
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PLAY_COLS = ["game_id", "away", "home", "market", "pick", "line", "book", "odds", "edge", "units", "type"]


def _git(*a) -> str:
    return subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT).stdout


def card_at(day: str, at: str) -> tuple[pd.DataFrame, str]:
    h = _git("log", "-1", f"--before={at}", "--format=%h %cI", "--", f"reports/cbb_{day}.csv").split()
    return pd.read_csv(io.StringIO(_git("show", f"{h[0]}:reports/cbb_{day}.csv"))), h[1]


def lines_at(moves: pd.DataFrame, at: str, card: pd.DataFrame) -> pd.DataFrame:
    m = moves[pd.to_datetime(moves["pulled_at"], utc=True) <= pd.Timestamp(at)]
    m = m.drop_duplicates(["game_key", "book"], keep="last")
    rows = []
    for _, g in card.iterrows():
        lo, hi = min(g["home_id"], g["away_id"]), max(g["home_id"], g["away_id"])
        q = m[(m["lo_id"] == lo) & (m["hi_id"] == hi)]
        home_lo = g["home_id"] == lo
        for _, x in q.iterrows():
            rows.append({"home_id": g["home_id"], "away_id": g["away_id"], "book": x["book"], "start": g["start"],
                         "home_spread": x["spread"] if home_lo else -x["spread"],
                         "home_spread_odds": x["spread_odds_lo"] if home_lo else x["spread_odds_hi"],
                         "away_spread_odds": x["spread_odds_hi"] if home_lo else x["spread_odds_lo"],
                         "total": x["total"], "over_odds": x["over_odds"], "under_odds": x["under_odds"]})
    return pd.DataFrame(rows, columns=["home_id", "away_id", "book", "start", "home_spread", "home_spread_odds",
                                       "away_spread_odds", "total", "over_odds", "under_odds"])


def play_rows(c: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, r in c.iterrows():
        for mk in ("spread", "total"):
            kinds = (["v1"] if r.get(f"{mk}_verdict") == "BET" else []) + (["bandB"] if bool(r.get(f"{mk}_bandb")) is True else [])
            for k in kinds:
                pick = f"{r[mk + '_pick']} {r[mk + '_line']:+g}" if mk == "spread" else f"{r['total_pick']} {r['total_line']:g}"
                out.append({"game_id": r["game_id"], "away": r["away"], "home": r["home"], "market": mk, "pick": pick,
                            "line": r[f"{mk}_line"], "book": r[f"{mk}_book"], "odds": r[f"{mk}_odds"],
                            "edge": round(float(r[f"{mk}_edge"]), 3), "units": r.get(f"{mk}_units"), "type": k})
    return pd.DataFrame(out, columns=PLAY_COLS)


def run(day: str, at: str, moves: pd.DataFrame) -> dict:
    card, committed = card_at(day, at)
    f = card.assign(final_margin=card["model_margin"], final_total=card["model_total"])
    lines = lines_at(moves, committed, card)
    path = os.path.join(OUT, "_moves_asof.csv")
    moves[pd.to_datetime(moves["pulled_at"], utc=True) <= pd.Timestamp(committed)].to_csv(path, index=False)
    o = pd.read_csv(os.path.join(odds.LINES, "openers.csv"))
    opath = os.path.join(OUT, "_openers_asof.csv")
    o[pd.to_datetime(o["first_seen"], utc=True, format="ISO8601") <= pd.Timestamp(committed)].to_csv(opath, index=False)
    fq = run_day.first_quotes(path, openers=opath)
    os.remove(path)
    os.remove(opath)
    run_day.OPENER_RULE = False
    off = play_rows(run_day.plays(f, lines, live=True, fq=fq))
    w_off = run_day.plays(f, lines, live=True, fq=fq)
    run_day.OPENER_RULE = True
    on_card = run_day.plays(f, lines, live=True, fq=fq)
    on = play_rows(on_card)
    a, b = off.to_csv(index=False), on.to_csv(index=False)
    removed = off.merge(on, how="left", indicator=True).query("_merge == 'left_only'").drop(columns="_merge")
    added = on.merge(off, how="left", indicator=True).query("_merge == 'left_only'").drop(columns="_merge")
    watch = int(sum(((w_off[f"{mk}_verdict"] == "WATCH") & (on_card[f"{mk}_verdict"] != "WATCH")).sum()
                    for mk in ("spread", "total") if f"{mk}_verdict" in w_off))
    return {"day": day, "run": committed, "plays_off": len(off), "plays_on": len(on), "identical": a == b,
            "removed": removed, "added": added, "watch_removed": watch, "gated": list(run_day.GATED)}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    moves = pd.read_csv(odds.MOVES)
    # three runs with plays and no line-move play, then the Nov 1 19:22 run (the hour of the 13-play burst)
    runs = [("2026-11-01", "2026-10-31T13:55:00Z"), ("2026-11-01", "2026-11-01T06:05:00Z"),
            ("2026-11-02", "2026-10-27T02:55:00Z"), ("2026-11-02", "2026-11-01T19:25:00Z")]
    L = [__doc__.split("\n\n")[1], ""]
    for day, at in runs:
        r = run(day, at, moves)
        L.append(f"{r['day']} card, run committed {r['run']}: {r['plays_off']} plays with the rule off, {r['plays_on']} "
                 f"with it on; v1 and band B output byte-identical: {'YES' if r['identical'] else 'NO'}; watches the "
                 f"rule removes: {r['watch_removed']}")
        if len(r["removed"]):
            L.append("  plays removed (and nothing else changed):" if not len(r["added"]) else "  plays removed:")
            L.append(r["removed"].to_string(index=False))
        if len(r["added"]):
            L.append("  PLAYS ADDED (the rule must never add one):\n" + r["added"].to_string(index=False))
        L.append("")
    txt = "\n".join(L)
    open(os.path.join(OUT, "replay.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
