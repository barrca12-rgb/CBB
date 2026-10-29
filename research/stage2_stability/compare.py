"""Comparison (PLAN.md): R-frozen (reference), R0 (leak fixed, baseline), ridge 1,000 on R0's inputs, S1 (season-centered
four factors), S2 (referee imputation). One fit each, identical games, live opening-week totals rule on every forecast.

    python -m research.stage2_stability.compare     # -> out/compare.txt, out/compare_metrics.csv, out/compare_plays.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.stage2_stability.common import OUT, PRIMARY, TEST, boot, frames, plays, walk

FF = ["efg_sum", "tov_rate_sum", "orb_rate_sum", "ft_rate_sum"]
PERIODS = [(str(s), [s]) for s in PRIMARY] + [("2024-26", PRIMARY), ("2020-23 (context)", [2020, 2021, 2022, 2023])]
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def centered(b: pd.DataFrame) -> pd.DataFrame:
    """S1: each four-factor sum minus that season's mean over games on earlier dates (200+ games), else last
    season's mean, else (2013 only) the season's mean."""
    b = b.copy()
    d = pd.to_datetime(b["date"])
    for f in FF:
        day = pd.DataFrame({"season": b["season"], "date": d, "x": b[f]}).groupby(["season", "date"])["x"].agg(["sum", "count"]).sort_index()
        g = day.groupby(level=0)
        ps, pn = g["sum"].cumsum() - day["sum"], g["count"].cumsum() - day["count"]
        m = (ps / pn.clip(lower=1)).where(pn >= 200)
        m = pd.Series(m.reindex(pd.MultiIndex.from_arrays([b["season"], d])).to_numpy(), index=b.index)
        prev = b[f].groupby(b["season"]).mean()
        m = m.fillna(b["season"].map(prev.shift())).fillna(b["season"].map(prev))
        b[f] = b[f] - m
    return b


def imputed(pred: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    """S2: unknown crews (prediction) take the training seasons' mean (2013..s-1) instead of 0."""
    pred = pred.copy()
    for s in TEST:
        tr = train[train["season"].between(2013, s - 1)]
        m = pred["season"] == s
        pred.loc[m, "ref_fouls"], pred.loc[m, "ref_pts"] = tr["ref_fouls"].mean(), tr["ref_pts"].mean()
    return pred


def wlp(p: pd.DataFrame) -> str:
    w, l, pu = int((p["cover"] > 0).sum()), int((p["cover"] < 0).sum()), int((p["cover"] == 0).sum())
    units = 0.9091 * w - l
    return f"{w}-{l}-{pu}" + (f" ({100 * w / (w + l):.2f}%, sim {units:+.1f}u, ROI {100 * units / (w + l + pu):+.1f}%)" if w + l else "")


def main() -> None:
    t0, p0 = frames(clean=False)
    train, pred = frames(clean=True)
    for b in (t0, p0, train, pred):
        b["points"], b["margin"] = b["home_pts"] + b["away_pts"], b["home_pts"] - b["away_pts"]
    models = {"R-frozen (reference)": walk(t0, p0), "R0 (baseline)": walk(train, pred),
              "ridge 1,000": walk(train, pred, lam=1000.0),
              "S1 centered four factors": walk(centered(train), centered(pred)),
              "S2 referee imputation": walk(train, imputed(pred, train))}
    ids = models["R0 (baseline)"]["game_id"].to_numpy()
    for k, m in models.items():
        assert (m["game_id"].to_numpy() == ids).all(), k
    base = models["R0 (baseline)"]
    rows = []
    for mk, col, tgt in (("total", "final_total", "points"), ("spread", "final_margin", "margin")):
        say(f"\n=== {mk}: forecast accuracy (gain = R0 error minus model error; + = better than R0)")
        for name, w in models.items():
            if mk == "spread" and name.startswith(("S1", "S2")):
                d = (w[col] - base[col]).abs().max()
                say(f"  {name}: margins identical to R0 (max difference {d:.1e})")
                continue
            for per, ss in PERIODS:
                m = base["season"].isin(ss).to_numpy()
                y = base.loc[m, tgt].to_numpy(float)
                e0, e1 = y - base.loc[m, col].to_numpy(float), y - w.loc[m, col].to_numpy(float)
                g, ci, ci3, se = boot(np.abs(e0) - np.abs(e1), base.loc[m, "date"])
                gq, ciq, _, _ = boot(e0 ** 2 - e1 ** 2, base.loc[m, "date"])
                r = {"market": mk, "model": name, "period": per, "games": int(m.sum()), "bias": e1.mean(), "MAE": np.abs(e1).mean(),
                     "RMSE": np.sqrt((e1 ** 2).mean()), "MAE gain": g, "lo95": ci[0], "hi95": ci[1], "lo983": ci3[0], "hi983": ci3[1], "SE": se,
                     "MSE gain": gq, "MSE lo95": ciq[0], "MSE hi95": ciq[1]}
                rows.append(r)
                say(f"  {name:26s} {per:18s} n {r['games']:6d} bias {r['bias']:+.3f} MAE {r['MAE']:.4f} RMSE {r['RMSE']:.4f} | "
                    f"MAE gain {g:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}] (98.3% [{ci3[0]:+.4f}, {ci3[1]:+.4f}], SE {se:.4f}); "
                    f"MSE gain {gq:+.3f} [{ciq[0]:+.3f}, {ciq[1]:+.3f}]")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "compare_metrics.csv"), index=False)

    # ---- fixed-threshold opener plays, by side, with shared/added/dropped vs R0
    prow = []
    for mk, sides in (("total", ("over", "under")), ("spread", ("home", "away"))):
        say(f"\n=== {mk}: opener plays at the frozen threshold ({'3+' if mk == 'total' else '2.5+'}); "
            "W-L-P, simulated -110 returns (pushes 0), opener-to-close CLV in points")
        for per, ss in PERIODS[:4]:
            pb = plays(base[base["season"].isin(ss)], mk, "open")
            ng = int((~base.loc[base["season"].isin(ss), "swapped"]).sum())
            cov = int(base.loc[base["season"].isin(ss) & ~base["swapped"], "open_total" if mk == "total" else "open_home_spread"].notna().sum())
            say(f"  {per}: games {ng}, with an opener {cov} ({100 * cov / ng:.1f}% coverage)")
            for name, w in models.items():
                if mk == "spread" and name.startswith(("S1", "S2")):
                    continue
                p = plays(w[w["season"].isin(ss)], mk, "open")
                p["side"] = np.where(p["edge"] > 0, sides[0], sides[1])
                pb2 = pb.assign(side=np.where(pb["edge"] > 0, sides[0], sides[1]))
                kb, kp = set(zip(pb2["game_id"], pb2["side"])), set(zip(p["game_id"], p["side"]))
                key = list(zip(p["game_id"], p["side"]))
                sh = p[[k in kb for k in key]]
                ad = p[[k not in kb for k in key]]
                dr = pb2[[k not in kp for k in zip(pb2["game_id"], pb2["side"])]]
                line = (f"    {name:26s} all {wlp(p)}, CLV {p['clv'].mean():+.2f} | {sides[0]}s {wlp(p[p['side'] == sides[0]])} | "
                        f"{sides[1]}s {wlp(p[p['side'] == sides[1]])}")
                if not name.startswith("R0"):
                    line += f"\n      vs R0: shared {wlp(sh)}; added {wlp(ad)} CLV {ad['clv'].mean() if len(ad) else float('nan'):+.2f}; dropped {wlp(dr)} CLV {dr['clv'].mean() if len(dr) else float('nan'):+.2f}"
                say(line)
                prow.append({"market": mk, "period": per, "model": name, "n": len(p), "w": int((p["cover"] > 0).sum()),
                             "l": int((p["cover"] < 0).sum()), "p": int((p["cover"] == 0).sum()), "clv": p["clv"].mean(),
                             "shared": len(sh), "added": len(ad), "dropped": len(dr)})
    pd.DataFrame(prow).to_csv(os.path.join(OUT, "compare_plays.csv"), index=False)

    # ---- pre-registered decision
    say("\n=== Decision (PLAN.md addendum): pooled 2024-26 totals")
    mt = pd.DataFrame(rows)
    mt = mt[(mt["market"] == "total") & (mt["period"] == "2024-26")].set_index("model")
    rg = mt.loc["ridge 1,000", "MAE gain"]
    pp = pd.DataFrame(prow)
    pp = pp[(pp["market"] == "total") & (pp["period"] == "2024-26")].set_index("model")
    wr = lambda k: pp.loc[k, "w"] / (pp.loc[k, "w"] + pp.loc[k, "l"])
    per_season = pd.DataFrame(rows)
    for k in ("S1 centered four factors", "S2 referee imputation"):
        g = mt.loc[k]
        ss = per_season[(per_season["market"] == "total") & (per_season["model"] == k) & per_season["period"].isin([str(s) for s in PRIMARY])]
        checks = {"gain >= +0.010": g["MAE gain"] >= 0.010, "98.3% interval above 0": g["lo983"] > 0,
                  "no season below -1 SE": bool((ss["MAE gain"] >= -ss["SE"]).all()),
                  "beats ridge 1,000": g["MAE gain"] > rg, "opener win% not lower": wr(k) >= wr("R0 (baseline)")}
        say(f"  {k}: gain {g['MAE gain']:+.4f}; " + "; ".join(f"{a} {'yes' if b else 'NO'}" for a, b in checks.items())
            + f" -> {'PASS' if all(checks.values()) else 'KILLED'}")
    open(os.path.join(OUT, "compare.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
