"""Step 2a on the Option B sample: model edge vs favorable quote, with real prices and times (LOG.md).

    python -m research.market.s2a_real
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from research.market.s1_sample_report import DATA, FOUR, HERE, OUT, ROOT, load, lookup, schedule

WIN_PROB_V1 = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}
THR = {"spread": 2.5, "total": 3.0}


def payout(o):
    o = np.asarray(o, float)
    return np.where(o > 0, o / 100, 100 / -np.where(o < 0, o, -1))


def winp(mk, e):
    s, c = WIN_PROB_V1[mk]
    return np.minimum(np.maximum(0.5 + s * e, 0.5), c)


def state_at(rows: pd.DataFrame, t) -> pd.DataFrame:
    """Each (book, outcome)'s latest quote at or before snapshot t (absent = gone)."""
    x = rows[rows["snapshot"] <= t].sort_values("snapshot").drop_duplicates(["book", "outcome"], keep="last")
    return x[x["status"] != "absent"]


def boot(v, d, n=5000):
    v, d = np.asarray(v, float), np.asarray(d)
    u = np.unique(d)
    if len(u) < 2:
        return np.nan
    idx = np.random.default_rng(20261026).integers(0, len(u), (n, len(u)))
    sums = np.array([[v[d == k].sum(), (d == k).sum()] for k in u])
    s = sums[idx].sum(axis=1)
    return float((s[:, 0] / s[:, 1]).std(ddof=1))


def main() -> None:
    plan = json.load(open(os.path.join(HERE, "sample_plan.json")))
    lk = lookup()
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))[["game_id", "final_margin", "final_total", "home_pts", "away_pts"]]
    sig, mo = [], []
    for d in plan["dates"]:
        q, s = load(d["date"])
        sch = schedule(d["date"], d["season"])
        q["h"] = q["home_team"].map(lambda n: lk.get(__import__("cbb").teams.norm(n or "")))
        q["a"] = q["away_team"].map(lambda n: lk.get(__import__("cbb").teams.norm(n or "")))
        ev = q.dropna(subset=["h", "a"]).drop_duplicates("event_id")[["event_id", "h", "a"]].astype({"h": int, "a": int})
        m = pd.concat([sch.merge(ev, left_on=["home_id", "away_id"], right_on=["h", "a"]).assign(flip=False),
                       sch.merge(ev, left_on=["home_id", "away_id"], right_on=["a", "h"]).assign(flip=True)]).drop_duplicates("game_id")
        m = m.merge(w, on="game_id")
        for _, g in m.iterrows():
            gq = q[q["event_id"] == g["event_id"]]
            for mk, key in (("spread", "spreads"), ("total", "totals")):
                r = gq[gq["market"] == key]
                if not len(r):
                    continue
                snaps = sorted(r["snapshot"].dropna().unique())
                t_open = None
                for t in snaps:
                    st = state_at(r, t)
                    if st["book"].nunique() >= 3:
                        t_open = t
                        break
                if t_open is None:
                    continue
                st = state_at(r, t_open)
                # reference-side number per book: home spread (ESPN home) or total
                if mk == "spread":
                    espn_home_name = r["away_team"].iloc[0] if g["flip"] else r["home_team"].iloc[0]
                    st = st.assign(side=np.where(st["outcome"] == espn_home_name, "home", "away"))
                    st["num"] = np.where(st["side"] == "home", st["point"], -st["point"])
                else:
                    st = st.assign(side=st["outcome"].str.lower(), num=st["point"])
                per_book = st.groupby("book")["num"].median()
                cands = []
                for _, x in st[st["book"].isin(FOUR)].iterrows():
                    others = per_book.drop(x["book"])
                    if len(others) < 2:
                        continue
                    ref = float(others.median())
                    if mk == "spread":
                        sgn = 1 if x["side"] == "home" else -1
                        edge = sgn * (g["final_margin"] + x["num"])
                        D, Q = sgn * (g["final_margin"] + ref), sgn * (x["num"] - ref)
                        res_m = sgn * (g["home_pts"] - g["away_pts"] + x["num"])
                    else:
                        sgn = 1 if x["side"] == "over" else -1
                        edge = sgn * (g["final_total"] - x["num"])
                        D, Q = sgn * (g["final_total"] - ref), sgn * (ref - x["num"])
                        res_m = sgn * (g["home_pts"] + g["away_pts"] - x["num"])
                    if edge <= 0:
                        continue
                    ev_ = float(winp(mk, edge) * payout(x["price"]) - (1 - winp(mk, edge)))
                    cands.append({"date": d["date"], "game_id": g["game_id"], "market": mk, "book": FOUR[x["book"]], "side": x["side"],
                                  "num": x["num"], "price": x["price"], "edge": edge, "ev": ev_, "D": D, "Q": Q, "ref": ref,
                                  "res": "W" if res_m > 0 else ("L" if res_m < 0 else "P"),
                                  "hours_before_tip": (g["tip"] - t_open).total_seconds() / 3600})
                if cands:
                    c = pd.DataFrame(cands).sort_values(["ev", "edge", "book"], ascending=[False, False, True]).iloc[0]
                    if c["edge"] >= THR[mk] and c["ev"] >= 0.02:
                        # line value: median across books at the last snapshot before tip, from the bet side
                        last = state_at(r, snaps[-1])
                        if mk == "spread":
                            ln = np.where(last["outcome"] == (r["away_team"].iloc[0] if g["flip"] else r["home_team"].iloc[0]), last["point"], -last["point"])
                            cl = float(np.median(ln)) if len(ln) else np.nan
                            lv = (c["num"] - cl) if c["side"] == "home" else (cl - c["num"])
                        else:
                            cl = float(last["point"].median()) if len(last) else np.nan
                            lv = (cl - c["num"]) if c["side"] == "over" else (c["num"] - cl)
                        sig.append({**c.to_dict(), "lv": lv})
                    # market-only benchmark: the four-book quote furthest from the others' median
                    cc = pd.DataFrame(cands + [])
                # market only (no model): any four-book quote 1+ points off the others' median, favorable side
                for _, x in st[st["book"].isin(FOUR)].iterrows():
                    others = per_book.drop(x["book"])
                    if len(others) < 2:
                        continue
                    ref = float(others.median())
                    adv = (x["num"] - ref) * (1 if (mk == "spread" and x["side"] == "home") else -1) if mk == "spread" else \
                        ((ref - x["num"]) if x["side"] == "over" else (x["num"] - ref))
                    if adv >= 1:
                        res_m = ((g["home_pts"] - g["away_pts"] + x["num"]) * (1 if x["side"] == "home" else -1)) if mk == "spread" else \
                            ((g["home_pts"] + g["away_pts"] - x["num"]) * (1 if x["side"] == "over" else -1))
                        mo.append({"date": d["date"], "game_id": g["game_id"], "market": mk, "price": x["price"],
                                   "res": "W" if res_m > 0 else ("L" if res_m < 0 else "P")})
        print(d["date"], "done", flush=True)
    S, M = pd.DataFrame(sig), pd.DataFrame(mo).drop_duplicates(["game_id", "market"])
    for df in (S, M):
        df["u"] = np.where(df["res"] == "W", payout(df["price"]), np.where(df["res"] == "L", -1.0, 0.0))
    S["cell"] = np.where(S["D"] >= S["market"].map(THR), "model opposes market", "model agrees") + " / " + \
        np.where(S["Q"] >= 0.5, "favorable quote", "ordinary quote")
    rows = []
    def rec(lab, g):
        dec = g[g["res"] != "P"]
        return {"group": lab, "picks": len(g), "win%": 100 * (dec["res"] == "W").mean() if len(dec) else np.nan,
                "ROI% (real prices)": 100 * g["u"].mean(), "ROI se": 100 * boot(g["u"], g["date"]),
                "line value": g["lv"].mean() if "lv" in g else np.nan, "median price": g["price"].median()}
    for mk in ("spread", "total"):
        g = S[S["market"] == mk]
        rows.append({"market": mk, **rec("current rule", g)})
        for c, gg in g.groupby("cell"):
            rows.append({"market": mk, **rec(c, gg)})
        rows.append({"market": mk, **rec("market only (1+ pt off the others, no model)", M[M["market"] == mk])})
    t = pd.DataFrame(rows)
    S.to_csv(os.path.join(OUT, "s2a_real_signals.csv"), index=False)
    t.to_csv(os.path.join(OUT, "s2a_real_cells.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string(index=False))
    print("hours before tip at the market open (picks): median", round(S["hours_before_tip"].median(), 1))
    print("pick books:", S["book"].value_counts().to_dict())


if __name__ == "__main__":
    main()
