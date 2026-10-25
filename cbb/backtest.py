"""Walk-forward backtest: every game predicted with ratings fit only on games before that day.

    python -m cbb.backtest --start 2013 --end 2026        # writes cbb/output/backtest_<start>_<end>.csv

Prior for each season: KenPom's preseason ratings (published before the first game, so no look-ahead),
as deviations from that season's average.
"""
from __future__ import annotations

import argparse
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import data, kenpom, ratings

OUT = os.path.join(os.path.dirname(__file__), "output")


def kenpom_prior(season: int) -> pd.DataFrame:
    p = kenpom.preseason(season).dropna(subset=["espn_id"]).set_index("espn_id")
    return pd.DataFrame({
        "off": p["AdjOE"] - p["AdjOE"].mean(),
        "def": p["AdjDE"].mean() - p["AdjDE"],
        "tempo": p["AdjTempo"] - p["AdjTempo"].mean(),
    })


def season(season: int, cfg: ratings.RatingConfig | None = None, prior: str = "kenpom") -> pd.DataFrame:
    g, t = data.season_games(season)
    ids = sorted(set(t["team_id"]))
    pr = kenpom_prior(season) if prior == "kenpom" else None
    league = ratings.league_averages(data.season_games(season - 1)[1])
    out = []
    for day, gd in g.groupby("date"):
        r = ratings.fit(t, day, ids, pr, cfg, league)
        p = ratings.predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
        p.index = gd.index
        out.append(gd[["game_id", "season", "date", "home_id", "away_id", "neutral", "conf_game", "season_type",
                       "home_pts", "away_pts"]].join(p.add_prefix("pred_")).assign(games_before=r["games"]))
    return pd.concat(out)


def summarize(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    b["margin"] = b["home_pts"] - b["away_pts"]
    b["err"] = b["pred_margin"] - b["margin"]
    b["tot_err"] = b["pred_total"] - (b["home_pts"] + b["away_pts"])
    b["month"] = b["date"].dt.month
    f = lambda d: pd.Series({"games": len(d), "margin_mae": d["err"].abs().mean(),
                             "margin_rmse": np.sqrt((d["err"] ** 2).mean()),
                             "winner": (np.sign(d["pred_margin"]) == np.sign(d["margin"])).mean(),
                             "total_mae": d["tot_err"].abs().mean(), "total_bias": d["tot_err"].mean()})
    return b.groupby("season").apply(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    # One season per worker. Run with OMP_NUM_THREADS=1 so the workers don't fight over cores.
    with Pool(4) as pool:
        b = pd.concat(pool.map(season, range(a.start, a.end + 1)))
    os.makedirs(OUT, exist_ok=True)
    b.to_csv(os.path.join(OUT, f"backtest_{a.start}_{a.end}.csv"), index=False)
    print(summarize(b).round(3).to_string())


if __name__ == "__main__":
    main()
