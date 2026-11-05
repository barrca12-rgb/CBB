"""Roster-based preseason ratings (PLAN.md, pre-registered Nov 5, 2026). Research only.

    python -m research.roster_prior.build check     # step 1: priors vs season-final ratings -> out/step1.txt
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from cbb import backtest, data, player_ratings as pr, ratings

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
FIRST = 2015            # first season with a roster prior (needs S-1 player ratings and S-2 league averages)
SEASONS = range(2014, 2027)
ALPHA = 1.0
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def final_ratings(season: int) -> pd.DataFrame:
    """The season's final stage-1 ratings with no prior (off, def, tempo), centered on the D-I average."""
    path = os.path.join(OUT, f"final_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    g, t = data.season_games(season)
    ids = sorted(set(t["team_id"]))
    league = ratings.league_averages(data.season_games(season - 1)[1])
    r = ratings.fit(t, pd.to_datetime(g["date"]).max() + pd.Timedelta(days=1), ids, None, None, league)
    f = pd.DataFrame({"off": r["off"], "def": r["def"], "tempo": r["tempo"]}, index=pd.Index(ids, name="team_id"))
    f = f - f.mean()
    os.makedirs(OUT, exist_ok=True)
    f.to_parquet(path)
    return f


def roster_features(season: int) -> pd.DataFrame:
    """Per team in `season`: roster strength, returning share and incoming-transfer share (PLAN.md)."""
    path = os.path.join(OUT, f"feat_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    prev_rate = pr.season_rates(season - 1)
    med = float(prev_rate.median())
    pp = pr.player_games(season - 1)
    prev_min = pp.groupby(["athlete_id", "team_id"])["min"].sum().reset_index()
    tot_prev = prev_min.groupby("athlete_id")["min"].sum()                 # minutes at any D-I team last season
    last_team = prev_min.sort_values("min").groupby("athlete_id")["team_id"].last()
    team_prev_min = prev_min.groupby("team_id")["min"].sum()
    now = pr.player_games(season)
    ids5 = (now.drop_duplicates(["team_id", "game_id"]).sort_values(["team_id", "date", "game_id"])
            .groupby("team_id").head(5)[["team_id", "game_id"]])
    first5 = now.merge(ids5, on=["team_id", "game_id"])
    rows = []
    for tid, g in first5.groupby("team_id"):
        roster = set(g["athlete_id"])
        proj = pd.Series({a: tot_prev.get(a, 0.0) for a in roster}, dtype=float)
        rate = pd.Series({a: prev_rate.get(a, med - pr.NEWCOMER) for a in roster}, dtype=float)
        newc = proj[proj <= 0].index
        team_min = 200.0 * 30                                                # a season's team minutes, nominal
        known = proj[proj > 0]
        # returning and transfer players keep their minutes (capped at the team total); newcomers share the rest
        scale = min(1.0, team_min / known.sum()) if known.sum() > 0 else 1.0
        w = known * scale
        rest = max(team_min - w.sum(), 0.0)
        if len(newc):
            w = pd.concat([w, pd.Series(rest / len(newc), index=newc)])
        strength = float((w * rate.reindex(w.index)).sum() / w.sum() - med) if w.sum() > 0 else 0.0
        ret = [a for a in roster if last_team.get(a) == tid]
        trans = [a for a in roster if a in last_team.index and last_team.get(a) != tid]
        ret_share = float(prev_min[(prev_min["team_id"] == tid) & prev_min["athlete_id"].isin(ret)]["min"].sum()
                          / team_prev_min.get(tid, np.nan)) if team_prev_min.get(tid, 0) else 0.0
        tr_share = float(w.reindex(trans).sum() / w.sum()) if w.sum() > 0 and trans else 0.0
        rows.append({"team_id": int(tid), "strength": strength, "ret_share": ret_share, "tr_share": tr_share,
                     "newc_share": float(w.reindex(newc).sum() / w.sum()) if len(newc) and w.sum() > 0 else 0.0})
    f = pd.DataFrame(rows).set_index("team_id")
    f.to_parquet(path)
    return f


def design(season: int) -> pd.DataFrame:
    """Features for season S (last season's final ratings + roster) joined with S's final ratings (the target)."""
    prev, now, ro = final_ratings(season - 1), final_ratings(season), roster_features(season)
    d = ro.join(prev.add_suffix("_prev"), how="inner").join(now.add_suffix("_now"), how="left")
    for c in ("off", "def", "tempo"):
        d[f"{c}_prev_x_ret"] = d[f"{c}_prev"] * d["ret_share"]
    d["season"] = season
    return d


X = {"off": ["off_prev", "def_prev", "strength", "ret_share", "off_prev_x_ret", "def_prev_x_ret", "tr_share", "newc_share"],
     "def": ["off_prev", "def_prev", "strength", "ret_share", "off_prev_x_ret", "def_prev_x_ret", "tr_share", "newc_share"],
     "tempo": ["tempo_prev", "tempo_prev_x_ret", "ret_share", "tr_share"]}


def ridge(X_: np.ndarray, y: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    mu, sd = X_.mean(0), X_.std(0) + 1e-9
    Z = np.column_stack([np.ones(len(X_)), (X_ - mu) / sd])
    pen = alpha * np.eye(Z.shape[1]); pen[0, 0] = 0
    b = np.linalg.solve(Z.T @ Z + pen, Z.T @ y)
    return lambda Xn: np.column_stack([np.ones(len(Xn)), (Xn - mu) / sd]) @ b


def roster_prior(season: int, frames: dict | None = None) -> pd.DataFrame:
    """Walk-forward prior for `season`: ridge fit on seasons FIRST..season-1, applied to season's features."""
    frames = frames or {s: design(s) for s in range(FIRST, season + 1)}
    train = pd.concat([frames[s] for s in range(FIRST, season)]).dropna(subset=["off_now", "def_now", "tempo_now"])
    d = frames[season]
    out = pd.DataFrame(index=d.index)
    for c, cols in X.items():
        f = ridge(train[cols].to_numpy(float), train[f"{c}_now"].to_numpy(float))
        out[c] = f(d[cols].to_numpy(float))
    return out - out.mean()


def check() -> None:
    from research.own_ratings import run as own
    os.makedirs(OUT, exist_ok=True)
    frames = {s: design(s) for s in range(FIRST, 2027)}
    rows = []
    for s in range(FIRST + 1, 2027):
        final = final_ratings(s)
        fm = final["off"] + final["def"]
        tier = pd.qcut((final_ratings(s - 1)["off"] + final_ratings(s - 1)["def"]).rank(method="first"), 3,
                       labels=["low", "mid", "high"])
        a = backtest.preseason_prior(s)
        b = (final_ratings(s - 1) * 0.6)
        c = roster_prior(s, frames)
        for lab, p in (("(a) KenPom/Barttorvik", a), ("(b) last season x0.6", b), ("(c) roster prior", c)):
            pm = (p["off"] + p["def"]).reindex(fm.index)
            pm = pm - pm.mean()
            ok = pm.notna()
            for t in ("all", "high", "mid", "low"):
                m = ok & ((tier.reindex(fm.index) == t) if t != "all" else True)
                e = (pm[m] - fm[m])
                rows.append({"season": s, "prior": lab, "tier": t, "n": int(m.sum()),
                             "sse": float((e ** 2).sum()), "corr_x": float(np.corrcoef(pm[m], fm[m])[0, 1])})
    r = pd.DataFrame(rows)
    say("Step 1: preseason priors vs the season's final margin rating (points per 100 possessions), 2016-2026")
    t = r.groupby(["prior", "tier"]).agg(n=("n", "sum"), sse=("sse", "sum"), corr=("corr_x", "mean"))
    t["rmse"] = np.sqrt(t["sse"] / t["n"])
    say(t[["n", "rmse", "corr"]].round(3).to_string())
    per = r[r["tier"] == "all"].assign(rmse=lambda d: np.sqrt(d["sse"] / d["n"])).pivot(index="season", columns="prior", values="rmse")
    say("\nBy season (all teams, RMSE):\n" + per.round(2).to_string())
    a_, b_, c_ = (float(t.loc[(k, "all"), "rmse"]) for k in ("(a) KenPom/Barttorvik", "(b) last season x0.6", "(c) roster prior"))
    need = b_ - (b_ - a_) / 3
    go = c_ <= need
    say(f"\nGate: (c) {c_:.3f} must be <= {need:.3f} (b minus a third of the b-a gap) -> {'GO to step 2' if go else 'STOP'}")
    # coefficients of the last fit, for the record
    train = pd.concat([frames[s] for s in range(FIRST, 2026)]).dropna(subset=["off_now"])
    say("\nFeature correlations with the final margin (all training rows):")
    m = train["off_now"] + train["def_now"]
    say(train[X["off"]].corrwith(m).round(3).to_string())
    open(os.path.join(OUT, "step1.txt"), "w").write("\n".join(L) + "\n")
    r.to_csv(os.path.join(OUT, "step1.csv"), index=False)


if __name__ == "__main__" and (len(sys.argv) < 2 or sys.argv[1] == "check"):
    check()


# ---------------------------------------------------------------- step 2
def _prior_cache(season: int) -> pd.DataFrame | None:
    """The roster prior for a season (from 2016; None before), cached."""
    if season < FIRST + 1:
        return None
    path = os.path.join(OUT, f"prior_{season}.parquet")
    if not os.path.exists(path):
        roster_prior(season).to_parquet(path)
    return pd.read_parquet(path)


def prior_roster(season: int) -> pd.DataFrame:
    p = _prior_cache(season)
    return backtest_prior(season) if p is None else p


def prior_blend(season: int) -> pd.DataFrame:
    p, cur = _prior_cache(season), backtest_prior(season)
    if p is None:
        return cur
    j = cur.join(p, rsuffix="_r", how="outer")
    for c in ("off", "def", "tempo"):
        j[c] = j[[c, c + "_r"]].mean(axis=1)
    return j[["off", "def", "tempo"]]


_ORIG_PRIOR = backtest.preseason_prior


def backtest_prior(season: int) -> pd.DataFrame:
    return _ORIG_PRIOR(season)


def stage1(tag: str) -> str:
    path = os.path.join(OUT, f"stage1_{tag}.csv")
    if os.path.exists(path):
        return path
    fn = {"roster": prior_roster, "blend": prior_blend}[tag]
    backtest.preseason_prior = fn
    try:
        parts = []
        for s in range(2013, 2027):
            parts.append(backtest.season(s))
            print(tag, s, flush=True)
        pd.concat(parts).to_csv(path, index=False)
    finally:
        backtest.preseason_prior = _ORIG_PRIOR
    return path


def score() -> None:
    from audit.common import frame
    from research.own_ratings import run as own
    OWN = os.path.join(HERE, "..", "own_ratings", "out")
    z = own.zero(own.BT + own.KP)
    frames = {"base": frame(stage1=os.path.join(OWN, "stage1_base.csv"), tag="own_base"),
              "B4 last season x0.6, no outside": frame(stage1=os.path.join(OWN, "stage1_ownprior.csv"), tag="own_only", features=z),
              "R1 roster prior, no outside": frame(stage1=stage1("roster"), tag="rp_R1", features=z),
              "R2 roster prior + outside in stage 2": frame(stage1=stage1("roster"), tag="rp_R2"),
              "R3 blended prior + outside in stage 2": frame(stage1=stage1("blend"), tag="rp_R3")}
    acc, plays = own.final_tables(frames)
    pd.set_option("display.width", 250)
    for name, t in (("final_accuracy", acc), ("opener_plays", plays)):
        t.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
        say(f"\n== {name}\n{t.to_string(index=False)}")
    open(os.path.join(OUT, "step2.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("stage1", "score", "priors"):
    if sys.argv[1] == "priors":
        for s in range(FIRST + 1, 2027):
            _prior_cache(s); print("prior", s, flush=True)
    elif sys.argv[1] == "stage1":
        stage1(sys.argv[2])
    else:
        score()
