"""Part D2: tier-specific stage-1 parameters (pre-registered in LOG.md). Needs the stage-1 files from
d2_stage1_grid.py.

    python -m research.originator.d2_tiers
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.originator.a_decompose import HIGH, MID
from research.originator.d_common import OUT, ROOT, clv, frames, info_beyond_close, oriented_openers, walk_forward
from research.originator.d2_stage1_grid import VARIANTS

DEV, TEST = range(2014, 2020), range(2020, 2027)


def tiers(w: pd.DataFrame) -> pd.Series:
    t = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    lvl = lambda ids: ids.map(t).map(lambda x: 2 if x in HIGH else (1 if x in MID else 0))
    return pd.Series(np.minimum(lvl(w["home_id"]), lvl(w["away_id"])), index=w.index).map({2: "high", 1: "mid", 0: "low"})


def main() -> None:
    fits = {"frozen": walk_forward(*frames())}
    for tag in VARIANTS:
        fits[tag] = walk_forward(*frames(os.path.join(OUT, f"stage1_{tag}.csv"), tag))
        print(tag, "fitted", flush=True)
    base = fits["frozen"]
    base = base.assign(tier=tiers(base))
    rows = []
    for tag, w in fits.items():
        d = base[["game_id", "season", "tier", "home_pts", "away_pts", "home_spread"]].merge(w[["game_id", "final_margin"]], on="game_id")
        d["err"] = (d["home_pts"] - d["away_pts"] - d["final_margin"]).abs()
        d["line_err"] = (d["home_pts"] - d["away_pts"] + d["home_spread"]).abs()
        for tr in ("high", "mid", "low"):
            for era, ss in (("dev 2014-19", DEV), ("test 2020-26", TEST)):
                x = d[(d["tier"] == tr) & d["season"].isin(list(ss))]
                rows.append({"variant": tag, "tier": tr, "era": era, "games": len(x), "margin MAE": x["err"].mean(),
                             "line MAE": x.dropna(subset=["home_spread"])["line_err"].mean()})
    t = pd.DataFrame(rows)
    dev = t[t["era"] == "dev 2014-19"]
    choice = dev.loc[dev.groupby("tier")["margin MAE"].idxmin(), ["tier", "variant"]].set_index("tier")["variant"].to_dict()
    # the tier-specific model: each game's numbers from the variant chosen for its tier on 2014-2019
    combo = base[["game_id", "tier"]].copy()
    parts = []
    for tr, tag in choice.items():
        ids = combo.loc[combo["tier"] == tr, "game_id"]
        parts.append(fits[tag][fits[tag]["game_id"].isin(ids)])
    cw = pd.concat(parts)
    cw = base.drop(columns=["final_margin", "final_total"]).merge(cw[["game_id", "final_margin", "final_total"]], on="game_id")
    d = cw.assign(err=(cw["home_pts"] - cw["away_pts"] - cw["final_margin"]).abs())
    res = []
    for tr in ("high", "mid", "low"):
        x = d[(d["tier"] == tr) & d["season"].isin(list(TEST))]
        f = t[(t["variant"] == "frozen") & (t["tier"] == tr) & (t["era"] == "test 2020-26")].iloc[0]
        res.append({"tier": tr, "variant chosen on 2014-19": choice[tr], "test games": len(x),
                    "tier-specific MAE": x["err"].mean(), "frozen MAE": f["margin MAE"], "line MAE": f["line MAE"],
                    "gain vs frozen": f["margin MAE"] - x["err"].mean()})
    r = pd.DataFrame(res)
    low_gain = float(r.loc[r["tier"] == "low", "gain vs frozen"].iloc[0])
    cl = {era: (clv(oriented_openers(cw), ss)["combined CLV"], clv(oriented_openers(base), ss)["combined CLV"])
          for era, ss in (("dev 2014-17", range(2014, 2018)), ("confirm 2024-26", range(2024, 2027)))}
    info = info_beyond_close(cw, base, TEST)
    t.to_csv(os.path.join(OUT, "d2_tier_mae.csv"), index=False)
    r.to_csv(os.path.join(OUT, "d2_result.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(3).to_string(index=False))
    print(r.round(4).to_string(index=False))
    print("opener CLV (tier-specific vs frozen):", {k: (round(a, 3), round(b, 3)) for k, (a, b) in cl.items()})
    print("information beyond the close (2020-26):", info)
    print("KILL (low-major gain < 0.03):", low_gain < 0.03)


if __name__ == "__main__":
    main()
