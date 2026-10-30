"""Runs the card exactly as `python -m cbb.run_day` does, and also saves each built day's stage-2 inputs to
reports/features_<date>.csv for the ridge-1,000 shadow (cbb/shadow_r1000.py), and every book's moneyline as the card
pulled it to lines/ml/ (research/moneyline/PLAN.md: how long a mispriced moneyline stays up; no extra credits, the
card's pull already carries them). Nothing the card computes, picks, logs or posts changes: projection.apply_saved
and run_day.plays are wrapped only to copy what they see, and a failure to save is printed and ignored. Used by
.github/workflows/update.yml in place of `python -m cbb.run_day` (same arguments).

    python -m cbb.card_features --auto | --date YYYY-MM-DD
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import projection, run_day

KEYS = ["game_id", "date", "start", "home", "away", "home_id", "away_id", "neutral", "state", "home_score", "away_score"]
_apply = projection.apply_saved


def _apply_and_save(b: pd.DataFrame) -> pd.DataFrame:
    f = _apply(b)
    try:
        cols = [c for c in KEYS if c in f] + [c for c in dict.fromkeys(projection.MARGIN_FEATURES + projection.TOTAL_FEATURES) if c in f] \
            + ["final_margin", "final_total"]
        day = pd.Timestamp(f["date"].iloc[0])
        os.makedirs(run_day.REPORTS, exist_ok=True)
        f[cols].to_csv(os.path.join(run_day.REPORTS, f"features_{day:%Y-%m-%d}.csv"), index=False)
    except Exception as e:   # never affects the card
        print(f"Saving stage-2 inputs failed ({e}); continuing.")
    return f


projection.apply_saved = _apply_and_save

ML_DIR = os.path.join(os.path.dirname(__file__), "..", "lines", "ml")
ML_COLS = ["observed_at", "pulled_at", "date", "start", "home_id", "away_id", "book", "home_ml", "away_ml", "status"]
_plays = run_day.plays


def log_moneylines(lines: pd.DataFrame, now: pd.Timestamp | None = None) -> int:
    """Append each (game, book) moneyline that is new or changed since its last logged row to
    lines/ml/<UTC date>.csv (change-only, like lines/moves.csv). A book quoting the game with no moneyline, or with
    one side only, is logged with status "missing" (never a price); status "ok" otherwise. Returns rows written."""
    if lines is None or not len(lines):
        return 0
    now = now or pd.Timestamp.now(tz="UTC")
    cur = lines.copy()
    for c in ML_COLS:
        if c not in cur:
            cur[c] = np.nan
    # this run's pull carries no pulled_at (odds.pull stamps the saved copy); carried rows keep their own
    from . import odds
    this_pull = getattr(odds.pull, "pulled_at", None) or now.isoformat(timespec="seconds")
    cur["pulled_at"] = cur["pulled_at"].where(cur["pulled_at"].notna(), this_pull)
    cur["date"] = cur["date"].where(cur["date"].notna(), pd.to_datetime(cur["start"], utc=True, errors="coerce")
                                    .dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))
    ok = cur["home_ml"].notna() & cur["away_ml"].notna() & (cur["home_ml"].abs() >= 100) & (cur["away_ml"].abs() >= 100)
    cur["status"] = np.where(ok, "ok", "missing")
    cur.loc[~ok, ["home_ml", "away_ml"]] = np.nan
    cur["observed_at"] = now.isoformat(timespec="seconds")
    cur = cur[ML_COLS]
    os.makedirs(ML_DIR, exist_ok=True)
    last_path = os.path.join(ML_DIR, "latest.csv")
    key = ["home_id", "away_id", "book"]
    if os.path.exists(last_path):
        old = pd.read_csv(last_path).reindex(columns=ML_COLS)
        old["status"] = old["status"].fillna("ok")
        last = old.drop_duplicates(key, keep="last").set_index(key)[["home_ml", "away_ml", "status"]]
        prev = last.reindex(pd.MultiIndex.from_frame(cur[key]))
        same = ((prev["home_ml"].fillna(0).to_numpy() == cur["home_ml"].fillna(0).to_numpy())
                & (prev["away_ml"].fillna(0).to_numpy() == cur["away_ml"].fillna(0).to_numpy())
                & (prev["status"].to_numpy() == cur["status"].to_numpy()))
        new = cur[~same]
        keep = pd.concat([old, cur]).drop_duplicates(key, keep="last")
    else:
        new, keep = cur, cur
    if len(new):
        day = os.path.join(ML_DIR, f"{now:%Y-%m-%d}.csv")
        if os.path.exists(day):
            old_cols = list(pd.read_csv(day, nrows=0).columns)
            if old_cols != ML_COLS:      # the first day's file predates the status column: rewrite it with one
                pd.read_csv(day).reindex(columns=ML_COLS).fillna({"status": "ok"}).to_csv(day, index=False)
        new.to_csv(day, mode="a", header=not os.path.exists(day), index=False)
    keep.to_csv(last_path, index=False)
    return len(new)


def _plays_and_log(f: pd.DataFrame, lines: pd.DataFrame, live: bool = True) -> pd.DataFrame:
    if live:
        try:
            log_moneylines(lines)
        except Exception as e:   # never affects the card
            print(f"Moneyline log failed ({e}); continuing.")
    return _plays(f, lines, live)


if __name__ == "__main__":
    run_day.plays = _plays_and_log      # only the card run logs moneylines (not tests or other importers)
    run_day.main()
