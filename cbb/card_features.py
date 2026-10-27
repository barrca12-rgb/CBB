"""Runs the card exactly as `python -m cbb.run_day` does, and also saves each built day's stage-2 inputs to
reports/features_<date>.csv for the ridge-1,000 shadow (cbb/shadow_r1000.py). Nothing the card computes, picks,
logs or posts changes: projection.apply_saved is wrapped only to copy its output, and a failure to save is printed
and ignored. Used by .github/workflows/update.yml in place of `python -m cbb.run_day` (same arguments).

    python -m cbb.card_features --auto | --date YYYY-MM-DD
"""
from __future__ import annotations

import os

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

if __name__ == "__main__":
    run_day.main()
