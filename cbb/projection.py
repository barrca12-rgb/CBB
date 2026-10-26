"""Second stage: turn the ratings projection plus context into the final margin and total.

The NFL model's projection.py idea. A ridge regression, trained walk-forward (each season is predicted with
coefficients fit only on earlier seasons), on features known before tipoff:

  * the ratings model's margin / total, and the same scaled by how far into the season we are
    (early on the ratings are mostly the preseason prior)
  * KenPom's FanMatch prediction and Barttorvik's ratings as of the day before (two independent ratings)
  * the Four Factors (eFG%, turnover rate, offensive rebound rate, free-throw rate), opponent- and venue-adjusted
    as of game day (ratings.py): home minus away for the margin, home plus away for the total
  * rest days for each team (capped), and a back-to-back flag
  * each home team's own home-court edge, measured from earlier seasons' results vs the model
  * player availability: share of usual minutes from players who missed the team's last game (players.py)

It never sees the betting line, so the projection stays the model's own opinion.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from . import barttorvik, data, players
from .ratings import FACTORS

MARGIN_FEATURES = ["pred_margin", "pred_margin_x_early", "kp_margin", "kp_margin_x_early", "bt_margin", "venue",
                   "rest_diff", "b2b_diff", "team_hca", "miss_diff"] + [f"{f}_diff" for f in FACTORS]
TOTAL_FEATURES = ["pred_total", "pred_total_x_early", "kp_total", "kp_total_x_early", "bt_total", "rest_sum",
                  "season_avg_total"] + [f"{f}_sum" for f in FACTORS]
# League-typical Four Factor values, used when a team has no games yet (first days of a season).
FACTOR_AVG = {"efg": 0.50, "tov_rate": 0.18, "orb_rate": 0.29, "ft_rate": 0.25}
# Coefficients fit on every backtest season, plus each team's home edge for the next season (written by fit()).
SAVED = os.path.join(os.path.dirname(__file__), "..", "data", "projection.json")


def rest_days(seasons) -> pd.DataFrame:
    """Days since each team's previous game (any opponent, D-I or not), per game. Scheduled games count too, so
    this works for today's slate; postponed and canceled games don't."""
    rows = []
    for s in seasons:
        sch = data.fetch("schedule", s)
        sch = sch[~sch["status_type_name"].isin(["STATUS_POSTPONED", "STATUS_CANCELED"])].drop_duplicates("game_id")
        d = pd.to_datetime(sch["game_date"])
        long = pd.concat([pd.DataFrame({"game_id": sch["game_id"], "team": sch["home_id"], "date": d}),
                          pd.DataFrame({"game_id": sch["game_id"], "team": sch["away_id"], "date": d})])
        long = long.sort_values(["team", "date"])
        long["rest"] = long.groupby("team")["date"].diff().dt.days
        rows.append(long)
    r = pd.concat(rows)
    r["rest"] = r["rest"].fillna(14).clip(upper=14)
    return r[["game_id", "team", "rest"]]


def add_features(b: pd.DataFrame, live: dict | None = None) -> pd.DataFrame:
    """Features for the second stage. Backtest: everything is computed from `b` and the cached data. Live (today's
    slate): `live` supplies what can't come from today's rows alone: `availability` (game_id, team_id,
    excess_missing), `team_hca` (Series by home team id), `season_avg_total` (float or None), and `season` (lets
    Barttorvik fall back to its live file)."""
    b = b.copy()
    live = live or {}
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

    av = live["availability"] if "availability" in live else players.excess_missing(sorted(b["season"].unique()), b)
    if "excess_value" not in av:
        av = av.assign(excess_value=av["excess_missing"])
    b = b.merge(av.rename(columns={"team_id": "home_id", "excess_missing": "home_missing", "excess_value": "home_missing_value"})[
        ["game_id", "home_id", "home_missing", "home_missing_value"]], on=["game_id", "home_id"], how="left")
    b = b.merge(av.rename(columns={"team_id": "away_id", "excess_missing": "away_missing", "excess_value": "away_missing_value"})[
        ["game_id", "away_id", "away_missing", "away_missing_value"]], on=["game_id", "away_id"], how="left")
    cols = ["home_missing", "away_missing", "home_missing_value", "away_missing_value"]
    b[cols] = b[cols].fillna(0)
    b["miss_diff"] = b["home_missing"] - b["away_missing"]
    b["miss_value_diff"] = b["home_missing_value"] - b["away_missing_value"]

    # "Early": 1 at the start of the season, fading to 0 by ~30 games played per team (about mid-January).
    per_team = b["games_before"] * 2 / 360
    b["early"] = np.clip(1 - per_team / 15, 0, 1)
    b["pred_margin_x_early"] = b["pred_margin"] * b["early"]
    b["pred_total_x_early"] = b["pred_total"] * b["early"]
    b["kp_margin"] = b["kp_margin"].fillna(b["pred_margin"])
    b["kp_total"] = b["kp_total"].fillna(b["pred_total"])
    b["kp_margin_x_early"] = b["kp_margin"] * b["early"]
    b["kp_total_x_early"] = b["kp_total"] * b["early"]

    # Barttorvik starts in 2015; earlier games (and any gaps) fall back to KenPom.
    bt = barttorvik.predict(b[["game_id", "date", "home_id", "away_id", "neutral"]], live.get("season"))
    b = b.merge(bt, on="game_id", how="left")
    b["bt_margin"] = b["bt_margin"].fillna(b["kp_margin"])
    b["bt_total"] = b["bt_total"].fillna(b["kp_total"])

    # Four Factors in percentage points (eFG 0.52 -> 52) so the coefficients are readable. Before a team's first
    # games there is nothing to fit, so they're league-typical.
    for f in FACTORS:
        h = b[f"pred_home_{f}"] if f"pred_home_{f}" in b else pd.Series(np.nan, index=b.index)
        a = b[f"pred_away_{f}"] if f"pred_away_{f}" in b else pd.Series(np.nan, index=b.index)
        h, a = h.fillna(FACTOR_AVG[f]), a.fillna(FACTOR_AVG[f])
        b[f"{f}_diff"] = 100 * (h - a)
        b[f"{f}_sum"] = 100 * (h + a)

    # Team home edge (see team_hca_table): only earlier seasons are used.
    if "team_hca" in live:
        b["team_hca"] = b["home_id"].map(live["team_hca"])
    else:
        hca = [team_hca_table(b, s).rename("team_hca").rename_axis("home_id").reset_index().assign(season=s)
               for s in sorted(b["season"].unique())]
        b = b.merge(pd.concat(hca), on=["season", "home_id"], how="left")
    b["team_hca"] = b["team_hca"].fillna(0) * b["venue"]

    # Scoring environment: average total in this season's games so far (rules and pace drift year to year), once
    # there are 200 games; before that, last season's average total.
    if "season_avg_total" in live:
        b["season_avg_total"] = live["season_avg_total"]
    else:
        b = b.sort_values("date")
        pts = b["home_pts"] + b["away_pts"]
        cum = pts.groupby(b["season"]).cumsum() - pts
        cnt = b.groupby("season").cumcount()
        b["season_avg_total"] = np.where(cnt >= 200, cum / cnt.clip(lower=1), np.nan)
        prev = (b["home_pts"] + b["away_pts"]).groupby(b["season"]).mean()
        b["season_avg_total"] = b["season_avg_total"].fillna(b["season"].map(prev.shift()))
    b["season_avg_total"] = pd.to_numeric(b["season_avg_total"], errors="coerce").fillna(
        b["pred_total"].groupby(b["season"]).transform("mean"))
    return b.sort_index()


def team_hca_table(b: pd.DataFrame, season: int) -> pd.Series:
    """Each team's own home edge for `season`: shrunk average of (result - ratings model) in its home games minus
    its road games over the three seasons before. League-wide the residual is ~0, so each team is shrunk toward 0
    with 60 games of prior."""
    d = b[(b["season"] < season) & (b["season"] >= season - 3) & ~b["neutral"].astype(bool)]
    r = (d["home_pts"] - d["away_pts"]) - d["pred_margin"]
    long = pd.concat([pd.DataFrame({"team": d["home_id"], "r": r}), pd.DataFrame({"team": d["away_id"], "r": -r})])
    g = long.groupby("team")["r"].agg(["sum", "count"])
    return g["sum"] / (g["count"] + 60)


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


def fit(b: pd.DataFrame, next_season: int) -> dict:
    """Coefficients on every season in `b` (already through add_features) and team home edges for next_season,
    saved to data/projection.json for live runs."""
    cm = ridge(b[MARGIN_FEATURES].to_numpy(float), (b["home_pts"] - b["away_pts"]).to_numpy(float))
    ct = ridge(b[TOTAL_FEATURES].to_numpy(float), (b["home_pts"] + b["away_pts"]).to_numpy(float))
    out = {"fitted_on": [int(b["season"].min()), int(b["season"].max())], "next_season": next_season,
           "margin": dict(zip(["intercept"] + MARGIN_FEATURES, map(float, cm))),
           "total": dict(zip(["intercept"] + TOTAL_FEATURES, map(float, ct))),
           "team_hca": {str(int(k)): round(float(v), 3) for k, v in team_hca_table(b, next_season).items()}}
    with open(SAVED, "w") as f:
        json.dump(out, f, indent=1)
    return out


def apply_saved(b: pd.DataFrame) -> pd.DataFrame:
    """Final margin and total from the saved coefficients (live runs)."""
    with open(SAVED) as f:
        c = json.load(f)
    b = b.copy()
    b["final_margin"] = c["margin"]["intercept"] + sum(b[k] * v for k, v in c["margin"].items() if k != "intercept")
    b["final_total"] = c["total"]["intercept"] + sum(b[k] * v for k, v in c["total"].items() if k != "intercept")
    return b


def saved_team_hca() -> pd.Series:
    with open(SAVED) as f:
        c = json.load(f)
    return pd.Series({int(k): v for k, v in c["team_hca"].items()}, dtype=float)


if __name__ == "__main__":
    # python -m cbb.projection 2027   refit on every backtest season (needs cbb/output/backtest_2013_2026.csv from
    # `python -m cbb.backtest`) and save data/projection.json for the 2027 season. Re-run after each season.
    import sys
    from . import evaluate
    nxt = int(sys.argv[1])
    out = fit(add_features(evaluate.load(2013, nxt - 1)), nxt)
    print(f"saved {SAVED}: fitted on {out['fitted_on']}, {len(out['team_hca'])} team home edges")
