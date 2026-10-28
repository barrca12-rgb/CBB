"""Grade the ridge-1,000 shadow's logged plays (bets/shadow_r1000/signals.csv) against final scores, live (v1)
vs ridge 1,000, at the logged line and price. For the Jan 15 read (descriptive) and March 14 (research/r1000/PLAN.md).

    python -m research.r1000.evaluate
"""
from __future__ import annotations

import os

import pandas as pd

from cbb import data

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def units(res: str, odds: float) -> float:
    o = float(odds) if pd.notna(odds) else -110.0
    return (o / 100 if o > 0 else 100 / -o) if res == "W" else (-1.0 if res == "L" else 0.0)


def main() -> None:
    s = pd.read_csv(os.path.join(ROOT, "bets", "shadow_r1000", "signals.csv"))
    g = pd.concat([data.season_games(int(x))[0][["game_id", "home_pts", "away_pts"]]
                   for x in sorted({int(d[:4]) + (1 if int(d[5:7]) >= 8 else 0) for d in s["date"]})])
    s = s.merge(g, on="game_id", how="left").dropna(subset=["home_pts"])
    m = s["home_pts"] - s["away_pts"]
    t = s["home_pts"] + s["away_pts"]
    v = pd.Series(0.0, index=s.index)
    sp = s["market"] == "spread"
    v[sp] = (m + s["line"]).where(s["side"] == "home", -m + s["line"])[sp]
    v[~sp] = (t - s["line"]).where(s["side"] == "over", s["line"] - t)[~sp]
    s["res"] = v.map(lambda x: "W" if x > 0 else ("L" if x < 0 else "P"))
    s["u"] = [units(r, o) for r, o in zip(s["res"], s["odds"])]
    s["group"] = s["other_model_signal"].map({True: "both", False: "only this model"})
    rows = []
    for keys, x in list(s.groupby(["market", "model"])) + list(s.groupby(["market", "model", "group"])):
        w, l, p = (x["res"] == "W").sum(), (x["res"] == "L").sum(), (x["res"] == "P").sum()
        rows.append({"cut": " / ".join(map(str, keys)), "plays": len(x), "W-L-P": f"{w}-{l}-{p}",
                     "win%": round(100 * w / max(w + l, 1), 2), "units (1 per play)": round(x["u"].sum(), 2),
                     "ROI %": round(100 * x["u"].mean(), 2)})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
