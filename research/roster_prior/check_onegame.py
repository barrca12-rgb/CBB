import os, numpy as np, pandas as pd
from cbb import backtest, player_ratings as pr
from research.roster_prior import build as v1, build_v2 as v2, build_v3 as v3, build_v4 as v4
R="research/roster_prior/out/"; os.makedirs(R+"onegame",exist_ok=True)
orig_pg=pr.player_games
def first_game_only(season):
    g=orig_pg(season)
    ids=(g.drop_duplicates(["team_id","game_id"]).sort_values(["team_id","date","game_id"]).groupby("team_id").head(1)[["team_id","game_id"]])
    return g.merge(ids,on=["team_id","game_id"])
v3.use("V3a")
fr5={s: v2.design(s,"V3a").join(v4.f1_features(s),how="left") for s in range(2015,2027)}
for s in fr5: fr5[s]=fr5[s].fillna({c: fr5[s][c].median() for c in fr5[s].columns if c.startswith("box_")})
fr1={}
for s in (2024,2025,2026):
    tgt=s
    def pg(season, refresh=False, _t=tgt): return first_game_only(season) if season==_t else orig_pg(season)
    pr.player_games=pg
    v4.OUT=R+"onegame"
    d=v2.design(s,"V3a1g").join(v4.f1_features(s),how="left")
    v4.OUT=R; pr.player_games=orig_pg
    fr1[s]=d.fillna({c: d[c].median() for c in d.columns if c.startswith("box_")})
v3.use("V2a")
def prior(frames_train, d):
    tr=pd.concat(frames_train).dropna(subset=["off_now","def_now","tempo_now"]); p=pd.DataFrame(index=d.index)
    for c in ("off","def"):
        cc=v4.cols("F2",c); p[c]=v4.model("F2",tr[cc].to_numpy(float),tr[f"{c}_now"].to_numpy(float))(d[cc].to_numpy(float))
    m=p["off"]+p["def"]; return m-m.mean()
w=pd.read_pickle("audit/out/wf_own_base.pkl"); w["date"]=pd.to_datetime(w.date)
rows=[]
for s in (2024,2025,2026):
    tr=[fr5[k] for k in range(2015,s)]
    m5,m1=prior(tr,fr5[s]),prior(tr,fr1[s])
    kp=backtest.preseason_prior(s); mk=kp["off"]+kp["def"]; mk=mk-mk.mean()
    fin=v1.final_ratings(s); fm=fin["off"]+fin["def"]
    g=w[w.season==s]; g=g[(g.date-g.date.min()).dt.days<=20].dropna(subset=["open_home_spread"]); g=g[g.open_home_spread.abs()>=15]
    fav=np.where(g.open_home_spread<0,g.home_id,g.away_id); dog=np.where(g.open_home_spread<0,g.away_id,g.home_id)
    gap=lambda m: np.nanmean(m.reindex(fav).to_numpy()-m.reindex(dog).to_numpy())
    rows.append({"season":s,"corr 5-game":np.corrcoef(m5.reindex(fm.index).dropna(),fm.reindex(m5.dropna().index).dropna())[0,1] if True else 0,
                 "corr 1-game":np.corrcoef(m1.dropna(),fm.reindex(m1.dropna().index))[0,1],
                 "sd 5-game":m5.std(),"sd 1-game":m1.std(),"gap KP/BT":gap(mk),"gap 5-game":gap(m5),"gap 1-game":gap(m1),"games 15+":len(g)})
r=pd.DataFrame(rows).round(3); print(r.to_string(index=False))
d=(r["gap 5-game"]-r["gap 1-game"]).mean(); print(f"\nmean gap shrink from 1-game rosters: {d:.2f} -> {'CAUSE' if d>=1.5 else 'not the main cause'}")
r.to_csv(R+"v4_onegame.csv",index=False)
