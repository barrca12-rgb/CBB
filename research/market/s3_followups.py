"""Helpers' review follow-ups on the Option B sample (pre-registered in LOG.md): (1) matched first-book vs
later-book comparison; (4) delay-window availability and results at the observed quote, for the reconciliation
table.

    python -m research.market.s3_followups
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from research.market.s1_sample_report import FOUR, HERE, OUT, load

THR = {"spreads": 2.5, "totals": 3.0}
WINDOWS = [(5, 10), (15, 25), (30, 45), (60, 80)]


def payout(o):
    o = float(o)
    return o / 100 if o > 0 else 100 / -o


def units(res, price):
    return payout(price) if res == "W" else (-1.0 if res == "L" else 0.0)


def side_rows(fq: pd.DataFrame) -> pd.DataFrame:
    """First quotes per game, market, book and side, oriented: num = the bettor's number; won = W/L/P."""
    w = pd.read_pickle(os.path.join(HERE, "..", "..", "audit", "out", "wf_live_approx.pkl"))[["game_id", "final_margin", "final_total", "home_pts", "away_pts"]]
    f = fq[fq["book"].isin(FOUR)].merge(w, on="game_id")
    rows = []
    for _, r in f.iterrows():
        if r["market"] == "spreads":
            home = (r["outcome"] == r["home_team"]) != bool(r["flip"])
            edge = (r["final_margin"] if home else -r["final_margin"]) + r["point"]
            m = (r["home_pts"] - r["away_pts"]) * (1 if home else -1) + r["point"]
            side = "home" if home else "away"
        else:
            over = str(r["outcome"]).lower() == "over"
            edge = (r["final_total"] - r["point"]) * (1 if over else -1)
            m = (r["home_pts"] + r["away_pts"] - r["point"]) * (1 if over else -1)
            side = "over" if over else "under"
        rows.append({"date": r["date"], "game_id": r["game_id"], "market": r["market"], "book": r["book"], "side": side,
                     "event_id": r["event_id"], "outcome": r["outcome"], "t": pd.Timestamp(r["snapshot"]),
                     "num": r["point"], "price": r["price"], "edge": edge, "res": "W" if m > 0 else ("L" if m < 0 else "P")})
    return pd.DataFrame(rows)


def boot_mean(v, d, n=5000):
    v, d = np.asarray(v, float), np.asarray(d)
    u = np.unique(d)
    idx = np.random.default_rng(20261026).integers(0, len(u), (n, len(u)))
    sums = np.array([[v[d == k].sum(), (d == k).sum()] for k in u])
    s = sums[idx].sum(axis=1)
    draws = s[:, 0] / s[:, 1]
    return float(v.mean()), float(np.quantile(draws, .025)), float(np.quantile(draws, .975))


def main() -> None:
    fq = pd.read_csv(os.path.join(OUT, "s1_first_quotes.csv.gz"))
    s = side_rows(fq)
    s["u"] = [units(r, p) for r, p in zip(s["res"], s["price"])]
    # first book per game and market = earliest first quote among the four
    first_t = s.groupby(["game_id", "market"])["t"].transform("min")
    s["is_first"] = s.groupby(["game_id", "market", "book"])["t"].transform("min") == first_t
    fb = s[s["is_first"]].sort_values(["game_id", "market", "book"]).drop_duplicates(["game_id", "market", "side"])
    picks = fb[fb["edge"] >= fb["market"].map(THR)]
    later = s[~s["is_first"]]
    pairs = picks.merge(later, on=["game_id", "market", "side"], suffixes=("_f", "_l"))
    pairs["du"] = pairs["u_f"] - pairs["u_l"]
    sgn = np.where(pairs["side"].isin(["home", "away", "under"]), 1, -1)   # bettor's view: higher spread / under number better
    pairs["dnum"] = sgn * (pairs["num_f"] - pairs["num_l"])
    rows = []
    for mk in ("spreads", "totals"):
        p = pairs[pairs["market"] == mk]
        eq = p[p["num_f"] == p["num_l"]]
        m, lo, hi = boot_mean(p["du"], p["date_f"])
        me, loe, hie = boot_mean(eq["du"], eq["date_f"]) if len(eq) > 1 else (np.nan, np.nan, np.nan)
        dec_f = p[p["res_f"] != "P"]
        dec_l = p[p["res_l"] != "P"]
        rows.append({"market": mk, "picks at first book": int((picks["market"] == mk).sum()), "matched pairs": len(p),
                     "win% at first quote (paired)": 100 * (dec_f["res_f"] == "W").mean(),
                     "win% at later quote (paired)": 100 * (dec_l["res_l"] == "W").mean(),
                     "paired ROI diff, first - later (units)": m, "95% CI": f"[{lo:.3f}, {hi:.3f}]",
                     "mean number advantage of first quote (pts)": p["dnum"].mean(),
                     "pairs with equal number": len(eq), "ROI diff, equal number": me, "95% CI equal": f"[{loe:.3f}, {hie:.3f}]"})
    matched = pd.DataFrame(rows)

    # delay windows after the first book's first quote: same book, same side, number equal or better, payout >= original
    plan = json.load(open(os.path.join(HERE, "sample_plan.json")))
    snaps = {d["date"]: pd.to_datetime(pd.read_csv(os.path.join(HERE, "data", f"snapshots_{d['date']}.csv"))["snapshot"], utc=True, format="ISO8601").sort_values().tolist()
             for d in plan["dates"]}
    dw = []
    for date, g in picks.groupby("date"):
        q, _ = load(date)
        for _, r in g.iterrows():
            z = q[(q["event_id"] == r["event_id"]) & (q["book"] == r["book"]) & (q["market"] == r["market"]) & (q["outcome"] == r["outcome"])].sort_values("snapshot")
            tip = pd.Timestamp(z["commence_time"].iloc[0]) if len(z) and pd.notna(z["commence_time"].iloc[0]) else None
            for lo, hi in WINDOWS:
                ws, we = r["t"] + pd.Timedelta(minutes=lo), r["t"] + pd.Timedelta(minutes=hi)
                inwin = [t for t in snaps[date] if ws <= t <= we and (tip is None or t < tip)]
                if not inwin:
                    dw.append({"date": date, "market": r["market"], "window": f"{lo}-{hi}", "status": "no snapshot"})
                    continue
                t1 = inwin[0]
                st = z[z["snapshot"] <= t1].tail(1)
                if not len(st) or st["status"].iloc[0] == "absent":
                    dw.append({"date": date, "market": r["market"], "window": f"{lo}-{hi}", "status": "unavailable"})
                    continue
                n1, p1 = st["point"].iloc[0], st["price"].iloc[0]
                better = (n1 >= r["num"]) if r["market"] == "spreads" or r["side"] == "under" else (n1 <= r["num"])
                ok = better and payout(p1) >= payout(r["price"]) - 1e-9
                res = r["res"] if n1 == r["num"] else None
                if n1 != r["num"]:
                    w_ = pd.read_pickle(os.path.join(HERE, "..", "..", "audit", "out", "wf_live_approx.pkl")) if False else None
                dw.append({"date": date, "market": r["market"], "window": f"{lo}-{hi}",
                           "status": "available at number or better" if ok else "moved or worse price",
                           "u_at_quote": units(r["res"], p1) if (ok and n1 == r["num"]) else np.nan})
    d = pd.DataFrame(dw)
    d["cadence"] = np.where(d["date"] == "2025-01-11", "5-min (Jan 11)", "30-min")
    avail = d.groupby(["market", "cadence", "window", "status"]).size().unstack(fill_value=0)
    roi = d[d["status"] == "available at number or better"].groupby(["market", "cadence", "window"])["u_at_quote"].agg(["count", "mean"])
    matched.to_csv(os.path.join(OUT, "s3_matched.csv"), index=False)
    avail.to_csv(os.path.join(OUT, "s3_windows.csv"))
    pd.set_option("display.width", 250)
    print("unmatched cohorts (as first reported), first book vs later books:")
    for mk in ("spreads", "totals"):
        a, b = picks[picks["market"] == mk], later[(later["market"] == mk) & (later["edge"] >= THR[mk])]
        wr = lambda x: 100 * (x["res"] == "W").sum() / max((x["res"] != "P").sum(), 1)
        print(f"  {mk}: first-book picks {len(a)} {wr(a):.1f}% | later-book picks (own selection) {len(b)} {wr(b):.1f}%")
    print(matched.round(3).to_string(index=False))
    print(avail.to_string())
    print(roi.round(3).to_string())


if __name__ == "__main__":
    main()
