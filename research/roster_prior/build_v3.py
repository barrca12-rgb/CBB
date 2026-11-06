"""Roster-based preseason ratings, version 3 (PLAN_v3.md, pre-registered Nov 6, 2026). Research only.

    python -m research.roster_prior.build_v3 check                 # steps 0 and 1 -> out/v3_step1.txt
    python -m research.roster_prior.build_v3 stage1 <V3a|V3b> <prior|blend>
    python -m research.roster_prior.build_v3 score <V3a|V3b>       # step 2 -> out/v3_step2.txt
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from cbb import backtest, player_ratings as pr
from research.roster_prior import build as v1
from research.roster_prior import build_v2 as v2

OUT = v1.OUT
LINEUP = (2024, 2025, 2026)
LAM = 500.0
MIN_POSS = 300.0
SHRINK = 150.0
STATS = {"pts": "points", "fga2": None, "fga3": "three_point_field_goals_attempted", "fta": "free_throws_attempted",
         "oreb": "offensive_rebounds", "dreb": "defensive_rebounds", "ast": "assists", "stl": "steals",
         "blk": "blocks", "tov": "turnovers", "pf": "fouls"}
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


# ---------------------------------------------------------------- box rates
def box(season: int) -> pd.DataFrame:
    """Per athlete for one season: stat totals, on-floor possessions, minutes, main team."""
    path = os.path.join(OUT, f"v3box_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    p = pr.player_games(season)
    num = lambda c: pd.to_numeric(p[c], errors="coerce").fillna(0)
    d = pd.DataFrame({"athlete_id": p["athlete_id"], "team_id": p["team_id"], "min": p["min"], "on_poss": p["on_poss"]})
    for k, c in STATS.items():
        d[k] = (num("field_goals_attempted") - num("three_point_field_goals_attempted")) if k == "fga2" else num(c)
    by = d.groupby(["athlete_id", "team_id"]).sum().reset_index()
    main = by.sort_values("min").groupby("athlete_id")["team_id"].last()
    tot = by.drop(columns="team_id").groupby("athlete_id").sum()
    tot["team_id"] = main
    tot.to_parquet(path)
    return tot


def rates(b: pd.DataFrame) -> pd.DataFrame:
    return b[list(STATS)].div(b["on_poss"].clip(lower=1), axis=0) * 100


# ---------------------------------------------------------------- lineup ratings (CBBD stints)
def _link(season: int) -> pd.Series:
    """CBBD player id -> ESPN athlete id for one season (name match within games)."""
    from research.player_impact import ratings as R
    _, pg, _ = R.load(season)
    names = json.load(open(os.path.join(v2.CBBD, f"players_{season}.json")))
    pg = pg.assign(name=pg["player"].map(lambda x: v2._norm(names.get(str(int(x)), [""])[0]) if pd.notna(x) else ""))
    bx = pr.player_games(season)[["game_id", "team_id", "athlete_id", "athlete_display_name"]]
    bx = bx.assign(name=bx["athlete_display_name"].map(v2._norm))
    m = pg.merge(bx, on=["game_id", "team_id", "name"], how="inner")
    return m.groupby("player")["athlete_id"].agg(lambda s: s.value_counts().index[0])


def lineup(seasons: tuple, prior_vals: dict | None = None, tag: str = "") -> pd.DataFrame:
    """Lineup ridge on the stints of `seasons` (one fit); off/def per ESPN athlete. prior_vals: ESPN id ->
    (off, def) starting points (xRAPM-style); None = zero."""
    path = os.path.join(OUT, f"v3lineup_{'-'.join(map(str, seasons))}{tag}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    from research.player_impact import ratings as R
    st = pd.concat([R.load(s)[0] for s in seasons], ignore_index=True)
    link = pd.concat([_link(s) for s in seasons])
    link = link[~link.index.duplicated(keep="last")]
    prior = {}
    if prior_vals:
        inv = {e: c for c, e in link.items()}
        prior = {int(inv[e]): v for e, v in prior_vals.items() if e in inv}
    f = R.fit(st, LAM, prior)
    out = pd.DataFrame({"off": pd.Series(f["off"]), "def": pd.Series(f["def"])})
    out.index = out.index.map(lambda c: link.get(c))
    out = out[out.index.notna()]
    out = out[~out.index.duplicated()]
    out.index = out.index.astype(int)
    out.index.name = "athlete_id"
    out.to_parquet(path)
    return out


# ---------------------------------------------------------------- learned weights
def spm(seasons: tuple):
    """Ridge of lineup off and def ratings on box rates, players with MIN_POSS+ possessions in `seasons`."""
    lu = lineup(seasons)
    b = pd.concat([box(s) for s in seasons]).groupby(level=0).sum(numeric_only=True)
    j = rates(b).join(lu, how="inner")
    w = b["on_poss"].reindex(j.index)
    keep = w >= MIN_POSS
    X, W = j.loc[keep, list(STATS)].to_numpy(float), w[keep].to_numpy(float)
    mu, sd = np.average(X, axis=0, weights=W), X.std(0) + 1e-9
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    pen = np.eye(Z.shape[1]); pen[0, 0] = 0
    coef = {}
    for c in ("off", "def"):
        y = j.loc[keep, c].to_numpy(float)
        coef[c] = np.linalg.solve(Z.T @ (Z * W[:, None]) + pen, Z.T @ (W * y))
    def f(R_: pd.DataFrame) -> pd.DataFrame:
        Zn = np.column_stack([np.ones(len(R_)), (R_[list(STATS)].to_numpy(float) - mu) / sd])
        return pd.DataFrame({c: Zn @ coef[c] for c in ("off", "def")}, index=R_.index)
    f.coef, f.mu, f.sd = coef, mu, sd
    return f


_SPM: dict = {}


def weights_for(season: int):
    """Walk-forward weights for player values of `season` (PLAN_v3.md)."""
    use = tuple(s for s in LINEUP if s <= season) or LINEUP
    if use not in _SPM:
        _SPM[use] = spm(use)
    return _SPM[use]


def box_value(season: int) -> pd.DataFrame:
    """Per athlete: learned-weight value (off, def, total), shrunk toward the league median by SHRINK possessions."""
    b = box(season)
    v = weights_for(season)(rates(b))
    v["total"] = v["off"] + v["def"]
    med = float(v["total"].median())
    poss = b["on_poss"]
    v["total_shrunk"] = (v["total"] * poss + med * SHRINK) / (poss + SHRINK)
    return v


# ---------------------------------------------------------------- player seasons on the new scale
def player_season_v3(season: int, variant: str) -> pd.DataFrame:
    path = os.path.join(OUT, f"ps3{variant}_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    b, v = box(season), box_value(season)
    rate = v["total_shrunk"]
    if variant == "V3b" and season in LINEUP:
        prior_vals = {int(a): (float(o), float(d_)) for a, o, d_ in zip(v.index, v["off"], v["def"])}
        x = lineup((season,), prior_vals, tag=f"_x{season}")
        xr = (x["off"] + x["def"])
        a_, b_ = xmap()
        rate = rate.where(~rate.index.isin(xr.index), a_ + b_ * xr.reindex(rate.index))
    team_rate = (rate * b["on_poss"]).groupby(b["team_id"]).sum() / b["on_poss"].groupby(b["team_id"]).sum()
    d = pd.DataFrame({"min": b["min"], "team_id": b["team_id"], "rate": rate})
    d["team_rate"] = d["team_id"].map(team_rate)
    d["season"] = season
    d.to_parquet(path)
    return d


_XMAP = None


def xmap() -> tuple[float, float]:
    """V3a box value ~ a + b * xRAPM rating on 2024 player seasons with 300+ possessions."""
    global _XMAP
    if _XMAP is None:
        v = box_value(2024)
        prior_vals = {int(a): (float(o), float(d_)) for a, o, d_ in zip(v.index, v["off"], v["def"])}
        x = lineup((2024,), prior_vals, tag="_x2024")
        j = v.join((x["off"] + x["def"]).rename("x"), how="inner")
        j = j[box(2024)["on_poss"].reindex(j.index) >= MIN_POSS]
        b_, a_ = np.polyfit(j["x"], j["total_shrunk"], 1)
        _XMAP = (float(a_), float(b_))
    return _XMAP


def use(variant: str) -> None:
    """Point version 2's machinery (development, transfer level, roster features) at the v3 player values."""
    v2.player_season = (lambda s: player_season_v3(s, variant)) if variant in ("V3a", "V3b") else v2._PS_ORIG


v2._PS_ORIG = v2.player_season


# ---------------------------------------------------------------- step 0 and 1
def step0() -> None:
    f = spm((2024, 2025))
    test = lineup((2026,))
    b = box(2026)
    j = rates(b).join(test, how="inner")
    w = b["on_poss"].reindex(j.index)
    j = j[w >= MIN_POSS]
    w = w[j.index]
    y = j["off"] + j["def"]
    pred = f(j).sum(axis=1)
    gs = pr.season_rates(2026).reindex(j.index)
    wc = lambda a, b_: float(np.cov(a, b_, aweights=w)[0, 1] / np.sqrt(np.cov(a, a, aweights=w)[0, 1] * np.cov(b_, b_, aweights=w)[0, 1]))
    say("Step 0: predicting 2026 lineup ratings (players with 300+ possessions, possession-weighted correlation)")
    say(f"  learned weights (fit on 2024-2025): {wc(pred, y):.3f}   Game Score fixed weights: {wc(gs.fillna(gs.median()), y):.3f}   players {len(j)}")
    full = weights_for(2026)
    names = list(STATS)
    say("  learned weights, 2024-2026, points per 100 possessions per unit of each stat per 100 (off / def):")
    for c in ("off", "def"):
        say(f"    {c}: " + ", ".join(f"{n} {k / s:+.3f}" for n, k, s in zip(names, full.coef[c][1:], full.sd)))


def check() -> None:
    os.makedirs(OUT, exist_ok=True)
    step0()
    frames = {}
    for var in ("V2a", "V3a", "V3b"):
        use(var)
        frames[var] = {s: v2.design(s, var) for s in range(v1.FIRST, 2027)}
    use("V2a")
    rows = []
    for s in range(v1.FIRST + 1, 2027):
        final = v1.final_ratings(s)
        fm = final["off"] + final["def"]
        tier = pd.qcut(v2.level(s - 1).rank(method="first"), 3, labels=["low", "mid", "high"]).reindex(fm.index)
        for lab, var in (("(d) roster V2a", "V2a"), ("(f) roster V3a", "V3a"), ("(g) roster V3b", "V3b")):
            use(var)
            p = v2.prior(s, var, frames[var])
            for t in ("all", "high", "mid", "low"):
                rows.append({"season": s, "prior": lab, "tier": t, **v2._err(p, fm, tier, t)})
        p = backtest.preseason_prior(s)
        for t in ("all", "high", "mid", "low"):
            rows.append({"season": s, "prior": "(a) KenPom/Barttorvik", "tier": t, **v2._err(p, fm, tier, t)})
    use("V2a")
    r = pd.DataFrame(rows)
    agg = lambda x: x.groupby(["prior", "tier"]).agg(n=("n", "sum"), sse=("sse", "sum"), corr=("corr", "mean")).assign(
        rmse=lambda d: np.sqrt(d["sse"] / d["n"]))[["n", "rmse", "corr"]].round(3)
    t = agg(r)
    say("\nStep 1: priors vs the season's final margin rating, 2016-2026")
    say(t.to_string())
    say("\n2025-2026 only (where V3b differs):")
    say(agg(r[r["season"].isin([2025, 2026])]).loc[(slice(None), "all"), :].to_string())
    say("\nBy season (correlation):")
    say(r[r["tier"] == "all"].pivot(index="season", columns="prior", values="corr").round(3).to_string())
    a, b = t.loc[("(d) roster V2a", "all")], t.loc[("(f) roster V3a", "all")]
    go = (b["corr"] - a["corr"] >= 0.010) or (a["rmse"] - b["rmse"] >= 0.10)
    say(f"\nGate: V3a corr {b['corr']:.3f} vs V2a {a['corr']:.3f}; RMSE {b['rmse']:.3f} vs {a['rmse']:.3f} -> "
        f"{'GO to step 2' if go else 'STOP'}")
    open(os.path.join(OUT, "v3_step1.txt"), "w").write("\n".join(L) + "\n")
    r.to_csv(os.path.join(OUT, "v3_step1.csv"), index=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "stage1":
        use(sys.argv[2])
        v2.stage1(sys.argv[2], sys.argv[3])
    elif cmd == "score":
        use(sys.argv[2])
        v2.score(sys.argv[2])
