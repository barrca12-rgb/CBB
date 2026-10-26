"""Audit: rebuild the stage-1 walk-forward ratings with an information lag.

backtest.season() predicts each game with ratings fit on games strictly before its date (lag 0). Here the cutoff is
moved back LAG days, so a game on day D uses only games before D-LAG. Everything else (prior, config, league
averages) is the production code path. Writes audit/out/backtest_lag<LAG>_2013_2026.csv; the production file
cbb/output/backtest_2013_2026.csv is not touched.

    python -m audit.stage1_lag 1
"""
from __future__ import annotations

import os
import sys
from multiprocessing import Pool

import pandas as pd

from cbb import backtest, data, ratings

OUT = os.path.join(os.path.dirname(__file__), "out")
LAG = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def season(s: int) -> pd.DataFrame:
    g, t = data.season_games(s)
    ids = sorted(set(t["team_id"]))
    pr = backtest.preseason_prior(s)
    league = ratings.league_averages(data.season_games(s - 1)[1])
    out = []
    for day, gd in g.groupby("date"):
        r = ratings.fit(t, day - pd.Timedelta(days=LAG), ids, pr, None, league)
        p = ratings.predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
        p.index = gd.index
        out.append(gd[["game_id", "season", "date", "home_id", "away_id", "neutral", "conf_game", "season_type",
                       "home_pts", "away_pts"]].join(p.add_prefix("pred_")).assign(games_before=r["games"]))
    return pd.concat(out)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with Pool(4) as pool:
        b = pd.concat(pool.map(season, range(2013, 2027)))
    b.to_csv(os.path.join(OUT, f"backtest_lag{LAG}_2013_2026.csv"), index=False)
    print("done", len(b))
