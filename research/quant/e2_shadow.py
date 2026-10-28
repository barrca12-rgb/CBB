"""E2 prospective test (research/quant/LOG.md): 2026-27 totals with a neutral-site term, scored after the fact from
files the live card already writes. Nothing runs live; nothing here touches the card.

  freeze   fit E2 (frozen total features + neutral + conf_game) on 2013-2026 and write out/e2_coefficients.json
           (done once, Oct 28, 2026, before the season; never refit during the test)
  score    for every 2026-27 game the card priced (reports/features_<date>.csv): v1 total exactly as the card
           computed it (the opening-week shift to KenPom included) vs E2 total from the frozen coefficients under the
           same rule; finals from the ESPN schedule (completed games); MAE overall and on neutral-site games, and opener totals win%
           at the fixed 3-point threshold using the card's open_total (reports/cbb_<date>.csv). Writes
           out/e2_shadow_games.csv

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


def _days() -> list[str]:
    fs = sorted(glob.glob(os.path.join(ROOT, "reports", "features_2026-1*.csv")) +
                glob.glob(os.path.join(ROOT, "reports", "features_2027-0*.csv")))
    return [os.path.basename(f)[9:19] for f in fs]


def build() -> pd.DataFrame:
    """Every 2026-27 game the card priced: v1 total exactly as the card computed it (opening-week shift included),
    E2 total from the frozen coefficients with the same rule, the card's opener, and the final score."""
    from cbb import data
    c = json.load(open(COEF))
    sch = data.fetch("schedule", 2027, refresh=True)
    conf = sch.drop_duplicates("game_id").set_index("game_id")["conference_competition"].astype(float)
    fin = sch[sch["status_type_completed"].fillna(False).astype(bool)].drop_duplicates("game_id")
    res = fin.set_index("game_id")[["home_id", "home_score", "away_score"]].rename(
        columns={"home_score": "home_pts", "away_score": "away_pts"})
    rows = []
    for day in _days():
        d = pd.read_csv(os.path.join(ROOT, "reports", f"features_{day}.csv"))
        card = pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{day}.csv"))
        d = d.merge(card[["game_id", "open_total", "total_shift"]], on="game_id", how="left")
        d["neutral"] = d["neutral"].astype(float)
        d["conf_game"] = d["game_id"].map(conf).fillna(0.0)
        d["e2_pre"] = c["intercept"] + sum(d[k].astype(float) * v for k, v in c.items() if k in FEATS)
        d["v1_total"], d["e2_total"] = d["final_total"], d["e2_pre"]
        if d["total_shift"].fillna(0).abs().max() > 0:          # opening week: run_day.opening_week_totals
            d["v1_total"] = d["final_total"] - (d["final_total"] - d["kp_total"]).mean()
            d["e2_total"] = d["e2_pre"] - (d["e2_pre"] - d["kp_total"]).mean()
        d["day"] = day
        rows.append(d)
    d = pd.concat(rows, ignore_index=True).drop_duplicates("game_id", keep="last")
    d = d.join(res, on="game_id", rsuffix="_res")
    d["points"] = pd.to_numeric(d["home_pts"], errors="coerce") + pd.to_numeric(d["away_pts"], errors="coerce")
    return d


def score() -> None:
    if not _days():
        print("no 2026-27 feature files yet")
        return
    d = build()
    d.to_csv(os.path.join(OUT, "e2_shadow_games.csv"), index=False)
    done = d.dropna(subset=["points"])
    L = [f"2026-27 games priced: {len(d)}; final: {len(done)} (neutral site {int((done['neutral'] == 1).sum())})"]
    if not len(done):
        print("\n".join(L))
        return
    done = done.assign(gain=(done["points"] - done["v1_total"]).abs() - (done["points"] - done["e2_total"]).abs())
    res = {}
    for name, m in (("all games", done.index == done.index), ("neutral site", done["neutral"] == 1)):
        x = done[m]
        if len(x) >= 2:
            g, lo, hi = boot(x["gain"], x["day"])
            res[name] = (g, lo, hi)
            L.append(f"{name}: n {len(x)}, MAE v1 {(x['points'] - x['v1_total']).abs().mean():.3f}, "
                     f"E2 {(x['points'] - x['e2_total']).abs().mean():.3f}, gain {g:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    win = {}
    for tag, col in (("v1", "v1_total"), ("E2", "e2_total")):
        x = done.dropna(subset=["open_total"])
        e = x[col] - x["open_total"]
        p = x[e.abs() >= 3]
        cov = np.sign(e[e.abs() >= 3]) * (p["points"] - p["open_total"])
        w = cov[cov != 0] > 0
        win[tag] = 100 * w.mean() if len(w) else np.nan
        L.append(f"opener totals, edge 3+, {tag}: {len(w)} plays, win% {win[tag]:.1f}" if len(w) else f"opener totals, {tag}: no plays")
    if "neutral site" in res and "all games" in res:
        ok = res["neutral site"][1] > 0 and res["all games"][0] >= 0 and not (win["E2"] < win["v1"])
        L.append(f"Pre-registered rule (applies at the March 14 read): {'PASS so far' if ok else 'not passing so far'}")
    print("\n".join(L))


if __name__ == "__main__":
    {"freeze": freeze, "score": score}[sys.argv[1]]()
