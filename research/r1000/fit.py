"""Ridge-1,000 shadow coefficients (research/r1000/PLAN.md): the live stage-2 fit (cbb/projection.fit: every season
2013-2026, same inputs, same frame) with ridge penalty 1,000 instead of 1. Writes data/shadow_r1000.json; the live
data/projection.json is untouched. With penalty 1 this reproduces data/projection.json exactly (checked: max
difference 0.0).

    python -m research.r1000.fit
"""
from __future__ import annotations

import json
import os

import numpy as np

from cbb import projection
from research.originator.d_common import frames

LAM = 1000.0
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "shadow_r1000.json")


def ridge(X, y, lam):
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0
    return np.linalg.solve(X1.T @ X1 + np.diag(pen), X1.T @ y)


def main() -> None:
    train, _ = frames()
    b = train[train["season"].between(2013, 2026)]
    live = json.load(open(projection.SAVED))
    for lam, check in ((1.0, True), (LAM, False)):
        cm = ridge(b[projection.MARGIN_FEATURES].to_numpy(float), (b["home_pts"] - b["away_pts"]).to_numpy(float), lam)
        ct = ridge(b[projection.TOTAL_FEATURES].to_numpy(float), (b["home_pts"] + b["away_pts"]).to_numpy(float), lam)
        if check:
            d = max(abs(cm[i] - live["margin"][k]) for i, k in enumerate(["intercept"] + projection.MARGIN_FEATURES))
            d = max(d, max(abs(ct[i] - live["total"][k]) for i, k in enumerate(["intercept"] + projection.TOTAL_FEATURES)))
            assert d < 1e-9, f"penalty 1 does not reproduce data/projection.json (max diff {d})"
    out = {"ridge_penalty": LAM, "fitted_on": [2013, 2026], "games": int(len(b)),
           "margin": dict(zip(["intercept"] + projection.MARGIN_FEATURES, map(float, cm))),
           "total": dict(zip(["intercept"] + projection.TOTAL_FEATURES, map(float, ct)))}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
