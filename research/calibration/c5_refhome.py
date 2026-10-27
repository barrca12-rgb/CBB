"""Check 5: referee home bias on margin, close only (LOG.md).

    python -m research.calibration.c5_refhome
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import context, projection
from research.calibration.common import OUT, TEST, base, mae
from research.originator.d_common import frames, walk_forward

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def ref_home(res: pd.DataFrame) -> pd.DataFrame:
    """Per game: crew average of each official's shrunk mean home residual over strictly earlier dates."""
    og = pd.concat([pd.read_parquet(os.path.join(ROOT, "cbb", "cache", f"officials_{s}.parquet"))[["game_id", "official_display_name"]]
                    for s in range(2013, 2027)]).rename(columns={"official_display_name": "official"})
    og = og.merge(res, on="game_id", how="inner").sort_values(["date", "game_id"])
    sums, out = {}, []
    for day, d in og.groupby("date", sort=True):
        v = [sums.get(o, (0.0, 0.0)) for o in d["official"]]
        out.append(d[["game_id"]].assign(x=[s / (n + context.REF_PRIOR) for s, n in v]))
        for o, r in zip(d["official"], d["res"]):
            s, n = sums.get(o, (0.0, 0.0))
            if r == r:
                sums[o] = (s + r, n + 1)
    return pd.concat(out).groupby("game_id")["x"].mean().rename("ref_home").reset_index()


def close_win(w: pd.DataFrame) -> tuple[int, float]:
    d = w[w["season"].isin(TEST) & ~w["swapped"]].dropna(subset=["home_spread"])
    e = d["final_margin"] + d["home_spread"]
    m = ((d["home_pts"] - d["away_pts"] + d["home_spread"]) * np.sign(e))[e.abs() >= 2.5]
    m = m[m != 0]
    return len(m), 100 * float((m > 0).mean())


def main() -> None:
    b = base()
    rh = ref_home(b[["game_id", "date", "res"]].assign(date=pd.to_datetime(b["date"])))
    train, pred = frames()
    tr, pr_ = (x.merge(rh, on="game_id", how="left").fillna({"ref_home": 0.0}) for x in (train, pred))
    print("coverage of ref_home != 0 (2014-26 pred):", round(float((pr_.loc[pr_["season"] >= 2014, "ref_home"] != 0).mean()), 3),
          "SD:", round(float(pr_["ref_home"].std()), 3))
    bench = walk_forward(tr, pr_)
    mf = projection.MARGIN_FEATURES
    try:
        projection.MARGIN_FEATURES = mf + ["ref_home"]
        ch = walk_forward(tr, pr_)
    finally:
        projection.MARGIN_FEATURES = mf
    for x in (bench, ch):
        x["swapped"] = x["game_id"].map(b.set_index("game_id")["swapped"]).fillna(False).astype(bool)
    t0, t1 = bench[bench["season"].isin(TEST)], ch[ch["season"].isin(TEST)]
    m0 = mae(t0["home_pts"] - t0["away_pts"] - t0["final_margin"])
    m1 = mae(t1["home_pts"] - t1["away_pts"] - t1["final_margin"])
    (n0, w0), (n1, w1) = close_win(bench), close_win(ch)
    killed = (m0 - m1 < 0.01) or (abs(w1 - w0) < 0.5)
    res = {"margin MAE 2020-26 benchmark / with ref_home": (round(m0, 4), round(m1, 4)), "MAE gain": round(m0 - m1, 4),
           "close spread plays / win% benchmark": (n0, round(w0, 2)), "close spread plays / win% with ref_home": (n1, round(w1, 2)),
           "verdict": "closed" if killed else "candidate for v3 at March 16"}
    pd.Series(res).to_csv(os.path.join(OUT, "c5_result.csv"))
    for k, v in res.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
