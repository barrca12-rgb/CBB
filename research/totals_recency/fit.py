"""Live totals weights with recency (PLAN.md; shipped Nov 9): the live stage-2 fit (projection.fit's frame, 2013-2026,
penalty 1) with each game weighted 0.5^(2026 - season), for the 2026-27 season. Margins untouched. Checks first that
equal weights reproduce data/projection.json's totals exactly, then writes the new totals block.

    python -m research.totals_recency.fit
"""
import json
import numpy as np
from cbb import projection
from research.originator.d_common import frames
from research.r1000w.backtest import wridge

H, NEXT = 1.0, 2027


def main():
    train, _ = frames()
    b = train[train["season"].between(2013, 2026)]
    X, y = b[projection.TOTAL_FEATURES].to_numpy(float), (b["home_pts"] + b["away_pts"]).to_numpy(float)
    live = json.load(open(projection.SAVED))
    keys = ["intercept"] + projection.TOTAL_FEATURES
    c0 = wridge(X, y, np.ones(len(b)), 1.0)
    d = max(abs(c0[i] - live["total"][k]) for i, k in enumerate(keys))
    assert d < 1e-6, f"equal weights do not reproduce the live totals (max diff {d})"
    w = 0.5 ** ((NEXT - 1 - b["season"].to_numpy()) / H)
    c1 = wridge(X, y, w / w.mean(), 1.0)
    live["total"] = dict(zip(keys, map(float, c1)))
    live["total_recency"] = {"half_life_seasons": H, "fit_for": NEXT, "note": "research/totals_recency"}
    json.dump(live, open(projection.SAVED, "w"), indent=1)
    print({k: round(v, 4) for k, v in live["total"].items()})


if __name__ == "__main__":
    main()
