"""C2 (PLAN.md): stage 2 fit by least absolute deviations instead of least squares. Same features, frames and
walk-forward as v1; only the loss changes. One run.

    python -m research.quant2.c2_median       # -> out/c2_run.txt, out/c2_by_season.csv, out/c2_preds.csv.gz
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.quant.common import CONF, DEV, SEASONS, base_frames, fit_predict, plays
from research.quant2.common import OUT

EVAL = list(range(2020, 2027))


def lad(X, y, lam=1.0, iters=60, eps=1e-3):
    """Least absolute deviations with v1's ridge penalty, by iteratively reweighted least squares."""
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0
    b = np.linalg.solve(X1.T @ X1 + np.diag(pen), X1.T @ y)
    for _ in range(iters):
        w = 1.0 / np.maximum(np.abs(y - X1 @ b), eps)
        bn = np.linalg.solve(X1.T @ (X1 * w[:, None]) + np.diag(pen), (X1 * w[:, None]).T @ y)
        if np.max(np.abs(bn - b)) < 1e-6:
            b = bn
            break
        b = bn
    return b


def fit_lad(train, pred, mf, tf):
    out = pred.copy()
    out["final_margin"], out["final_total"] = np.nan, np.nan
    for s in SEASONS:
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        te = out["season"] == s
        cm = lad(tr[mf].to_numpy(float), tr["margin"].to_numpy(float))
        ct = lad(tr[tf].to_numpy(float), tr["points"].to_numpy(float))
        out.loc[te, "final_margin"] = cm[0] + out.loc[te, mf].to_numpy(float) @ cm[1:]
        out.loc[te, "final_total"] = ct[0] + out.loc[te, tf].to_numpy(float) @ ct[1:]
    return out[out["season"].isin(SEASONS)]


def boot_diff(v, groups, n=4000, seed=20261028):
    u, inv = np.unique(np.asarray(groups), return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(np.mean(v)), np.quantile(r, [.025, .975]), np.quantile(r, [.003, .997])


def main() -> None:
    train, pred = base_frames()
    mf, tf = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
    b = fit_predict(train, pred)
    c = fit_lad(train, pred, mf, tf)
    assert (b["game_id"].to_numpy() == c["game_id"].to_numpy()).all()
    L, seas = [], []
    for mk, y, f in (("spread", "margin", "final_margin"), ("total", "points", "final_total")):
        ev = b["season"].isin(EVAL).to_numpy()
        eb, ec = (b[y] - b[f]).to_numpy(), (c[y] - c[f]).to_numpy()
        g_mae, ci95, ci99 = boot_diff((np.abs(eb) - np.abs(ec))[ev], b.loc[ev, "date"])
        g_mse, _, _ = boot_diff((eb ** 2 - ec ** 2)[ev], b.loc[ev, "date"])
        rmse_b, rmse_c = np.sqrt((eb[ev] ** 2).mean()), np.sqrt((ec[ev] ** 2).mean())
        per = {s: float((np.abs(eb) - np.abs(ec))[b["season"].to_numpy() == s].mean()) for s in EVAL}
        seas.append({"market": mk, **{str(k): round(v, 4) for k, v in per.items()}})
        L.append(f"{mk}: MAE 2020-26 {np.abs(eb[ev]).mean():.4f} -> {np.abs(ec[ev]).mean():.4f}, gain {g_mae:+.4f} "
                 f"95% [{ci95[0]:+.4f}, {ci95[1]:+.4f}], 99.4% [{ci99[0]:+.4f}, {ci99[1]:+.4f}]; seasons better "
                 f"{sum(v > 0 for v in per.values())} of 7; RMSE {rmse_b:.4f} -> {rmse_c:.4f}; mean shift of the "
                 f"forecast {float((c.loc[ev, f] - b.loc[ev, f]).mean()):+.3f}, SD of the change {float((c.loc[ev, f] - b.loc[ev, f]).std()):.3f}")
        # fixed thresholds: opener 2024-26 and 2015-17, close 2020-26, and which plays changed
        for era, ss, line in (("opener 2024-26", CONF, "open"), ("opener 2015-17", DEV, "open"), ("close 2020-26", EVAL, "close")):
            pb = plays(b[b["season"].isin(ss)], mk, line).dropna(subset=["win"])
            pc = plays(c[c["season"].isin(ss)], mk, line).dropna(subset=["win"])
            kb = set(zip(pb["game_id"], np.sign(pb["edge"])))
            kc = set(zip(pc["game_id"], np.sign(pc["edge"])))
            ob = pb[[k not in kc for k in zip(pb["game_id"], np.sign(pb["edge"]))]]
            oc = pc[[k not in kb for k in zip(pc["game_id"], np.sign(pc["edge"]))]]
            side = ""
            if mk == "total":
                side = (f"; overs share {100 * (pb['edge'] > 0).mean():.0f}% -> {100 * (pc['edge'] > 0).mean():.0f}%")
            L.append(f"   {era}: {len(pb)} plays {100 * pb['win'].mean():.2f}% -> {len(pc)} plays {100 * pc['win'].mean():.2f}%; "
                     f"dropped {len(ob)} ({100 * ob['win'].mean():.1f}%), added {len(oc)} ({100 * oc['win'].mean():.1f}%)" + side)
        d = b[b["season"].isin(EVAL) & ~b["swapped"]].dropna(subset=["home_spread", "total"])
        dc = c[c["season"].isin(EVAL) & ~c["swapped"]].dropna(subset=["home_spread", "total"])
        if mk == "spread":
            sl = [np.polyfit(x[f] + x["home_spread"], x[y] + x["home_spread"], 1)[0] for x in (d, dc)]
        else:
            sl = [np.polyfit(x[f] - x["total"], x[y] - x["total"], 1)[0] for x in (d, dc)]
        L.append(f"   slope of (result - close) on (model - close): {sl[0]:.3f} -> {sl[1]:.3f}")
    s = pd.DataFrame(seas)
    s.to_csv(os.path.join(OUT, "c2_by_season.csv"), index=False)
    c[["game_id", "season", "date", "final_margin", "final_total"]].to_csv(os.path.join(OUT, "c2_preds.csv.gz"), index=False)
    txt = "\n".join(L) + "\n\nMAE gain by season (+ = LAD better):\n" + s.to_string(index=False) + "\n"
    open(os.path.join(OUT, "c2_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
