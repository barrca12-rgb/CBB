"""Team totals at real lines (pre-registered in LOG.md).

    python -m research.team_totals.t_real
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.market.s3_followups import payout, units

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
ORDER = ["DraftKings", "FanDuel", "Caesars"]
THR = 3.0


def boot(v, d, n=5000):
    """Game-level (cluster) bootstrap of the mean."""
    v, d = np.asarray(v, float), np.asarray(d)
    u, inv = np.unique(d, return_inverse=True)
    s, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(20261027).integers(0, len(u), (n, len(u)))
    return np.quantile(s[i].sum(1) / c[i].sum(1), [.025, .975])


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    l = pd.read_csv(os.path.join(ROOT, "data", "research", "tt_lines.csv"))
    l = l[(l["status"] == "ok") & l["book"].isin(ORDER)].dropna(subset=["team_id", "point"])
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[~evaluate.swapped(w.assign(pred_margin=w["final_margin"]))]
    w = w[["game_id", "date", "home_id", "away_id", "home_pts", "away_pts", "final_margin", "final_total", "home_spread", "total"]]
    l = l.merge(w, on="game_id")
    home = l["team_id"].astype(int) == l["home_id"]
    l = l[home | (l["team_id"].astype(int) == l["away_id"])]
    home = l["team_id"].astype(int) == l["home_id"]
    l["model"] = np.where(home, (l["final_total"] + l["final_margin"]) / 2, (l["final_total"] - l["final_margin"]) / 2)
    l["proxy"] = np.where(home, (l["total"] - l["home_spread"]) / 2, (l["total"] + l["home_spread"]) / 2)
    l["actual"] = np.where(home, l["home_pts"], l["away_pts"])
    l["edge"] = l["model"] - l["point"]
    l["hold"] = 1 / (1 + l["over_price"].map(payout)) + 1 / (1 + l["under_price"].map(payout)) - 1
    l["o"] = l["book"].map({b: i for i, b in enumerate(ORDER)})
    ref = l.sort_values("o").drop_duplicates(["game_id", "team_id"]).copy()

    def grade(d):
        over = d["edge"] > 0
        m = np.where(over, d["actual"] - d["point"], d["point"] - d["actual"])
        price = np.where(over, d["over_price"], d["under_price"])
        u = [units("W" if x > 0 else ("L" if x < 0 else "P"), p) for x, p in zip(m, price)]
        return d.assign(side=np.where(over, "over", "under"), m=m, price=price, u=u)

    rows = []
    for t in (2.5, 3.0, 4.0, 5.0):
        p = grade(ref[ref["edge"].abs() >= t])
        for part, x in (("all", p), ("overs", p[p["side"] == "over"]), ("unders", p[p["side"] == "under"])):
            if not len(x):
                continue
            dec = x[x["m"] != 0]
            ci = boot(x["u"], x["game_id"])
            be = np.mean([1 / (1 + payout(v)) for v in x["price"]])
            rows.append({"threshold": t, "side": part, "plays": len(x), "win%": round(100 * (dec["m"] > 0).mean(), 2),
                         "break-even win% (avg price)": round(100 * be, 2), "ROI %": round(100 * x["u"].mean(), 2),
                         "ROI 95% CI": f"[{100*ci[0]:.1f}, {100*ci[1]:.1f}]"})
    t = pd.DataFrame(rows)
    # best number, then price, across the three books, same side as the reference play
    p = grade(ref[ref["edge"].abs() >= THR])
    best = []
    for _, r in p.iterrows():
        c = l[(l["game_id"] == r["game_id"]) & (l["team_id"] == r["team_id"])].copy()
        c["v"] = -c["point"] if r["side"] == "over" else c["point"]
        c["pr"] = c["over_price"] if r["side"] == "over" else c["under_price"]
        c = c.assign(pay=c["pr"].map(payout)).sort_values(["v", "pay"]).iloc[-1]
        mm = (r["actual"] - c["point"]) * (1 if r["side"] == "over" else -1)
        best.append(units("W" if mm > 0 else ("L" if mm < 0 else "P"), c["pr"]))
    p["u_best"] = best
    p["month"] = pd.to_datetime(p["date"]).dt.strftime("%Y-%m")
    by_month = p.groupby("month").agg(plays=("u", "size"), win=("m", lambda m: round(100 * (m > 0).sum() / max((m != 0).sum(), 1), 1)),
                                      roi=("u", lambda u: round(100 * u.mean(), 1)))
    ci = boot(p["u"], p["game_id"])
    roi = p["u"].mean()
    verdict = "PASS" if ci[0] > 0 else ("PROMISING" if roi > 0 else "KILL")
    desc = {"team lines graded (reference)": len(ref), "games": ref["game_id"].nunique(),
            "hold by book %": (l.groupby("book")["hold"].mean() * 100).round(2).to_dict(),
            "real line - proxy, mean (pts)": round(float((ref["point"] - ref["proxy"]).mean()), 3),
            "real line - proxy, mean abs (pts)": round(float((ref["point"] - ref["proxy"]).abs().mean()), 3),
            "model MAE / line MAE": (round(float((ref["model"] - ref["actual"]).abs().mean()), 3), round(float((ref["point"] - ref["actual"]).abs().mean()), 3)),
            "plays at 3.0": len(p), "ROI % at reference book": round(100 * roi, 2), "95% CI": f"[{100*ci[0]:.1f}, {100*ci[1]:.1f}]",
            "ROI % at best of three": round(100 * float(np.mean(best)), 2), "verdict": verdict}
    t.to_csv(os.path.join(OUT, "t_ladder.csv"), index=False)
    by_month.to_csv(os.path.join(OUT, "t_by_month.csv"))
    p.to_csv(os.path.join(OUT, "t_plays.csv"), index=False)
    pd.set_option("display.width", 250)
    for k, v in desc.items():
        print(f"{k}: {v}")
    print(t.to_string(index=False))
    print(by_month.to_string())


if __name__ == "__main__":
    main()
