"""C2 totals, deeper (research/quant3/PLAN.md). One run; nothing tuned on 2024-26.

    python -m research.quant3.study        # -> out/run.txt, out/seasons.csv, out/variants.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import ridge_w
from research.quant.common import SEASONS, base_frames, fit_predict, plays
from research.quant2.c2_median import fit_lad

OUT = os.path.join(os.path.dirname(__file__), "out")
PRIMARY = [2024, 2025, 2026]
GRID = [250, 500, 1000, 2000, 4000]
SHIFT = -0.61


def regulation() -> pd.DataFrame:
    """game_id -> regulation total (score after period 2) and final total from the cached ESPN play-by-play.
    Some games' play-by-play is truncated (2025-26: 236 games, about 44 points short), so the regulation total is
    used only where the play-by-play final equals the schedule's final."""
    path = os.path.join(OUT, "regulation_v2.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    parts = []
    for s in range(2014, 2027):
        p = pd.read_parquet(os.path.join("cbb", "cache", "pbp", f"play_by_play_{s}.parquet"),
                            columns=["game_id", "period_number", "home_score", "away_score", "sequence_number"])
        p["seq"] = pd.to_numeric(p["sequence_number"], errors="coerce")
        p = p.sort_values(["game_id", "seq"])
        reg = p[p["period_number"] <= 2].groupby("game_id").tail(1).set_index("game_id")
        full = p.groupby("game_id").tail(1).set_index("game_id")
        parts.append(pd.DataFrame({"reg": reg["home_score"] + reg["away_score"],
                                   "pbp_final": full["home_score"] + full["away_score"]}).astype(float))
    r = pd.concat(parts)
    r.index = r.index.astype(int)
    r = r[~r.index.duplicated()]
    r.to_pickle(path)
    return r


def opening_week(w: pd.DataFrame) -> pd.DataFrame:
    """The live rule (run_day.opening_week_totals): first 7 days of each season, shift each day's totals so their
    mean equals KenPom's."""
    w = w.copy()
    d = pd.to_datetime(w["date"])
    ow = d < d.groupby(w["season"]).transform("min") + pd.Timedelta(days=7)
    gap = (w["final_total"] - w["kp_total"]).groupby([w["season"], d]).transform("mean")
    m = ow & gap.notna()
    w.loc[m, "final_total"] -= gap[m]
    return w


def running_bias(w: pd.DataFrame, k: float) -> pd.Series:
    """For each game: sum of this season's residuals (result - forecast) from earlier dates / (n + k)."""
    d = pd.to_datetime(w["date"])
    r = (w["points"] - w["final_total"]).to_numpy(float)
    out = pd.Series(0.0, index=w.index)
    for s, g in w.groupby("season"):
        day = pd.DataFrame({"r": r[g.index.map(w.index.get_loc)], "date": d[g.index]}).groupby("date")["r"].agg(["sum", "count"]).sort_index()
        cs, cn = day["sum"].cumsum().shift(1).fillna(0), day["count"].cumsum().shift(1).fillna(0)
        corr = (cs / (cn + k))
        out[g.index] = d[g.index].map(corr).to_numpy()
    return out


def boot(v, groups, n=4000, seed=20261029):
    v, groups = np.asarray(v, float), np.asarray(groups)
    u, inv = np.unique(groups, return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(v.mean()), np.quantile(r, [.025, .975]), np.quantile(r, [.0085, .9915]), float(r.std())


def main() -> None:
    train, pred = base_frames()
    tf = projection.TOTAL_FEATURES
    L = []
    # --- base forecasts, live opening-week rule applied to each
    v1 = opening_week(fit_predict(train, pred)).reset_index(drop=True)
    lad = opening_week(fit_lad(train, pred, projection.MARGIN_FEATURES, tf)).reset_index(drop=True)
    t2, p2 = train.copy(), pred.copy()
    for d_ in (t2, p2):
        d_["neutral"], d_["conf_game"] = d_["neutral"].astype(float), d_["conf_game"].astype(float)
    e2 = opening_week(fit_predict(t2, p2, tf=tf + ["neutral", "conf_game"])).reset_index(drop=True)
    assert (v1["game_id"].to_numpy() == lad["game_id"].to_numpy()).all() and (v1["game_id"].to_numpy() == e2["game_id"].to_numpy()).all()
    reg = regulation()
    for w in (v1, lad, e2):
        w["reg"] = w["game_id"].map(reg["reg"]).where(w["game_id"].map(reg["pbp_final"]) == w["points"])
    # --- V2: choose k for season s on seasons 2015..s-1 only
    rb = {k: running_bias(v1, k) for k in GRID}
    rb_e2 = {k: running_bias(e2, k) for k in GRID}
    chosen = {}
    for s in PRIMARY + [2020, 2021, 2022, 2023]:
        prior = v1["season"].between(2015, s - 1)
        maes = {k: float((v1.loc[prior, "points"] - v1.loc[prior, "final_total"] - rb[k][prior]).abs().mean()) for k in GRID}
        chosen[s] = min(maes, key=maes.get)
    L.append("V2 shrinkage chosen on earlier seasons only: " + ", ".join(f"{s}: k={chosen[s]}" for s in sorted(chosen)))
    k_of = v1["season"].map(chosen)

    def variants(base, rbx):
        out = {"V0 v1": base["final_total"], "V1 v1-0.61": base["final_total"] + SHIFT}
        corr = pd.Series(0.0, index=base.index)
        for k in GRID:
            corr[k_of == k] = rbx[k][k_of == k]
        out["V2 running bias"] = base["final_total"] + corr
        return out, corr
    V, corr = variants(v1, rb)
    V["V3 median stage 2"] = lad["final_total"]
    # --- step 1/2: seasonal bias, level, regulation diagnostics
    rows = []
    trainmean = {s: float(train.loc[train["season"].between(2013, s - 1), "points"].mean()) for s in SEASONS}
    for s in range(2015, 2027):
        x = v1[v1["season"] == s]
        r = x["points"] - x["final_total"]
        ot = (x["points"] - x["reg"]).dropna()
        rows.append({"season": s, "games": len(x), "level": round(x["points"].mean(), 2),
                     "level - training mean": round(x["points"].mean() - trainmean[s], 2),
                     "v1 bias": round(r.mean(), 2), "bias SE": round(r.std() / np.sqrt(x["date"].nunique() * 1.0) / np.sqrt(len(x) / x["date"].nunique()), 2),
                     "v1 MAE": round(r.abs().mean(), 3), "mean - median": round(r.mean() - r.median(), 2),
                     "games with full pbp": len(ot), "OT games %": round(100 * (ot > 0.5).mean(), 1), "OT pts per game": round(ot.mean(), 2),
                     "regulation mean - median": round((x["reg"] - x["final_total"]).dropna().pipe(lambda z: z.mean() - z.median()), 2),
                     "v1 bias, Nov-Dec": round(r[pd.to_datetime(x["date"]).dt.month.isin([11, 12])].mean(), 2),
                     "v1 bias, Jan-Apr": round(r[pd.to_datetime(x["date"]).dt.month.isin([1, 2, 3, 4])].mean(), 2)})
    sea = pd.DataFrame(rows)
    sea.to_csv(os.path.join(OUT, "seasons.csv"), index=False)
    b = np.polyfit(sea["level - training mean"], sea["v1 bias"], 1)
    cr = np.corrcoef(sea["level - training mean"], sea["v1 bias"])[0, 1]
    xl, yl = sea["level - training mean"].to_numpy(float), sea["v1 bias"].to_numpy(float)
    se_b = np.sqrt(((yl - np.polyval(b, xl)) ** 2).sum() / (len(xl) - 2) / ((xl - xl.mean()) ** 2).sum())
    L.append(f"\nH-level: season bias = {b[1]:+.2f} + {b[0]:.3f} x (season level - training mean); correlation {cr:.2f} (2015-26, 12 seasons); "
             f"slope 95% interval [{b[0] - 2.228 * se_b:+.3f}, {b[0] + 2.228 * se_b:+.3f}] (t, 10 df)")
    # stage-2 level pass-through: coefficients of the 2026 fit on the level-carrying inputs
    tr = train[train["season"].between(2013, 2025)]
    ct = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)))
    co = dict(zip(["intercept"] + tf, ct))
    L.append("2026 stage-2 totals weights on level-carrying inputs: " + ", ".join(f"{k} {co[k]:+.3f}" for k in
             ["intercept", "pred_total", "pred_total_x_early", "kp_total", "kp_total_x_early", "bt_total", "season_avg_total"]))
    # where each season's bias comes from: the actual level change vs what stage 2 passed through, by feature
    # (training residuals average zero, so bias before the opening-week rule = actual change - sum of contributions)
    L.append("\nBias decomposition (stage 2 walk-forward, before the opening-week rule): change vs the training seasons")
    for s in range(2015, 2027):
        tr = train[train["season"].between(2013, s - 1)]
        te = pred[pred["season"] == s]
        cs = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)))
        con = {f: cs[1 + i] * (te[f].mean() - tr[f].mean()) for i, f in enumerate(tf)}
        dy = te["points"].mean() - tr["points"].mean()
        top = sorted(con.items(), key=lambda kv: -abs(kv[1]))[:6]
        L.append(f"  {s}: actual {dy:+.2f}, stage-1 total {te['pred_total'].mean() - tr['pred_total'].mean():+.2f}, "
                 f"KenPom {te['kp_total'].mean() - tr['kp_total'].mean():+.2f}, forecast {sum(con.values()):+.2f}, "
                 f"bias {dy - sum(con.values()):+.2f}; largest: " + ", ".join(f"{k} {v:+.2f}" for k, v in top))
    # within-season path: how fast stage 1 absorbs a level change (mean residual by month, primary seasons)
    for s in PRIMARY:
        x = v1[v1["season"] == s]
        m = pd.to_datetime(x["date"]).dt.month
        L.append(f"  {s} v1 bias by month: " + ", ".join(f"{mm} {(x.loc[m == mm, 'points'] - x.loc[m == mm, 'final_total']).mean():+.2f}"
                                                        for mm in [11, 12, 1, 2, 3] if (m == mm).any())
                 + f"; inputs mean: pred_total {x['pred_total'].mean():.1f}, kp_total {x['kp_total'].mean():.1f}, bt_total {x['bt_total'].mean():.1f}, actual {x['points'].mean():.1f}")
    # --- step 4: variants on the primary seasons
    out = []
    for label, base, Vx in (("v1", v1, V), ("E2 spec", e2, None)):
        if Vx is None:
            Vx, _ = variants(e2, rb_e2)
            Vx["V3 median stage 2"] = lad["final_total"] - v1["final_total"] + e2["final_total"]   # LAD's change applied to E2
        for name, f in Vx.items():
            for per, ss in [(str(s), [s]) for s in PRIMARY] + [("2024-26", PRIMARY), ("2020-23 (older)", [2020, 2021, 2022, 2023])]:
                m = base["season"].isin(ss).to_numpy()
                y = base.loc[m, "points"].to_numpy(float)
                e0 = y - Vx["V0 v1"][m].to_numpy(float)
                e1 = y - f[m].to_numpy(float)
                g, ci, ci3, se = boot(np.abs(e0) - np.abs(e1), base.loc[m, "date"])
                gq, _, _, _ = boot(e0 ** 2 - e1 ** 2, base.loc[m, "date"])
                row = {"base": label, "variant": name, "period": per, "games": int(m.sum()), "bias": round(e1.mean(), 3),
                       "MAE": round(np.abs(e1).mean(), 4), "RMSE": round(float(np.sqrt((e1 ** 2).mean())), 4),
                       "MAE gain vs V0": round(g, 4), "gain 95%": f"[{ci[0]:+.4f}, {ci[1]:+.4f}]", "gain 98.3%": f"[{ci3[0]:+.4f}, {ci3[1]:+.4f}]",
                       "gain SE": round(se, 4),
                       "RMSE gain": round(float(np.sqrt((e0 ** 2).mean()) - np.sqrt((e1 ** 2).mean())), 4)}
                w = base.assign(final_total=f)
                for ln in ("open", "close"):
                    if ln == "open" and not set(ss) <= {2024, 2025, 2026, 2015, 2016, 2017}:
                        continue
                    p = plays(w[w["season"].isin(ss)], "total", ln).dropna(subset=["win"])
                    o, u = p[p["edge"] > 0], p[p["edge"] < 0]
                    row[f"{ln} overs n/win%"] = f"{len(o)} / {100 * o['win'].mean():.1f}" if len(o) else "0"
                    row[f"{ln} unders n/win%"] = f"{len(u)} / {100 * u['win'].mean():.1f}" if len(u) else "0"
                    row[f"{ln} all n/win%"] = f"{len(p)} / {100 * p['win'].mean():.2f}"
                out.append(row)
    res = pd.DataFrame(out)
    res.to_csv(os.path.join(OUT, "variants.csv"), index=False)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    cols = ["base", "variant", "period", "games", "bias", "MAE", "RMSE", "MAE gain vs V0", "gain 95%", "gain 98.3%", "gain SE", "RMSE gain"]
    txt = ("\n".join(L) + "\n\nSeasons (v1, opening-week rule applied):\n" + sea.to_string(index=False) +
           "\n\nVariants, forecast accuracy:\n" + res[cols].to_string(index=False) +
           "\n\nVariants, fixed thresholds (opener edge 3+, close edge 3+):\n" +
           res[["base", "variant", "period"] + [c for c in res.columns if "n/win%" in c]].fillna("").to_string(index=False) + "\n")
    open(os.path.join(OUT, "run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
