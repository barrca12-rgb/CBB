"""Step 4: does the market overreact to a shooting night? (existing closes and box scores)

Predeclared specification (written before any result was computed; later changes go to LOG.md):

Surprise, per team-game, in points (3 x (made - expected made threes)), from information before that game only:
  (a) "league":   expected = attempts x the season's league 3P% (the model's existing 3-point-luck machinery,
                  data.THREE_LUCK), season rate computed from the whole season as in data.py.
  (b) "adjusted": expected = attempts x p, p = league x (team shooting factor) x (opponent defence factor); the
                  factors are season-to-date rates before the game, shrunk to the league rate with 250 (shooting)
                  and 500 (defence: 3P% allowed is mostly noise) attempts of prior.
  Net surprise of a team's previous game = its own shooting surprise minus its opponent's shooting surprise.

Per game with both teams' previous game in the same season: S = home net surprise - away net surprise.
  Test 1 (market prices noise as skill): y1 = closing home margin (-home_spread) - the frozen model's live-like
          home margin. Slope of y1 on S > 0: the close moves away from the model in the surprise's direction.
  Test 2 (does it pay): y2 = actual home margin - closing home margin. Slope of y2 on S < 0: the move was an
          overreaction and betting against it would have won.
  Controls: the model's home margin (opponent quality), home and away missing-player values (roster news, where
  observable), neutral site. OLS; slopes with date-clustered bootstrap SEs (2,000 draws). Per era: 2014-2018,
  2019-2022, 2023-2026. Closes: ESPN consensus (lines_hist.consensus), as in the backtest.

    python -m research.market.s4_shooting
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
ERAS = {"2014-2018": range(2014, 2019), "2019-2022": range(2019, 2023), "2023-2026": range(2023, 2027)}
K_OFF, K_DEF = 250.0, 500.0
N_BOOT, SEED = 2000, 20261026


def team_games(season: int) -> pd.DataFrame:
    t = pd.read_parquet(os.path.join(ROOT, "cbb", "cache", f"team_box_{season}.parquet"))
    t = t.rename(columns={"three_point_field_goals_made": "m", "three_point_field_goals_attempted": "a"})
    t = t[["game_id", "game_date", "team_id", "opponent_team_id", "m", "a"]].dropna()
    t["date"] = pd.to_datetime(t["game_date"])
    t = t.sort_values(["date", "game_id"]).reset_index(drop=True)
    lg = t["m"].sum() / t["a"].sum()
    t["s_league"] = 3 * (t["m"] - t["a"] * lg)
    # season-to-date (strictly before this game) shooting and 3P%-allowed, shrunk to the league rate
    for who, col in (("off", "team_id"), ("def", "opponent_team_id")):
        g = t.groupby(col)
        t[f"{who}_m"] = g["m"].cumsum() - t["m"]
        t[f"{who}_a"] = g["a"].cumsum() - t["a"]
    f_off = (t["off_m"] + K_OFF * lg) / (t["off_a"] + K_OFF) / lg
    # defence factor of this game's opponent = what the opponent allowed before (rows where the opponent defended)
    dmap = t.set_index(["game_id", "opponent_team_id"])[["def_m", "def_a"]]
    opp = dmap.reindex(pd.MultiIndex.from_arrays([t["game_id"], t["opponent_team_id"]]))
    f_def = ((opp["def_m"].to_numpy() + K_DEF * lg) / (opp["def_a"].to_numpy() + K_DEF)) / lg
    t["s_adj"] = 3 * (t["m"] - t["a"] * lg * f_off.to_numpy() * f_def)
    # net surprise: own shooting minus the opponent's shooting against us
    o = t.set_index(["game_id", "team_id"])[["s_league", "s_adj"]]
    oo = o.reindex(pd.MultiIndex.from_arrays([t["game_id"], t["opponent_team_id"]])).to_numpy()
    t["net_league"] = t["s_league"] - oo[:, 0]
    t["net_adj"] = t["s_adj"] - oo[:, 1]
    # previous game's net surprise for each team (same season)
    t = t.sort_values(["team_id", "date", "game_id"])
    for c in ("net_league", "net_adj"):
        t[f"prev_{c}"] = t.groupby("team_id")[c].shift(1)
    return t[["game_id", "team_id", "prev_net_league", "prev_net_adj"]]


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def slope(d: pd.DataFrame, y: str, s: str, controls: list[str]) -> dict:
    d = d.dropna(subset=[y, s] + controls)
    X, Y = d[[s] + controls].to_numpy(float), d[y].to_numpy(float)
    b = ols(X, Y)[1]
    dates = d["date"].to_numpy()
    u, inv = np.unique(dates, return_inverse=True)
    rows = [np.where(inv == k)[0] for k in range(len(u))]
    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(N_BOOT):
        idx = np.concatenate([rows[k] for k in rng.integers(0, len(u), len(u))])
        draws.append(ols(X[idx], Y[idx])[1])
    se = float(np.std(draws, ddof=1))
    return {"n": len(d), "dates": len(u), "slope": float(b), "se": se, "z": float(b / se) if se > 0 else np.nan}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[["game_id", "season", "date", "home_id", "away_id", "neutral", "home_pts", "away_pts", "home_spread",
           "final_margin", "home_missing_value", "away_missing_value"]].dropna(subset=["home_spread", "final_margin"])
    parts = []
    for s in sorted(w["season"].unique()):
        tg = team_games(int(s))
        g = w[w["season"] == s]
        h = tg.rename(columns={"team_id": "home_id", "prev_net_league": "h_league", "prev_net_adj": "h_adj"})
        a = tg.rename(columns={"team_id": "away_id", "prev_net_league": "a_league", "prev_net_adj": "a_adj"})
        parts.append(g.merge(h, on=["game_id", "home_id"]).merge(a, on=["game_id", "away_id"]))
    d = pd.concat(parts, ignore_index=True)
    d["S_league"], d["S_adj"] = d["h_league"] - d["a_league"], d["h_adj"] - d["a_adj"]
    d["y1"] = -d["home_spread"] - d["final_margin"]
    d["y2"] = (d["home_pts"] - d["away_pts"]) + d["home_spread"]
    d["neutral"] = d["neutral"].astype(float)
    ctrl = ["final_margin", "home_missing_value", "away_missing_value", "neutral"]
    d[["home_missing_value", "away_missing_value"]] = d[["home_missing_value", "away_missing_value"]].fillna(0)
    rows = []
    for era, seasons in ERAS.items():
        e = d[d["season"].isin(list(seasons))]
        for sv in ("S_league", "S_adj"):
            rows.append({"era": era, "surprise": sv, "test": "1: close vs model (+ = market follows the surprise)",
                         **slope(e, "y1", sv, ctrl)})
            rows.append({"era": era, "surprise": sv, "test": "2: result vs close (- = overreaction paid)",
                         **slope(e, "y2", sv, ctrl)})
        print(era, "done", flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "s4_slopes.csv"), index=False)
    # size check: the close's move per point of surprise vs the share the model already keeps (1 - THREE_LUCK)
    pd.set_option("display.width", 200)
    print(t.round(4).to_string(index=False))
    print("surprise SD (points):", d[["S_league", "S_adj"]].std().round(2).to_dict())


if __name__ == "__main__":
    main()
