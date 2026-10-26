"""Walk-forward backtest: every game predicted with ratings fit only on games before that day.

    python -m cbb.backtest --start 2013 --end 2026        # writes cbb/output/backtest_<start>_<end>.csv

Prior for each season: KenPom's and Barttorvik's preseason ratings averaged (both published before the first
game, so no look-ahead), as deviations from that season's average.
"""
from __future__ import annotations

import argparse
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import barttorvik, data, kenpom, ratings

OUT = os.path.join(os.path.dirname(__file__), "output")


def kenpom_prior(season: int) -> pd.DataFrame:
    p = kenpom.preseason(season).dropna(subset=["espn_id"]).set_index("espn_id")
    return pd.DataFrame({
        "off": p["AdjOE"] - p["AdjOE"].mean(),
        "def": p["AdjDE"].mean() - p["AdjDE"],
        "tempo": p["AdjTempo"] - p["AdjTempo"].mean(),
    })


def preseason_prior(season: int) -> pd.DataFrame:
    """The ratings each season starts from: KenPom's and Barttorvik's preseason ratings averaged, each centered on
    its own national average. KenPom alone for teams (or seasons) Barttorvik doesn't have. Against KenPom alone
    (2015-2026): November line value +1.09 -> +1.29 at the opener in 2015-17 and +0.83 -> +0.87 in 2024-26."""
    k = kenpom_prior(season)
    t = barttorvik.preseason(season)
    if t is None:
        return k
    t = t.dropna(subset=["espn_id"]).assign(espn_id=lambda d: d["espn_id"].astype(int))
    t = t.drop_duplicates("espn_id").set_index("espn_id")
    t = pd.DataFrame({"off": t["adj_oe"] - t["adj_oe"].mean(), "def": t["adj_de"].mean() - t["adj_de"],
                      "tempo": t["adj_tempo"] - t["adj_tempo"].mean()})
    j = k.join(t, rsuffix="_t", how="left")
    for c in ["off", "def", "tempo"]:
        j[c] = np.where(j[c + "_t"].notna(), (j[c] + j[c + "_t"]) / 2, j[c])
    return j[["off", "def", "tempo"]]


def season(season: int, cfg: ratings.RatingConfig | None = None, prior: str = "blend") -> pd.DataFrame:
    g, t = data.season_games(season)
    ids = sorted(set(t["team_id"]))
    pr = preseason_prior(season) if prior == "blend" else kenpom_prior(season) if prior == "kenpom" else None
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
