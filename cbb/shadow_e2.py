"""E2 totals shadow (research/e2_shadow/PLAN.md). Run after each card run by .github/workflows/shadow_e2.yml.

E2 = v1's stage-2 totals with two extra inputs, neutral site and conference game (research/quant, E2), fit once on
2013-2026 and frozen on Oct 28 in research/quant/out/e2_coefficients.json (the same
coefficients the research E2 prospective test uses; never refit). For each card game this adds E2's difference from v1's stage-2 total
(same saved inputs, reports/features_<date>.csv) to the card's v1 total, so everything else in v1's total (opening-week
rule, injury adjustments) carries over unchanged; in opening week the day's mean difference is removed, as v1's rule
re-centres each day on KenPom. Then v1's totals rule unchanged (run_day: best EV across books, edge 3+, EV +2%), and each
new E2 totals signal is logged once to bets/shadow_e2/signals.csv.

Never alerts, posts, stakes or touches bets/bets.csv, the card or any frozen file. Not part of the site's record.

    python -m cbb.shadow_e2 [--now ISO]
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

from . import data, run_day

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "bets", "shadow_e2")
SIGNALS = os.path.join(DIR, "signals.csv")
RUNS = os.path.join(DIR, "runs.csv")
GAMES = os.path.join(DIR, "games_latest.csv")
SPEC = os.path.join(ROOT, "research", "quant", "out", "e2_coefficients.json")   # frozen Oct 28, never refit
COLS = ["bet_id", "pick", "game", "date", "game_id", "home_id", "away_id", "start", "side", "book", "line", "odds",
        "v1_total", "e2_delta", "e2_total", "neutral", "conf_game", "edge", "ev", "v1_edge_at_quote", "v1_signal_at_quote",
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
    """Card games today and later with the v1 total and the saved stage-2 inputs for the same run."""
    today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
    parts = []
    for f in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_*.csv"))):
        d = os.path.basename(f)[4:14]
        feat = os.path.join(ROOT, "reports", f"features_{d}.csv")
        if d < today or not os.path.exists(feat):
            continue
        x = pd.read_csv(f)
        if not len(x) or "model_total" not in x:
            continue
        fe = pd.read_csv(feat).drop(columns=["date", "start", "home", "away", "home_id", "away_id", "state", "home_score",
                                             "away_score"], errors="ignore")
        x = x[["game_id", "start", "home_id", "away_id", "home", "away", "model_total", "total_shift"]].merge(
            fe, on="game_id", how="inner")
        parts.append(x.assign(date=d))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def conf_games(dates, seasons) -> dict:
    """Conference-game flag per game: ESPN's scoreboard for each card date (the card's own slate source,
    run_day.slate), with the hoopR schedule as a fallback (it lags for upcoming games)."""
    out = {}
    for s in seasons:
        try:
            sch = data.fetch("schedule", s, refresh=True)
            out.update(dict(zip(sch["game_id"].astype(int), sch["conference_competition"].fillna(False).astype(bool))))
        except Exception:
            pass
    for d in dates:
        try:
            sl = run_day.slate(pd.Timestamp(d))
            out.update(dict(zip(sl["game_id"].astype(int), sl["conf_game"].astype(bool))))
        except Exception:
            pass
    return out


def best_total(lines: pd.DataFrame, g, t: float):
    l = lines[((lines["home_id"] == g["home_id"]) & (lines["away_id"] == g["away_id"])) |
              ((lines["home_id"] == g["away_id"]) & (lines["away_id"] == g["home_id"]))]
    if not len(l):
        return None
    return run_day._best(l, "total", {"over": ("total", lambda x: t - x, "over_odds"),
                                      "under": ("total", lambda x: x - t, "under_odds")})


def main(now: pd.Timestamp | None = None) -> None:
    now = now or pd.Timestamp.now(tz="UTC")
    os.makedirs(DIR, exist_ok=True)
    have = set(pd.read_csv(SIGNALS)["bet_id"]) if os.path.exists(SIGNALS) else set()
    run = {"run_at": now.isoformat(timespec="seconds"), "games": 0, "games_with_delta": 0, "signals": 0, "error": ""}
    try:
        raw = json.load(open(SPEC))
        feats = [k for k in raw if k not in ("fitted_on", "frozen", "intercept")]
        spec = {"features": feats, "intercept": raw["intercept"], "coef": {k: raw[k] for k in feats}}
        games = card_games(now)
        lines = latest_lines(now)
        run["games"] = len(games)
        if not len(games) or not len(lines):
            return
        cg = conf_games(sorted(games["date"].unique()), sorted({season_of(pd.Timestamp(d)) for d in games["date"]}))
        games["conf_game"] = games["game_id"].map(cg)
        games["neutral"] = games["neutral"].astype(float)
        ok = games["conf_game"].notna() & games["final_total"].notna()
        games = games[ok].copy()
        games["conf_game"] = games["conf_game"].astype(float)
        X = games[spec["features"]].astype(float).to_numpy()
        e2_raw = spec["intercept"] + X @ np.array([spec["coef"][f] for f in spec["features"]])
        games["e2_delta"] = e2_raw - games["final_total"].astype(float)
        # opening week: v1's rule re-centres each day's totals on KenPom's mean, so E2 keeps only its game-to-game part
        ow = games.groupby("date")["total_shift"].transform(lambda s: bool((s.fillna(0) != 0).any()))
        games.loc[ow, "e2_delta"] -= games.loc[ow].groupby("date")["e2_delta"].transform("mean")
        games["e2_total"] = games["model_total"].astype(float) + games["e2_delta"]
        run["games_with_delta"] = len(games)
        new, gl = [], []
        for _, g in games.iterrows():
            t1, t2 = float(g["model_total"]), float(g["e2_total"])
            if pd.to_datetime(g["start"], utc=True, errors="coerce") > now:
                gl.append({"game_id": int(g["game_id"]), "date": g["date"], "start": g["start"], "home_id": int(g["home_id"]),
                           "away_id": int(g["away_id"]), "v1_total": round(t1, 3), "e2_delta": round(float(g["e2_delta"]), 3),
                           "e2_total": round(t2, 3), "neutral": bool(g["neutral"]), "conf_game": bool(g["conf_game"]),
                           "updated_at": now.isoformat(timespec="seconds")})
            b = best_total(lines, g, t2)
            if not b:
                continue
            side, row, edge, p, value = b
            if not (edge >= run_day.TOTAL_CALLS[0][0] and value >= run_day.MIN_EV):
                continue
            bid = f"{g['date']}|{int(g['game_id'])}|total|{side}"
            if bid in have:
                continue
            e1 = (t1 - row["total"]) if side == "over" else (row["total"] - t1)
            p1 = run_day.win_prob("total", e1)
            v1_sig = bool(e1 >= run_day.TOTAL_CALLS[0][0] and run_day.ev(p1, row.get(f"{side}_odds")) >= run_day.MIN_EV)
            new.append({"bet_id": bid, "pick": f"{side.title()} {row['total']:g}", "game": f"{g['away']} at {g['home']}",
                        "date": g["date"], "game_id": int(g["game_id"]), "home_id": int(g["home_id"]), "away_id": int(g["away_id"]),
                        "start": g["start"], "side": side, "book": row["book"], "line": float(row["total"]),
                        "odds": row.get(f"{side}_odds"), "v1_total": round(t1, 3), "e2_delta": round(float(g["e2_delta"]), 3),
                        "e2_total": round(t2, 3), "neutral": bool(g["neutral"]), "conf_game": bool(g["conf_game"]),
                        "edge": round(edge, 3), "ev": round(value, 4), "v1_edge_at_quote": round(e1, 3),
                        "v1_signal_at_quote": v1_sig, "lines_pulled_at": str(row.get("pulled_at", "")),
                        "logged_at": now.isoformat(timespec="seconds")})
        if new:
            pd.DataFrame(new).reindex(columns=COLS).to_csv(SIGNALS, mode="a", header=not os.path.exists(SIGNALS), index=False)
        if gl:   # keep each game's latest pregame row; games already started keep their last pregame row
            old = pd.read_csv(GAMES) if os.path.exists(GAMES) else pd.DataFrame(columns=list(gl[0]))
            cur = pd.DataFrame(gl)
            pd.concat([old[~old["game_id"].isin(cur["game_id"])], cur], ignore_index=True).sort_values(["date", "game_id"]).to_csv(GAMES, index=False)
        run["signals"] = len(new)
    except Exception as e:      # the shadow never stops anything; failures are logged
        run["error"] = str(e)[:300]
        print(f"shadow_e2 failed: {e}")
    finally:
        pd.DataFrame([run]).to_csv(RUNS, mode="a", header=not os.path.exists(RUNS), index=False)
        print(run)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    a = ap.parse_args()
    main(pd.Timestamp(a.now) if a.now else None)
