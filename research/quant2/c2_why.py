"""Why does C2 win on totals? Planned ablations, run after the C2 result (logged as such in LOG.md):
  A1  v1's least-squares slopes, intercept moved to the training residuals' median (median-centered OLS)
  A2  how much of the training mean-minus-median gap comes from overtime games
  A3  season by season: v1's mean total residual (bias) next to each version's MAE gain
  A4  share of games finishing over the forecast (a median forecast should be near 50%)
  A5  secondary: does median-centering add to frozen E2 (E2's features, refit walk-forward, never touching E2)?

    python -m research.quant2.c2_why       # -> out/c2_why.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import data, projection
from research.originator.d_common import ridge_w
from research.quant.common import CONF, SEASONS, base_frames, fit_predict, plays
from research.quant2.c2_median import boot_diff, fit_lad
from research.quant2.common import OUT

EVAL = list(range(2020, 2027))


def centered(train, pred, tf):
    """OLS walk-forward for totals with the intercept moved by the training residuals' median."""
    out = pred.copy()
    out["final_total"] = np.nan
    shifts = {}
    for s in SEASONS:
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        ct = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)))
        r = tr["points"].to_numpy(float) - (ct[0] + tr[tf].to_numpy(float) @ ct[1:])
        shifts[s] = float(np.median(r))
        te = out["season"] == s
        out.loc[te, "final_total"] = ct[0] + shifts[s] + out.loc[te, tf].to_numpy(float) @ ct[1:]
    return out[out["season"].isin(SEASONS)], shifts


def gain(b, c, mask):
    v = (np.abs(b["points"] - b["final_total"]) - np.abs(c["points"] - c["final_total"])).to_numpy()[mask]
    return boot_diff(v, b.loc[mask, "date"])


def main() -> None:
    train, pred = base_frames()
    tf = projection.TOTAL_FEATURES
    b = fit_predict(train, pred)
    lad = fit_lad(train, pred, projection.MARGIN_FEATURES, tf)
    cen, shifts = centered(train, pred, tf)
    ev = b["season"].isin(EVAL).to_numpy()
    L = []
    for tag, c in (("C2 LAD", lad), ("A1 median-centered OLS", cen)):
        g, ci, _ = gain(b, c, ev)
        L.append(f"{tag}: totals MAE gain 2020-26 {g:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]; by season "
                 + ", ".join(f"{s} {gain(b, c, (b['season'] == s).to_numpy())[0]:+.4f}" for s in EVAL))
    L.append("A1 intercept shift by season (training median residual): " + ", ".join(f"{s} {shifts[s]:+.2f}" for s in EVAL))
    # A2: overtime share of the gap, on the training rows of the 2026 fit (2013-2025)
    per = []
    for s in range(2013, 2026):
        g, _ = data.season_games(s)
        per.append(g[["game_id", "periods"]])
    per = pd.concat(per).drop_duplicates("game_id")
    tr = train[train["season"].between(2013, 2025)].merge(per, on="game_id", how="left")
    ct = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)))
    r = tr["points"].to_numpy(float) - (ct[0] + tr[tf].to_numpy(float) @ ct[1:])
    ot = (tr["periods"] > 2).to_numpy()
    L.append(f"A2 training 2013-25: overtime games {100 * ot.mean():.1f}%, their mean residual {r[ot].mean():+.1f}; "
             f"mean - median of residuals: all games {r.mean() - np.median(r):+.2f}, regulation only "
             f"{r[~ot].mean() - np.median(r[~ot]):+.2f}; skewness all {pd.Series(r).skew():.2f}, regulation {pd.Series(r[~ot]).skew():.2f}")
    # A3: v1 bias by season
    L.append("A3 v1 mean total residual by season (result - forecast): " + ", ".join(
        f"{s} {float((b.loc[b['season'] == s, 'points'] - b.loc[b['season'] == s, 'final_total']).mean()):+.2f}" for s in EVAL))
    # A4: share over the forecast
    for tag, c in (("v1", b), ("C2 LAD", lad), ("A1", cen)):
        x = c[c["season"].isin(EVAL)]
        L.append(f"A4 {tag}: share of 2020-26 games over the forecast {100 * (x['points'] > x['final_total']).mean():.1f}%")
    # A5: beyond E2 (E2's feature set, refit walk-forward here; frozen E2 untouched)
    t2, p2 = train.copy(), pred.copy()
    for d in (t2, p2):
        d["neutral"], d["conf_game"] = d["neutral"].astype(float), d["conf_game"].astype(float)
    tf2 = tf + ["neutral", "conf_game"]
    e2 = fit_predict(t2, p2, tf=tf2)
    e2c, _ = centered(t2, p2, tf2)
    g, ci, _ = gain(e2, e2c, ev)
    L.append(f"A5 E2 -> E2 median-centered: totals MAE gain 2020-26 {g:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    for tag, c in (("v1", b), ("E2", e2), ("C2 LAD", lad), ("A1", cen), ("E2 centered", e2c)):
        p = plays(c[c["season"].isin(CONF)], "total").dropna(subset=["win"])
        q = plays(c[c["season"].isin(EVAL)], "total", "close").dropna(subset=["win"])
        L.append(f"   {tag}: opener 2024-26 {len(p)} plays {100 * p['win'].mean():.2f}% (overs {100 * (p['edge'] > 0).mean():.0f}%); "
                 f"close 2020-26 {len(q)} plays {100 * q['win'].mean():.2f}%; MAE 2020-26 "
                 f"{float((c.loc[c['season'].isin(EVAL), 'points'] - c.loc[c['season'].isin(EVAL), 'final_total']).abs().mean()):.4f}")
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "c2_why.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
