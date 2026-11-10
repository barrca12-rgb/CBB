"""Sharp-market shadow (Chad, Nov 10, 2026: "shadow it"). Display/research only: never changes the card or stakes.

For each main play, take the newest sharp quote (Novig, Pinnacle, BetOnline) seen at or before the play was logged,
for the same game and market. gap = how many points better our number is than the sharp number on our side;
sharp_edge = the model's edge measured against the sharp number (edge - gap).
The rule under test: flag the play (skip, or minimum stake) when a sharp line is up and the model still disagrees
with it by GAP or more points (the smallest sharp_edge across sharp books >= GAP).
Output: bets/shadow_sharp.csv, one row per main play, refreshed on each run.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAP = 2.0
MAX_PRICE = 200  # |American odds| above this on either side = no real market
SINCE = "2026-10-30"
OUT = os.path.join(ROOT, "bets", "shadow_sharp.csv")
SOURCES = {"Novig": ("novig_log.csv", "pulled_at"), "Pinnacle": ("pinnacle_log.csv", "observed_at"),
           "PinnacleT": ("pinnacle_log_targeted.csv", "observed_at"), "BetOnline": ("betonline_log.csv", "observed_at")}


def quotes() -> pd.DataFrame:
    out = []
    for name, (f, ts) in SOURCES.items():
        p = os.path.join(ROOT, "lines", f)
        if not os.path.exists(p):
            continue
        q = pd.read_csv(p)
        q["sharp"] = "Pinnacle" if name.startswith("Pinnacle") else name
        q["seen"] = pd.to_datetime(q[ts], utc=True, errors="coerce")
        q["gday"] = pd.to_datetime(q["start"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        # Novig is an exchange: with no money on a game it lists an empty ladder rung (prices like -9900) at a
        # fake line. Keep a number only when both sides are priced like a real market.
        ok = lambda a, b: q[a].abs().le(MAX_PRICE) & q[b].abs().le(MAX_PRICE)
        q.loc[~ok("home_spread_odds", "away_spread_odds"), "home_spread"] = np.nan
        q.loc[~ok("over_odds", "under_odds"), "total"] = np.nan
        out.append(q[["sharp", "seen", "gday", "home_id", "away_id", "home_spread", "total"]])
    q = pd.concat(out, ignore_index=True)
    for c in ("home_id", "away_id"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    return q.dropna(subset=["seen"])


def gap(r: pd.Series, s: pd.Series) -> float:
    """Points our number is better than the sharp number, on our side."""
    if r["market"] == "spread":
        sharp = s["home_spread"] if r["side"] == "home" else -s["home_spread"]
        return float(r["line"] - sharp)
    if pd.isna(s["total"]):
        return np.nan
    return float(s["total"] - r["line"]) if r["side"] == "over" else float(r["line"] - s["total"])


def table(since: str = SINCE) -> pd.DataFrame:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[b["bet_type"].isna() & (b["status"] != "void") & (b["date"].astype(str) >= since)].copy()
    b["t"] = pd.to_datetime(b["logged_at"], utc=True, errors="coerce")
    q = quotes()
    rows = []
    for _, r in b.iterrows():
        m = q[(q["gday"] == str(r["date"])) & (q["home_id"] == r["home_id"]) & (q["away_id"] == r["away_id"])
              & (q["seen"] <= r["t"])]
        col = "home_spread" if r["market"] == "spread" else "total"
        m = m[m[col].notna()]
        row = {"bet_id": r["bet_id"], "date": r["date"], "market": r["market"], "pick": r["pick"], "line": r["line"],
               "odds": r["odds"], "edge": r["edge"], "stake": r["stake"], "result": r["result"],
               "profit": r["profit"]}
        best = None
        for name, g in m.sort_values("seen").groupby("sharp"):
            s = g.iloc[-1]
            x = gap(r, s)
            row[f"{name.lower()}_line"] = s[col]
            row[f"{name.lower()}_gap"] = x
            if pd.notna(x) and (best is None or x > best):
                best = x
        row["sharp_up"] = best is not None
        row["max_gap"] = best
        row["sharp_edge"] = None if best is None else round(float(r["edge"]) - best, 2)
        row["flag"] = bool(best is not None and float(r["edge"]) - best >= GAP)
        rows.append(row)
    return pd.DataFrame(rows)


def flat(r: pd.Series) -> float:
    if r["result"] == "W":
        return 100 / abs(r["odds"]) if r["odds"] < 0 else r["odds"] / 100
    return -1.0 if r["result"] == "L" else 0.0


def summary(t: pd.DataFrame) -> pd.DataFrame:
    s = t[t["result"].isin(["W", "L", "P"])].copy()
    s["flat"] = s.apply(flat, axis=1)
    s["grp"] = np.where(s["flag"], "flagged: sharp up, model off it by 2+",
                        np.where(s["sharp_up"], "sharp up, model within 2", "no sharp line yet"))
    return s.groupby("grp").agg(n=("flat", "size"), W=("result", lambda x: (x == "W").sum()),
                                L=("result", lambda x: (x == "L").sum()), flat_u=("flat", "sum"),
                                staked_u=("profit", "sum")).round(2)


def main() -> None:
    t = table()
    t.to_csv(OUT, index=False)
    print(summary(t).to_string())


if __name__ == "__main__":
    main()
