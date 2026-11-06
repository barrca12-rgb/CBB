"""F2-blend replay of the 2026-27 season so far (Nov 6 question: what would its record be). Research only.
    PYTHONPATH=. python research/roster_prior/live_replay_2027.py  -> scratchpad f2_delta.csv (copy in out/f2_delta_2027.csv)"""
import json, os, numpy as np, pandas as pd
from cbb import data, ratings, teams
from research.roster_prior import build as v1, build_v2 as v2, build_v3 as v3, build_v4 as v4
OUT="/tmp/claude-0/-home-user/f2a02b25-602b-5476-ac16-03709c8080c8/scratchpad"
# fresh 2027 box scores and schedule
data.fetch("player_box", 2027, refresh=True); hist, tg = data.season_games(2027, refresh=True)
# F2 prior for 2027 (train 2015-2026)
v3.use("V3a")
fr = {s: v2.design(s, "V3a").join(v4.f1_features(s), how="left") for s in range(2015, 2028)}
v3.use("V2a")
for s in fr: fr[s] = fr[s].fillna({c: fr[s][c].median() for c in fr[s].columns if c.startswith("box_")})
train = pd.concat([fr[s] for s in range(2015, 2027)]).dropna(subset=["off_now", "def_now", "tempo_now"])
d = fr[2027]; p = pd.DataFrame(index=d.index)
for c in ("off", "def", "tempo"):
    cc = v4.cols("F2", c); p[c] = v4.model("F2", train[cc].to_numpy(float), train[f"{c}_now"].to_numpy(float))(d[cc].to_numpy(float))
p = p - p.mean()
cur = pd.read_csv("audit/out/frozen_preseason_prior_2027.csv").set_index("espn_id")[["off", "def", "tempo"]]
j = cur.join(p, rsuffix="_r", how="left")
blend = pd.DataFrame({c: j[[c, c + "_r"]].mean(axis=1) for c in ("off", "def", "tempo")})
print("teams with F2 prior", p.shape[0], "of", cur.shape[0])
L = ratings.league_averages(data.season_games(2026)[1])
ids = sorted(set(teams.load()["espn_id"]) | set(tg["team_id"]))
g = hist[(hist["date"] >= "2026-11-01") & (hist["date"] <= "2026-11-05")]
rows = []
for day, gd in g.groupby("date"):
    for lab, prior in (("cur", cur), ("blend", blend)):
        r = ratings.fit(tg, day, ids, prior, None, L)
        q = ratings.predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
        rows.append(pd.DataFrame({"game_id": gd["game_id"].to_numpy(), "lab": lab, "m": q["margin"].to_numpy(), "t": q["total"].to_numpy(), "games": r["games"]}))
x = pd.concat(rows).pivot_table(index="game_id", columns="lab", values=["m", "t", "games"])
pj = json.load(open("data/projection.json"))
early = np.clip(1 - x[("games", "cur")] * 2 / 360 / 15, 0, 1)
dm = (pj["margin"]["pred_margin"] + pj["margin"]["pred_margin_x_early"] * early) * (x[("m", "blend")] - x[("m", "cur")])
dt = (pj["total"]["pred_total"] + pj["total"]["pred_total_x_early"] * early) * (x[("t", "blend")] - x[("t", "cur")])
out = pd.DataFrame({"d_margin": dm, "d_total": dt})
out.to_csv(f"{OUT}/f2_delta.csv")
print(out.describe().round(2))
