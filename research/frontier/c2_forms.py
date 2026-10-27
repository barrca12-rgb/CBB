"""C2: stage-1 functional form (pre-registered in PLAN.md). The frozen stage 1 (cbb/ratings.py) is a decayed ridge on
additive points per 100 possessions. Two alternatives on the same data, schedule, half-life, prior strength and
3-point luck regression; pace and the Four Factors are fit exactly as now:

  mult     ratings on log points per possession (KenPom's form): log ppp = b0 + hca*venue + off[team] - def[opp];
           predictions exp(.), with a smearing correction (training-weighted mean ppp / mean exp(fit)) so the level is
           the arithmetic, not geometric, mean.
  poisson  each team-game's points ~ Poisson(possessions * exp(b0 + hca*venue + off - def)), log link with a
           log(possessions) offset, fit by penalized IRLS from the mult solution. The ridge pull is scaled by the
           mean Fisher information per game so the prior is still worth the same number of games.
           (Negative binomial only if overdispersed: the dispersion is reported.)

Each writes a stage-1 file in the frozen file's format (research/frontier/out/c2_<form>/backtest_2013_2026.csv);
the unchanged stage 2 then runs through d_common.

    OMP_NUM_THREADS=1 python -m research.frontier.c2_forms
"""
from __future__ import annotations

import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from cbb import backtest, data, ratings

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
FORMS = ("mult", "poisson")
DISP = []


def _design(h, idx, k):
    n = len(h)
    rows = np.arange(n)
    X = np.zeros((n, 2 + 2 * k))
    X[:, 0] = 1.0
    X[:, 1] = h["venue"].to_numpy()
    X[rows, 2 + idx[h["team_id"]].to_numpy()] = 1.0
    X[rows, 2 + k + idx[h["opp_id"]].to_numpy()] = -1.0
    return X


def _eff(X, y_ppp, pace, w, lam, beta0_add, form):
    """Efficiency coefficients in log form: [b0, hca, off..., def...] on log(ppp/100)."""
    m = float(np.average(y_ppp, weights=w))
    # the additive prior (points per 100 above average) mapped to log units around this level
    beta0 = np.concatenate([[np.log(m / 100)], beta0_add[1:] / m])
    ly = np.log(np.clip(y_ppp, 1.0, None) / 100)
    b = ratings._solve(X, ly, w, lam, beta0)
    if form == "poisson":
        off = np.log(pace)                                # log mu = log(ppp/100) + log(possessions)
        pts = y_ppp * pace / 100
        for _ in range(6):
            eta = X @ b + off
            mu = np.exp(eta)
            s = float(np.average(mu, weights=w))          # Fisher information per game (Poisson: mu)
            z = eta - off + (pts - mu) / mu
            bn = ratings._solve(X, z, w * mu, lam * s, beta0)
            if np.max(np.abs(bn - b)) < 1e-7:
                b = bn
                break
            b = bn
        mu = np.exp(X @ b + off)
        DISP.append(float(np.average((pts - mu) ** 2 / mu, weights=w)))
    fitted = np.exp(X @ b) * 100
    smear = m / float(np.average(fitted, weights=w))
    return b, smear


def fit(tg, asof, teams, prior, cfg, league, form):
    r = ratings.fit(tg, asof, teams, prior, cfg, league)       # pace, factors, and the additive fit (unused)
    cfg = cfg or ratings.RatingConfig()
    asof = pd.Timestamp(asof)
    k = len(teams)
    idx = pd.Series(np.arange(k), index=teams)
    h = tg[(tg["date"] < asof) & tg["team_id"].isin(idx.index) & tg["opp_id"].isin(idx.index)]
    pr = (prior if prior is not None else pd.DataFrame(index=teams)).reindex(teams).reindex(columns=["off", "def", "tempo"]).fillna(0.0)
    if not len(h):
        lg = {**ratings.DEFAULT_LEAGUE, **(league or {})}["ppp"]
        r.update(form=form, lb0=np.log(lg / 100), lhca=cfg.hca_prior / lg, loff=pr["off"] / lg, ldef=pr["def"] / lg, smear=1.0)
        return r
    w = 0.5 ** ((asof - h["date"]).dt.days.to_numpy() / cfg.half_life)
    wbar = w.mean()
    X = _design(h, idx, k)
    lam = np.full(2 + 2 * k, cfg.prior_games * wbar)
    lam[0] = 1e-6
    lam[1] = 20 * wbar
    pace = h["pace"].to_numpy(float)
    beta0 = np.concatenate([[0.0, cfg.hca_prior], pr["off"], pr["def"]])
    if "ppp_off" in h and "ppp_def" in h:
        bo, so = _eff(X, h["ppp_off"].to_numpy(float), pace, w, lam, beta0, form)
        bd, sd = _eff(X, h["ppp_def"].to_numpy(float), pace, w, lam, beta0, form)
        b = np.concatenate([(bo[:2] + bd[:2]) / 2, bo[2:2 + k], bd[2 + k:]])
        smear = (so + sd) / 2
    else:
        b, smear = _eff(X, h["ppp"].to_numpy(float), pace, w, lam, beta0, form)
    r.update(form=form, lb0=b[0], lhca=b[1], loff=pd.Series(b[2:2 + k], index=teams),
             ldef=pd.Series(b[2 + k:], index=teams), smear=smear)
    return r


def predict(r, home, away, neutral):
    out = ratings.predict(r, home, away, neutral)                # pace and factors as now
    home, away = np.asarray(home), np.asarray(away)
    v = np.where(np.asarray(neutral, dtype=bool), 0.0, 1.0)
    hp = 100 * r["smear"] * np.exp(r["lb0"] + r["lhca"] * v + r["loff"].reindex(home).to_numpy() - r["ldef"].reindex(away).to_numpy())
    ap = 100 * r["smear"] * np.exp(r["lb0"] - r["lhca"] * v + r["loff"].reindex(away).to_numpy() - r["ldef"].reindex(home).to_numpy())
    out["home_pts"], out["away_pts"] = out["poss"] * hp / 100, out["poss"] * ap / 100
    out["margin"], out["total"] = out["home_pts"] - out["away_pts"], out["home_pts"] + out["away_pts"]
    return out


def season(arg):
    s, form = arg
    g, t = data.season_games(s)
    ids = sorted(set(t["team_id"]))
    pr = backtest.preseason_prior(s)
    league = ratings.league_averages(data.season_games(s - 1)[1])
    out = []
    DISP.clear()
    for day, gd in g.groupby("date"):
        r = fit(t, day, ids, pr, None, league, form)
        p = predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
        p.index = gd.index
        out.append(gd[["game_id", "season", "date", "home_id", "away_id", "neutral", "conf_game", "season_type",
                       "home_pts", "away_pts"]].join(p.add_prefix("pred_")).assign(games_before=r["games"]))
    print(form, s, "done", f"dispersion {np.mean(DISP):.3f}" if DISP else "", flush=True)
    return pd.concat(out), (form, s, float(np.mean(DISP)) if DISP else None)


def main() -> None:
    jobs = [(s, f) for f in FORMS for s in range(2013, 2027)]
    with Pool(4) as pool:
        res = pool.map(season, jobs)
    for f in FORMS:
        d = os.path.join(OUT, f"c2_{f}")
        os.makedirs(d, exist_ok=True)
        pd.concat([b for (b, (ff, _, _)) in res if ff == f]).to_csv(os.path.join(d, "backtest_2013_2026.csv"), index=False)
    pd.DataFrame([x for _, x in res], columns=["form", "season", "dispersion"]).to_csv(os.path.join(OUT, "c2_dispersion.csv"), index=False)


if __name__ == "__main__":
    main()
