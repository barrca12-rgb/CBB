"""Line shopping on the Option B sample (pre-registered in LOG.md): at the same pick moment and side, the best of
the big four (and of all books) vs a single book, by expected value from historical outcome distributions and by
actual results.

    python -m research.market.s5_shopping
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from research.market.s1_sample_report import FOUR, HERE, OUT, ROOT, load
from research.market.s3_followups import payout, units

THR = {"spreads": 2.5, "totals": 3.0}
MIN_N = 300


def history() -> dict:
    """{market: (closing numbers, outcomes)} oriented to the bettor: spreads pooled from both sides (number the
    side gets, side margin); totals (closing total, total points)."""
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["home_pts", "away_pts"])
    s = w.dropna(subset=["home_spread"])
    m = (s["home_pts"] - s["away_pts"]).to_numpy(float)
    hs = s["home_spread"].to_numpy(float)
    t = w.dropna(subset=["total"])
    return {"spreads": (np.concatenate([hs, -hs]), np.concatenate([m, -m])),
            "totals": (t["total"].to_numpy(float), (t["home_pts"] + t["away_pts"]).to_numpy(float))}


def outcome_dist(h, market: str, m: float) -> np.ndarray:
    """Historical outcomes for closing number m, shifted onto m."""
    c, x = h[market]
    for k in (0, 1, 2):
        sel = (np.abs(c - m) <= k + 1e-9) & (np.abs((c - m) - np.round(c - m)) < 1e-9)
        if sel.sum() >= MIN_N or k == 2:
            # spreads: the side's expected margin is -c, so moving the number from c to m shifts the margin by c - m;
            # totals: expected points are c, so the shift is m - c
            return x[sel] + ((c[sel] - m) if market == "spreads" else (m - c[sel]))


def ev(dist: np.ndarray, market: str, side: str, n: float, price: float) -> tuple[float, float]:
    """(expected units, win probability excluding pushes) for a quote at number n."""
    if market == "spreads":
        z = dist + n
    else:
        z = (dist - n) if side == "over" else (n - dist)
    if not len(z):
        return np.nan, np.nan
    pw, pl = (z > 0).mean(), (z < 0).mean()
    return float(pw * payout(price) - pl), float(pw / (pw + pl))


def states(q: pd.DataFrame, snaps) -> "iterator":
    q = q.sort_values("snapshot")
    for t in snaps:
        st = q[q["snapshot"] <= t].drop_duplicates(["event_id", "book", "market", "outcome"], keep="last")
        st = st[(st["status"] != "absent") & (st["commence_time"] > t)]
        yield t, st


def main() -> None:
    plan = json.load(open(os.path.join(HERE, "sample_plan.json")))
    fq = pd.read_csv(os.path.join(OUT, "s1_first_quotes.csv.gz"))
    emap = fq.drop_duplicates("event_id").set_index("event_id")[["game_id", "flip"]]
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl")).set_index("game_id")
    h = history()
    picks = []
    for d in plan["dates"]:
        q, s = load(d["date"])
        q = q[q["event_id"].isin(emap.index)].copy()
        q["game_id"] = q["event_id"].map(emap["game_id"])
        q["flip"] = q["event_id"].map(emap["flip"]).astype(bool)
        q = q[q["game_id"].isin(w.index)]
        q["side"] = np.where(q["market"] == "spreads",
                             np.where((q["outcome"] == q["home_team"]) != q["flip"], "home", "away"),
                             q["outcome"].str.lower())
        done = set()
        for t, st in states(q, sorted(s["snapshot"].dropna().unique())):
            for (gid, mk), g in st.groupby(["game_id", "market"]):
                if (gid, mk) in done:
                    continue
                four = g[g["book"].isin(FOUR)]
                both = four.groupby("book")["side"].nunique()
                if (both >= 2).sum() < 2:
                    continue
                four = four[four["book"].isin(both[both >= 2].index)]
                done.add((gid, mk))
                r = w.loc[gid]
                if mk == "spreads":
                    med = four.loc[four["side"] == "home", "point"].median()
                    e = r["final_margin"] + med
                    side = "home" if e >= THR[mk] else ("away" if -e >= THR[mk] else None)
                    margin = r["home_pts"] - r["away_pts"]
                else:
                    med = four.loc[four["side"] == "over", "point"].median()
                    e = r["final_total"] - med
                    side = "over" if e >= THR[mk] else ("under" if -e >= THR[mk] else None)
                if side is None:
                    continue
                g = g[g["side"] == side].copy()
                g["v"] = np.where(g["side"] == "over", -g["point"], g["point"])
                g["pay"] = g["price"].map(payout)
                ref = float(g.loc[g["book"].isin(FOUR), "point"].median())
                dist = outcome_dist(h, mk, ref)
                for _, x in g.iterrows():
                    if mk == "spreads":
                        res_pts = (margin if side == "home" else -margin) + x["point"]
                    else:
                        tot = r["home_pts"] + r["away_pts"]
                        res_pts = (tot - x["point"]) if side == "over" else (x["point"] - tot)
                    e_u, p_w = ev(dist, mk, side, x["point"], x["price"])
                    picks.append({"date": d["date"], "game_id": gid, "market": mk, "side": side, "t": t,
                                  "book": x["book"], "four": x["book"] in FOUR, "point": x["point"], "v": x["v"],
                                  "price": x["price"], "pay": x["pay"], "ev": e_u, "pwin": p_w,
                                  "u": units("W" if res_pts > 0 else ("L" if res_pts < 0 else "P"), x["price"])})
        print(d["date"], "done", flush=True)
    p = pd.DataFrame(picks)
    p.to_csv(os.path.join(OUT, "s5_quotes.csv.gz"), index=False)
    best = lambda x: x.sort_values(["v", "pay"]).iloc[-1]
    rows, by_book = [], []
    rng = np.random.default_rng(20261027)
    for mk in ("spreads", "totals"):
        pm = p[p["market"] == mk]
        per = []
        for gid, g in pm.groupby("game_id"):
            f = g[g["four"]]
            b4, ba = best(f), best(g)
            per.append({"game_id": gid, "books": len(f), "single_ev": f["ev"].mean(), "single_pw": f["pwin"].mean(),
                        "single_u": f["u"].mean(), "single_v": f["v"].mean(),
                        "b4_ev": b4["ev"], "b4_pw": b4["pwin"], "b4_u": b4["u"], "b4_v": b4["v"],
                        "ba_ev": ba["ev"], "ba_pw": ba["pwin"], "ba_u": ba["u"], "ba_v": ba["v"],
                        "b4_beats": float((b4["v"] > f["v"]).mean())})
            for _, x in f.iterrows():
                by_book.append({"market": mk, "book": FOUR[x["book"]], "ev_gain_best4_vs_this_book": b4["ev"] - x["ev"],
                                "pts_gain": b4["v"] - x["v"]})
        per = pd.DataFrame(per)
        for tag in ("b4", "ba"):
            gain = (per[f"{tag}_ev"] - per["single_ev"]).dropna().to_numpy()
            ug = (per[f"{tag}_u"] - per["single_u"]).to_numpy()
            ci = np.quantile(gain[rng.integers(0, len(gain), (5000, len(gain)))].mean(axis=1), [.025, .975])
            ciu = np.quantile(ug[rng.integers(0, len(ug), (5000, len(ug)))].mean(axis=1), [.025, .975])
            rows.append({"market": mk, "compare": "best of four" if tag == "b4" else "best of all books",
                         "picks": len(per), "picks with EV (history match)": len(gain), "avg big-four books quoting": round(per["books"].mean(), 2),
                         "pts gained vs one book": round(float((per[f"{tag}_v"] - per["single_v"]).mean()), 3),
                         "one-book EV %": round(100 * per.dropna(subset=[f"{tag}_ev", "single_ev"])["single_ev"].mean(), 2),
                         "best EV %": round(100 * per.dropna(subset=[f"{tag}_ev", "single_ev"])[f"{tag}_ev"].mean(), 2),
                         "EV gain % per bet": round(100 * gain.mean(), 2), "EV gain 95% CI": f"[{100*ci[0]:.2f}, {100*ci[1]:.2f}]",
                         "win% one book (hist.)": round(100 * per["single_pw"].mean(), 2),
                         "win% best (hist.)": round(100 * per[f"{tag}_pw"].mean(), 2),
                         "actual ROI gain %": round(100 * ug.mean(), 2), "actual 95% CI": f"[{100*ciu[0]:.2f}, {100*ciu[1]:.2f}]"})
        if mk == "spreads":
            b4row = rows[-2]
            verdict = "WORTH ACTING ON" if (b4row["EV gain % per bet"] >= 1.0 and ci_lo_pos(b4row)) else "NOT MET"
    t = pd.DataFrame(rows)
    bb = pd.DataFrame(by_book).groupby(["market", "book"]).agg(picks=("pts_gain", "size"), pts_gain=("pts_gain", "mean"),
                                                                  ev_gain_pct=("ev_gain_best4_vs_this_book", lambda v: 100 * v.mean()))
    t.to_csv(os.path.join(OUT, "s5_result.csv"), index=False)
    bb.to_csv(os.path.join(OUT, "s5_by_book.csv"))
    pd.set_option("display.width", 250)
    print(t.T.to_string())
    print(bb.round(3).to_string())
    print("spreads, pre-registered bar (+1.0% EV per bet, CI above 0):", verdict)


def ci_lo_pos(row) -> bool:
    return float(row["EV gain 95% CI"].strip("[]").split(",")[0]) > 0


if __name__ == "__main__":
    main()
