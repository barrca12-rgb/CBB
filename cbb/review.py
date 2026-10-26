"""Loss review: why each graded bet won or lost, and where the record is coming from.

Every settled bet in bets/bets.csv gets a reason (losses especially):

  beat_close     our number was better than the close: the market moved our way, so a loss is variance
  shooting       3-point luck swung the game against us by 6+ points (makes vs the league rate on the attempts,
                 both teams, from that game's box score)
  late_news      the line moved against us and one of the two teams showed up on the injury report after we bet
  model_miss     the line moved against us with no news: the market disagreed and was right. These are the ones
                 to study.
  even           closed at our number (or no closing line) and none of the above

summary() breaks the record and CLV down by reason, market, edge size and month, for the card's Review section.
Run directly for a text report:  python -m cbb.review
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import data, tracker

INJURY_LOG = os.path.join(os.path.dirname(__file__), "..", "injuries", "log.csv")
SHOOTING_SWING = 6.0     # points of 3-point luck against our side to call it a shooting loss


def _three_luck(bets: pd.DataFrame) -> pd.Series:
    """Points of 3-point luck for our side in each bet's game (+ = luck helped us)."""
    out = pd.Series(np.nan, index=bets.index)
    for season in sorted({int(d[:4]) + (int(d[5:7]) >= 8) for d in bets["date"]}):
        try:
            _, t = data.season_games(season, refresh=True)
        except Exception:
            continue
        p3 = t["fg3m"].sum() / t["fg3a"].sum()
        t = t.assign(luck=3 * (t["fg3m"] - t["fg3a"] * p3))
        by = t.set_index(["game_id", "team_id"])["luck"]
        for i, r in bets.iterrows():
            h = by.get((int(r["game_id"]), int(r["home_id"])), np.nan)
            a = by.get((int(r["game_id"]), int(r["away_id"])), np.nan)
            if r["market"] == "spread":
                out[i] = (h - a) if r["side"] == "home" else (a - h)
            else:
                out[i] = (h + a) if r["side"] == "over" else -(h + a)
    return out


def _late_news(bets: pd.DataFrame) -> pd.Series:
    """True if either team appeared on the injury report after the bet was logged and before the game day ended."""
    if not os.path.exists(INJURY_LOG):
        return pd.Series(False, index=bets.index)
    log = pd.read_csv(INJURY_LOG)
    log["pulled_at"] = pd.to_datetime(log["pulled_at"], utc=True)
    out = []
    for _, r in bets.iterrows():
        t0 = pd.to_datetime(r["logged_at"], utc=True)
        t1 = pd.Timestamp(r["date"], tz="America/New_York") + pd.Timedelta(days=1)
        m = log[log["team_id"].isin([r["home_id"], r["away_id"]]) & (log["pulled_at"] > t0) & (log["pulled_at"] < t1)]
        out.append(len(m) > 0)
    return pd.Series(out, index=bets.index)


def classify(b: pd.DataFrame | None = None) -> pd.DataFrame:
    b = tracker.load() if b is None else b
    s = b[b["status"] == "settled"].copy()
    if not len(s):
        return s.assign(reason=[], luck=[])
    s["luck"] = _three_luck(s)
    s["news"] = _late_news(s)
    clv = s["clv_pts"].astype(float)
    reason = np.where(clv > 0, "Beat the close",
             np.where(s["luck"] <= -SHOOTING_SWING, "Shooting luck",
             np.where((clv < 0) & s["news"], "Late injury news",
             np.where(clv < 0, "Market disagreed", "Closed at our number"))))
    s["reason"] = reason
    return s


def _agg(d: pd.DataFrame) -> dict:
    w, l = int((d["result"] == "W").sum()), int((d["result"] == "L").sum())
    staked = d["stake"].astype(float).sum()
    return {"bets": len(d), "w": w, "l": l, "win": w / (w + l) if w + l else None,
            "units": round(float(d["profit"].astype(float).sum()), 2),
            "roi": round(float(d["profit"].astype(float).sum() / staked), 4) if staked else None,
            "clv": round(float(d["clv_pts"].astype(float).mean()), 2) if d["clv_pts"].notna().any() else None}


def summary(b: pd.DataFrame | None = None) -> dict:
    s = classify(b)
    if not len(s):
        return {}
    s["edge_bk"] = pd.cut(s["edge"].astype(float), [0, 3.5, 4.5, 6, 99], labels=["3-3.5", "3.5-4.5", "4.5-6", "6+"])
    s["month"] = pd.to_datetime(s["date"]).dt.strftime("%b")
    losses = s[s["result"] == "L"]
    out = {"losses_by_reason": losses["reason"].value_counts().to_dict(), "total_losses": len(losses)}
    for key, col in [("by_reason", "reason"), ("by_market", "market"), ("by_edge", "edge_bk"), ("by_month", "month")]:
        out[key] = {str(k): _agg(d) for k, d in s.groupby(col, observed=True)}
    worst = losses[losses["reason"] == "Market disagreed"].sort_values("clv_pts").head(10)
    out["model_misses"] = worst[["date", "away", "home", "pick", "line", "close_line", "clv_pts", "model",
                                 "away_score", "home_score"]].to_dict("records")
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=1, default=str))
