"""Roster-based preseason ratings, version 2 (PLAN_v2.md, pre-registered Nov 5, 2026). Research only.

    python -m research.roster_prior.build_v2 check            # step 1 -> out/v2_step1.txt
    python -m research.roster_prior.build_v2 stage1 <V2a|V2b> <prior|blend>
    python -m research.roster_prior.build_v2 score <V2a|V2b>  # step 2 -> out/v2_step2.txt
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd

from cbb import backtest, player_ratings as pr
from research.roster_prior import build as v1

OUT = v1.OUT
FIRST = v1.FIRST
MINMIN = 200.0
CBBD = os.path.join(os.path.dirname(__file__), "..", "..", "..", "cbb-data", "research", "player_impact")
RAPM_SEASONS = (2024, 2025, 2026)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


# ---------------------------------------------------------------- player seasons
def player_season(season: int) -> pd.DataFrame:
    """Per athlete: minutes, rate (shrunk value per 100 on-floor possessions), main team, that team's rate."""
    path = os.path.join(OUT, f"ps_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    p = pr.player_games(season)
    rate = pr.season_rates(season)
    by = p.groupby(["athlete_id", "team_id"])[["min", "value", "on_poss"]].sum().reset_index()
    team_rate = by.groupby("team_id").apply(lambda x: 100 * x["value"].sum() / x["on_poss"].sum())
    main = by.sort_values("min").groupby("athlete_id").tail(1).set_index("athlete_id")
    tot = by.groupby("athlete_id")["min"].sum()
    d = pd.DataFrame({"min": tot, "team_id": main["team_id"], "rate": rate.reindex(tot.index)})
    d["team_rate"] = d["team_id"].map(team_rate)
    d["season"] = season
    d.to_parquet(path)
    return d


def experience(season: int) -> pd.Series:
    """Number of seasons (2013..season) in which each athlete played, as of the end of `season`."""
    seen = pd.concat([player_season(s)[["min"]].assign(s=s) for s in range(2013, season + 1)])
    return seen.groupby(level=0)["s"].nunique()


def level(season: int) -> pd.Series:
    f = v1.final_ratings(season)
    return f["off"] + f["def"]


# ---------------------------------------------------------------- 3b: lineup ratings
def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def rapm(season: int) -> pd.Series:
    """Lineup-based rating (off + def per 100 possessions) per ESPN athlete id, full season, lambda 500."""
    path = os.path.join(OUT, f"rapm_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)["rapm"]
    from research.player_impact import ratings as R
    st, pg, _ = R.load(season)
    f = R.fit(st, 500.0, {})
    val = pd.Series({p: f["off"][p] + f["def"][p] for p in f["off"]})
    names = json.load(open(os.path.join(CBBD, f"players_{season}.json")))
    pg = pg.assign(name=pg["player"].map(lambda x: _norm(names.get(str(int(x)), [""])[0]) if pd.notna(x) else ""))
    box = pr.player_games(season)[["game_id", "team_id", "athlete_id", "athlete_display_name"]]
    box = box.assign(name=box["athlete_display_name"].map(_norm))
    m = pg.merge(box, on=["game_id", "team_id", "name"], how="inner")
    link = m.groupby("player")["athlete_id"].agg(lambda s: s.value_counts().index[0])
    out = pd.DataFrame({"rapm": val.reindex(link.index).to_numpy()}, index=pd.Index(link.to_numpy(), name="athlete_id"))
    out = out[~out.index.duplicated()].dropna()
    out.to_parquet(path)
    return out["rapm"]


def rapm_map() -> tuple[float, float]:
    """Box rate ~ a + b * lineup rating on 2024 player-seasons with 200+ minutes (PLAN_v2.md 3b)."""
    ps, r = player_season(2024), rapm(2024)
    j = ps[ps["min"] >= MINMIN].join(r, how="inner")
    b, a = np.polyfit(j["rapm"], j["rate"], 1)
    return float(a), float(b)


# ---------------------------------------------------------------- 1 and 2: development and transfer level
def dev_model(season: int) -> tuple[dict, float]:
    """(mean rate change by experience bucket for same-team returners, transfer level slope), from season pairs
    (s-1, s) with s < season."""
    rows = []
    for s in range(2014, season):
        a, b = player_season(s - 1), player_season(s)
        ex = experience(s - 1)
        j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j["min_a"] >= MINMIN) & (j["min_b"] >= MINMIN)]
        j["exp"] = ex.reindex(j.index).clip(upper=4)
        j["d"] = j["rate_b"] - j["rate_a"]
        j["moved"] = j["team_id_a"] != j["team_id_b"]
        lv = level(s - 1)
        j["dlev"] = j["team_id_b"].map(lv) - j["team_id_a"].map(lv)
        rows.append(j[["exp", "d", "moved", "dlev"]])
    j = pd.concat(rows)
    dev = j[~j["moved"]].groupby("exp")["d"].mean().to_dict()
    t = j[j["moved"]].dropna(subset=["dlev"])
    resid = t["d"] - t["exp"].map(dev)
    slope = float(np.polyfit(t["dlev"], resid, 1)[0]) if len(t) > 30 else 0.0
    return dev, slope


# ---------------------------------------------------------------- roster features v2
def roster_features(season: int, variant: str) -> pd.DataFrame:
    path = os.path.join(OUT, f"feat2{variant}_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    prev = player_season(season - 1)
    med = float(prev["rate"].median())
    ex = experience(season - 1)
    dev, slope = dev_model(season)
    lv = level(season - 1)
    rate = prev["rate"].copy()
    if variant == "V2b" and season - 1 in RAPM_SEASONS:
        a, b = rapm_map()
        rr = rapm(season - 1)
        rate = rate.where(~rate.index.isin(rr.index), (rate + a + b * rr.reindex(rate.index)) / 2)
    now = pr.player_games(season)
    ids5 = (now.drop_duplicates(["team_id", "game_id"]).sort_values(["team_id", "date", "game_id"])
            .groupby("team_id").head(5)[["team_id", "game_id"]])
    first5 = now.merge(ids5, on=["team_id", "game_id"])
    team_prev_min = prev.groupby("team_id")["min"].sum()
    rows = []
    for tid, g in first5.groupby("team_id"):
        roster = sorted(set(g["athlete_id"]))
        known = prev.reindex(roster).dropna(subset=["min"])
        known = known[known["min"] > 0]
        newc = [a for a in roster if a not in known.index]
        team_min = 200.0 * 30
        scale = min(1.0, team_min / known["min"].sum()) if len(known) else 1.0
        w = known["min"] * scale
        rest = max(team_min - w.sum(), 0.0)
        e = ex.reindex(known.index).clip(upper=4)
        moved = known["team_id"] != tid
        proj = rate.reindex(known.index) + e.map(dev).fillna(0.0)
        proj = proj + np.where(moved, slope * (lv.get(tid, 0.0) - known["team_id"].map(lv).fillna(0.0)), 0.0)
        wn = pd.Series(rest / len(newc), index=newc) if newc else pd.Series(dtype=float)
        W = pd.concat([w, wn])
        P = pd.concat([proj, pd.Series(med - pr.NEWCOMER, index=newc)]) if newc else proj
        tot = W.sum()
        lvl_w = (w * known["team_id"].map(lv).fillna(0.0)).sum() / tot if tot else 0.0
        rel_w = (w * (rate.reindex(known.index) - known["team_rate"])).sum() / tot if tot else 0.0
        ret = known.index[~moved]
        rows.append({"team_id": int(tid),
                     "strength": float((W * P.reindex(W.index)).sum() / tot - med) if tot else 0.0,
                     "ret_share": float(known.loc[ret, "min"].sum() / team_prev_min.get(tid, np.nan)) if team_prev_min.get(tid, 0) else 0.0,
                     "tr_share": float(w[moved].sum() / tot) if tot else 0.0,
                     "newc_share": float(wn.sum() / tot) if tot and newc else 0.0,
                     "lvl_w": float(lvl_w), "rel_w": float(rel_w)})
    f = pd.DataFrame(rows).set_index("team_id")
    f.to_parquet(path)
    return f


X2 = {k: v + ["lvl_w", "rel_w"] if k != "tempo" else v for k, v in v1.X.items()}


def design(season: int, variant: str) -> pd.DataFrame:
    prev, now, ro = v1.final_ratings(season - 1), v1.final_ratings(season), roster_features(season, variant)
    d = ro.join(prev.add_suffix("_prev"), how="inner").join(now.add_suffix("_now"), how="left")
    for c in ("off", "def", "tempo"):
        d[f"{c}_prev_x_ret"] = d[f"{c}_prev"] * d["ret_share"]
    d["season"] = season
    return d


def prior(season: int, variant: str, frames: dict | None = None) -> pd.DataFrame:
    frames = frames or {s: design(s, variant) for s in range(FIRST, season + 1)}
    train = pd.concat([frames[s] for s in range(FIRST, season)]).dropna(subset=["off_now", "def_now", "tempo_now"])
    d = frames[season]
    out = pd.DataFrame(index=d.index)
    for c, cols in X2.items():
        f = v1.ridge(train[cols].to_numpy(float), train[f"{c}_now"].to_numpy(float))
        out[c] = f(d[cols].to_numpy(float))
    return out - out.mean()


def _err(p: pd.DataFrame, fm: pd.Series, tier: pd.Series, t: str) -> dict:
    pm = (p["off"] + p["def"]).reindex(fm.index)
    pm = pm - pm.mean()
    m = pm.notna() & ((tier == t) if t != "all" else True)
    e = pm[m] - fm[m]
    return {"n": int(m.sum()), "sse": float((e ** 2).sum()), "corr": float(np.corrcoef(pm[m], fm[m])[0, 1])}


def check() -> None:
    os.makedirs(OUT, exist_ok=True)
    fr = {v: {s: design(s, v) for s in range(FIRST, 2027)} for v in ("V2a", "V2b")}
    fr1 = {s: v1.design(s) for s in range(FIRST, 2027)}
    rows = []
    for s in range(FIRST + 1, 2027):
        final = v1.final_ratings(s)
        fm = final["off"] + final["def"]
        tier = pd.qcut(level(s - 1).rank(method="first"), 3, labels=["low", "mid", "high"]).reindex(fm.index)
        for lab, p in (("(a) KenPom/Barttorvik", backtest.preseason_prior(s)), ("(c) roster v1", v1.roster_prior(s, fr1)),
                       ("(d) roster V2a", prior(s, "V2a", fr["V2a"])), ("(e) roster V2b", prior(s, "V2b", fr["V2b"]))):
            for t in ("all", "high", "mid", "low"):
                rows.append({"season": s, "prior": lab, "tier": t, **_err(p, fm, tier, t)})
    r = pd.DataFrame(rows)
    agg = lambda x: x.groupby(["prior", "tier"]).agg(n=("n", "sum"), sse=("sse", "sum"), corr=("corr", "mean")).assign(
        rmse=lambda d: np.sqrt(d["sse"] / d["n"]))[["n", "rmse", "corr"]].round(3)
    say("Version 2, step 1: priors vs the season's final margin rating, 2016-2026")
    t = agg(r)
    say(t.to_string())
    say("\n2025-2026 only (where V2b differs):")
    say(agg(r[r["season"].isin([2025, 2026])]).loc[(slice(None), "all"), :].to_string())
    dev, slope = dev_model(2026)
    say(f"\nDevelopment (rate change by earlier seasons, fit through 2025): { {k: round(v, 2) for k, v in dev.items()} }; "
        f"transfer level slope {slope:+.3f} per point of team margin")
    if os.path.exists(os.path.join(OUT, "rapm_2024.parquet")) or True:
        a, b = rapm_map()
        say(f"Lineup rating -> box scale (2024): rate = {a:.2f} + {b:.3f} x lineup rating")
    c1 = t.loc[("(c) roster v1", "all")]
    c2 = t.loc[("(d) roster V2a", "all")]
    go = (c2["corr"] - c1["corr"] >= 0.010) or (c1["rmse"] - c2["rmse"] >= 0.10)
    say(f"\nGate: V2a corr {c2['corr']:.3f} vs v1 {c1['corr']:.3f}; RMSE {c2['rmse']:.3f} vs {c1['rmse']:.3f} -> "
        f"{'GO to step 2' if go else 'STOP'}")
    open(os.path.join(OUT, "v2_step1.txt"), "w").write("\n".join(L) + "\n")
    r.to_csv(os.path.join(OUT, "v2_step1.csv"), index=False)


# ---------------------------------------------------------------- step 2
def _cached(season: int, variant: str) -> pd.DataFrame | None:
    if season < FIRST + 1:
        return None
    path = os.path.join(OUT, f"prior2{variant}_{season}.parquet")
    if not os.path.exists(path):
        prior(season, variant).to_parquet(path)
    return pd.read_parquet(path)


def stage1(variant: str, mode: str) -> str:
    path = os.path.join(OUT, f"stage1_{variant}_{mode}.csv")
    if os.path.exists(path):
        return path

    def fn(season):
        p, cur = _cached(season, variant), v1._ORIG_PRIOR(season)
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
            print(variant, mode, s, flush=True)
        pd.concat(parts).to_csv(path, index=False)
    finally:
        backtest.preseason_prior = v1._ORIG_PRIOR
    return path


def score(variant: str) -> None:
    from audit.common import frame
    from research.own_ratings import run as own
    OWN = os.path.join(os.path.dirname(__file__), "..", "own_ratings", "out")
    z = own.zero(own.BT + own.KP)
    frames = {"base": frame(stage1=os.path.join(OWN, "stage1_base.csv"), tag="own_base"),
              "R1 v1 roster prior, no outside": frame(stage1=v1.stage1("roster"), tag="rp_R1", features=z),
              f"R1v2 {variant} prior, no outside": frame(stage1=stage1(variant, "prior"), tag=f"rp2_{variant}_R1", features=z),
              f"R3v2 {variant} blended prior + outside": frame(stage1=stage1(variant, "blend"), tag=f"rp2_{variant}_R3")}
    acc, plays = own.final_tables(frames)
    pd.set_option("display.width", 250)
    for name, t in (("v2_final_accuracy", acc), ("v2_opener_plays", plays)):
        t.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
        say(f"\n== {name}\n{t.to_string(index=False)}")
    open(os.path.join(OUT, "v2_step2.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "priors":
        for s in range(FIRST + 1, 2027):
            _cached(s, sys.argv[2]); print("prior", s, flush=True)
    elif cmd == "stage1":
        stage1(sys.argv[2], sys.argv[3])
    else:
        score(sys.argv[2])
