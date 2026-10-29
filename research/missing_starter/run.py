"""Missing-starter totals term (research/missing_starter/PLAN.md). One run; nothing tuned.

    python -m research.missing_starter.run        # -> out/run.txt, out/seasons.csv, out/eras.csv

Baseline: frozen v1 stage 2, walk-forward (season s fit on 2013..s-1), live opening-week rule.
Candidate: the same with miss_sum = home_missing + away_missing added to the totals inputs.
All intervals: 95% from a date-clustered bootstrap.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import ridge_w
from research.quant.common import SEASONS, base_frames, fit_predict, plays
from research.quant3.study import opening_week

OUT = os.path.join(os.path.dirname(__file__), "out")
TF = projection.TOTAL_FEATURES
TF_C = TF + ["miss_sum"]
STARTER = 0.17
B, SEED = 4000, 20261029
ERAS_FIT = {"2014-19": range(2014, 2020), "2020-23": range(2020, 2024), "2024-26": range(2024, 2027)}
ERAS_OPEN = {"dev 2015-17": [2015, 2016, 2017], "conf 2024-26": [2024, 2025, 2026]}
MOVE_PERIODS = {"2020-26 (primary)": range(2020, 2027), "2015-19": range(2015, 2020),
                "2020-23": range(2020, 2024), "2024-26": range(2024, 2027)}


def draws(dates, n=B, seed=SEED):
    """Date clusters and a (n, clusters) matrix of bootstrap counts (resampling dates with replacement)."""
    u, inv = np.unique(np.asarray(dates), return_inverse=True)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    cnt = np.zeros((n, len(u)))
    np.add.at(cnt, (np.repeat(np.arange(n), len(u)), i.ravel()), 1)
    return inv, cnt


def boot_mean(v, dates):
    """Mean with a date-clustered 95% interval and SE."""
    v = np.asarray(v, float)
    inv, cnt = draws(dates)
    r = (cnt @ np.bincount(inv, v, minlength=cnt.shape[1])) / (cnt @ np.bincount(inv, minlength=cnt.shape[1]))
    return float(v.mean()), float(np.quantile(r, .025)), float(np.quantile(r, .975)), float(r.std())


def boot_diff(a, da, b, db):
    """Mean(a) - mean(b) for two play sets on shared date clusters (resampling dates, not plays)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    dates = np.concatenate([np.asarray(da), np.asarray(db)])
    inv, cnt = draws(dates)
    ia, ib = inv[:len(a)], inv[len(a):]
    k = cnt.shape[1]
    ra = (cnt @ np.bincount(ia, a, minlength=k)) / (cnt @ np.bincount(ia, minlength=k))
    rb = (cnt @ np.bincount(ib, b, minlength=k)) / (cnt @ np.bincount(ib, minlength=k))
    r = ra - rb
    return float(a.mean() - b.mean()), float(np.nanquantile(r, .025)), float(np.nanquantile(r, .975)), float(np.nanstd(r))


def boot_coef(tr: pd.DataFrame, feats: list, target: str = "points", lam: float = 1.0):
    """Ridge (intercept unpenalized) coefficient on the last feature, with a date-clustered bootstrap: per-date
    X'X and X'y are summed with bootstrap counts, so each draw is an exact refit on the resampled dates."""
    X1 = np.column_stack([np.ones(len(tr)), tr[feats].to_numpy(float)])
    y = tr[target].to_numpy(float)
    inv, cnt = draws(tr["date"].astype(str))
    k, p = cnt.shape[1], X1.shape[1]
    xx = np.zeros((k, p, p))
    np.add.at(xx, inv, X1[:, :, None] * X1[:, None, :])
    xy = np.zeros((k, p))
    np.add.at(xy, inv, X1 * y[:, None])
    pen = np.diag(np.r_[0.0, np.full(p - 1, lam)])
    full = np.linalg.solve(xx.sum(0) + pen, xy.sum(0))[-1]
    XX = (cnt @ xx.reshape(k, -1)).reshape(-1, p, p) + pen
    r = np.linalg.solve(XX, (cnt @ xy)[:, :, None])[:, -1, 0]
    return float(full), float(r.std()), float(np.quantile(r, .025)), float(np.quantile(r, .975))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = base_frames()
    for b in (train, pred):
        b["miss_sum"] = b["home_missing"] + b["away_missing"]
    L = []
    base = opening_week(fit_predict(train, pred)).reset_index(drop=True)
    cand = opening_week(fit_predict(train, pred, tf=TF_C)).reset_index(drop=True)
    assert (base["game_id"].to_numpy() == cand["game_id"].to_numpy()).all()
    assert np.allclose(base["final_margin"], cand["final_margin"])
    base["date"] = cand["date"] = base["date"].astype(str)

    # --- reconciliation: research/quant3 "V0 v1", season 2026 close totals at 3+: 1,478 plays at 48.71%
    c26 = plays(base[base["season"] == 2026], "total", "close").dropna(subset=["win"])
    ok = len(c26) == 1478 and round(100 * c26["win"].mean(), 2) == 48.71
    L.append(f"Reconciliation (baseline = quant3 V0 v1): 2026 close totals 3+: {len(c26)} plays at "
             f"{100 * c26['win'].mean():.2f}% (target 1,478 at 48.71%) -> {'PASS' if ok else 'FAIL'}")
    m20 = base["season"].between(2020, 2026)
    L.append(f"Baseline 2020-26 totals MAE {np.abs(base.loc[m20, 'points'] - base.loc[m20, 'final_total']).mean():.4f} "
             f"(quant3 2020-23 13.1371 and 2024-26 13.1585 for cross-check)")
    for lab, ss in (("2020-23", range(2020, 2024)), ("2024-26", range(2024, 2027))):
        m = base["season"].isin(list(ss))
        L.append(f"  baseline {lab} MAE {np.abs(base.loc[m, 'points'] - base.loc[m, 'final_total']).mean():.4f}")
    if not ok:
        L.append("RECONCILIATION FAILED: results below are not comparable to quant3.")

    # --- 1. totals MAE, pooled and by season
    rows = []
    e0 = np.abs(base["points"] - base["final_total"]).to_numpy()
    e1 = np.abs(cand["points"] - cand["final_total"]).to_numpy()
    mv = (cand["final_total"] - base["final_total"]).to_numpy()
    for lab, ss in [("2020-26", range(2020, 2027)), ("2020-23", range(2020, 2024)), ("2024-26", range(2024, 2027))] + \
                   [(str(s), [s]) for s in range(2015, 2027)]:
        m = base["season"].isin(list(ss)).to_numpy()
        g, lo, hi, se = boot_mean(e0[m] - e1[m], base.loc[m, "date"])
        rows.append({"period": lab, "games": int(m.sum()), "base MAE": round(e0[m].mean(), 4),
                     "cand MAE": round(e1[m].mean(), 4), "MAE gain": round(g, 4), "gain 95%": f"[{lo:+.4f}, {hi:+.4f}]",
                     "mean move": round(mv[m].mean(), 3), "sd move": round(mv[m].std(), 3),
                     "moved 1+ %": round(100 * (np.abs(mv[m]) >= 1).mean(), 2)})
    sea = pd.DataFrame(rows)
    sea.to_csv(os.path.join(OUT, "seasons.csv"), index=False)

    # --- 2. the miss_sum coefficient: era refits (bootstrap) and the walk-forward coefficient per season
    era_rows = []
    for lab, ss in ERAS_FIT.items():
        tr = train[train["season"].isin(list(ss))]
        c, se, lo, hi = boot_coef(tr, TF_C)
        era_rows.append({"era": lab, "games": len(tr), "dates": tr["date"].nunique(), "coef": round(c, 3),
                         "SE": round(se, 3), "95%": f"[{lo:+.2f}, {hi:+.2f}]", "per starter": round(STARTER * c, 3),
                         "per starter 95%": f"[{STARTER * lo:+.2f}, {STARTER * hi:+.2f}]"})
    eras = pd.DataFrame(era_rows)
    eras.to_csv(os.path.join(OUT, "eras.csv"), index=False)
    wf = []
    for s in range(2015, 2027):
        tr = train[train["season"].between(2013, s - 1)]
        ct = ridge_w(tr[TF_C].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)))
        wf.append(f"{s} {ct[-1]:+.2f}")
    L.append("Walk-forward miss_sum coefficient used for each season (fit 2013..s-1): " + ", ".join(wf))

    # --- 3. opener totals at 3+ (and close, descriptive)
    op = []
    for lab, ss in ERAS_OPEN.items():
        pb = plays(base[base["season"].isin(ss)], "total", "open")
        pc = plays(cand[cand["season"].isin(ss)], "total", "open")
        kb, kc = pb.dropna(subset=["clv"]), pc.dropna(subset=["clv"])      # a few dev plays have no closing total
        g, lo, hi, se = boot_diff(kc["clv"], kc["date"], kb["clv"], kb["date"])
        wb, wc = pb.dropna(subset=["win"]), pc.dropna(subset=["win"])
        cb = plays(base[base["season"].isin(ss)], "total", "close").dropna(subset=["win"])
        cc = plays(cand[cand["season"].isin(ss)], "total", "close").dropna(subset=["win"])
        op.append({"era": lab, "base open n/win%": f"{len(wb)} / {100 * wb['win'].mean():.2f}",
                   "cand open n/win%": f"{len(wc)} / {100 * wc['win'].mean():.2f}",
                   "base CLV": round(pb["clv"].mean(), 3), "cand CLV": round(pc["clv"].mean(), 3),
                   "CLV gain": round(g, 3), "gain 95%": f"[{lo:+.3f}, {hi:+.3f}]",
                   "base close n/win%": f"{len(cb)} / {100 * cb['win'].mean():.2f}",
                   "cand close n/win%": f"{len(cc)} / {100 * cc['win'].mean():.2f}"})
    opens = pd.DataFrame(op)

    # --- 4. beyond the close, on games the term moves by 1+
    mvr = []
    ok_close = (~base["swapped"]) & base["total"].notna()
    for lab, ss in MOVE_PERIODS.items():
        m = (ok_close & base["season"].isin(list(ss)) & (np.abs(cand["final_total"] - base["final_total"]) >= 1)).to_numpy()
        x, xc = base[m], cand[m]
        res = (x["points"] - x["total"]).to_numpy(float)
        sb, sc = np.sign(x["final_total"] - x["total"]).to_numpy(), np.sign(xc["final_total"] - xc["total"]).to_numpy()
        ob, oc = sb * res, sc * res
        g, lo, hi, se = boot_mean(oc - ob, x["date"])
        win = lambda o: 100 * float((o > 0).sum() / max((o != 0).sum(), 1))
        mvr.append({"period": lab, "moved games": int(m.sum()), "lower %": round(100 * (xc["final_total"] < x["final_total"]).mean(), 1),
                    "side flips": int((sb != sc).sum()), "base vs close": round(ob.mean(), 3), "cand vs close": round(oc.mean(), 3),
                    "cand - base": round(g, 3), "95%": f"[{lo:+.3f}, {hi:+.3f}]",
                    "base win% vs close": round(win(ob), 2), "cand win% vs close": round(win(oc), 2)})
    moved = pd.DataFrame(mvr)

    # --- kill rule
    g20 = float(sea.loc[sea["period"] == "2020-26", "MAE gain"].iloc[0])
    clv = dict(zip(opens["era"], opens["CLV gain"]))
    mg = float(moved.loc[moved["period"] == "2020-26 (primary)", "cand - base"].iloc[0])
    fails = []
    if g20 < 0.02:
        fails.append(f"MAE gain 2020-26 {g20:+.4f} < 0.02")
    for k, v in clv.items():
        if v < 0.1:
            fails.append(f"opener CLV gain {k} {v:+.3f} < 0.1")
    if mg < 0:
        fails.append(f"moved games vs close {mg:+.3f} < 0")
    verdict = "KILL (closed): " + "; ".join(fails) if fails else "candidate for the Mar 14 list"

    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    txt = ("\n".join(L) + "\n\n1. Totals MAE (baseline vs candidate, identical games; gain = base - cand):\n" + sea.to_string(index=False) +
           "\n\n2. miss_sum coefficient, stage-2 totals ridge refit on each era (points per 1.0 combined missing share):\n" +
           eras.to_string(index=False) +
           "\n\n3. Opener totals at 3+ (swapped excluded; CLV = close - open, oriented):\n" + opens.to_string(index=False) +
           "\n\n4. Beyond the close, games moved 1+ (outcome = side x (result - close)):\n" + moved.to_string(index=False) +
           f"\n\nVERDICT: {verdict}\n")
    open(os.path.join(OUT, "run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
