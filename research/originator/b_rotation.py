"""Part B: rotation adjustment, gate only (specification in LOG.md and in the task; written before running).

For each team-game, from games before it only:
  expected minutes  last-5-game weighted average (weights 5,4,3,2,1; missed games count 0), shrunk toward the
                    embedded minutes with 2 games of weight; 0 if the player sat out the team's previous game (the
                    only historical absence information, as the model uses)
  embedded minutes  the player's minutes over the team's season so far, weighted 0.5^(days/120) (the rating's
                    half-life), i.e. the rotation the team rating was built on
  player value      offensive and defensive box-score value per 100 on-floor possessions relative to the team,
                    season to date, shrunk toward the team average with 150 possessions (player_ratings' scheme,
                    with Game Score weights split into offensive and defensive terms)
  adjustment        sum over players of (expected - embedded minutes)/200 x relative value x team possessions/100,
                    offense and defence separately, in points

Gate: margin adjustment = (home off + home def) - (away off + away def). Does it predict the frozen model's margin
residual? Fit 2014-2019, test 2020-2026: coefficient with date-clustered 95% interval (on the test seasons) and
out-of-sample R-squared. Kill: interval includes 0, or R-squared < 0.01.

    python -m research.originator.b_rotation
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import player_ratings as pr

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
OFF = ["points", "missed_fg", "missed_ft", "offensive_rebounds", "assists", "turnovers"]
DEF = ["defensive_rebounds", "steals", "blocks", "fouls"]
W5 = np.array([5, 4, 3, 2, 1], float)


def season_adjustments(season: int) -> pd.DataFrame:
    p = pr.player_games(season)
    p["off_v"] = p[OFF].to_numpy(float) @ pr.WEIGHTS[OFF].to_numpy(float)
    p["def_v"] = p[DEF].to_numpy(float) @ pr.WEIGHTS[DEF].to_numpy(float)
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        games = [(gid, g) for gid, g in tg.groupby("game_id", sort=False)]
        hist: list[dict] = []          # per earlier game: {athlete: minutes}
        dates: list[pd.Timestamp] = []
        cum: dict = {}                 # athlete -> [off, def, on_poss]
        tv_o = tv_d = tps = 0.0
        poss_hist: list[float] = []
        for gid, g in games:
            d0 = g["date"].iloc[0]
            if hist:
                players = set().union(*hist)
                w = np.array([0.5 ** ((d0 - d).days / 120) for d in dates])
                last = hist[-1]
                rate_o, rate_d = (100 * tv_o / tps, 100 * tv_d / tps) if tps else (0.0, 0.0)
                adj_o = adj_d = 0.0
                tposs = float(np.mean(poss_hist[-10:]))
                for a in players:
                    mins = np.array([h.get(a, 0.0) for h in hist])
                    emb = float((w * mins).sum() / w.sum())
                    rec = mins[::-1][:5]
                    rw = W5[:len(rec)]
                    recent = (float((rw * rec).sum()) + 2 * emb) / (rw.sum() + 2)
                    exp = 0.0 if last.get(a, 0.0) == 0 else recent
                    o, dv, ps = cum.get(a, (0.0, 0.0, 0.0))
                    rel_o = (100 * o + rate_o * pr.REL_PRIOR) / (ps + pr.REL_PRIOR) - rate_o
                    rel_d = (100 * dv + rate_d * pr.REL_PRIOR) / (ps + pr.REL_PRIOR) - rate_d
                    adj_o += (exp - emb) / 200 * rel_o * tposs / 100
                    adj_d += (exp - emb) / 200 * rel_d * tposs / 100
                out.append((int(gid), int(team), adj_o, adj_d))
            mins_now = dict(zip(g["athlete_id"], g["min"]))
            hist.append(mins_now)
            dates.append(d0)
            for a, o, dv, ps in zip(g["athlete_id"], g["off_v"], g["def_v"], g["on_poss"]):
                c = cum.get(a, (0.0, 0.0, 0.0))
                cum[a] = (c[0] + o, c[1] + dv, c[2] + ps)
            tv_o += g["off_v"].sum()
            tv_d += g["def_v"].sum()
            tps += g["on_poss"].sum()
            poss_hist.append(float(g["poss"].iloc[0]))
    return pd.DataFrame(out, columns=["game_id", "team_id", "adj_off", "adj_def"])


def cluster_ols(X, y, groups):
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(groups).sum().to_numpy()
    return b, np.sqrt(np.diag(bread @ (s.T @ s) @ bread))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "b_adjustments.csv.gz")
    if os.path.exists(path):
        adj = pd.read_csv(path)
    else:
        adj = pd.concat([season_adjustments(s).assign(season=s) for s in range(2014, 2027)], ignore_index=True)
        adj.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["final_margin"])
    a = adj.drop(columns="season")
    w = w.merge(a.rename(columns={"team_id": "home_id", "adj_off": "h_off", "adj_def": "h_def"}), on=["game_id", "home_id"]) \
         .merge(a.rename(columns={"team_id": "away_id", "adj_off": "a_off", "adj_def": "a_def"}), on=["game_id", "away_id"])
    w["adj_margin"] = (w["h_off"] + w["h_def"]) - (w["a_off"] + w["a_def"])
    w["adj_total"] = (w["h_off"] + w["a_off"]) - (w["h_def"] + w["a_def"])
    w["res_margin"] = (w["home_pts"] - w["away_pts"]) - w["final_margin"]
    w["res_total"] = (w["home_pts"] + w["away_pts"]) - w["final_total"]
    rows = []
    for mk in ("margin", "total"):
        tr, te = w[w["season"] <= 2019], w[w["season"] >= 2020]
        b_tr, _ = cluster_ols(tr[[f"adj_{mk}"]].to_numpy(float), tr[f"res_{mk}"].to_numpy(float), tr["date"].to_numpy())
        pred = b_tr[0] + b_tr[1] * te[f"adj_{mk}"]
        y = te[f"res_{mk}"]
        r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        b_te, s_te = cluster_ols(te[[f"adj_{mk}"]].to_numpy(float), y.to_numpy(float), te["date"].to_numpy())
        rows.append({"target": f"frozen model {mk} residual", "fit 2014-19 coef": b_tr[1],
                     "test 2020-26 coef": b_te[1], "95% interval": f"[{b_te[1] - 1.96 * s_te[1]:.3f}, {b_te[1] + 1.96 * s_te[1]:.3f}]",
                     "out-of-sample R2": r2, "adjustment SD (pts)": te[f"adj_{mk}"].std(), "games (test)": len(te),
                     "gate": "PASS" if (abs(b_te[1]) > 1.96 * s_te[1] and r2 >= 0.01) else "FAIL (kill rule)"})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "b_gate.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
