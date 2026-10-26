"""Idea 2: where the opener edge concentrates (specification in LOG.md, fixed before running).

    python -m research.edges.e2_segments
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.edges.common import OUT, ROOT, frame, opener_plays, record

POWER = {"ACC", "B10", "B12", "BE", "SEC", "P12"}


def segments(p: pd.DataFrame) -> pd.DataFrame:
    t = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    pw = p["home_id"].map(t).isin(POWER).astype(int) + p["away_id"].map(t).isin(POWER).astype(int)
    mon = pd.to_datetime(p["date"]).dt.month
    out = pd.DataFrame(index=p.index)
    out["month"] = np.select([mon == 11, mon == 12, mon == 1, mon == 2], ["Nov", "Dec", "Jan", "Feb"], "Mar+")
    out["conference tier"] = pw.map({2: "two power teams", 1: "one power team", 0: "no power team"})
    sz = p["open_home_spread"].abs()
    out["opening spread size"] = pd.cut(sz, [-0.1, 4.75, 9.75, 14.75, 99], labels=["0-4.5", "5-9.5", "10-14.5", "15+"]).astype(str)
    out["opening total"] = pd.cut(p["open_total"], [0, 134.75, 144.75, 154.75, 999], labels=["<135", "135-144.5", "145-154.5", "155+"]).astype(str)
    out["site"] = np.where(p["neutral"].astype(bool), "neutral", "home court")
    fav_home = p["open_home_spread"] < 0
    out["side"] = np.where(p["market"] == "spread",
                           np.where((p["side"] == "home") == fav_home, "favourite", "underdog"), p["side"])
    out["edge size"] = np.where(p["market"] == "spread",
                                pd.cut(p["edge"], [0, 3.5, 5, 99], right=False, labels=["2.5-3.5", "3.5-5", "5+"]).astype(str),
                                pd.cut(p["edge"], [0, 4, 6, 99], right=False, labels=["3-4", "4-6", "6+"]).astype(str))
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    p = opener_plays(frame())
    p = p[p["season"].isin([2014, 2015, 2016, 2017, 2024, 2025, 2026])]
    seg = segments(p)
    rows = []
    for mk in ("spread", "total"):
        m = p[p["market"] == mk]
        base = {sp: record(g["res"], g["u"], g["date"]) for sp, g in m.groupby("split")}
        for sp, r in base.items():
            rows.append({"market": mk, "segment": "ALL", "value": "", "split": sp, **r})
        for col in seg.columns:
            if mk == "total" and col == "opening spread size":
                continue
            if mk == "spread" and col == "opening total":
                continue
            for val, g in m.groupby(seg.loc[m.index, col]):
                for sp, gg in g.groupby("split"):
                    r = record(gg["res"], gg["u"], gg["date"])
                    rows.append({"market": mk, "segment": col, "value": val, "split": sp, **r})
    t = pd.DataFrame(rows)
    allw = t[t["segment"] == "ALL"].set_index(["market", "split"])["win%"]
    t["diff vs market"] = t["win%"] - [allw.get((m, s), np.nan) for m, s in zip(t["market"], t["split"])]
    dev = t[(t["split"] == "development") & (t["segment"] != "ALL")]
    flags = dev[(dev["bets"] >= 100) & (dev["diff vs market"].abs() >= 2 * dev["win% se"])]
    tests = int((dev["bets"] >= 100).sum())
    hold = t[t["split"] == "holdout"].set_index(["market", "segment", "value"])
    fl = flags.assign(**{
        "holdout bets": [hold["bets"].get((r.market, r.segment, r.value), np.nan) for r in flags.itertuples()],
        "holdout win%": [hold["win%"].get((r.market, r.segment, r.value), np.nan) for r in flags.itertuples()],
        "holdout diff": [hold["diff vs market"].get((r.market, r.segment, r.value), np.nan) for r in flags.itertuples()],
        "holdout se": [hold["win% se"].get((r.market, r.segment, r.value), np.nan) for r in flags.itertuples()]})
    t.to_csv(os.path.join(OUT, "e2_segments.csv"), index=False)
    fl.to_csv(os.path.join(OUT, "e2_flags.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string(index=False))
    print(f"\nsegments tested (100+ development plays): {tests}; flagged at 2 SE: {len(flags)}; "
          f"expected by chance about {0.046 * tests:.1f}")
    print(fl[["market", "segment", "value", "bets", "win%", "diff vs market", "win% se", "holdout bets", "holdout win%",
              "holdout diff", "holdout se"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
