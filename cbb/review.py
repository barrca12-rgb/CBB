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
    if b is None:   # CLV from the protocol's primary close, as every other surface (cbb/clv_primary.py)
        from . import clv_primary
        b = clv_primary.attach(tracker.load())
    s = b[b["status"] == "settled"].copy()
    if not len(s):
        return s.assign(reason=[], luck=[])
    s["luck"] = _three_luck(s)
    s["news"] = _late_news(s)
    clv = s["clv_pts"].astype(float)
    reason = np.where(clv.isna(), "No primary close",
             np.where(clv > 0, "Beat the close",
             np.where(s["luck"] <= -SHOOTING_SWING, "Shooting luck",
             np.where((clv < 0) & s["news"], "Late injury news",
             np.where(clv < 0, "Market disagreed", "Closed at our number")))))
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
    s["venue"] = np.where(s["market"] == "total", "Total (n/a)", "")
    cards = {}
    import glob
    for p in glob.glob(os.path.join(os.path.dirname(__file__), "..", "reports", "cbb_*.csv")):
        d = pd.read_csv(p, usecols=lambda c: c in ("game_id", "neutral"))
        cards.update(dict(zip(d["game_id"], d["neutral"])))
    neutral = s["game_id"].map(cards).fillna(False).astype(bool)
    s.loc[s["market"] == "spread", "venue"] = np.where(neutral, "Neutral site", np.where(s["side"] == "home", "Bet home team", "Bet away team"))[s["market"] == "spread"]
    losses = s[s["result"] == "L"]
    out = {"losses_by_reason": losses["reason"].value_counts().to_dict(), "total_losses": len(losses)}
    for key, col in [("by_reason", "reason"), ("by_market", "market"), ("by_edge", "edge_bk"), ("by_month", "month"),
                     ("by_venue", "venue")]:
        out[key] = {str(k): _agg(d) for k, d in s.groupby(col, observed=True)}
    worst = losses[losses["reason"] == "Market disagreed"].sort_values("clv_pts").head(10)
    try:
        out["home_court"] = home_court()
    except Exception:
        out["home_court"] = {}
    out["model_misses"] = worst[["date", "away", "home", "pick", "line", "close_line", "clv_pts", "model",
                                 "away_score", "home_score"]].to_dict("records")
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=1, default=str))


def home_court(season: int | None = None) -> dict:
    """Is our home edge right? Every game a card projected (reports/cbb_<date>.csv keeps the model margin) against
    the final score and the closing line, split by home vs neutral, plus each team with 5+ home games.

    resid = actual home margin - model margin (+ = home teams beat our number: home edge too low)
    vs_close = closing line's home margin - model margin (+ = the market gives home teams more than we do)"""
    import glob
    rep = os.path.join(os.path.dirname(__file__), "..", "reports")
    cards = [pd.read_csv(p) for p in sorted(glob.glob(os.path.join(rep, "cbb_*.csv")))]
    if not cards:
        return {}
    c = pd.concat(cards).drop_duplicates("game_id", keep="last")
    c = c[["game_id", "home_id", "away_id", "home", "neutral", "model_margin", "line_home_spread"]]
    season = season or max(int(str(d)[:4]) for d in pd.concat(cards)["start"].dropna().str[:4])
    finals = []
    for s in {season, season + 1}:
        try:
            g, _ = data.season_games(s, refresh=True)
            finals.append(g[["game_id", "home_pts", "away_pts"]])
        except Exception:
            pass
    if not finals:
        return {}
    c = c.merge(pd.concat(finals), on="game_id", how="inner")
    if not len(c):
        return {}
    c["resid"] = (c["home_pts"] - c["away_pts"]) - c["model_margin"]
    c["vs_close"] = -c["line_home_spread"] - c["model_margin"]
    def agg(d):
        n = len(d)
        return {"games": n, "resid": round(float(d["resid"].mean()), 2) if n else None,
                "resid_se": round(float(d["resid"].std() / np.sqrt(n)), 2) if n > 1 else None,
                "vs_close": round(float(d["vs_close"].mean()), 2) if d["vs_close"].notna().any() else None}
    home = c[~c["neutral"].astype(bool)]
    teams = home.groupby("home").filter(lambda d: len(d) >= 5).groupby("home")["resid"].agg(["mean", "size"])
    teams = teams.sort_values("mean")
    return {"home": agg(home), "neutral": agg(c[c["neutral"].astype(bool)]),
            "teams_low": [(t, round(r["mean"], 1), int(r["size"])) for t, r in teams.head(5).iterrows()],
            "teams_high": [(t, round(r["mean"], 1), int(r["size"])) for t, r in teams.tail(5)[::-1].iterrows()]}
