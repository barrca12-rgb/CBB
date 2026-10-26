"""Audit follow-up, item 4: a controlled baseline comparison.

Every source uses the same information cutoff (nothing from the game day or the day before):
  stage-1 only   ratings from games before D-1 (audit/stage1_lag.py), no stage 2
  KenPom         KenPom-method line from KenPom's archive dated D-1 (ratings through games of D-2)
  Barttorvik     Barttorvik file before D-1, with the same home-court rule as the KenPom method (home efficiency
                 x1.02, away x0.98 at non-neutral sites; the original audit's Barttorvik line had no home edge)
  market         ratings fit to consensus closes of games before D-1 (spreads only: the market total is stored as a
                 deviation, not a full total)
  final model    the conservative variant (audit/a2_timing.py 'safe_lag1')
Accuracy is on one common game universe (every source present); betting uses the predeclared rule (spread 2.5+,
total 3+ vs the consensus opener) on that same universe, with coverage and overlap shown. Read-only.

    python -m audit.b4_baselines_fair
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.a2_timing import _cached_snapshot
from audit.b2_opener_cleaning import mkt_lagged
from audit.common import OUT, bets, frame, record
from cbb import barttorvik

DAY = pd.Timedelta(days=1)


def bt_hca(games: pd.DataFrame) -> pd.DataFrame:
    out = []
    for day, g in games.groupby("date"):
        t = None
        for k in range(2, 9):           # file dated D-2 or earlier (cached files only)
            t = _cached_snapshot(day - pd.Timedelta(days=k))
            if t is not None:
                break
        if t is None:
            continue
        t = t.dropna(subset=["espn_id"]).drop_duplicates("espn_id").set_index("espn_id")
        avg_e, avg_t = t["adj_oe"].mean(), t["adj_tempo"].mean()
        h, a = t.reindex(g["home_id"].to_numpy()), t.reindex(g["away_id"].to_numpy())
        hca = np.where(g["neutral"].astype(bool).to_numpy(), 0.0, 0.02)
        poss = h["adj_tempo"].to_numpy() * a["adj_tempo"].to_numpy() / avg_t
        hp = poss * h["adj_oe"].to_numpy() * a["adj_de"].to_numpy() / avg_e / 100 * (1 + hca)
        ap = poss * a["adj_oe"].to_numpy() * h["adj_de"].to_numpy() / avg_e / 100 * (1 - hca)
        out.append(pd.DataFrame({"game_id": g["game_id"].to_numpy(), "bth_margin": hp - ap, "bth_total": hp + ap}))
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    w = frame(tag="safe_lag1")             # kp_* here = KenPom archive D-1; pred_* = stage-1 lag 1
    path = os.path.join(OUT, "bt_hca_lag.pkl")
    bt = pd.read_pickle(path) if os.path.exists(path) else bt_hca(w[["game_id", "date", "home_id", "away_id", "neutral"]])
    bt.to_pickle(path)
    mkt = mkt_lagged(w).rename(columns={"mkt_margin": "mkt_line_margin"})
    d = w.merge(bt, on="game_id", how="left").merge(mkt[["game_id", "mkt_line_margin", "mkt_n"]].rename(columns={"mkt_n": "mkt_n_lag"}), on="game_id", how="left")
    kp_ok = d["kp_margin"] != d["pred_margin"]          # kp fell back to stage 1 where KenPom's archive was missing
    d["mkt_ok"] = d["mkt_n_lag"] >= 10
    src = {"final model": ("final_margin", "final_total"), "stage-1 only": ("pred_margin", "pred_total"),
           "KenPom": ("kp_margin", "kp_total"), "Barttorvik (home edge added)": ("bth_margin", "bth_total"),
           "market ratings": ("mkt_line_margin", None)}
    common = d[kp_ok & d["bth_margin"].notna() & d["mkt_ok"] & (d["season"] >= 2015)]
    print(f"games 2015-2026: {int((d['season'] >= 2015).sum())}; with KenPom archive {int((kp_ok & (d['season'] >= 2015)).sum())}, "
          f"Barttorvik {int((d['bth_margin'].notna() & (d['season'] >= 2015)).sum())}, market (10+ lined games each) "
          f"{int((d['mkt_ok'] & (d['season'] >= 2015)).sum())}; common universe {len(common)}")
    rows = []
    for name, (mc, tc) in src.items():
        rows.append({"source": name, "games": len(common), "margin MAE": round((common[mc] - common["margin"]).abs().mean(), 3),
                     "total MAE": round((common[tc] - common["points"]).abs().mean(), 3) if tc else None})
    cl = common.dropna(subset=["home_spread", "total"])
    rows.append({"source": "closing line (reference)", "games": len(cl), "margin MAE": round((-cl["home_spread"] - cl["margin"]).abs().mean(), 3),
                 "total MAE": round((cl["total"] - cl["points"]).abs().mean(), 3)})
    print("\nAccuracy on the common universe\n" + pd.DataFrame(rows).to_string(index=False))
    rows = []
    for mk, thr in (("spread", 2.5), ("total", 3.0)):
        for ss in ((2015, 2017), (2024, 2026)):
            fin = bets(common, mk, "open", thr, ss)
            fin_ids = set(fin["game_id"])
            for name, (mc, tc) in src.items():
                if mk == "total" and tc is None:
                    continue
                b = bets(common, mk, "open", thr, ss, margin_col=mc, total_col=tc or "final_total")
                r = record(b)
                same_side = b.merge(fin[["game_id", "side"]], on="game_id", suffixes=("", "_f"))
                rows.append({"market": mk, "seasons": f"{ss[0]}-{ss[1]}", "source": name, "selections": r["plays"],
                             "W": r["W"], "L": r["L"], "P": r["P"], "win%": round(r["win%"], 2), "ROI%@-110 (assumed)": r["ROI%"],
                             "mean line value": round(b["clv"].mean(), 2),
                             "overlap with final model": f"{len(same_side)} games ({int((same_side['side'] == same_side['side_f']).sum())} same side)"})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "baselines_fair.csv"), index=False)
    print("\nBetting on the common universe (same rule, same openers)\n" + t.to_string(index=False))
