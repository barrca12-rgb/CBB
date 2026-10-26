"""Validation output for the two proposed (not applied) production fixes in audit/patches/:

  referee_fix.diff          evaluate.py: opener-time evaluation predicts totals with crew inputs at 0 (crews are not
                            posted when openers are); the walk-forward weights are fit exactly as before
  opener_cleaning_fix.diff  lines_hist.py: no close-based correction of openers; drop-only plausibility rule
                            (spreads within +-60, totals within 100-200)

Prints production numbers before and after each fix, against the opener, on the production model. Read-only.

    python -m audit.b6_fix_validation
"""
from __future__ import annotations

import os

import pandas as pd

from audit.a2_timing import score
from audit.b1_live_approx import walk_forward_split
from audit.b2_opener_cleaning import apply, raw_openers
from audit.common import OUT, frame
from cbb import evaluate, projection

if __name__ == "__main__":
    base = frame(tag="base")
    path = os.path.join(OUT, "wf_refs_zero_at_open.pkl")
    if os.path.exists(path):
        rz = pd.read_pickle(path)
    else:
        old = evaluate.OUT_DIR
        evaluate.OUT_DIR = os.path.join(OUT, "_stage1_base")
        try:
            train = projection.add_features(evaluate.load(2013, 2026))
        finally:
            evaluate.OUT_DIR = old
        rz = walk_forward_split(train, train.assign(ref_fouls=0.0, ref_pts=0.0))
        rz.to_pickle(path)
    raw = raw_openers(sorted(base["season"].unique()))
    clean, _, _ = apply(base, raw, "A_range", None)
    rows = (score(base, "production (before)") + score(rz, "referee fix: crews 0 at open") +
            score(clean, "opener-cleaning fix: no close rule, range rule only"))
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "fix_validation.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.to_string(index=False))
