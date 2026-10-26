"""Adjusted efficiency ratings: opponent- and venue-adjusted, time-decayed ridge regression.

The NFL model's method (model/ratings.py there), in per-possession units. For each team-game:

    points per 100 possessions = b0 + hca * venue + off[team] - def[opp]       (venue: +1 home, -1 away, 0 neutral)
    pace (possessions per 40)  = p0 + tempo[team] + tempo[opp]

fit by weighted ridge. A game's weight halves every `half_life` days. Instead of shrinking every team toward
average, the ridge shrinks toward a preseason prior (KenPom's preseason ratings, or last season's ratings pulled
toward the mean), so in November a team starts where the prior says and moves as games come in.

Ratings are points per 100 possessions above average: off = how much better than average the offense is, def =
how many points per 100 the defense saves (positive = good), tempo = extra possessions per 40 minutes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RatingConfig:
    half_life: float = 120.0       # days for a game's weight to halve (grid 2014-2019: 30-120 within 0.1 pts)
    prior_games: float = 6.0       # strength of the preseason prior, in games (grid best: 6)
    pace_prior_games: float = 12.0  # stronger prior on tempo helped totals in the grid
    hca_prior: float = 3.5         # home edge in points per 100 possessions per side (~2.4 pts/game each way)
    factor_prior_games: float = 8.0  # Four Factors shrink toward average (no preseason prior for them)
    fit_factors: bool = True


# The Four Factors (Dean Oliver / KenPom), per team-game in data.py: eFG%, turnover rate, offensive rebound rate,
# free-throw rate. Fit with the same opponent/venue adjustment as efficiency, so off_efg = how much better than
# average a team shoots and def_efg = how much it holds opponents below average.
FACTORS = ["efg", "tov_rate", "orb_rate", "ft_rate"]
# Style stats fit the same way, for matchup tests: 3-point attempt rate (defenses control volume more than makes).
STYLE = ["fg3a_rate"]


def _solve(X, y, w, lam, beta0):
    """Weighted ridge toward beta0: min sum w (y - X b)^2 + sum lam (b - beta0)^2."""
    XtW = X.T * w
    return np.linalg.solve(XtW @ X + np.diag(lam), XtW @ y + lam * beta0)


def league_averages(tg: pd.DataFrame) -> dict:
    """League-wide averages from a season's team-games (efficiency, pace, Four Factors): the starting point for
    the next season, before it has games of its own."""
    return {"ppp": float(tg["ppp"].mean()), "pace": float(tg["pace"].mean()),
            **{f: float(tg[f].mean()) for f in FACTORS + STYLE if f in tg}}


# Used only when no league averages are passed and there are no games yet (2012-2026 means).
DEFAULT_LEAGUE = {"ppp": 103.4, "pace": 67.9, "efg": 0.504, "tov_rate": 0.183, "orb_rate": 0.293, "ft_rate": 0.250,
                  "fg3a_rate": 0.37}


def fit(tg: pd.DataFrame, asof, teams: list[int], prior: pd.DataFrame | None = None,
        cfg: RatingConfig | None = None, league: dict | None = None) -> dict:
    """Ratings using only team-games strictly before `asof` (a date).

    tg: team_games from data.load (one season, or more; older games just get tiny weights).
    prior: index = team id, columns off, def, tempo (deviations from average). Missing teams get 0.
    league: last season's league averages (league_averages), the baseline before this season has games. Without
    it, a long-run default is used, which runs low in high-scoring seasons (2026 averaged 108.5 per 100).
    """
    league = {**DEFAULT_LEAGUE, **(league or {})}
    cfg = cfg or RatingConfig()
    asof = pd.Timestamp(asof)
    h = tg[tg["date"] < asof]
    k = len(teams)
    idx = pd.Series(np.arange(k), index=teams)
    pr = (prior if prior is not None else pd.DataFrame(index=teams)).reindex(teams)
    pr = pr.reindex(columns=["off", "def", "tempo"]).fillna(0.0)

    h = h[h["team_id"].isin(idx.index) & h["opp_id"].isin(idx.index)]
    n = len(h)
    ti = idx[h["team_id"]].to_numpy()
    oi = idx[h["opp_id"]].to_numpy()
    days = (asof - h["date"]).dt.days.to_numpy()
    w = 0.5 ** (days / cfg.half_life) if n else np.zeros(0)
    if n and "wt_mult" in h:      # optional per-game weight (e.g. blowouts down-weighted)
        w = w * h["wt_mult"].to_numpy(dtype=float)
    wbar = w.mean() if n else 1.0
    rows = np.arange(n)

    # Efficiency: [b0, hca, off..., def...]
    X = np.zeros((n, 2 + 2 * k))
    X[:, 0] = 1.0
    X[:, 1] = h["venue"].to_numpy()
    X[rows, 2 + ti] = 1.0
    X[rows, 2 + k + oi] = -1.0
    y = h["ppp"].to_numpy(dtype=float)
    lam = np.full(2 + 2 * k, cfg.prior_games * wbar)
    lam[0] = 1e-6
    lam[1] = 20 * wbar  # home edge is well identified; light pull toward the usual value
    beta0 = np.concatenate([[y.mean() if n else league["ppp"], cfg.hca_prior], pr["off"], pr["def"]])
    b = _solve(X, y, w, lam, beta0) if n else beta0
    # Optional separate targets: offense ratings from ppp_off, defense ratings from ppp_def (e.g. 3-point luck
    # regressed more on the defensive side, where opponents' 3P% is mostly noise).
    if n and "ppp_off" in h and "ppp_def" in h:
        bo = _solve(X, h["ppp_off"].to_numpy(dtype=float), w, lam, beta0)
        bd = _solve(X, h["ppp_def"].to_numpy(dtype=float), w, lam, beta0)
        b = np.concatenate([(bo[:2] + bd[:2]) / 2, bo[2:2 + k], bd[2 + k:]])

    # Four Factors: same design matrix, shrunk toward average.
    factors = {}
    if n and cfg.fit_factors:
        XtW = X.T * w
        A = XtW @ X
        lamf = np.full(2 + 2 * k, cfg.factor_prior_games * wbar)
        lamf[:2] = 1e-6
    for f in FACTORS + STYLE:
        if not n and cfg.fit_factors:   # no games yet: everyone at last season's league average
            factors[f] = {"b0": league.get(f, DEFAULT_LEAGUE.get(f, 0.0)), "hca": 0.0, "off": pd.Series(0.0, index=teams), "def": pd.Series(0.0, index=teams)}
            continue
        if not n or not cfg.fit_factors or f not in h:
            continue
        yf = h[f].to_numpy(dtype=float)
        ok = np.isfinite(yf)
        yf = np.where(ok, yf, np.nanmean(yf))
        bf = np.linalg.solve(A + np.diag(lamf), XtW @ yf + lamf * np.r_[yf.mean(), np.zeros(1 + 2 * k)])
        factors[f] = {"b0": bf[0], "hca": bf[1], "off": pd.Series(bf[2:2 + k], index=teams),
                      "def": pd.Series(bf[2 + k:], index=teams)}

    # Pace: [p0, tempo...]; both teams add to the game's pace.
    P = np.zeros((n, 1 + k))
    P[:, 0] = 1.0
    P[rows, 1 + ti] += 1.0
    P[rows, 1 + oi] += 1.0
    yp = h["pace"].to_numpy(dtype=float)
    lamp = np.full(1 + k, cfg.pace_prior_games * wbar)
    lamp[0] = 1e-6
    p0 = np.concatenate([[yp.mean() if n else league["pace"]], pr["tempo"]])
    bp = _solve(P, yp, w, lamp, p0) if n else p0

    return {
        "asof": asof, "games": n // 2, "b0": b[0], "hca": b[1], "p0": bp[0],
        "off": pd.Series(b[2:2 + k], index=teams), "def": pd.Series(b[2 + k:], index=teams),
        "tempo": pd.Series(bp[1:], index=teams), "factors": factors,
    }


def predict(r: dict, home, away, neutral) -> pd.DataFrame:
    """Expected possessions, points, margin (home - away) and total for each game."""
    home, away = np.asarray(home), np.asarray(away)
    v = np.where(np.asarray(neutral, dtype=bool), 0.0, 1.0)
    poss = r["p0"] + r["tempo"].reindex(home).to_numpy() + r["tempo"].reindex(away).to_numpy()
    home_ppp = r["b0"] + r["hca"] * v + r["off"].reindex(home).to_numpy() - r["def"].reindex(away).to_numpy()
    away_ppp = r["b0"] - r["hca"] * v + r["off"].reindex(away).to_numpy() - r["def"].reindex(home).to_numpy()
    out = pd.DataFrame({"poss": poss, "home_pts": poss * home_ppp / 100, "away_pts": poss * away_ppp / 100})
    out["margin"] = out["home_pts"] - out["away_pts"]
    out["total"] = out["home_pts"] + out["away_pts"]
    # Expected Four Factors for each side: offense's adjusted factor against the defense's.
    for f, fr in r.get("factors", {}).items():
        out[f"home_{f}"] = fr["b0"] + fr["hca"] * v + fr["off"].reindex(home).to_numpy() - fr["def"].reindex(away).to_numpy()
        out[f"away_{f}"] = fr["b0"] - fr["hca"] * v + fr["off"].reindex(away).to_numpy() - fr["def"].reindex(home).to_numpy()
        # each side's own offense and defense numbers (deviations from average), for matchup interactions
        for side, team in (("home", home), ("away", away)):
            out[f"{side}_off_{f}"] = fr["off"].reindex(team).to_numpy()
            out[f"{side}_def_{f}"] = fr["def"].reindex(team).to_numpy()
    out["home_tempo"] = r["tempo"].reindex(home).to_numpy()
    out["away_tempo"] = r["tempo"].reindex(away).to_numpy()
    return out


def table(r: dict) -> pd.DataFrame:
    t = pd.DataFrame({"off": r["off"], "def": r["def"], "tempo": r["tempo"]})
    t["net"] = t["off"] + t["def"]                      # points per 100 possessions better than average
    t["adj_oe"] = r["b0"] + t["off"]
    t["adj_de"] = r["b0"] - t["def"]
    t["adj_tempo"] = r["p0"] + t["tempo"]                # possessions vs an average opponent
    return t.sort_values("net", ascending=False)
