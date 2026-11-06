"""CLV against Pinnacle's no-vig close (Chad, Nov 6: "I only want to measure clv with pinnacles no vig close").

For each play:
  1. Pinnacle close: the last Pinnacle quote observed in the 15 minutes before the feed's start (lines/pinnacle_log.csv,
     live from Nov 6; lines/pinnacle_hist.csv, the historical backfill for earlier plays).
  2. No-vig: both sides' implied probabilities scaled to sum to 1 (multiplicative), giving our side's fair chance at
     Pinnacle's number.
  3. Our number: that chance moved to the number we took with a normal approximation of the result around the close
     (sd 11.19 points for spreads, 16.5 for totals: 2020-2026 games, the final result minus the closing line).
  4. CLV: expected ROI at our price = p x payout - (1 - p), in percent. Also the point difference to Pinnacle's number.
A play with no Pinnacle quote in the window has no Pinnacle CLV (counted, never zero).

    python -m cbb.clv_pinnacle [--since 2026-11-01]
"""
from __future__ import annotations

import argparse
import os
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOGS = [os.path.join(ROOT, "lines", "pinnacle_log.csv"), os.path.join(ROOT, "lines", "pinnacle_hist.csv")]
WINDOW = pd.Timedelta(minutes=15)
SD = {"spread": 11.19, "total": 16.5}
N = NormalDist()


def implied(o: float) -> float:
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def payout(o: float) -> float:
    return o / 100 if o > 0 else 100 / -o


def quotes() -> pd.DataFrame:
    parts = [pd.read_csv(p) for p in LOGS if os.path.exists(p)]
    if not parts:
        return pd.DataFrame()
    q = pd.concat(parts, ignore_index=True)
    q["t"] = pd.to_datetime(q["observed_at"], utc=True, errors="coerce", format="ISO8601")
    q["st"] = pd.to_datetime(q["start"], utc=True, errors="coerce", format="ISO8601")
    return q.dropna(subset=["t", "st"])


def one(r: pd.Series, q: pd.DataFrame) -> dict:
    g = q[((q["home_id"] == r["home_id"]) & (q["away_id"] == r["away_id"])) |
          ((q["home_id"] == r["away_id"]) & (q["away_id"] == r["home_id"]))]
    if not len(g):
        return {"status": "no Pinnacle line"}
    st = g["st"].max()
    w = g[(g["t"] < st) & (g["t"] >= st - WINDOW)].sort_values("t")
    col = ["home_spread", "home_spread_odds", "away_spread_odds"] if r["market"] == "spread" else ["total", "over_odds", "under_odds"]
    w = w.dropna(subset=col)
    if not len(w):
        return {"status": "no Pinnacle quote in the 15 minutes before tip"}
    c = w.iloc[-1]
    same = c["home_id"] == r["home_id"]
    if r["market"] == "spread":
        home_line = c["home_spread"] if same else -c["home_spread"]
        h_odds, a_odds = (c["home_spread_odds"], c["away_spread_odds"]) if same else (c["away_spread_odds"], c["home_spread_odds"])
        pin_line = home_line if r["side"] == "home" else -home_line
        mine, other = (h_odds, a_odds) if r["side"] == "home" else (a_odds, h_odds)
        diff = float(r["line"]) - pin_line                      # + = we have more points than Pinnacle's close
    else:
        pin_line = c["total"]
        mine, other = (c["over_odds"], c["under_odds"]) if r["side"] == "over" else (c["under_odds"], c["over_odds"])
        diff = (float(r["line"]) - pin_line) if r["side"] == "under" else (pin_line - float(r["line"]))
    pm, po = implied(float(mine)), implied(float(other))
    p_fair = pm / (pm + po)
    p = N.cdf(N.inv_cdf(p_fair) + diff / SD[r["market"]])
    ev = p * payout(float(r["odds"])) - (1 - p)
    return {"status": "ok", "pin_close": pin_line, "pin_price": mine, "pin_fair": round(p_fair, 4), "points": round(diff, 2),
            "p_at_ours": round(p, 4), "clv_ev": round(100 * ev, 2), "observed": c["t"].isoformat()}


def table(since: str = "2026-11-01") -> pd.DataFrame:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(b["status"] != "void") & (b["date"].astype(str) >= since)]
    q = quotes()
    rows = [{"bet_id": r["bet_id"], "kind": "band B" if r.get("bet_type") == "bandB" else "main", "pick": r["pick"],
             "book": r["book"], "odds": r["odds"], "result": r["result"], **one(r, q)} for _, r in b.iterrows()]
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-11-01")
    t = table(ap.parse_args().since)
    pd.set_option("display.width", 250)
    for kind, x in t.groupby("kind"):
        ok = x[x["status"] == "ok"]
        print(f"{kind}: {len(ok)} of {len(x)} plays with a Pinnacle close; mean CLV {ok['clv_ev'].mean():+.2f}% "
              f"(median {ok['clv_ev'].median():+.2f}%), beat the no-vig close {100 * (ok['clv_ev'] > 0).mean():.0f}%, "
              f"mean {ok['points'].mean():+.2f} points vs Pinnacle's number")
    print(t["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
