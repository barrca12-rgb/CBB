"""Learning step (PLAN.md): features, chronological validation on earlier seasons only, frozen settings.

Never reads 2025-26 outcomes: the totals folds stop at 2025, the spread folds use 2015-17 and 2024-25 only.

    python -m research.persistent_disagreement.learn    # -> out/frozen.json, out/learn.txt, out/history_lag{0,1}.pkl
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import (KS, LAMS, NS, OUT, baseline, design, feats, fit_candidate,
                                                     fit_comparator, grade, history_sums, select)

L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def rows(w, hist, market):
    if market == "total":
        m = (~w["swapped"]) & w["total"].notna() & w["final_total"].notna()
        d0 = (w["final_total"] - w["total"])
        y = (w["points"] - w["total"])
    else:
        m = (~w["swapped"]) & w["open_home_spread"].notna() & w["home_spread"].notna() & w["final_margin"].notna()
        d0 = (w["final_margin"] + w["open_home_spread"])
        y = (w["margin"] + w["open_home_spread"])
    return m, d0, y


def units_at_110(edge, cover, market):
    p = np.full(len(edge), -110.0)
    bet, side, price = select(edge, p, p, market)
    return float(grade(side[bet], cover[bet], price[bet]).sum()), int(bet.sum())


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    hist = {}
    for lag in (0, 1):
        path = os.path.join(OUT, f"history_lag{lag}.pkl")
        if os.path.exists(path):
            hist[lag] = pd.read_pickle(path)
        else:
            hist[lag] = history_sums(w, lag)
            pd.to_pickle(hist[lag], path)
    frozen = {}
    for market, lag, folds, final in (
            ("total", 0, [(list(range(2016, v)), v) for v in range(2019, 2026)], list(range(2016, 2026))),
            ("spread", 1, [([2015, 2016], 2017), ([2015, 2016, 2017], 2024), ([2015, 2016, 2017, 2024], 2025)],
             [2015, 2016, 2017, 2024, 2025])):
        m, d0, y = rows(w, hist, market)
        say(f"\n=== {market} (history lag {lag} day{'s' if lag != 1 else ''})")
        res = []
        for nk in NS:
            for k in KS:
                f = feats(hist[lag][nk], d0, market, k)
                for lam in LAMS:
                    mse, mse_c, mse_b, uc, ub, ucan = [], [], [], 0.0, 0.0, 0.0
                    for tr_s, v in folds:
                        tr = m & w["season"].isin(tr_s)
                        va = m & (w["season"] == v)
                        mu, sd = f.loc[tr, ["V", "Sdir", "S"]].mean(), f.loc[tr, ["V", "Sdir", "S"]].std().replace(0, 1)
                        Xtr = design(d0[tr].to_numpy(), f[tr], mu, sd)
                        b = fit_candidate(Xtr, y[tr].to_numpy(), lam)
                        c = fit_comparator(d0[tr].to_numpy(), y[tr].to_numpy())
                        Xva = design(d0[va].to_numpy(), f[va], mu, sd)
                        yv, dv = y[va].to_numpy(), d0[va].to_numpy()
                        pc, pcomp = Xva @ b, c * dv
                        mse.append(np.mean((yv - pc) ** 2)); mse_c.append(np.mean((yv - pcomp) ** 2)); mse_b.append(np.mean((yv - dv) ** 2))
                        ucan += units_at_110(pc, yv, market)[0]; uc += units_at_110(pcomp, yv, market)[0]; ub += units_at_110(dv, yv, market)[0]
                    res.append({"N": nk, "k": k, "lam": lam, "val_mse": np.mean(mse), "comparator_mse": np.mean(mse_c),
                                "baseline_mse": np.mean(mse_b), "val_units_candidate": ucan, "val_units_comparator": uc, "val_units_baseline": ub})
        r = pd.DataFrame(res).sort_values("val_mse")
        r.to_csv(os.path.join(OUT, f"validation_{market}.csv"), index=False)
        say(r.round(4).head(8).to_string(index=False))
        best = r.iloc[0]
        say(f"chosen by validation MSE: N={best['N']}, k={best['k']}, lambda={best['lam']} "
            f"(MSE {best['val_mse']:.4f} vs comparator {best['comparator_mse']:.4f} vs baseline {best['baseline_mse']:.4f}; "
            f"validation units at -110, descriptive: candidate {best['val_units_candidate']:+.1f}, comparator {best['val_units_comparator']:+.1f}, baseline {best['val_units_baseline']:+.1f})")
        # final fit on all learning seasons
        f = feats(hist[lag][best["N"]], d0, market, best["k"])
        tr = m & w["season"].isin(final)
        mu, sd = f.loc[tr, ["V", "Sdir", "S"]].mean(), f.loc[tr, ["V", "Sdir", "S"]].std().replace(0, 1)
        b = fit_candidate(design(d0[tr].to_numpy(), f[tr], mu, sd), y[tr].to_numpy(), best["lam"])
        c = fit_comparator(d0[tr].to_numpy(), y[tr].to_numpy())
        frozen[market] = {"history_lag_days": lag, "N": best["N"], "k": float(best["k"]), "lambda": float(best["lam"]),
                          "train_seasons": final, "mu": mu.to_dict(), "sd": sd.to_dict(),
                          "candidate_coefs[D0, D0*V, D0*Sdir, S]": [float(x) for x in b], "comparator_c": c, "train_rows": int(tr.sum())}
        say(f"final fit on {final}: {int(tr.sum())} games; candidate coefficients {np.round(b, 4).tolist()}; comparator c {c:.4f}")
    json.dump(frozen, open(os.path.join(OUT, "frozen.json"), "w"), indent=1)
    open(os.path.join(OUT, "learn.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
