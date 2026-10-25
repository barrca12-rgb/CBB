"""Second stage: turn the ratings projection plus context into the final margin and total.

The NFL model's projection.py idea. A ridge regression, trained walk-forward (each season is predicted with
coefficients fit only on earlier seasons), on features known before tipoff:

  * the ratings model's margin / total, and the same scaled by how far into the season we are
    (early on the ratings are mostly the preseason prior)
  * KenPom's FanMatch prediction (a second, independently built rating)
  * rest days for each team (capped), and a back-to-back flag
  * each home team's own home-court edge, measured from earlier seasons' results vs the model
  * player availability: share of usual minutes from players who missed the team's last game (players.py)

It never sees the betting line, so the projection stays the model's own opinion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data, players

MARGIN_FEATURES = ["pred_margin", "pred_margin_x_early", "kp_margin", "kp_margin_x_early", "venue",
                   "rest_diff", "b2b_diff", "team_hca", "miss_diff"]
TOTAL_FEATURES = ["pred_total", "pred_total_x_early", "kp_total", "kp_total_x_early", "rest_sum", "season_avg_total"]


def rest_days(seasons) -> pd.DataFrame:
    """Days since each team's previous game (any opponent, D-I or not), per game."""
    rows = []
    for s in seasons:
        sch = data.fetch("schedule", s)
        sch = sch[sch["status_type_completed"].fillna(False).astype(bool)].drop_duplicates("game_id")
        d = pd.to_datetime(sch["game_date"])
        long = pd.concat([pd.DataFrame({"game_id": sch["game_id"], "team": sch["home_id"], "date": d}),
                          pd.DataFrame({"game_id": sch["game_id"], "team": sch["away_id"], "date": d})])
        long = long.sort_values(["team", "date"])
        long["rest"] = long.groupby("team")["date"].diff().dt.days
        rows.append(long)
    r = pd.concat(rows)
    r["rest"] = r["rest"].fillna(14).clip(upper=14)
    return r[["game_id", "team", "rest"]]


def add_features(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    rest = rest_days(sorted(b["season"].unique()))
    rest = rest.astype({"game_id": int, "team": int})
    hr = rest.rename(columns={"team": "home_id", "rest": "home_rest"})
    ar = rest.rename(columns={"team": "away_id", "rest": "away_rest"})
    b = b.merge(hr, on=["game_id", "home_id"], how="left").merge(ar, on=["game_id", "away_id"], how="left")
    b[["home_rest", "away_rest"]] = b[["home_rest", "away_rest"]].fillna(7)
    b["rest_diff"] = b["home_rest"].clip(upper=7) - b["away_rest"].clip(upper=7)
    b["b2b_diff"] = (b["away_rest"] <= 1).astype(int) - (b["home_rest"] <= 1).astype(int)
    b["rest_sum"] = b["home_rest"].clip(upper=7) + b["away_rest"].clip(upper=7)
    b["venue"] = (~b["neutral"].astype(bool)).astype(float)

    av = players.excess_missing(sorted(b["season"].unique()), b)
    b = b.merge(av.rename(columns={"team_id": "home_id", "excess_missing": "home_missing"})[
        ["game_id", "home_id", "home_missing"]], on=["game_id", "home_id"], how="left")
    b = b.merge(av.rename(columns={"team_id": "away_id", "excess_missing": "away_missing"})[
        ["game_id", "away_id", "away_missing"]], on=["game_id", "away_id"], how="left")
    b[["home_missing", "away_missing"]] = b[["home_missing", "away_missing"]].fillna(0)
    b["miss_diff"] = b["home_missing"] - b["away_missing"]

    # "Early": 1 at the start of the season, fading to 0 by ~30 games played per team (about mid-January).
    per_team = b["games_before"] * 2 / 360
    b["early"] = np.clip(1 - per_team / 15, 0, 1)
    b["pred_margin_x_early"] = b["pred_margin"] * b["early"]
    b["pred_total_x_early"] = b["pred_total"] * b["early"]
    b["kp_margin"] = b["kp_margin"].fillna(b["pred_margin"])
    b["kp_total"] = b["kp_total"].fillna(b["pred_total"])
    b["kp_margin_x_early"] = b["kp_margin"] * b["early"]
    b["kp_total_x_early"] = b["kp_total"] * b["early"]

    # Team home edge: shrunk average of (result - model) in the team's home games minus its road games, over the
    # three previous seasons. Only earlier seasons are used.
    b["resid"] = (b["home_pts"] - b["away_pts"]) - b["pred_margin"]
    nn = b[~b["neutral"].astype(bool)]
    long = pd.concat([pd.DataFrame({"season": nn["season"], "team": nn["home_id"], "r": nn["resid"]}),
                      pd.DataFrame({"season": nn["season"], "team": nn["away_id"], "r": -nn["resid"]})])
    st = long.groupby(["team", "season"])["r"].agg(["sum", "count"]).reset_index()
    hca = []
    for s in sorted(b["season"].unique()):
        prev = st[(st["season"] < s) & (st["season"] >= s - 3)].groupby("team")[["sum", "count"]].sum()
        # League-wide average residual is ~0; shrink each team's toward 0 with 60 games of prior.
        hca.append(pd.DataFrame({"season": s, "home_id": prev.index, "team_hca": prev["sum"] / (prev["count"] + 60)}))
    b = b.merge(pd.concat(hca), on=["season", "home_id"], how="left")
    b["team_hca"] = b["team_hca"].fillna(0) * b["venue"]

    # Scoring environment: average total in this season's games so far (rules and pace drift year to year).
    b = b.sort_values("date")
    pts = b["home_pts"] + b["away_pts"]
    cum = pts.groupby(b["season"]).cumsum() - pts
    cnt = b.groupby("season").cumcount()
    prior_avg = pts.groupby(b["season"]).transform("mean").groupby(b["season"]).shift().fillna(pts.mean())
    b["season_avg_total"] = np.where(cnt >= 200, cum / cnt.clip(lower=1), np.nan)
    b["season_avg_total"] = b["season_avg_total"].fillna(b["pred_total"].groupby(b["season"]).transform("mean"))
    return b.drop(columns=["resid"]).sort_index()


def ridge(X, y, lam=1.0):
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0
    return np.linalg.solve(X1.T @ X1 + np.diag(pen), X1.T @ y)


def walk_forward(b: pd.DataFrame, first_train: int = 2013, min_seasons: int = 1) -> pd.DataFrame:
    """Final margin and total for every season after `first_train` + min_seasons, trained on earlier seasons."""
    b = b.copy()
    b["margin"] = b["home_pts"] - b["away_pts"]
    b["points"] = b["home_pts"] + b["away_pts"]
    b["final_margin"] = np.nan
    b["final_total"] = np.nan
    for s in sorted(b["season"].unique()):
        tr = b[(b["season"] < s) & (b["season"] >= first_train)]
        if tr["season"].nunique() < min_seasons:
            continue
        te = b["season"] == s
        cm = ridge(tr[MARGIN_FEATURES].to_numpy(float), tr["margin"].to_numpy(float))
        ct = ridge(tr[TOTAL_FEATURES].to_numpy(float), tr["points"].to_numpy(float))
        b.loc[te, "final_margin"] = cm[0] + b.loc[te, MARGIN_FEATURES].to_numpy(float) @ cm[1:]
        b.loc[te, "final_total"] = ct[0] + b.loc[te, TOTAL_FEATURES].to_numpy(float) @ ct[1:]
    return b


def coefficients(b: pd.DataFrame, upto: int) -> pd.DataFrame:
    tr = b[b["season"] < upto]
    cm = ridge(tr[MARGIN_FEATURES].to_numpy(float), (tr["home_pts"] - tr["away_pts"]).to_numpy(float))
    ct = ridge(tr[TOTAL_FEATURES].to_numpy(float), (tr["home_pts"] + tr["away_pts"]).to_numpy(float))
    return pd.concat([pd.Series(cm, ["intercept"] + MARGIN_FEATURES, name="margin"),
                      pd.Series(ct, ["intercept"] + TOTAL_FEATURES, name="total")], axis=1)
