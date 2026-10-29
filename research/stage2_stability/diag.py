"""Step 0 and step 1 diagnostics (PLAN.md), on the leak-free research baseline R0.

    python -m research.stage2_stability.diag      # -> out/diag.txt, out/paths.csv, out/oracle.csv, ...
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.stage2_stability.common import (GROUPS_M, GROUPS_T, MF, OUT, PRIMARY, TEST, TF, boot, fit, frames,
                                              predict, walk)

L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def clustered(X, r, g):
    """OLS of r on X (with intercept) and a date-clustered covariance."""
    X1 = np.column_stack([np.ones(len(X)), X])
    XtX = np.linalg.inv(X1.T @ X1)
    b = XtX @ X1.T @ r
    e = r - X1 @ b
    u, inv = np.unique(g, return_inverse=True)
    S = np.zeros((len(u), X1.shape[1]))
    np.add.at(S, inv, X1 * e[:, None])
    V = XtX @ (S.T @ S) @ XtX * len(u) / (len(u) - 1)
    return b, V


def wald(b, V, idx):
    from scipy import stats
    bb, VV = b[idx], V[np.ix_(idx, idx)]
    w = float(bb @ np.linalg.solve(VV, bb))
    return w, float(1 - stats.chi2.cdf(w, len(idx)))


def suff_stats(tr, feats, target):
    """Per-date X1'X1 and X1'y for a fast date-clustered bootstrap of the ridge fit."""
    X1 = np.column_stack([np.ones(len(tr)), tr[feats].to_numpy(float)])
    y = tr[target].to_numpy(float)
    u, inv = np.unique(tr["date"].astype(str).to_numpy(), return_inverse=True)
    A = np.zeros((len(u), X1.shape[1], X1.shape[1]))
    B = np.zeros((len(u), X1.shape[1]))
    for k in range(len(u)):
        m = inv == k
        A[k], B[k] = X1[m].T @ X1[m], X1[m].T @ y[m]
    return A, B


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames(clean=True)
    t0, p0 = frames(clean=False)
    for b in (train, pred, t0, p0):
        b["points"], b["margin"] = b["home_pts"] + b["away_pts"], b["home_pts"] - b["away_pts"]

    # ---- step 0: reference, baseline, leak effect
    fz, r0 = walk(t0, p0), walk(train, pred)
    say("Step 0. Leak fix (season_avg_total from earlier dates only): R0 vs R-frozen, totals")
    for per, ss in [(str(s), [s]) for s in PRIMARY] + [("2024-26", PRIMARY), ("2020-23", [2020, 2021, 2022, 2023])]:
        m = r0["season"].isin(ss).to_numpy()
        y = r0.loc[m, "points"].to_numpy()
        ef, e0 = y - fz.loc[m, "final_total"].to_numpy(), y - r0.loc[m, "final_total"].to_numpy()
        g, ci, _, se = boot(np.abs(ef) - np.abs(e0), r0.loc[m, "date"])
        say(f"  {per}: bias frozen {ef.mean():+.3f} R0 {e0.mean():+.3f}; MAE {np.abs(ef).mean():.4f} -> {np.abs(e0).mean():.4f} "
            f"(gain {g:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]); RMSE {np.sqrt((ef ** 2).mean()):.4f} -> {np.sqrt((e0 ** 2).mean()):.4f}; "
            f"forecast change RMS {np.sqrt(((ef - e0) ** 2).mean()):.3f}")
    r0[["game_id", "season", "date", "final_total", "final_margin"]].to_pickle(os.path.join(OUT, "r0.pkl"))

    # ---- 1. coefficient paths (standardized) and level pass-through
    rows, coefs = [], {}
    for mk, feats, tgt, groups in (("total", TF, "points", GROUPS_T), ("margin", MF, "margin", GROUPS_M)):
        for s in TEST:
            tr = train[train["season"].between(2013, s - 1)]
            c = fit(tr, feats, tgt)
            coefs[(mk, s)] = c
            sd = tr[feats].std().to_numpy()
            for f, beta, z in zip(feats, c[1:], c[1:] * sd):
                rows.append({"market": mk, "fit_for": s, "feature": f, "group": next(k for k, v in groups.items() if f in v),
                             "coef": beta, "std_coef": z})
    paths = pd.DataFrame(rows)
    paths.to_csv(os.path.join(OUT, "paths.csv"), index=False)
    say("\n1. Standardized totals coefficients (coef x training SD, points per 1 SD), fits for 2015..2026")
    piv = paths[paths["market"] == "total"].pivot(index="feature", columns="fit_for", values="std_coef").loc[TF]
    say(piv[[2015, 2018, 2020, 2022, 2023, 2024, 2025, 2026]].round(2).to_string())
    lvl = paths[(paths["market"] == "total") & paths["feature"].isin(["pred_total", "kp_total", "bt_total", "season_avg_total"])]
    say("  level pass-through (sum of pred_total, kp_total, bt_total, season_avg_total raw coefs): " +
        ", ".join(f"{s} {v:.3f}" for s, v in lvl.groupby("fit_for")["coef"].sum().items()))

    # ---- 2. prediction-level sensitivity
    say("\n2. Prediction-level sensitivity, totals (season-s forecasts; RMS in points)")
    say("  season  churn(s-1 vs s-2 fit) by group: total | " + " | ".join(GROUPS_T) + " ;  LOSO: forecast RMS change max, MAE range, bias range")
    sens = []
    for s in TEST:
        te = pred[pred["season"] == s]
        y = te["points"].to_numpy()
        c1 = coefs[("total", s)]
        c2 = fit(train[train["season"].between(2013, s - 2)], TF, "points")
        Xc = te[TF].to_numpy(float) - train.loc[train["season"].between(2013, s - 2), TF].to_numpy(float).mean(0)
        d = (c1[1:] - c2[1:])
        churn = np.sqrt(((predict(c1, te, TF) - predict(c2, te, TF)) ** 2).mean())
        grp = {g: np.sqrt(((Xc[:, [TF.index(f) for f in fs]] @ d[[TF.index(f) for f in fs]]) ** 2).mean()) for g, fs in GROUPS_T.items()}
        base = predict(c1, te, TF)
        alts = {"drop first": fit(train[train["season"].between(2014, s - 1)], TF, "points"),
                "drop latest": c2}
        for k in range(2013, s):
            alts[f"loso {k}"] = fit(train[train["season"].between(2013, s - 1) & (train["season"] != k)], TF, "points")
        rms, mae, bias = [], [], []
        for k, c in alts.items():
            f = predict(c, te, TF)
            rms.append(np.sqrt(((f - base) ** 2).mean()))
            mae.append(np.abs(y - f).mean() - np.abs(y - base).mean())
            bias.append((y - f).mean())
        sens.append({"season": s, "churn": churn, **{f"churn {g}": v for g, v in grp.items()}, "pert_rms_max": max(rms),
                     "mae_delta_min": min(mae), "mae_delta_max": max(mae), "bias_min": min(bias), "bias_max": max(bias),
                     "bias_base": (y - base).mean(), "drop_first_mae": mae[0], "drop_latest_mae": mae[1]})
        say(f"  {s}  {churn:.3f} | " + " | ".join(f"{v:.3f}" for v in grp.values()) +
            f" ;  {max(rms):.3f}, MAE {min(mae):+.4f}..{max(mae):+.4f}, bias {min(bias):+.2f}..{max(bias):+.2f} (base {(y - base).mean():+.2f})")
    pd.DataFrame(sens).to_csv(os.path.join(OUT, "sensitivity.csv"), index=False)

    # bootstrap of the training set (date clusters): SD of each group's mean contribution and of the season bias
    say("\n  Date-clustered bootstrap of the training set (200 resamples), totals: SD across resamples")
    say("  season  bias SD | mean-contribution SD by group (" + ", ".join(GROUPS_T) + ") | MAE SD")
    rng = np.random.default_rng(20261029)
    bs = []
    for s in PRIMARY + [2020, 2022]:
        tr = train[train["season"].between(2013, s - 1)]
        A, B = suff_stats(tr, TF, "points")
        P = np.diag(np.concatenate([[0.0], np.ones(len(TF))]))
        te = pred[pred["season"] == s]
        X1 = np.column_stack([np.ones(len(te)), te[TF].to_numpy(float)])
        y = te["points"].to_numpy()
        dx = te[TF].to_numpy(float).mean(0) - tr[TF].to_numpy(float).mean(0)
        res = []
        for _ in range(200):
            w = np.bincount(rng.integers(0, len(A), len(A)), minlength=len(A)).astype(float)
            c = np.linalg.solve(np.tensordot(w, A, 1) + P, w @ B)
            f = X1 @ c
            res.append([(y - f).mean(), np.abs(y - f).mean()] + [float(dx[[TF.index(x) for x in fs]] @ c[1:][[TF.index(x) for x in fs]]) for fs in GROUPS_T.values()])
        res = np.array(res)
        bs.append([s] + list(res.std(0)))
        say(f"  {s}  {res[:, 0].std():.3f} | " + ", ".join(f"{v:.3f}" for v in res[:, 2:].std(0)) + f" | {res[:, 1].std():.4f}")
    pd.DataFrame(bs, columns=["season", "bias_sd", "mae_sd"] + list(GROUPS_T)).to_csv(os.path.join(OUT, "bootstrap.csv"), index=False)

    # ---- 3. drivers: correlations, VIF, input shift, referee offset
    say("\n3. Drivers")
    tr = train[train["season"].between(2013, 2025)]
    Z = (tr[TF] - tr[TF].mean()) / tr[TF].std()
    vif = {}
    for f in TF:
        A = np.column_stack([np.ones(len(Z)), Z.drop(columns=f).to_numpy()])
        e = Z[f].to_numpy() - A @ np.linalg.lstsq(A, Z[f].to_numpy(), rcond=None)[0]
        vif[f] = 1 / ((e ** 2).sum() / ((Z[f] - Z[f].mean()) ** 2).sum())
    say("  VIF (2026 training set): " + ", ".join(f"{f} {v:.1f}" for f, v in vif.items()))
    say("  correlations, four factors + Torvik + level: \n" +
        tr[["pred_total", "kp_total", "bt_total", "efg_sum", "tov_rate_sum", "orb_rate_sum", "ft_rate_sum", "season_avg_total"]].corr().round(2).to_string())
    say("  standardized input shift (season mean - training mean) / training SD:")
    sh = []
    for s in TEST:
        trs = train[train["season"].between(2013, s - 1)]
        te = pred[pred["season"] == s]
        sh.append(((te[TF].mean() - trs[TF].mean()) / trs[TF].std()).rename(s))
    say(pd.DataFrame(sh).round(2)[["pred_total", "kp_total", "bt_total", "season_avg_total", "efg_sum", "tov_rate_sum",
                                   "orb_rate_sum", "ft_rate_sum", "mkt_t", "ref_fouls", "ref_pts"]].to_string())
    say("  referee offset in prediction (crews 0 instead of the training mean): forecast shift = sum coef x (0 - train mean)")
    for s in TEST:
        trs = train[train["season"].between(2013, s - 1)]
        c = coefs[("total", s)]
        off = sum(c[1 + TF.index(f)] * (0 - trs[f].mean()) for f in ("ref_fouls", "ref_pts"))
        say(f"    {s}: ref_fouls coef {c[1 + TF.index('ref_fouls')]:+.3f} (train mean {trs['ref_fouls'].mean():+.2f}), "
            f"ref_pts coef {c[1 + TF.index('ref_pts')]:+.3f} (train mean {trs['ref_pts'].mean():+.2f}); offset {off:+.2f} points")

    # ---- 4. partial-residual tests, 2024-26 (R0 residuals)
    say("\n4. Do the inputs explain R0's 2024-26 totals residuals after the other inputs? (standardized, within-season de-meaned, date-clustered)")
    r0i = r0.set_index("game_id")
    feats = [f for f in TF if f not in ("ref_fouls", "ref_pts")]
    out4 = []
    for per, ss in [(str(s), [s]) for s in PRIMARY] + [("2024-26", PRIMARY), ("2019-22", [2019, 2020, 2021, 2022])]:
        te = pred[pred["season"].isin(ss)].copy()
        r = (te["points"] - te["game_id"].map(r0i["final_total"])).to_numpy()
        Xd = te[feats] - te.groupby("season")[feats].transform("mean")
        Xd = (Xd / Xd.std()).fillna(0)
        b, V = clustered(Xd.to_numpy(float), r - pd.Series(r).groupby(te["season"].to_numpy()).transform("mean").to_numpy(), te["date"].astype(str).to_numpy())
        gi = {g: [1 + feats.index(f) for f in fs if f in feats] for g, fs in GROUPS_T.items()}
        line = f"  {per}: " + "; ".join(f"{g} Wald p {wald(b, V, ix)[1]:.3f}" for g, ix in gi.items() if ix)
        line += " | partial (pts per SD, t): " + ", ".join(f"{f} {b[1 + feats.index(f)]:+.2f} ({b[1 + feats.index(f)] / np.sqrt(V[1 + feats.index(f), 1 + feats.index(f)]):+.1f})"
                                                         for f in ["efg_sum", "ft_rate_sum", "orb_rate_sum", "tov_rate_sum", "bt_total", "kp_total", "pred_total"])
        say(line)
        # referees: the same games with crews as recorded (training frame), would knowing the crew have helped?
        trf = train.set_index("game_id").loc[te["game_id"]]
        Xr = pd.concat([Xd.reset_index(drop=True), ((trf[["ref_fouls", "ref_pts"]] - trf[["ref_fouls", "ref_pts"]].mean()) /
                                                    trf[["ref_fouls", "ref_pts"]].std()).reset_index(drop=True)], axis=1)
        b2, V2 = clustered(Xr.to_numpy(float), r - r.mean(), te["date"].astype(str).to_numpy())
        k = [Xr.columns.get_loc("ref_fouls") + 1, Xr.columns.get_loc("ref_pts") + 1]
        say(f"       recorded crews (training frame, same games): ref_fouls {b2[k[0]]:+.2f} ({b2[k[0]] / np.sqrt(V2[k[0], k[0]]):+.1f}), "
            f"ref_pts {b2[k[1]]:+.2f} ({b2[k[1]] / np.sqrt(V2[k[1], k[1]]):+.1f}); joint p {wald(b2, V2, k)[1]:.3f}")
        out4.append({"period": per, **{f: b[1 + feats.index(f)] for f in feats}})
    pd.DataFrame(out4).to_csv(os.path.join(OUT, "partial.csv"), index=False)

    # ---- 5. oracle bounds (cross-fitted within season) and 6a. ex-ante Nov-Dec -> Jan-Mar
    say("\n5. Cross-fitted oracle: MAE gain over R0 from refitting within the season (odd/even dates), totals")
    say("   and 6a. ex-ante: the same refits on Nov-Dec games applied to Jan-Mar (Jan-Mar MAE gain)")
    sets = {"(i) intercept": [], "(ii) level": GROUPS_T["level"], "(iii) adjustments": GROUPS_T["four factors"] + ["rest_sum", "mkt_t", "altitude"],
            "(iv) all": [f for f in TF if f not in ("ref_fouls", "ref_pts")]}
    orc = []
    for mk, feats_all, tgt, col, sets_m in (("total", TF, "points", "final_total", sets),
                                           ("margin", MF, "margin", "final_margin",
                                            {"(i) intercept": [], "(ii) level": GROUPS_M["level"], "(iii) adjustments": GROUPS_M["four factors"] + GROUPS_M["venue/rest/injury"],
                                             "(iv) all": MF})):
        for s in TEST:
            te = pred[pred["season"] == s].copy()
            r = (te[tgt] - te["game_id"].map(r0i[col])).to_numpy()
            dates = pd.to_datetime(te["date"])
            half = (dates.rank(method="dense").astype(int) % 2).to_numpy()
            early = dates.dt.month.isin([11, 12]).to_numpy()
            row = {"market": mk, "season": s, "base_mae": np.abs(r).mean()}
            for name, fs in sets_m.items():
                Xs = te[fs].to_numpy(float) if fs else np.zeros((len(te), 0))
                adj = np.zeros(len(te))
                for h in (0, 1):
                    trn, tst = half != h, half == h
                    mu = Xs[trn].mean(0) if fs else None
                    c = np.linalg.lstsq(np.column_stack([np.ones(trn.sum()), Xs[trn] - mu]) if fs else np.ones((trn.sum(), 1)), r[trn], rcond=None)[0]
                    adj[tst] = c[0] + ((Xs[tst] - mu) @ c[1:] if fs else 0)
                row[name] = np.abs(r).mean() - np.abs(r - adj).mean()
                # ex-ante: Nov-Dec fit applied to Jan-Mar (shrunk 50% toward 0 is NOT applied: raw, as an upper-ish probe)
                if early.sum() > 50 and (~early).sum() > 50:
                    mu = Xs[early].mean(0) if fs else None
                    c = np.linalg.lstsq(np.column_stack([np.ones(early.sum()), Xs[early] - mu]) if fs else np.ones((early.sum(), 1)), r[early], rcond=None)[0]
                    a2 = c[0] + ((Xs[~early] - mu) @ c[1:] if fs else 0)
                    row["exante " + name] = np.abs(r[~early]).mean() - np.abs(r[~early] - a2).mean()
            orc.append(row)
    orc = pd.DataFrame(orc)
    orc.to_csv(os.path.join(OUT, "oracle.csv"), index=False)
    for mk in ("total", "margin"):
        o = orc[orc["market"] == mk].set_index("season")
        say(f"  {mk}:")
        say(o.round(4).to_string())
        p = o.loc[PRIMARY]
        say(f"  {mk} pooled 2024-26 (season mean): oracle (iv)-(i) = {(p['(iv) all'] - p['(i) intercept']).mean():+.4f}; "
            f"ex-ante (iv)-(i) = {(p['exante (iv) all'] - p['exante (i) intercept']).mean():+.4f}")

    # ---- 6a persistence of coefficient deviations within season; 6b early-warning (descriptive)
    say("\n6a. Within-season persistence: partial slope of R0 residual on each standardized feature, Nov-Dec vs Jan-Mar, totals")
    pers = []
    for s in TEST:
        te = pred[pred["season"] == s]
        r = (te["points"] - te["game_id"].map(r0i["final_total"])).to_numpy()
        early = pd.to_datetime(te["date"]).dt.month.isin([11, 12]).to_numpy()
        fs = [f for f in TF if f not in ("ref_fouls", "ref_pts")]
        Z = ((te[fs] - te[fs].mean()) / te[fs].std()).fillna(0).to_numpy()
        for part, m in (("early", early), ("late", ~early)):
            c = np.linalg.lstsq(np.column_stack([np.ones(m.sum()), Z[m]]), r[m], rcond=None)[0]
            for f, v in zip(fs, c[1:]):
                pers.append({"season": s, "part": part, "feature": f, "slope": v})
    pers = pd.DataFrame(pers).pivot_table(index=["season", "feature"], columns="part", values="slope").reset_index()
    cr = np.corrcoef(pers["early"], pers["late"])[0, 1]
    seas = pers["season"].unique()
    bc = []
    rng = np.random.default_rng(1)
    for _ in range(2000):
        sm = rng.choice(seas, len(seas))
        q = pd.concat([pers[pers["season"] == x] for x in sm])
        bc.append(np.corrcoef(q["early"], q["late"])[0, 1])
    say(f"  correlation of Nov-Dec and Jan-Mar partial slopes across features x seasons: {cr:+.2f} "
        f"[{np.quantile(bc, .025):+.2f}, {np.quantile(bc, .975):+.2f}] (bootstrap over seasons)")
    for f in ["efg_sum", "ft_rate_sum", "orb_rate_sum", "bt_total", "kp_total", "pred_total", "season_avg_total"]:
        q = pers[pers["feature"] == f]
        say(f"    {f}: corr {np.corrcoef(q['early'], q['late'])[0, 1]:+.2f}; 2024-26 early/late: " +
            ", ".join(f"{int(a)} {b:+.2f}/{c:+.2f}" for a, b, c in q[q["season"].isin(PRIMARY)][["season", "early", "late"]].to_numpy()))
    sens = pd.DataFrame(sens).set_index("season")
    o = orc[orc["market"] == "total"].set_index("season")
    shift_max = pd.DataFrame(sh).abs().drop(columns=["ref_fouls", "ref_pts"]).max(1)
    from scipy import stats
    say("\n6b. Early warning (12 seasons, Spearman, descriptive):")
    for nm, x in (("fit-to-fit churn", sens["churn"]), ("max standardized input shift", shift_max)):
        for tn, y in (("|season bias|", sens["bias_base"].abs()), ("oracle (iv)-(i)", o["(iv) all"] - o["(i) intercept"])):
            rho, p = stats.spearmanr(x.loc[TEST], y.loc[TEST])
            say(f"  {nm} vs {tn}: rho {rho:+.2f} (p {p:.2f})")
    open(os.path.join(OUT, "diag.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
