"""Audit follow-up, item 2: the conservative variant ('safe_lag1', audit/a2_timing.py) with Barttorvik removed
entirely: KenPom-only preseason prior in stage 1 (audit/b3_stage1_lag1_kenpom_prior.py) and the Barttorvik inputs
set to zero in stage 2 (constant, so the ridge gives them no weight). Read-only.

    python -m audit.b3_no_barttorvik
"""
from __future__ import annotations

import os

import pandas as pd

from audit.a2_timing import safe, score
from audit.common import OUT, frame

STAGE1 = os.path.join(OUT, "backtest_lag1_kpprior_2013_2026.csv")


def safe_no_bt(b):
    return safe(b).assign(bt_margin=0.0, bt_total=0.0)


if __name__ == "__main__":
    w = frame(stage1=STAGE1, tag="safe_lag1_nobt", features=safe_no_bt)
    rows = score(frame(tag="safe_lag1"), "safe_lag1") + score(w, "safe_lag1_nobt")
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "no_barttorvik.csv"), index=False)
    pd.set_option("display.width", 200)
    print(t.to_string(index=False))
