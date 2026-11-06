"""Roster-based preseason ratings, version 4: different fits, chosen on 2016-2021, judged on 2022-2026
(PLAN_v4.md, pre-registered Nov 6, 2026). Research only.

    python -m research.roster_prior.build_v4      # -> out/v4.txt, out/v4.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from cbb import player_ratings as pr
from research.roster_prior import build as v1
from research.roster_prior import build_v2 as v2
from research.roster_prior import build_v3 as v3

OUT = v1.OUT
SEASONS = range(v1.FIRST + 1, 2027)
SELECT, HOLD = range(2016, 2022), range(2022, 2027)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def f1_features(season: int) -> pd.DataFrame:
    """Projected-minutes-weighted last-season box rates (per 100 possessions) of the roster's known players."""
    path = os.path.join(OUT, f"f1_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    b = v3.box(season - 1)
    R = v3.rates(b)
    now = pr.player_games(season)
    ids5 = (now.drop_duplicates(["team_id", "game_id"]).sort_values(["team_id", "date", "game_id"])
            .groupby("team_id").head(5)[["team_id", "game_id"]])
    first5 = now.merge(ids5, on=["team_id", "game_id"])
    rows = []
    for tid, g in first5.groupby("team_id"):
        known = [a for a in set(g["athlete_id"]) if a in b.index and b.at[a, "min"] > 0]
        if not known:
            continue
        w = b.loc[known, "min"]
        rows.append(pd.Series((R.loc[known].mul(w, axis=0).sum() / w.sum()).to_numpy(), index=[f"box_{k}" for k in v3.STATS], name=int(tid)))
    f = pd.DataFrame(rows)
    f.index.name = "team_id"
    f.to_parquet(path)
    return f


BASE = ["off_prev", "def_prev", "tempo_prev", "ret_share", "tr_share", "newc_share"]
V3X = v2.X2
F1X = BASE + [f"box_{k}" for k in v3.STATS]


def cols(fit: str, target: str) -> list[str]:
    if fit in ("F0", "F4", "F5"):
        return V3X[target]
    if fit == "F1":
        return F1X
    return sorted(set(F1X) | set(V3X[target]))


def model(fit: str, X: np.ndarray, y: np.ndarray):
    if fit == "F3":
        m = HistGradientBoostingRegressor(max_iter=200, max_depth=3, learning_rate=0.05, random_state=0).fit(X, y)
        return m.predict
    alpha = {"F4": 10.0, "F5": 0.1}.get(fit, 1.0)
    return v1.ridge(X, y, alpha)


def main() -> None:
    v3.use("V3a")
    frames = {s: v2.design(s, "V3a").join(f1_features(s), how="left") for s in range(v1.FIRST, 2027)}
    v3.use("V2a")
    for s in frames:
        frames[s] = frames[s].fillna({c: frames[s][c].median() for c in frames[s].columns if c.startswith("box_")})
    rows = []
    for fit in ("F0", "F1", "F2", "F3", "F4", "F5"):
        for s in SEASONS:
            train = pd.concat([frames[k] for k in range(v1.FIRST, s)]).dropna(subset=["off_now", "def_now", "tempo_now"])
            d = frames[s]
            p = pd.DataFrame(index=d.index)
            for c in ("off", "def", "tempo"):
                cc = cols(fit, c)
                f = model(fit, train[cc].to_numpy(float), train[f"{c}_now"].to_numpy(float))
                p[c] = f(d[cc].to_numpy(float))
            p = p - p.mean()
            final = v1.final_ratings(s)
            fm = final["off"] + final["def"]
            pm = (p["off"] + p["def"]).reindex(fm.index)
            pm = pm - pm.mean()
            ok = pm.notna()
            e = pm[ok] - fm[ok]
            rows.append({"fit": fit, "season": s, "n": int(ok.sum()), "sse": float((e ** 2).sum()),
                         "corr": float(np.corrcoef(pm[ok], fm[ok])[0, 1])})
    r = pd.DataFrame(rows)
    per = lambda ss: r[r["season"].isin(ss)].groupby("fit").agg(n=("n", "sum"), sse=("sse", "sum"), corr=("corr", "mean")).assign(
        rmse=lambda d: np.sqrt(d["sse"] / d["n"]))[["corr", "rmse"]].round(3)
    a, h = per(SELECT), per(HOLD)
    say("Version 4: fits chosen on 2016-2021, judged on 2022-2026 (correlation with the final margin rating; RMSE)")
    say(a.add_suffix(" 2016-21").join(h.add_suffix(" 2022-26")).to_string())
    best = a["corr"].idxmax()
    go = (h.at[best, "corr"] - h.at["F0", "corr"] >= 0.010) or (h.at["F0", "rmse"] - h.at[best, "rmse"] >= 0.10)
    say(f"\nChosen on 2016-2021: {best} (corr {a.at[best, 'corr']:.3f}). Holdout 2022-2026: corr {h.at[best, 'corr']:.3f} "
        f"vs F0 {h.at['F0', 'corr']:.3f}; RMSE {h.at[best, 'rmse']:.3f} vs {h.at['F0', 'rmse']:.3f} -> "
        f"{'GO to step 2' if go else 'STOP'}")
    say("\nBy season (correlation):\n" + r.pivot(index="season", columns="fit", values="corr").round(3).to_string())
    open(os.path.join(OUT, "v4.txt"), "w").write("\n".join(L) + "\n")
    r.to_csv(os.path.join(OUT, "v4.csv"), index=False)


if __name__ == "__main__" and len(__import__("sys").argv) == 1:
    main()


# ---------------------------------------------------------------- step 2 (PLAN_v4.md: chosen fit through the full model)
def f2_priors() -> dict:
    """Walk-forward F2 priors for 2016-2026, cached."""
    out = {}
    need = [s for s in SEASONS if not os.path.exists(os.path.join(OUT, f"priorF2_{s}.parquet"))]
    if need:
        v3.use("V3a")
        frames = {s: v2.design(s, "V3a").join(f1_features(s), how="left") for s in range(v1.FIRST, 2027)}
        v3.use("V2a")
        for s in frames:
            frames[s] = frames[s].fillna({c: frames[s][c].median() for c in frames[s].columns if c.startswith("box_")})
        for s in need:
            train = pd.concat([frames[k] for k in range(v1.FIRST, s)]).dropna(subset=["off_now", "def_now", "tempo_now"])
            d = frames[s]
            p = pd.DataFrame(index=d.index)
            for c in ("off", "def", "tempo"):
                cc = cols("F2", c)
                p[c] = model("F2", train[cc].to_numpy(float), train[f"{c}_now"].to_numpy(float))(d[cc].to_numpy(float))
            (p - p.mean()).to_parquet(os.path.join(OUT, f"priorF2_{s}.parquet"))
    for s in SEASONS:
        out[s] = pd.read_parquet(os.path.join(OUT, f"priorF2_{s}.parquet"))
    return out


def stage1(mode: str) -> str:
    from cbb import backtest
    path = os.path.join(OUT, f"stage1_F2_{mode}.csv")
    if os.path.exists(path):
        return path
    pri = f2_priors()

    def fn(season):
        cur = v1._ORIG_PRIOR(season)
        p = pri.get(season)
        if p is None:
            return cur
        if mode == "prior":
            return p
        j = cur.join(p, rsuffix="_r", how="outer")
        for c in ("off", "def", "tempo"):
            j[c] = j[[c, c + "_r"]].mean(axis=1)
        return j[["off", "def", "tempo"]]

    backtest.preseason_prior = fn
    try:
        parts = []
        for s in range(2013, 2027):
            parts.append(backtest.season(s))
            print("F2", mode, s, flush=True)
        pd.concat(parts).to_csv(path, index=False)
    finally:
        backtest.preseason_prior = v1._ORIG_PRIOR
    return path


def score() -> None:
    from audit.common import frame
    from research.own_ratings import run as own
    OWN = os.path.join(os.path.dirname(__file__), "..", "own_ratings", "out")
    z = own.zero(own.BT + own.KP)
    frames = {"base": frame(stage1=os.path.join(OWN, "stage1_base.csv"), tag="own_base"),
              "R1 v1 roster prior, no outside": frame(stage1=v1.stage1("roster"), tag="rp_R1", features=z),
              "R1v4 F2 prior, no outside": frame(stage1=stage1("prior"), tag="rp4_R1", features=z),
              "R3v4 F2 blended prior + outside": frame(stage1=stage1("blend"), tag="rp4_R3")}
    acc, plays = own.final_tables(frames)
    pd.set_option("display.width", 250)
    for name, t in (("v4_final_accuracy", acc), ("v4_opener_plays", plays)):
        t.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
        say(f"\n== {name}\n{t.to_string(index=False)}")
    open(os.path.join(OUT, "v4_step2.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__" and len(__import__("sys").argv) > 1:
    import sys
    if sys.argv[1] == "priors":
        f2_priors()
    elif sys.argv[1] == "stage1":
        stage1(sys.argv[2])
    elif sys.argv[1] == "score":
        score()
