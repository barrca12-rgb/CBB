"""Stage-1 ratings with game-state-weighted inputs (research only; PLAN.md).

The production stage 1 (cbb/ratings.fit) fits, by decayed ridge toward the preseason prior,

    ppp  (points per 100 possessions, 3-point luck regressed) = b0 + hca*venue + off[team] - def[opp]
    pace (possessions per 40 minutes)                          = p0 + tempo[team] + tempo[opp]

on every possession of every earlier game, equally. Here each possession gets a weight from the game state before
it, and each team-game's ppp and pace targets move by (weighted - unweighted) play-by-play value:

    D   = 2 * Phi(|margin| / (SIGMA * sqrt(max(tau, 1) / 2400))) - 1      how decided the game is (0 = level, ->1 = over)
    w   = 1 - alpha * D**kappa                                             smooth down-weighting, alpha = 0 is none
    ppp_adj  = ppp  + (100 * sum(w * pts) / sum(w)        - 100 * sum(pts) / n)       per team-game (offense)
    pace_adj = pace + (2400 * sum(w) / (2 * sum(w * dur)) - 2400 * n / (2 * sum(dur))) per game, both teams

Games without valid play-by-play keep their production targets (delta 0). The ratings are then fit exactly as
production does (same decay, prior, league averages, penalties), solving all variants at once (same matrices).

Strength vs settled score: the adjusted fit gives hca, off, def and tempo (strength in context-neutral play). The
level terms b0 and p0 are kept from the unadjusted fit, so the forecast stays on the full-game scale that already
includes average late-game fouling; overtime enters as before (pace per 40 minutes, stage 2's intercept). Output:
pred_margin and pred_total per variant, and their difference from the unadjusted run (`d_margin`, `d_total`), which
is added to the baseline frames' stage-1 inputs.

    OMP_NUM_THREADS=1 python -m research.game_state.stage1 <lag> [seasons...]   # -> out/s1_lag<lag>_<season>.parquet
"""
from __future__ import annotations

import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy.stats import norm

from cbb import backtest, data, ratings

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
SIGMA = 11.0
# (name, alpha, kappa); "foul" = weight 0 on inferred late-game fouling possessions only
VARIANTS = [("none", 0.0, 0.0)] + [(f"k{k}_a{a:g}", a, k) for k in (2.0, 8.0) for a in (0.25, 0.5, 0.75, 1.0)] + [("foul", 0.0, 0.0)]


def decided(margin, tau) -> np.ndarray:
    z = np.abs(margin) / (SIGMA * np.sqrt(np.maximum(tau, 1.0) / 2400.0))
    return 2 * norm.cdf(z) - 1


def weights(P: pd.DataFrame, name: str, alpha: float, kappa: float) -> np.ndarray:
    if name == "foul":
        return np.where(P["late_foul"], 0.0, 1.0)
    return 1.0 - alpha * decided(P["margin"].to_numpy(float), P["tau"].to_numpy(float)) ** kappa if alpha else np.ones(len(P))


def deltas(season: int) -> pd.DataFrame:
    """Per team-game (game_id, team_id): ppp and pace deltas for every variant, 0 where play-by-play is not valid."""
    P = pd.read_parquet(os.path.join(OUT, f"poss_{season}.parquet"))
    G = pd.read_parquet(os.path.join(OUT, f"games_{season}.parquet"))
    P = P[P["game_id"].isin(G.loc[G["valid"], "game_id"])].copy()
    P["one"] = 1.0
    out = None
    for name, a, k in VARIANTS:
        w = weights(P, name, a, k)
        P["w"], P["wp"], P["wd"], P["d1"] = w, w * P["pts"], w * P["dur"], P["dur"]
        off = P.groupby(["game_id", "offense"])[["w", "wp", "one", "pts"]].sum()
        ppp_d = 100 * off["wp"] / off["w"] - 100 * off["pts"] / off["one"]
        gm = P.groupby("game_id")[["w", "wd", "one", "d1"]].sum()
        pace_d = 1200 * gm["w"] / gm["wd"] - 1200 * gm["one"] / gm["d1"]
        d = ppp_d.rename(f"ppp_{name}").reset_index().rename(columns={"offense": "team_id"})
        d[f"pace_{name}"] = d["game_id"].map(pace_d)
        out = d if out is None else out.merge(d, on=["game_id", "team_id"], how="outer")
    return out


def run(args) -> pd.DataFrame:
    season, lag = args
    g, t = data.season_games(season)
    dl = deltas(season)
    t = t.merge(dl, on=["game_id", "team_id"], how="left")
    names = [v[0] for v in VARIANTS]
    for nm in names:
        t[f"ppp_{nm}"] = t["ppp"] + t[f"ppp_{nm}"].fillna(0.0)
        t[f"pace_{nm}"] = t["pace"] + t[f"pace_{nm}"].fillna(0.0)
    ids = sorted(set(t["team_id"]))
    pr = backtest.preseason_prior(season)
    league = {**ratings.DEFAULT_LEAGUE, **ratings.league_averages(data.season_games(season - 1)[1])}
    cfg = ratings.RatingConfig()
    k = len(ids)
    idx = pd.Series(np.arange(k), index=ids)
    prr = pr.reindex(ids).reindex(columns=["off", "def", "tempo"]).fillna(0.0)
    rows = []
    for day, gd in g.groupby("date"):
        asof = pd.Timestamp(day) - pd.Timedelta(days=lag)
        h = t[(t["date"] < asof) & t["team_id"].isin(idx.index) & t["opp_id"].isin(idx.index)]
        n = len(h)
        hi, ai = idx.reindex(gd["home_id"]).to_numpy(), idx.reindex(gd["away_id"]).to_numpy()
        v = np.where(gd["neutral"].to_numpy(bool), 0.0, 1.0)
        res = {}
        if n:
            ti, oi = idx[h["team_id"]].to_numpy(), idx[h["opp_id"]].to_numpy()
            days = (asof - h["date"]).dt.days.to_numpy()
            w = 0.5 ** (days / cfg.half_life)
            wbar = w.mean()
            r_ = np.arange(n)
            X = np.zeros((n, 2 + 2 * k))
            X[:, 0], X[:, 1] = 1.0, h["venue"].to_numpy()
            X[r_, 2 + ti] = 1.0
            X[r_, 2 + k + oi] = -1.0
            lam = np.full(2 + 2 * k, cfg.prior_games * wbar)
            lam[0], lam[1] = 1e-6, 20 * wbar
            XtW = X.T * w
            A = XtW @ X + np.diag(lam)
            Y = np.column_stack([h[f"ppp_{nm}"].to_numpy(float) for nm in names])
            B0 = np.column_stack([np.concatenate([[Y[:, j].mean(), cfg.hca_prior], prr["off"], prr["def"]]) for j in range(len(names))])
            Bs = np.linalg.solve(A, XtW @ Y + lam[:, None] * B0)
            Pm = np.zeros((n, 1 + k))
            Pm[:, 0] = 1.0
            Pm[r_, 1 + ti] += 1.0
            Pm[r_, 1 + oi] += 1.0
            lamp = np.full(1 + k, cfg.pace_prior_games * wbar)
            lamp[0] = 1e-6
            PtW = Pm.T * w
            Ap = PtW @ Pm + np.diag(lamp)
            YP = np.column_stack([h[f"pace_{nm}"].to_numpy(float) for nm in names])
            P0 = np.column_stack([np.concatenate([[YP[:, j].mean()], prr["tempo"]]) for j in range(len(names))])
            Bp = np.linalg.solve(Ap, PtW @ YP + lamp[:, None] * P0)
        else:
            Bs = np.tile(np.concatenate([[league["ppp"], cfg.hca_prior], prr["off"], prr["def"]])[:, None], (1, len(names)))
            Bp = np.tile(np.concatenate([[league["pace"]], prr["tempo"]])[:, None], (1, len(names)))
        b0, p0 = Bs[0, 0], Bp[0, 0]                      # level from the unadjusted fit (variant "none")
        for j, nm in enumerate(names):
            b, bp = Bs[:, j], Bp[:, j]
            poss = p0 + bp[1 + hi] + bp[1 + ai]
            hp = b0 + b[1] * v + b[2 + hi] - b[2 + k + ai]
            ap = b0 - b[1] * v + b[2 + ai] - b[2 + k + hi]
            res[f"m_{nm}"] = poss * (hp - ap) / 100
            res[f"t_{nm}"] = poss * (hp + ap) / 100
        rows.append(pd.DataFrame({"game_id": gd["game_id"].to_numpy(), "season": season, "date": gd["date"].to_numpy(), **res}))
    out = pd.concat(rows, ignore_index=True)
    for nm in names:
        out[f"dm_{nm}"] = out[f"m_{nm}"] - out["m_none"]
        out[f"dt_{nm}"] = out[f"t_{nm}"] - out["t_none"]
    out.to_parquet(os.path.join(OUT, f"s1_lag{lag}_{season}.parquet"), index=False)
    return out


if __name__ == "__main__":
    lag = int(sys.argv[1])
    seasons = [int(x) for x in sys.argv[2:]] or list(range(2014, 2026))
    with Pool(4) as pool:
        for o in pool.imap_unordered(run, [(s, lag) for s in seasons]):
            print(int(o["season"].iloc[0]), len(o), flush=True)
