"""Audit step 2: information timing. Rebuild the stage-2 projection with inputs restricted to what was public at an
earlier cutoff, then re-score the opener plays. Production code and outputs are untouched.

Variants (each changes only the named inputs, then refits the walk-forward stage 2 on the changed features):
  base        production inputs
  no_refs     referee crews removed (crews are assigned/published around game day, after most openers)
  kp_prev     KenPom from its archive of the day before (ratings through D-2) instead of game-day FanMatch
  bt_prev     Barttorvik file one day earlier
  mkt_prev    market ratings from closes before D-1
  safe        all four together (stage-1 ratings unchanged: games before D)
  safe_lag1   'safe' plus stage-1 ratings from games before D-1 (audit/stage1_lag.py)

    python -m audit.a2_timing
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import OUT, bets, frame, record
from cbb import barttorvik, context, kenpom

DAY = pd.Timedelta(days=1)


def no_refs(b):
    return b.assign(ref_fouls=0.0, ref_pts=0.0)


def kp_prev(b):
    rows = []
    for day, g in b.groupby("date"):
        try:
            r = kenpom.archive((day - DAY).strftime("%Y-%m-%d"))
        except Exception:
            continue
        rows.append(kenpom._predict(r, g[["game_id", "home_id", "away_id", "neutral"]]))
    k = pd.concat(rows).set_index("game_id")
    b = b.copy()
    b["kp_margin"] = b["game_id"].map(k["kp_margin"]).fillna(b["pred_margin"])
    b["kp_total"] = b["game_id"].map(k["kp_total"]).fillna(b["pred_total"])
    b["kp_margin_x_early"] = b["kp_margin"] * b["early"]
    b["kp_total_x_early"] = b["kp_total"] * b["early"]
    return b


def _cached_snapshot(day):
    """Cached files only (no downloads during the audit); a missing day falls back to earlier ones in before()."""
    path = os.path.join(barttorvik.CACHE, pd.Timestamp(day).strftime("%Y%m%d") + ".parquet")
    if not os.path.exists(path):
        return None
    t = pd.read_parquet(path)
    return t if len(t) else None


def bt_prev(b):
    orig_before, orig_snap = barttorvik.before, barttorvik.snapshot
    barttorvik.snapshot = _cached_snapshot
    barttorvik.before = lambda day: orig_before(pd.Timestamp(day) - DAY)
    try:
        bt = barttorvik.predict(b[["game_id", "date", "home_id", "away_id", "neutral"]])
    finally:
        barttorvik.before, barttorvik.snapshot = orig_before, orig_snap
    b = b.drop(columns=["bt_margin", "bt_total"]).merge(bt, on="game_id", how="left")
    b["bt_margin"] = b["bt_margin"].fillna(b["kp_margin"])
    b["bt_total"] = b["bt_total"].fillna(b["kp_total"])
    return b


def mkt_prev(b):
    keys = b[["game_id", "season", "date", "home_id", "away_id", "neutral"]].assign(date=lambda d: d["date"] - DAY)
    ctx = context.market(keys, context.backtest_closes(sorted(b["season"].unique()))).set_index("game_id")
    w = np.minimum(b["game_id"].map(ctx["mkt_n"]).fillna(0) / 10, 1)
    return b.assign(mkt_m=b["game_id"].map(ctx["mkt_margin"]).fillna(0) * w,
                    mkt_t=b["game_id"].map(ctx["mkt_total"]).fillna(0) * w)


def safe(b):
    return mkt_prev(bt_prev(kp_prev(no_refs(b))))


VARIANTS = {"base": (None, None), "no_refs": (None, no_refs), "kp_prev": (None, kp_prev), "bt_prev": (None, bt_prev),
            "mkt_prev": (None, mkt_prev), "safe": (None, safe),
            "safe_lag1": (os.path.join(OUT, "backtest_lag1_2013_2026.csv"), safe)}


def score(w, tag):
    out = []
    for mk, thr in (("spread", 2.5), ("total", 3.0)):
        for ss in ((2015, 2017), (2024, 2026)):
            b = bets(w, mk, "open", thr, ss)
            r = record(b)
            out.append({"variant": tag, "market": mk, "seasons": f"{ss[0]}-{ss[1]}", "plays": r["plays"],
                        "win%": round(r["win%"], 2), "ROI%@-110": r["ROI%"], "mean move our way": round(b["clv"].mean(), 2),
                        "same plays win% at close": round(record(b, "res_at_close")["win%"], 2)})
    return out


if __name__ == "__main__":
    import sys
    want = sys.argv[1:] or list(VARIANTS)
    rows = []
    for tag in want:
        stage1, fn = VARIANTS[tag]
        if stage1 and not os.path.exists(stage1):
            print("skip", tag, "(stage-1 file missing)")
            continue
        kw = {"stage1": stage1} if stage1 else {}
        w = frame(tag=tag, features=fn, **kw)
        rows += score(w, tag)
        print(tag, "done", flush=True)
    t = pd.DataFrame(rows)
    path = os.path.join(OUT, "timing_variants.csv")
    if os.path.exists(path):
        t = pd.concat([pd.read_csv(path), t]).drop_duplicates(["variant", "market", "seasons"], keep="last")
    t.to_csv(path, index=False)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
