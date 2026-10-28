"""Robustness for E2 (logged in LOG.md as diagnostics run after the result; nothing here changes the verdict or
the feature set). Decomposition, where the gain comes from, paired opener win% interval, simulated -110 ROI.

    python -m research.quant.e2_checks       # -> out/e2_checks.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.quant.common import CONF, OUT, base_frames, fit_predict, plays
from research.quant.experiments import add

EVAL = list(range(2020, 2027))


def mae_gain(b, c, mask):
    return float((np.abs(b.loc[mask, "points"] - b.loc[mask, "final_total"]) -
                  np.abs(c.loc[mask, "points"] - c.loc[mask, "final_total"])).mean()), int(mask.sum())


def main() -> None:
    train, pred = base_frames()
    train, pred = add(train), add(pred)
    base = fit_predict(train, pred).set_index("game_id")
    L = []
    variants = {"E2 (neutral + conf_game)": ["neutral", "conf_game"], "neutral only": ["neutral"], "conf_game only": ["conf_game"]}
    fits = {}
    for k, v in variants.items():
        c = fit_predict(train, pred, tf=projection.TOTAL_FEATURES + v).set_index("game_id")
        fits[k] = c
        ev = base["season"].isin(EVAL)
        L.append(f"{k}: MAE gain 2020-26 {mae_gain(base, c, ev)[0]:+.4f}")
    c = fits["E2 (neutral + conf_game)"]
    ev = base["season"].isin(EVAL)
    m = pd.to_datetime(base["date"]).dt.month
    subsets = {"neutral, Nov-Dec": ev & (base["neutral"] == 1) & m.isin([11, 12]),
               "neutral, Jan-Feb": ev & (base["neutral"] == 1) & m.isin([1, 2]),
               "neutral, Mar-Apr": ev & (base["neutral"] == 1) & m.isin([3, 4]),
               "home/away, conference": ev & (base["neutral"] == 0) & (base["conf_game"] == 1),
               "home/away, non-conference": ev & (base["neutral"] == 0) & (base["conf_game"] == 0)}
    L.append("\nWhere the E2 gain comes from (2020-26):")
    for k, msk in subsets.items():
        g, n = mae_gain(base, c, msk)
        r = (base.loc[msk, "points"] - base.loc[msk, "final_total"]).mean()
        L.append(f"  {k:28s} n {n:6d}  MAE gain {g:+.4f}  baseline mean residual {r:+.2f}")
    # paired opener comparison 2024-26 at the fixed threshold
    b2, c2 = base.reset_index(), c.reset_index()
    pb, pc = plays(b2[b2["season"].isin(CONF)], "total"), plays(c2[c2["season"].isin(CONF)], "total")
    both = set(pb["game_id"]) & set(pc["game_id"])
    only_b, only_c = pb[~pb["game_id"].isin(both)], pc[~pc["game_id"].isin(both)]
    flip = pb[pb["game_id"].isin(both)].set_index("game_id")["edge"].pipe(np.sign) != \
        pc[pc["game_id"].isin(both)].set_index("game_id")["edge"].pipe(np.sign)
    L.append(f"\nOpener totals 2024-26: baseline {len(pb)} plays, E2 {len(pc)}; shared {len(both)} "
             f"(side flips {int(flip.sum())}); baseline-only {len(only_b)} win% {100 * only_b['win'].mean():.1f}; "
             f"E2-only {len(only_c)} win% {100 * only_c['win'].mean():.1f}")
    # date-bootstrap of the win% difference
    days = sorted(set(pb["date"]) | set(pc["date"]))
    gb, gc = pb.dropna(subset=["win"]).groupby("date")["win"].agg(["sum", "count"]), pc.dropna(subset=["win"]).groupby("date")["win"].agg(["sum", "count"])
    gb, gc = gb.reindex(days, fill_value=0), gc.reindex(days, fill_value=0)
    i = np.random.default_rng(20261028).integers(0, len(days), (4000, len(days)))
    diff = gc["sum"].to_numpy()[i].sum(1) / gc["count"].to_numpy()[i].sum(1) - gb["sum"].to_numpy()[i].sum(1) / gb["count"].to_numpy()[i].sum(1)
    L.append(f"Win% difference E2 - baseline: {100 * (gc['sum'].sum() / gc['count'].sum() - gb['sum'].sum() / gb['count'].sum()):+.2f} "
             f"points, 95% [{100 * np.quantile(diff, .025):+.2f}, {100 * np.quantile(diff, .975):+.2f}]")
    for tag, p in (("baseline", pb), ("E2", pc)):
        x = p.dropna(subset=["win"])
        L.append(f"Simulated ROI at -110 (not executable evidence; opener prices only sampled on 12 dates): {tag} "
                 f"{100 * (x['win'].mean() * (1 + 100 / 110) - 1):+.1f}% on {len(x)} plays")
    # by season, opener and close
    L.append("\nBy season, totals at the fixed threshold (baseline -> E2):")
    for s in range(2015, 2027):
        bb, cc = b2[b2["season"] == s], c2[c2["season"] == s]
        ln = "open" if s in (2015, 2016, 2017, 2024, 2025, 2026) else "close"
        xb, xc = plays(bb, "total", ln).dropna(subset=["win"]), plays(cc, "total", ln).dropna(subset=["win"])
        L.append(f"  {s} vs {ln:5s}: {len(xb):5d} plays {100 * xb['win'].mean():.1f}% -> {len(xc):5d} plays {100 * xc['win'].mean():.1f}%")
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "e2_checks.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
