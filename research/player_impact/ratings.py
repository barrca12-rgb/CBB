"""Player-impact ratings (weekly walk-forward ridge on lineup stints) and the absence term J (PLAN.md).

    python -m research.player_impact.ratings          # -> ../cbb-data/research/player_impact/features_<variant>.parquet
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import cg

from cbb import data

DATA = Path(__file__).resolve().parents[3] / "cbb-data" / "research" / "player_impact"
OUT = Path(__file__).resolve().parent / "out"
SEASONS = [2024, 2025, 2026]
LAMS = [500.0, 1000.0, 2000.0, 4000.0]
RHOS = [0.0, 0.5]
REGULAR_GAMES, BENCH_SHARE = 3, 0.10


def games(season: int) -> pd.DataFrame:
    g, _ = data.season_games(season)
    return g[["game_id", "date", "home_id", "away_id", "neutral", "home_pts", "away_pts"]]


def load(season: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Stints and player-game seconds for one season, each game once (a game can appear in two UTC-date pulls),
    joined to the ESPN schedule (date, team ids, neutral) with home/away checked against the final score."""
    d = DATA / "stints" / str(season)
    st = pd.concat([pd.read_parquet(f).assign(pull=f.stem) for f in sorted(d.glob("????-??-??.parquet")) if os.path.getsize(f) > 0], ignore_index=True)
    pg = pd.concat([pd.read_parquet(f).assign(pull=f.stem[:10]) for f in sorted(d.glob("*_players.parquet")) if os.path.getsize(f) > 0], ignore_index=True)
    # a game can be returned by two consecutive date pulls: keep it from one pull only (the one with more stints)
    size = st.groupby(["cbbd_game_id", "pull"]).size().rename("n").reset_index().sort_values(["n", "pull"]).drop_duplicates("cbbd_game_id", keep="last")
    st = st.merge(size[["cbbd_game_id", "pull"]], on=["cbbd_game_id", "pull"])
    pg = pg.merge(size[["cbbd_game_id", "pull"]], on=["cbbd_game_id", "pull"])
    g = games(season).set_index("game_id")
    st = st[st["game_id"].isin(g.index)].copy()
    tot = st.groupby("game_id")[["home_pts", "away_pts"]].sum()
    gg = g.loc[tot.index]
    TOL = 3                                   # play-by-play finals can differ from the official score by a point or two
    same = ((tot["home_pts"] - gg["home_pts"]).abs() <= TOL) & ((tot["away_pts"] - gg["away_pts"]).abs() <= TOL)
    flip = ((tot["home_pts"] - gg["away_pts"]).abs() <= TOL) & ((tot["away_pts"] - gg["home_pts"]).abs() <= TOL) & ~same
    exact = (tot["home_pts"] == gg["home_pts"]) & (tot["away_pts"] == gg["away_pts"])
    info = {"games_schedule": len(g), "games_with_stints": int(len(tot)), "final_exact": int(exact.sum()),
            "final_within_3": int(same.sum()), "final_flipped": int(flip.sum()), "final_mismatch": int((~same & ~flip).sum())}
    bad = tot.index[~same & ~flip]
    st = st[~st["game_id"].isin(bad)].copy()             # games whose stints don't add up are not used
    st["flip"] = st["game_id"].map(flip)
    st["espn_date"] = st["game_id"].map(g["date"])
    st["neutral"] = st["game_id"].map(g["neutral"]).astype(bool)
    # ESPN team ids for CBBD home/away (swapped where CBBD's home is ESPN's away)
    st["home_id"] = np.where(st["flip"], st["game_id"].map(g["away_id"]), st["game_id"].map(g["home_id"]))
    st["away_id"] = np.where(st["flip"], st["game_id"].map(g["home_id"]), st["game_id"].map(g["away_id"]))
    team_of = pd.concat([st[["game_id", "home", "home_id"]].set_axis(["game_id", "team", "team_id"], axis=1),
                         st[["game_id", "away", "away_id"]].set_axis(["game_id", "team", "team_id"], axis=1)]).drop_duplicates()
    pg = pg.merge(team_of, on=["game_id", "team"], how="inner")
    pg["espn_date"] = pg["game_id"].map(g["date"])
    return st, pg, info


def design(st: pd.DataFrame, idx: dict) -> tuple[sp.csr_matrix, np.ndarray, np.ndarray]:
    """Rows: each stint twice (home offense, away offense). Columns: [mu, home, offense(players), defense(players)]."""
    k = len(idx)
    rows, cols, vals, y, w = [], [], [], [], []
    hp = [f"h{i}" for i in range(6) if f"h{i}" in st]
    ap = [f"a{i}" for i in range(6) if f"a{i}" in st]
    H = st[hp].to_numpy(float)
    A = st[ap].to_numpy(float)
    r = 0
    for side in ("home", "away"):
        O, Dm = (H, A) if side == "home" else (A, H)
        no, nd = (st["nh"], st["na"]) if side == "home" else (st["na"], st["nh"])
        poss = st[f"{side}_poss"].to_numpy(float)
        pts = st[f"{side}_pts"].to_numpy(float)
        venue = np.where(st["neutral"], 0.0, 1.0 if side == "home" else -1.0)
        venue = np.where(st["flip"] & ~st["neutral"], -venue, venue)
        ok = poss >= 0.5
        for i in np.where(ok)[0]:
            rows += [r, r]
            cols += [0, 1]
            vals += [1.0, venue[i]]
            for p in O[i][~np.isnan(O[i])]:
                rows.append(r); cols.append(2 + idx[int(p)]); vals.append(5.0 / no.iat[i])
            for p in Dm[i][~np.isnan(Dm[i])]:
                rows.append(r); cols.append(2 + k + idx[int(p)]); vals.append(-5.0 / nd.iat[i])
            y.append(100.0 * pts[i] / poss[i])
            w.append(poss[i])
            r += 1
    X = sp.csr_matrix((vals, (rows, cols)), shape=(r, 2 + 2 * k))
    return X, np.array(y), np.array(w)


def fit(st: pd.DataFrame, lam: float, prior: dict[int, tuple[float, float]], x0=None):
    players = sorted({int(p) for c in st.columns if c[:1] in "ha" and c[1:].isdigit() for p in st[c].dropna()})
    idx = {p: i for i, p in enumerate(players)}
    k = len(players)
    X, y, w = design(st, idx)
    b0 = np.zeros(2 + 2 * k)
    b0[0] = np.average(y, weights=w)
    for p, i in idx.items():
        if p in prior:
            b0[2 + i], b0[2 + k + i] = prior[p]
    pen = np.full(2 + 2 * k, lam)
    pen[:2] = 1e-3
    Xw = X.multiply(w[:, None]).tocsr()
    Amat = (X.T @ Xw + sp.diags(pen)).tocsr()
    rhs = Xw.T @ y + pen * b0
    b, _ = cg(Amat, rhs, x0=x0 if x0 is not None and len(x0) == len(rhs) else b0, rtol=1e-8, maxiter=3000)
    off = dict(zip(players, b[2:2 + k]))
    dfn = dict(zip(players, b[2 + k:]))
    return {"mu": b[0], "home": b[1], "off": off, "def": dfn}


def mondays(dates: pd.Series) -> list[pd.Timestamp]:
    d0, d1 = pd.Timestamp(dates.min()), pd.Timestamp(dates.max())
    m = d0 - pd.Timedelta(days=d0.weekday())
    out = []
    while m <= d1:
        out.append(m)
        m += pd.Timedelta(days=7)
    return out


def absence_features(season: int, st: pd.DataFrame, pg: pd.DataFrame, fits: dict[pd.Timestamp, dict]) -> pd.DataFrame:
    """Per ESPN game: D_home, D_away (excess impact lost, per 100 possessions) and coverage flags."""
    g = games(season).sort_values("date")
    full = data.fetch("schedule", season)          # every completed game, D-I opponent or not
    full = full[full["status_type_completed"].fillna(False).astype(bool)].drop_duplicates("game_id")
    full = pd.DataFrame({"game_id": full["game_id"].astype(int), "date": pd.to_datetime(full["game_date"]),
                         "home_id": full["home_id"].astype(int), "away_id": full["away_id"].astype(int)})
    sched = pd.concat([full[["game_id", "date", "home_id"]].rename(columns={"home_id": "team_id"}),
                       full[["game_id", "date", "away_id"]].rename(columns={"away_id": "team_id"})]).sort_values("date")
    sched_by_team = {t: x for t, x in sched.groupby("team_id")}
    team_secs = pg.groupby(["team_id", "game_id"])["secs"].sum() / 5.0     # floor seconds per team-game
    by_team = {t: x.sort_values("espn_date") for t, x in pg.groupby("team_id")}
    game_dates = pg.drop_duplicates(["team_id", "game_id"])[["team_id", "game_id", "espn_date"]]
    hist: dict[int, list[float]] = {}
    rows = []
    for _, r in g.iterrows():
        D = r["date"]
        T = max(t for t in fits if t <= D) if any(t <= D for t in fits) else None
        f = fits.get(T)
        out = {"game_id": r["game_id"], "cutoff": T}
        for side in ("home", "away"):
            team = r[f"{side}_id"]
            x = by_team.get(team)
            prior_games = game_dates[(game_dates["team_id"] == team) & (game_dates["espn_date"] < D)].sort_values("espn_date")
            val, vo, vd, known = 0.0, 0.0, 0.0, False
            sx = sched_by_team.get(team)
            last_sched = sx.loc[sx["date"] < D, "game_id"] if sx is not None else pd.Series(dtype=int)
            # status needs the team's actual last scheduled game in the play-by-play data
            if x is not None and len(last_sched) and f is not None and last_sched.iloc[-1] in set(prior_games["game_id"]):
                last = last_sched.iloc[-1]
                h = x[x["espn_date"] < D]
                gp = h.groupby("player")["game_id"].nunique()
                secs = h.groupby("player")["secs"].sum()
                tsec = team_secs.loc[team].loc[prior_games["game_id"]].sum()
                played_last = set(h.loc[(h["game_id"] == last) & (h["secs"] > 0), "player"])
                regs = [p for p in gp.index if gp[p] >= REGULAR_GAMES]
                rr = {p: f["off"].get(int(p), 0.0) + f["def"].get(int(p), 0.0) for p in regs}
                miss = [p for p in regs if p not in played_last] if tsec > 0 else []
                val = sum((secs[p] / tsec) * (rr[p] - f["rep"]) for p in miss)
                vo = sum((secs[p] / tsec) * (f["off"].get(int(p), 0.0) - f["rep_off"]) for p in miss)
                vd = sum((secs[p] / tsec) * (f["def"].get(int(p), 0.0) - f["rep_def"]) for p in miss)
                known = True
            past = hist.setdefault(team, [])
            exc = val - (np.mean(past) if past else 0.0)
            if known:
                past.append(val)
            out[f"D_{side}"], out[f"known_{side}"] = (exc if known else 0.0), known
            out[f"DO_{side}"], out[f"DD_{side}"] = (vo, vd) if known else (0.0, 0.0)   # raw (not excess), descriptive totals
        rows.append(out)
    return pd.DataFrame(rows)


def run_variant(lam: float, rho: float, data_by_season: dict) -> pd.DataFrame:
    feats, prev_final = [], {}
    for season in SEASONS:
        if season not in data_by_season:
            continue
        st, pg, _ = data_by_season[season]
        prior = {p: (rho * prev_final["off"].get(p, 0.0), rho * prev_final["def"].get(p, 0.0)) for p in prev_final.get("off", {})} if rho else {}
        fits, x0 = {}, None
        for T in mondays(st["espn_date"]):
            s = st[st["espn_date"] < T]
            if not len(s):
                continue
            f = fit(s, lam, prior)
            share = pg[pg["espn_date"] < T].groupby("player")["secs"].sum() / (pg[pg["espn_date"] < T].groupby("team_id")["secs"].sum().mean())
            # replacement: possession-weighted mean net rating of players with < 10% of team minutes (share of 5 spots)
            mins = pg[pg["espn_date"] < T].groupby(["team_id", "player"])["secs"].sum()
            tm = pg[pg["espn_date"] < T].groupby("team_id")["secs"].sum()
            frac = (mins / mins.index.get_level_values(0).map(tm).to_numpy() * 5)
            bench = [int(p) for (t, p), v in frac.items() if v < BENCH_SHARE]
            net = np.array([f["off"].get(p, 0.0) + f["def"].get(p, 0.0) for p in bench])
            wts = np.array([mins.xs(p, level=1).sum() for p in bench])
            ok = len(bench) and wts.sum() > 0
            f["rep"] = float(np.average(net, weights=wts)) if ok else 0.0
            f["rep_off"] = float(np.average([f["off"].get(p, 0.0) for p in bench], weights=wts)) if ok else 0.0
            f["rep_def"] = float(np.average([f["def"].get(p, 0.0) for p in bench], weights=wts)) if ok else 0.0
            fits[T] = f
        fe = absence_features(season, st, pg, fits)
        fe["season"] = season
        feats.append(fe)
        final = fit(st, lam, prior)
        prev_final = final
    out = pd.concat(feats, ignore_index=True)
    out["lam"], out["rho"] = lam, rho
    return out


def main(seasons=None) -> None:
    import sys
    OUT.mkdir(exist_ok=True)
    seasons = seasons or [int(x) for x in sys.argv[1:]] or SEASONS
    dbs = {s: load(s) for s in seasons}
    info = {s: v[2] for s, v in dbs.items()}
    print(json.dumps(info, indent=1))
    for lam in LAMS:
        for rho in RHOS:
            fe = run_variant(lam, rho, dbs)
            fe.to_parquet(DATA / f"features_lam{int(lam)}_rho{rho}.parquet", index=False)
            print(lam, rho, len(fe), flush=True)


if __name__ == "__main__":
    main()
