"""Part D2: stage 1 re-run for 2013-2026 under each one-at-a-time parameter variant (LOG.md). Resumable.

    python -m research.originator.d2_stage1_grid
"""
from __future__ import annotations

import dataclasses
import os

import pandas as pd

from cbb import backtest, data, ratings

OUT = os.path.join(os.path.dirname(__file__), "out")
VARIANTS = {"hl60": {"half_life": 60.0}, "hl240": {"half_life": 240.0}, "prior3": {"prior_games": 3.0},
            "prior12": {"prior_games": 12.0}, "luck20": {"luck": 0.20}, "luck50": {"luck": 0.50}}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    frozen_luck = data.THREE_LUCK
    for tag, kw in VARIANTS.items():
        path = os.path.join(OUT, f"stage1_{tag}.csv")
        if os.path.exists(path):
            continue
        cfg = dataclasses.replace(ratings.RatingConfig(), **{k: v for k, v in kw.items() if k != "luck"})
        data.THREE_LUCK = kw.get("luck", frozen_luck)
        try:
            parts = [backtest.season(s, cfg) for s in range(2013, 2027)]
        finally:
            data.THREE_LUCK = frozen_luck
        pd.concat(parts).to_csv(path, index=False)
        print(tag, "done", flush=True)


if __name__ == "__main__":
    main()
