"""CLV against Pinnacle's no-vig close (Chad, Nov 6: "I only want to measure clv with pinnacles no vig close").

For each play:
  1. Pinnacle close: the last Pinnacle quote observed in the 15 minutes before tip: the earlier of the feed's start and
     the actual jump ball (lines/tipoffs.csv, ESPN play-by-play), so an in-game quote can never count (lines/pinnacle_log.csv
     and lines/pinnacle_log_targeted.csv, live from Nov 6; lines/pinnacle_hist.csv, the historical backfill for earlier plays).
  2. No-vig: both sides' implied probabilities scaled to sum to 1 (multiplicative), giving our side's fair chance at
     Pinnacle's number.
  3. Our number: that chance moved to the number we took with a normal approximation of the result around the close.
     The sd is set so a point is worth what it was worth in 2020-2026 games (37,424 closes; the cover chance gained
     by 2 extra points, pushes counted half; `--calibrate` reruns it): 10.8 for spreads under 20 (3.7% a point),
     14.7 for spreads of 20 or more (2.7%), 16.5 for totals (2.4%). Until Nov 6 one sd of 11.19 was used for every
     spread, which overvalued points on big spreads.
  4. CLV: expected ROI at our price = p x payout - (1 - p), in percent. Also the point difference to Pinnacle's number.
A play with no Pinnacle quote in the window has no Pinnacle CLV (counted, never zero).

    python -m cbb.clv_pinnacle [--since 2026-11-01]
    python -m cbb.clv_pinnacle --calibrate
"""
from __future__ import annotations

import argparse
import os
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOGS = [os.path.join(ROOT, "lines", f) for f in ("pinnacle_log.csv", "pinnacle_log_targeted.csv", "pinnacle_hist.csv")]
WINDOW = pd.Timedelta(minutes=15)
SD_SPREAD, SD_SPREAD_BIG, SD_TOTAL = 10.8, 14.7, 16.5
BIG = 20.0   # a closing spread of this many points or more uses SD_SPREAD_BIG


def sd(market: str, close: float) -> float:
    if market == "total":
        return SD_TOTAL
    return SD_SPREAD_BIG if abs(close) >= BIG else SD_SPREAD
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


def tips() -> pd.Series:
    """game_id -> actual jump ball (UTC) from lines/tipoffs.csv; empty when the file is missing."""
    p = os.path.join(ROOT, "lines", "tipoffs.csv")
    if not os.path.exists(p):
        return pd.Series(dtype="datetime64[ns, UTC]")
    t = pd.read_csv(p, usecols=["game_id", "actual_tip"]).dropna().drop_duplicates("game_id", keep="last")
    return pd.Series(pd.to_datetime(t["actual_tip"], utc=True, errors="coerce", format="ISO8601").to_numpy(),
                     index=t["game_id"].astype(str)).dropna()


def one(r: pd.Series, q: pd.DataFrame, tip: pd.Timestamp | None = None) -> dict:
    g = q[((q["home_id"] == r["home_id"]) & (q["away_id"] == r["away_id"])) |
          ((q["home_id"] == r["away_id"]) & (q["away_id"] == r["home_id"]))]
    if not len(g):
        return {"status": "no Pinnacle line"}
    st = g["st"].max()
    if tip is not None and not pd.isna(tip):
        st = min(st, tip)   # the feed's start can run minutes past the real jump ball (Nov 2-3 backfill: up to 8)
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
    p = N.cdf(N.inv_cdf(p_fair) + diff / sd(r["market"], float(pin_line)))
    ev = p * payout(float(r["odds"])) - (1 - p)
    return {"status": "ok", "pin_close": pin_line, "pin_price": mine, "pin_fair": round(p_fair, 4), "points": round(diff, 2),
            "p_at_ours": round(p, 4), "clv_ev": round(100 * ev, 2), "observed": c["t"].isoformat()}


def table(since: str = "2026-11-01") -> pd.DataFrame:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(b["status"] != "void") & (b["date"].astype(str) >= since)]
    q, tp = quotes(), tips()
    rows = [{"bet_id": r["bet_id"], "kind": "band B" if r.get("bet_type") == "bandB" else "main", "pick": r["pick"],
             "book": r["book"], "odds": r["odds"], "result": r["result"], **one(r, q, tp.get(str(r["game_id"])))}
            for _, r in b.iterrows()]
    return pd.DataFrame(rows)


def calibrate(seasons=range(2020, 2027), extra: float = 2.0) -> dict:
    """The sd that makes `extra` points worth what they were in past games: the cover chance gained (pushes half, both
    sides averaged) at ESPN's closing number (DraftKings, else consensus, ESPN BET, Caesars, FanDuel)."""
    from . import data
    rows = []
    for s in seasons:
        p = os.path.join(ROOT, "data", "lines", f"espn_{s}.csv")
        if not os.path.exists(p):
            continue
        l = pd.read_csv(p)
        l = l[l["book"].isin(["DraftKings", "consensus", "ESPN BET", "Caesars", "FanDuel"])].dropna(subset=["home_spread", "total"])
        sch = data.fetch("schedule", s)[["game_id", "home_score", "away_score"]].dropna()
        rows.append(l.sort_values("book").drop_duplicates("game_id").merge(sch, on="game_id"))
    d = pd.concat(rows, ignore_index=True)
    d = d[d["home_score"] > 0]
    rs = (d["home_score"] - d["away_score"] + d["home_spread"]).to_numpy(float)
    rt = (d["home_score"] + d["away_score"] - d["total"]).to_numpy(float)
    big = d["home_spread"].abs().to_numpy(float) >= BIG

    def gain(x):
        w = lambda D: ((x + D > 0).mean() + 0.5 * (x + D == 0).mean() + (-x + D > 0).mean() + 0.5 * (-x + D == 0).mean()) / 2
        return (w(extra) - w(0.0)) / extra

    out = {}
    for k, x in (("spread", rs[~big]), ("spread_big", rs[big]), ("total", rt)):
        g = gain(x)
        out[k] = {"n": int(len(x)), "per_point": round(float(g), 4), "sd": round(float(1 / (g * np.sqrt(2 * np.pi))), 2)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-11-01")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    if a.calibrate:
        print(calibrate())
        return
    t = table(a.since)
    pd.set_option("display.width", 250)
    for kind, x in t.groupby("kind"):
        ok = x[x["status"] == "ok"]
        print(f"{kind}: {len(ok)} of {len(x)} plays with a Pinnacle close; mean CLV {ok['clv_ev'].mean():+.2f}% "
              f"(median {ok['clv_ev'].median():+.2f}%), beat the no-vig close {100 * (ok['clv_ev'] > 0).mean():.0f}%, "
              f"mean {ok['points'].mean():+.2f} points vs Pinnacle's number")
    print(t["status"].value_counts().to_string())


if __name__ == "__main__":
    main()


def attach(b: pd.DataFrame) -> pd.DataFrame:
    """b with pin_status, pin_clv (expected ROI %, + = beat the no-vig close), pin_points and pin_close per bet."""
    q, tp = quotes(), tips()
    res = [one(r, q, tp.get(str(r["game_id"]))) if len(q) else {"status": "no Pinnacle line"} for _, r in b.iterrows()]
    b = b.copy()
    b["pin_status"] = [r["status"] for r in res]
    b["pin_clv"] = [r.get("clv_ev") for r in res]
    b["pin_points"] = [r.get("points") for r in res]
    b["pin_close"] = [r.get("pin_close") for r in res]
    b["pin_price"] = [r.get("pin_price") for r in res]
    return b


def coverage(s: pd.DataFrame) -> dict:
    """Decided plays (W or L): how many have a Pinnacle close, their mean Pinnacle CLV (%), the share beating the
    no-vig close and the mean points against Pinnacle's number. Missing closes are counted, never zero."""
    d = s[s["result"].isin(["W", "L"])] if "result" in s else s.iloc[0:0]
    c = d[d["pin_status"] == "ok"] if len(d) else d
    v = pd.to_numeric(c["pin_clv"], errors="coerce").dropna() if len(c) else pd.Series(dtype=float)
    pts = pd.to_numeric(c["pin_points"], errors="coerce").dropna() if len(c) else pd.Series(dtype=float)
    return {"decided": int(len(d)), "with_close": int(len(v)), "clv": round(float(v.mean()), 2) if len(v) else None,
            "beat": float((v > 0).mean()) if len(v) else None, "points": round(float(pts.mean()), 2) if len(pts) else None}
