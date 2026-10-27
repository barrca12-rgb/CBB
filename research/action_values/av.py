"""Possession-value (EV) weights for the lineup adjustment vs Game Score (pre-registered in LOG.md).

    python -m research.action_values.av
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import lineup
from cbb import player_ratings as pr
from cbb.evaluate import swapped
from research.originator.d_common import clv, oriented_openers

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
PBP = os.path.join(ROOT, "cbb", "cache", "pbp")


def constants(season: int, p: pd.DataFrame) -> dict:
    t = p.groupby(["game_id", "team_id"]).agg(pts=("points", "sum"), poss=("poss", "first"), fgm=("field_goals_made", "sum"),
                                              fga=("field_goals_attempted", "sum"), fta=("free_throws_attempted", "sum"),
                                              ftm=("free_throws_made", "sum"), oreb=("offensive_rebounds", "sum"),
                                              dreb=("defensive_rebounds", "sum"), fouls=("fouls", "sum"))
    s = t.sum()
    v0 = s["pts"] / s["poss"]
    p_or = s["oreb"] / (s["oreb"] + s["dreb"])
    f_net = (s["ftm"] - 0.44 * v0 * s["fta"]) / s["fouls"]
    b = pd.read_parquet(os.path.join(PBP, f"play_by_play_{season}.parquet"), columns=["type_text", "text", "scoring_play", "shooting_play"])
    tt, tx = b["type_text"].astype(str), b["text"].astype(str)
    fga = b["shooting_play"].astype(bool) & ~tt.str.contains("FreeThrow|Free Throw") & ~tx.str.contains("Free Throw")
    three = tt.str.contains("Three") | tx.str.contains("Three Point")
    rim = fga & ~three & tt.isin(["LayUpShot", "DunkShot", "TipShot"])
    r_rim = float(b.loc[rim, "scoring_play"].astype(bool).mean())
    ast = fga & b["scoring_play"].astype(bool) & tx.str.contains("Assisted by")
    a_pts = float(np.where(three[ast], 3.0, 2.0).mean())
    return {"season": season, "V0": v0, "p_or": p_or, "r_rim": r_rim, "a_pts": a_pts, "f_net": f_net}


def values(p: pd.DataFrame, c: dict | None) -> pd.DataFrame:
    p = p.copy()
    if c is None:      # Game Score, exactly as cbb/lineup.py
        p["off_v"] = p[lineup.OFF].to_numpy(float) @ pr.WEIGHTS[lineup.OFF].to_numpy(float)
        p["def_v"] = p[lineup.DEF].to_numpy(float) @ pr.WEIGHTS[lineup.DEF].to_numpy(float)
        return p
    v0, po = c["V0"], c["p_or"]
    fgm, fga = p["field_goals_made"].astype(float), p["field_goals_attempted"].astype(float)
    p["off_v"] = (p["points"] - v0 * fgm - (1 - po) * v0 * (fga - fgm) - 0.44 * v0 * p["free_throws_attempted"]
                  + (1 - po) * v0 * p["offensive_rebounds"] - v0 * p["turnovers"] + 0.5 * (c["a_pts"] - v0) * p["assists"])
    p["def_v"] = (po * v0 * p["defensive_rebounds"] + v0 * p["steals"] + (2 * c["r_rim"] - po * v0) * p["blocks"]
                  - c["f_net"] * p["fouls"])
    return p


def adjustments(p: pd.DataFrame) -> pd.DataFrame:
    """cbb/lineup.adjustments' loop on precomputed off_v / def_v."""
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        hist, dates, poss_hist, cum = [], [], [], {}
        tv_o = tv_d = tps = 0.0
        for gid, g in tg.groupby("game_id", sort=False):
            d0 = g["date"].iloc[0]
            if hist:
                out.append((int(gid), int(team), *lineup._state(hist, dates, cum, tv_o, tv_d, tps, poss_hist, d0)))
            hist.append(dict(zip(g["athlete_id"], g["min"])))
            dates.append(d0)
            for a, o, dv, ps in zip(g["athlete_id"], g["off_v"], g["def_v"], g["on_poss"]):
                x = cum.get(a, (0.0, 0.0, 0.0))
                cum[a] = (x[0] + o, x[1] + dv, x[2] + ps)
            tv_o += g["off_v"].sum()
            tv_d += g["def_v"].sum()
            tps += g["on_poss"].sum()
            poss_hist.append(float(g["poss"].iloc[0]))
    return pd.DataFrame(out, columns=["game_id", "team_id", "adj_off", "adj_def"])


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = os.path.join(OUT, "ev_adjustments.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    cons, parts = [], []
    for s in range(2014, 2027):
        p = pr.player_games(s)
        c = constants(s, p)
        cons.append(c)
        parts.append(adjustments(values(p, c)).assign(season=s))
        print(s, {k: round(v, 3) for k, v in c.items()}, flush=True)
    res = (pd.DataFrame(cons), pd.concat(parts, ignore_index=True))
    pd.to_pickle(res, path)
    return res


def frame(adj: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    a = adj.assign(v=adj["adj_off"] + adj["adj_def"])[["game_id", "team_id", "v"]]
    w = w.merge(a.rename(columns={"team_id": "home_id", "v": "hv"}), on=["game_id", "home_id"], how="left") \
         .merge(a.rename(columns={"team_id": "away_id", "v": "av"}), on=["game_id", "away_id"], how="left")
    w["adj"] = w["hv"].fillna(0) - w["av"].fillna(0)
    w["beta"] = np.nan
    for s in range(2015, 2027):
        tr = w[w["season"] < s]
        b = np.linalg.lstsq(np.column_stack([np.ones(len(tr)), tr["adj"]]), tr["res"].to_numpy(float), rcond=None)[0][1]
        w.loc[w["season"] == s, "beta"] = b
    w["badj"] = w["beta"] * w["adj"]
    return w[w["season"] >= 2015]


def cluster(X, y, g):
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    br = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(g).sum().to_numpy()
    return b, np.sqrt(np.diag(br @ (s.T @ s) @ br))


def win(w, col, seasons):
    d = w[w["season"].isin(seasons)].dropna(subset=["open_home_spread"])
    e = d[col] + d["open_home_spread"]
    s = d[e.abs() >= 2.5]
    m = (s["home_pts"] - s["away_pts"] + s["open_home_spread"]) * np.sign(e[e.abs() >= 2.5])
    m = m[m != 0]
    return round(100 * (m > 0).mean(), 2), len(m)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    cons, ev = build()
    gs = pd.read_csv(os.path.join(ROOT, "research", "originator", "out", "b_adjustments.csv.gz"))
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["final_margin"])
    w = oriented_openers(w)
    w = w[~swapped(w.assign(pred_margin=w["final_margin"]))]
    w["res"] = (w["home_pts"] - w["away_pts"]) - w["final_margin"]
    rows = []
    for tag, adj in (("GS (current)", gs.drop(columns="season")), ("EV (possession values)", ev.drop(columns="season"))):
        f = frame(adj, w)
        te = f[f["season"] >= 2020]
        r2 = 1 - ((te["res"] - te["badj"]) ** 2).sum() / ((te["res"] - te["res"].mean()) ** 2).sum()
        c = te.dropna(subset=["home_spread"])
        b, se = cluster(np.column_stack([c["badj"], c["final_margin"] + c["home_spread"]]),
                        (c["home_pts"] - c["away_pts"] + c["home_spread"]).to_numpy(float), c["date"].astype(str).to_numpy())
        f["v2"] = f["final_margin"] + f["badj"]
        g = f.assign(final_margin=f["v2"])
        cd, cc = clv(g, range(2015, 2018))["spread CLV"], clv(g, range(2024, 2027))["spread CLV"]
        wd, wh = win(f, "v2", [2015, 2016, 2017, 2024]), win(f, "v2", [2025, 2026])
        rows.append({"version": tag, "beta 2026": round(float(f.loc[f["season"] == 2026, "beta"].iloc[0]), 3),
                     "adj SD (pts, after beta)": round(float(te["badj"].std()), 3), "OOS R2 2020-26": round(float(r2), 5),
                     "beyond-close coef (se)": f"{b[1]:.3f} ({se[1]:.3f})", "beyond-close t": round(float(b[1] / se[1]), 2),
                     "spread CLV 2015-17": round(cd, 3), "spread CLV 2024-26": round(cc, 3),
                     "win% dev (n)": f"{wd[0]} ({wd[1]})", "win% holdout (n)": f"{wh[0]} ({wh[1]})"})
    base = w[w["season"] >= 2015]
    rows.append({"version": "v1 (no adjustment)", "spread CLV 2015-17": round(clv(base, range(2015, 2018))["spread CLV"], 3),
                 "spread CLV 2024-26": round(clv(base, range(2024, 2027))["spread CLV"], 3),
                 "win% dev (n)": "%s (%s)" % win(base, "final_margin", [2015, 2016, 2017, 2024]),
                 "win% holdout (n)": "%s (%s)" % win(base, "final_margin", [2025, 2026])})
    t = pd.DataFrame(rows).set_index("version")
    g_, e_ = t.loc["GS (current)"], t.loc["EV (possession values)"]
    ok = (e_["OOS R2 2020-26"] > g_["OOS R2 2020-26"] and e_["beyond-close t"] > g_["beyond-close t"]
          and e_["spread CLV 2015-17"] >= g_["spread CLV 2015-17"] and e_["spread CLV 2024-26"] >= g_["spread CLV 2024-26"])
    cons.to_csv(os.path.join(OUT, "constants.csv"), index=False)
    t.to_csv(os.path.join(OUT, "av_result.csv"))
    pd.set_option("display.width", 250)
    print(cons.round(3).to_string(index=False))
    print(t.T.to_string())
    print("verdict:", "PASS (v2.1 shadow candidate)" if ok else "KILL")


if __name__ == "__main__":
    main()
