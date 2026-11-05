"""Totals: tracking the season's scoring level (PLAN.md, pre-registered Nov 5, 2026). Research only.

    python -m research.totals_level.backtest     # -> out/results.txt, out/accuracy.csv, out/plays.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.a2_timing import score
from audit.common import frame

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
STAGE1 = os.path.join(HERE, "..", "own_ratings", "out", "stage1_base.csv")
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def recent_miss(w: pd.DataFrame, days: int, min_games: int = 50) -> pd.Series:
    """Per game: mean (actual - model total) over the same season's games in the previous `days` days (0 if fewer
    than min_games)."""
    d = w[["season", "date", "points", "final_total"]].copy()
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d["r"] = d["points"] - d["final_total"]
    daily = d.groupby(["season", "date"])["r"].agg(["sum", "count"]).reset_index()
    out = {}
    for s, x in daily.groupby("season"):
        x = x.set_index("date").sort_index()
        full = x.reindex(pd.date_range(x.index.min(), x.index.max())).fillna(0)
        cs, cc = full["sum"].cumsum(), full["count"].cumsum()
        for day in x.index:
            hi, lo = day - pd.Timedelta(days=1), day - pd.Timedelta(days=days + 1)
            ssum = cs.get(hi, 0.0) - (cs.get(lo, 0.0) if lo in cs.index else 0.0)
            scnt = cc.get(hi, 0.0) - (cc.get(lo, 0.0) if lo in cc.index else 0.0)
            out[(s, day)] = ssum / scnt if scnt >= min_games else 0.0
    key = list(zip(w["season"], pd.to_datetime(w["date"]).dt.normalize()))
    return pd.Series([out.get(k, 0.0) for k in key], index=w.index)


def smooth_env(b: pd.DataFrame, k: float = 400.0) -> pd.DataFrame:
    """T2: season_avg_total shrunk toward last season's average with k games, from earlier dates only."""
    b = b.copy()
    b["_d"] = pd.to_datetime(b["date"]).dt.normalize()
    pts = b["home_pts"] + b["away_pts"]
    prev = pts.groupby(b["season"]).mean().shift()
    daily = pd.DataFrame({"season": b["season"], "_d": b["_d"], "p": pts}).groupby(["season", "_d"])["p"].agg(["sum", "count"])
    daily = daily.groupby(level=0).cumsum().groupby(level=0).shift().fillna(0)          # totals before each date
    j = b[["season", "_d"]].join(daily, on=["season", "_d"])
    last = b["season"].map(prev).fillna(pts.mean())
    b["season_avg_total"] = (last * k + j["sum"]) / (k + j["count"])
    return b.drop(columns="_d")


def acc(w: pd.DataFrame, tag: str, col: str = "final_total") -> list[dict]:
    w = w[w["season"] >= 2015].copy()
    dt = pd.to_datetime(w["date"])
    w["day"] = (dt - dt.groupby(w["season"]).transform("min")).dt.days
    rows = []
    for lab, x in (("days 0-20", w[w["day"] <= 20]), ("days 21-60", w[(w["day"] > 20) & (w["day"] <= 60)]), ("all", w)):
        e = x[col] - x["points"]
        rows.append({"variant": tag, "part": lab, "games": len(x), "total MAE": round(float(e.abs().mean()), 3),
                     "bias": round(float(e.mean()), 2)})
    return rows


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    base = frame(stage1=STAGE1, tag="own_base")
    variants = {"T0 base": base}
    for k, days in ((0.5, 7), (0.25, 7), (1.0, 7), (0.5, 14)):
        w = base.copy()
        w["final_total"] = w["final_total"] + k * recent_miss(base, days)
        variants[f"T1 k={k} {days}d" + (" (primary)" if (k, days) == (0.5, 7) else "")] = w
    variants["T2 smooth environment"] = frame(stage1=STAGE1, tag="tl_T2", features=smooth_env)
    a, p = [], []
    for tag, w in variants.items():
        a += acc(w, tag)
        p += [r for r in score(w[w["season"] >= 2015], tag) if r["market"] == "total"]
    A, P = pd.DataFrame(a), pd.DataFrame(p)
    pd.set_option("display.width", 250)
    say("Totals scoring level (PLAN.md). Final total average miss and bias (model - actual), 2015-2026:")
    say(A.to_string(index=False))
    say("\nOpener totals at 3+ (assumed -110):")
    say(P.to_string(index=False))
    say("\nProposal rule:")
    b0 = A[A["variant"] == "T0 base"].set_index("part")["total MAE"]
    pb = P[P["variant"] == "T0 base"].set_index("seasons")["win%"]
    for tag in ("T1 k=0.5 7d (primary)", "T2 smooth environment"):
        m = A[A["variant"] == tag].set_index("part")["total MAE"]
        pw = P[P["variant"] == tag].set_index("seasons")["win%"]
        c1 = m["days 0-20"] < b0["days 0-20"] and m["all"] < b0["all"]
        c2 = all(pw[s] >= pb[s] - 0.3 for s in pb.index)
        c3 = any(pw[s] > pb[s] for s in pb.index)
        say(f"  {tag}: misses lower {c1}; win % within 0.3 {c2}; higher somewhere {c3} -> "
            f"{'PASS' if c1 and c2 and c3 else 'no'}")
    A.to_csv(os.path.join(OUT, "accuracy.csv"), index=False)
    P.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
