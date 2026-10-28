"""E2 prospective test (research/quant/LOG.md): 2026-27 totals with a neutral-site term, scored after the fact from
files the live card already writes. Nothing runs live; nothing here touches the card.

  freeze   fit E2 (frozen total features + neutral + conf_game) on 2013-2026 and write out/e2_coefficients.json
           (done once, Oct 28, 2026, before the season; never refit during the test)
  score    for every reports/features_<date>.csv of 2026-27 with a final score: v1 total (final_total as the card
           computed it) vs E2 total from the frozen coefficients; MAE overall and on neutral-site games, and
           opener totals win% at the fixed 3-point threshold using the card's open_total (reports/cbb_<date>.csv)

    python -m research.quant.e2_shadow freeze
    python -m research.quant.e2_shadow score
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import ridge_w
from research.quant.common import OUT, base_frames, boot

COEF = os.path.join(OUT, "e2_coefficients.json")
FEATS = projection.TOTAL_FEATURES + ["neutral", "conf_game"]
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def freeze() -> None:
    train, _ = base_frames()
    t = train[train["season"].between(2013, 2026)].copy()
    t["neutral"], t["conf_game"] = t["neutral"].astype(float), t["conf_game"].astype(float)
    c = ridge_w(t[FEATS].to_numpy(float), t["points"].to_numpy(float), np.ones(len(t)))
    json.dump({"fitted_on": [2013, 2026], "frozen": "2026-10-28", "intercept": float(c[0]),
               **{k: float(v) for k, v in zip(FEATS, c[1:])}}, open(COEF, "w"), indent=1)
    print(open(COEF).read())


def score() -> None:
    c = json.load(open(COEF))
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "reports", "features_2026-1*.csv")) +
                    glob.glob(os.path.join(ROOT, "reports", "features_2027-*.csv"))):
        d = pd.read_csv(f)
        day = os.path.basename(f)[9:19]
        card = os.path.join(ROOT, "reports", f"cbb_{day}.csv")
        if os.path.exists(card):
            k = pd.read_csv(card)[["game_id", "open_total", "conf_game"] if "conf_game" in pd.read_csv(card, nrows=0) else ["game_id", "open_total"]]
            d = d.merge(k, on="game_id", how="left")
        if "conf_game" not in d:
            d["conf_game"] = np.nan          # filled below from the schedule if the card did not carry it
        rows.append(d)
    if not rows:
        print("no 2026-27 feature files yet")
        return
    d = pd.concat(rows, ignore_index=True)
    d = d[d["state"].eq("post") & d["home_score"].notna()].drop_duplicates("game_id", keep="last")
    if d["conf_game"].isna().any():
        from cbb import data
        g, _ = data.season_games(2027)
        d["conf_game"] = d["conf_game"].fillna(d["game_id"].map(g.set_index("game_id")["conf_game"]))
    d["neutral"] = d["neutral"].astype(float)
    d["conf_game"] = d["conf_game"].astype(float).fillna(0.0)
    d["e2_total"] = c["intercept"] + sum(d[k].astype(float) * v for k, v in c.items() if k in FEATS)
    d["points"] = d["home_score"] + d["away_score"]
    d["gain"] = (d["points"] - d["final_total"]).abs() - (d["points"] - d["e2_total"]).abs()
    L = [f"2026-27 games scored: {len(d)}"]
    for name, m in (("all", d.index == d.index), ("neutral site", d["neutral"] == 1)):
        x = d[m]
        if len(x):
            g, lo, hi = boot(x["gain"], x["date"])
            L.append(f"{name}: n {len(x)}, MAE v1 {(x['points'] - x['final_total']).abs().mean():.3f}, "
                     f"E2 {(x['points'] - x['e2_total']).abs().mean():.3f}, gain {g:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    for tag, col in (("v1", "final_total"), ("E2", "e2_total")):
        x = d.dropna(subset=["open_total"])
        e = x[col] - x["open_total"]
        p = x[e.abs() >= 3]
        cov = np.sign(e[e.abs() >= 3]) * (p["points"] - p["open_total"])
        win = cov[cov != 0] > 0
        L.append(f"opener totals, edge 3+, {tag}: {len(win)} plays, win% {100 * win.mean():.1f}" if len(win) else f"{tag}: no plays")
    print("\n".join(L))


if __name__ == "__main__":
    {"freeze": freeze, "score": score}[sys.argv[1]]()
