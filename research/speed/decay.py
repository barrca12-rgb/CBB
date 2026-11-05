"""How long an alerted number stays available, and what a delay costs (research only). python research/speed/decay.py
Reads research/speed/out/pulls.parquet (built by research.speed.measure) and bets/bets.csv."""
import numpy as np, pandas as pd
pd.set_option("display.width",250)
p=pd.read_parquet("research/speed/out/pulls.parquet")
p["t"]=pd.to_datetime(p.pulled_at,utc=True,format="ISO8601"); p["st"]=pd.to_datetime(p.start,utc=True,format="ISO8601")
b=pd.read_csv("bets/bets.csv"); b=b[b.status!="void"].copy()
b["t0"]=pd.to_datetime(b.logged_at,utc=True,format="ISO8601"); b=b[b.t0>="2026-10-31"]
BOOKS={"DraftKings","FanDuel","BetMGM","Caesars","Fanatics","theScore Bet","BetRivers"}
p=p[p.book.isin(BOOKS)]
key=lambda h,a: (min(h,a),max(h,a))
p["k"]=[key(h,a) for h,a in zip(p.home_id,p.away_id)]
groups={k:g.sort_values("t") for k,g in p.groupby("k")}
H=[10,30,60,120,240]
rows=[]
for _,r in b.iterrows():
    g=groups.get(key(r.home_id,r.away_id))
    if g is None: continue
    g=g[(g.t>=r.t0-pd.Timedelta(minutes=1))&(g.t<g.st)]
    same=g.home_id==r.home_id
    if r.market=="spread":
        hl=np.where(same,g.home_spread,-g.home_spread); bl=hl if r.side=="home" else -hl; ok=bl>=r.line-1e-9
    else:
        bl=g.total.to_numpy(); ok=(bl<=r.line+1e-9) if r.side=="over" else (bl>=r.line-1e-9)
    g=g.assign(bl=bl,ok=ok)
    g=g[~pd.isna(g.bl)]
    out={"bet_id":r.bet_id,"t0":r.t0,"book":r.book,"market":r.market,"hour_et":r.t0.tz_convert("America/New_York").hour}
    tip=g.st.iloc[0] if len(g) else pd.NaT
    for h in H+["8am","tip"]:
        if h=="8am":
            et=r.t0.tz_convert("America/New_York"); 
            if et.hour>=8: out["8am_same"]=np.nan; out["8am_any"]=np.nan; continue
            tt=et.normalize().tz_convert("UTC")+pd.Timedelta(hours=8)+(et.normalize().tz_convert("UTC")-et.normalize().tz_convert("UTC"))
            tt=(et.normalize()+pd.Timedelta(hours=8)).tz_convert("UTC")
        elif h=="tip": tt=tip-pd.Timedelta(minutes=15) if pd.notna(tip) else pd.NaT
        else: tt=r.t0+pd.Timedelta(minutes=h)
        if pd.isna(tt) or (pd.notna(tip) and tt>=tip): out[f"{h}_same"]=np.nan; out[f"{h}_any"]=np.nan; continue
        snap=g[g.t<=tt]
        if not len(snap): out[f"{h}_same"]=np.nan; out[f"{h}_any"]=np.nan; continue
        last=snap.groupby("book").tail(1)
        last=last[last.t>=tt-pd.Timedelta(minutes=35)]
        s=last[last.book==r.book]
        out[f"{h}_same"]=float(s.ok.iloc[0]) if len(s) else np.nan
        out[f"{h}_any"]=float(last.ok.any()) if len(last) else np.nan
    rows.append(out)
d=pd.DataFrame(rows)
print(len(d),"plays")
cols=[c for c in d.columns if c.endswith("_same") or c.endswith("_any")]
print((100*d[cols].mean()).round(1).to_string()); print(d[cols].count().to_string())
d["slot"]=pd.cut(d.hour_et,[-1,7,11,17,23],labels=["0-7 ET (overnight)","8-11","12-17","18-23"])
print((100*d.groupby("slot",observed=True)[["30_same","60_same","120_same","240_same","8am_same","8am_any"]].mean()).round(1))
print(d.groupby("slot",observed=True).size())
d.to_pickle("/tmp/claude-0/-home-user/f2a02b25-602b-5476-ac16-03709c8080c8/scratchpad/decay.pkl")

# points lost vs the alerted number at the same book, by delay (negative = worse for us)
rows=[]
for _,r in b.iterrows():
    g=groups.get(key(r.home_id,r.away_id))
    if g is None: continue
    g=g[(g.book==r.book)&(g.t>=r.t0-pd.Timedelta(minutes=1))&(g.t<g.st)]
    same=g.home_id==r.home_id
    if r.market=="spread":
        hl=np.where(same,g.home_spread,-g.home_spread); bl=hl if r.side=="home" else -hl; gain=bl-r.line
    else:
        bl=g.total.to_numpy(); gain=(r.line-bl) if r.side=="over" else (bl-r.line)
    g=g.assign(gain=gain).dropna(subset=["gain"])
    o={"bet_id":r.bet_id,"hour_et":r.t0.tz_convert("America/New_York").hour}
    for h in [10,30,60,120,240]:
        s=g[g.t<=r.t0+pd.Timedelta(minutes=h)]
        o[h]=s.gain.iloc[-1] if len(s) else np.nan
    rows.append(o)
x=pd.DataFrame(rows)
print("\nmean points vs the alerted number at the same book (negative = line moved against a late bettor)")
print(x[[10,30,60,120,240]].mean().round(2).to_string())
x["slot"]=pd.cut(x.hour_et,[-1,7,11,17,23],labels=["0-7 ET","8-11","12-17","18-23"])
print(x.groupby("slot",observed=True)[[30,60,120,240]].mean().round(2))
