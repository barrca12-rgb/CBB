"""Lineup v2 shadow (research/v2_lineup/PLAN.md). Run after each card run by .github/workflows/shadow_v2.yml.

Reads what the card run committed (reports/cbb_<date>.csv for today and later days: the frozen v1 margins;
lines/closing.csv: the latest pull's quotes), adds the lineup adjustment (cbb/lineup.py, frozen BETA) to v1's
spread margin, applies v1's spread rule unchanged (run_day: best EV across books, edge 2.5+, EV +2%), and logs each
new v2 spread signal once to bets/shadow_v2/signals.csv. Never alerts, posts, stakes or touches bets/bets.csv, the
card or any frozen file. Totals are v1's (unchanged in v2) and are not logged here.

    python -m cbb.shadow_v2 [--now ISO]
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

from . import lineup, run_day

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "bets", "shadow_v2")
SIGNALS = os.path.join(DIR, "signals.csv")
RUNS = os.path.join(DIR, "runs.csv")
COLS = ["bet_id", "date", "game_id", "home_id", "away_id", "start", "side", "book", "line", "odds", "v1_margin",
        "home_adj", "away_adj", "adj_margin", "v2_margin", "edge", "ev", "v1_edge_at_quote", "v1_signal_at_quote",
        "lines_pulled_at", "logged_at"]


def season_of(day: pd.Timestamp) -> int:
    return day.year + 1 if day.month >= 8 else day.year


def latest_lines(now: pd.Timestamp) -> pd.DataFrame:
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    c["pulled"] = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    c["st"] = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    c = c[c["pulled"] == c["pulled"].max()]           # the latest pull = what the card just used
    return c[c["st"] > now]                            # pregame only


def card_games(now: pd.Timestamp) -> pd.DataFrame:
    today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
    parts = []
    for f in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_*.csv"))):
        d = os.path.basename(f)[4:14]
        if d >= today:
            x = pd.read_csv(f)
            if len(x) and "model_margin" in x:
                parts.append(x.assign(date=d)[["date", "game_id", "start", "home_id", "away_id", "model_margin"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def best_spread(lines: pd.DataFrame, g, m: float):
    """run_day's spread selection on one game's book lines at model margin m (handles reversed listings)."""
    l = lines[(lines["home_id"] == g["home_id"]) & (lines["away_id"] == g["away_id"])]
    flip = lines[(lines["home_id"] == g["away_id"]) & (lines["away_id"] == g["home_id"])]
    if not len(l) and len(flip):
        l = flip.rename(columns={"home_spread_odds": "away_spread_odds", "away_spread_odds": "home_spread_odds"}).assign(
            home_spread=-flip["home_spread"])
    if not len(l):
        return None
    return run_day._best(l, "spread", {"home": ("home_spread", lambda s_: m + s_, "home_spread_odds"),
                                       "away": ("home_spread", lambda s_: -(m + s_), "away_spread_odds")})


def main(now: pd.Timestamp | None = None) -> None:
    now = now or pd.Timestamp.now(tz="UTC")
    os.makedirs(DIR, exist_ok=True)
    have = set(pd.read_csv(SIGNALS)["bet_id"]) if os.path.exists(SIGNALS) else set()
    run = {"run_at": now.isoformat(timespec="seconds"), "games": 0, "teams_with_adjustment": 0, "signals": 0, "error": ""}
    try:
        games = card_games(now)
        lines = latest_lines(now)
        run["games"] = len(games)
        if not len(games) or not len(lines):
            return
        try:
            adj = lineup.adjustments(season_of(now.tz_convert("America/New_York").tz_localize(None)), upcoming=True,
                                     asof=now.tz_convert("America/New_York"), refresh=True)
            nxt = adj[adj["game_id"] == 0].set_index("team_id")
            v = (nxt["adj_off"] + nxt["adj_def"]).to_dict()
        except Exception as e:   # no box scores yet (preseason): every adjustment 0, so v2 = v1
            v = {}
            run["error"] = f"no adjustments: {str(e)[:150]}"
        run["teams_with_adjustment"] = len(v)
        new = []
        for _, g in games.iterrows():
            ha, aa = float(v.get(int(g["home_id"]), 0.0)), float(v.get(int(g["away_id"]), 0.0))
            m1 = float(g["model_margin"])
            m2 = m1 + lineup.BETA * (ha - aa)
            b2 = best_spread(lines, g, m2)
            if not b2:
                continue
            side, row, edge, p, value = b2
            if not (edge >= run_day.SPREAD_CALLS[0][0] and value >= run_day.MIN_EV):
                continue
            bid = f"{g['date']}|{int(g['game_id'])}|spread|{side}"
            if bid in have:
                continue
            line = row["home_spread"] if side == "home" else -row["home_spread"]
            e1 = (m1 + row["home_spread"]) if side == "home" else -(m1 + row["home_spread"])
            p1 = run_day.win_prob("spread", e1)
            v1_sig = bool(e1 >= run_day.SPREAD_CALLS[0][0] and run_day.ev(p1, row.get(f"{side}_spread_odds")) >= run_day.MIN_EV)
            new.append({"bet_id": bid, "date": g["date"], "game_id": int(g["game_id"]), "home_id": int(g["home_id"]),
                        "away_id": int(g["away_id"]), "start": g["start"], "side": side, "book": row["book"], "line": line,
                        "odds": row.get(f"{side}_spread_odds"), "v1_margin": round(m1, 3), "home_adj": round(ha, 3),
                        "away_adj": round(aa, 3), "adj_margin": round(ha - aa, 3), "v2_margin": round(m2, 3),
                        "edge": round(edge, 3), "ev": round(value, 4), "v1_edge_at_quote": round(e1, 3),
                        "v1_signal_at_quote": v1_sig, "lines_pulled_at": str(row.get("pulled_at", "")),
                        "logged_at": now.isoformat(timespec="seconds")})
        if new:
            pd.DataFrame(new).reindex(columns=COLS).to_csv(SIGNALS, mode="a", header=not os.path.exists(SIGNALS), index=False)
        run["signals"] = len(new)
    except Exception as e:      # the shadow never stops anything; failures are logged
        run["error"] = str(e)[:300]
        print(f"shadow_v2 failed: {e}")
    finally:
        pd.DataFrame([run]).to_csv(RUNS, mode="a", header=not os.path.exists(RUNS), index=False)
        print(run)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    a = ap.parse_args()
    main(pd.Timestamp(a.now) if a.now else None)
