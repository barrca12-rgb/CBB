"""Bet tracking, closing line value (CLV) and an automatic shutoff, like the NFL model's tracker.

Every daily run (run_day.py) does three things here, so nothing needs logging by hand:

  settle()   bets from earlier days: closing line (last pregame number at the same book, lines/closing.csv),
             final score, result, profit and CLV
  log(card)  every BET on today's card, recorded once: the number, price and book when it first showed up
  status()   record, ROI and CLV per market, and the stake multiplier the card applies

Bets live in bets/bets.csv. Edit a row to the line, price or stake you actually got; set `placed` to "no" for a
bet you skipped (it's still graded, but report() also shows placed bets on their own).

CLV: points you got versus the close from the same side (+1 = a point better than the close). clv_prob prices that
with the result's spread around the closing line (2020-2026: 11.3 points for margins, 16.5 for totals): the cover
probability at your number minus at the close. Beating the close by more than half the vig (2.4%) on average is
what an edge looks like long before the win rate can show it.

Shutoff: each market starts from its backtested win rate (against the opener, 2024-2026) as a prior worth 100 bets;
the stake multiplier is how far the live-updated win rate still sits above break-even relative to the backtest:
    multiplier = clip((posterior - 0.524) / (backtest - 0.524), 0, 1)
and it's capped at 0.5 if a market averages negative CLV after 25 bets.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
BETS = os.path.join(ROOT, "bets", "bets.csv")
CLOSING = os.path.join(ROOT, "lines", "closing.csv")
MARKETS = {"spread": {"backtest": 0.582, "sd": 11.34}, "total": {"backtest": 0.575, "sd": 16.5}}
BREAKEVEN = 110 / 210
PRIOR_BETS = 100
MIN_CLV_BETS = 25
CLV_TARGET = 0.5 * (2 * BREAKEVEN - 1)
COLS = ["bet_id", "date", "game_id", "market", "pick", "side", "home_id", "away_id", "home", "away", "line", "odds",
        "book", "edge", "model", "stake", "placed", "logged_at", "close_line", "clv_pts", "clv_prob", "home_score",
        "away_score", "result", "profit", "status"]


def load() -> pd.DataFrame:
    if not os.path.exists(BETS):
        return pd.DataFrame(columns=COLS)
    b = pd.read_csv(BETS, dtype={"bet_id": str, "result": str, "status": str, "placed": str, "side": str})
    return b.reindex(columns=COLS)


def save(b: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(BETS), exist_ok=True)
    b[COLS].to_csv(BETS, index=False)


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def payout(odds) -> float:
    o = -110.0 if odds is None or (isinstance(odds, float) and math.isnan(odds)) else float(odds)
    return o / 100 if o > 0 else 100 / -o


def log(card: pd.DataFrame, day: pd.Timestamp, stakes: dict | None = None) -> int:
    """Record today's BET plays that aren't logged yet. Returns how many were added."""
    b = load()
    have = set(b["bet_id"].astype(str))
    stakes = stakes or {}
    now = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    new = []
    for _, g in card.iterrows():
        for mk in ("spread", "total"):
            if g.get(f"{mk}_verdict") != "BET":
                continue
            side = g["spread_side"] if mk == "spread" else str(g["total_pick"]).lower()
            bid = f"{day:%Y-%m-%d}|{int(g['game_id'])}|{mk}|{side}"
            if bid in have:
                continue
            new.append({"bet_id": bid, "date": f"{day:%Y-%m-%d}", "game_id": int(g["game_id"]), "market": mk,
                        "pick": f"{g[mk + '_pick']} {g[mk + '_line']:+g}" if mk == "spread" else f"{g['total_pick']} {g['total_line']:g}",
                        "side": side, "home_id": int(g["home_id"]), "away_id": int(g["away_id"]), "home": g["home"],
                        "away": g["away"], "line": g[f"{mk}_line"], "odds": g.get(f"{mk}_odds"), "book": g.get(f"{mk}_book"),
                        "edge": round(float(g[f"{mk}_edge"]), 2),
                        "model": round(float(g["model_margin"] if mk == "spread" else g["model_total"]), 2),
                        "stake": stakes.get(mk, 1.0), "placed": "", "logged_at": now, "status": "open"})
    if new:
        b = pd.concat([b, pd.DataFrame(new)], ignore_index=True) if len(b) else pd.DataFrame(new)
        save(b.reindex(columns=COLS))
    return len(new)


def _closing(bet: pd.Series, closing: pd.DataFrame) -> float:
    """Last pregame number at the bet's book (or the median of all books), from the bet's side."""
    c = closing[(closing["date"] == bet["date"])]
    same = c[(c["home_id"] == bet["home_id"]) & (c["away_id"] == bet["away_id"])]
    flip = c[(c["home_id"] == bet["away_id"]) & (c["away_id"] == bet["home_id"])]
    flipped = not len(same) and len(flip)
    c = flip if flipped else same
    if not len(c):
        return np.nan
    at = c[c["book"] == bet["book"]]
    c = at if len(at) else c
    if bet["market"] == "total":
        return float(c["total"].median())
    hs = float(c["home_spread"].median()) * (-1 if flipped else 1)
    return hs if bet["side"] == "home" else -hs


def settle(scores: pd.DataFrame | None = None) -> int:
    """Grade open bets whose games are final. scores: game_id, home_score, away_score, state (from run_day.slate);
    fetched per date when not given. Returns how many were settled."""
    b = load()
    if not len(b):
        return 0
    from .run_day import slate
    closing = pd.read_csv(CLOSING) if os.path.exists(CLOSING) else pd.DataFrame(
        columns=["date", "home_id", "away_id", "book", "home_spread", "total"])
    n = 0
    for d in sorted(b.loc[b["status"] == "open", "date"].unique()):
        if pd.Timestamp(d) >= pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None) + pd.Timedelta(days=1):
            continue
        sc = scores if scores is not None else slate(pd.Timestamp(d))
        sc = sc.set_index("game_id")
        for i in b.index[(b["date"] == d) & (b["status"] == "open")]:
            g = sc.loc[b.at[i, "game_id"]] if b.at[i, "game_id"] in sc.index else None
            if g is None or g.get("state") != "post":
                continue
            hs, as_ = float(g["home_score"]), float(g["away_score"])
            bet = b.loc[i]
            line = float(bet["line"])
            if bet["market"] == "spread":
                margin = (hs - as_) if bet["side"] == "home" else (as_ - hs)
                res = margin + line
            else:
                res = (hs + as_ - line) * (1 if bet["side"] == "over" else -1)
            result = "W" if res > 0 else "L" if res < 0 else "P"
            stake = float(bet["stake"]) if pd.notna(bet["stake"]) else 1.0
            profit = stake * payout(bet["odds"]) if result == "W" else -stake if result == "L" else 0.0
            close = _closing(bet, closing)
            sd = MARKETS[bet["market"]]["sd"]
            if bet["market"] == "spread":
                clv = line - close
                cp = _phi((line - close) / sd) - 0.5 if pd.notna(close) else np.nan
            else:
                clv = (close - line) if bet["side"] == "over" else (line - close)
                cp = _phi(clv / sd) - 0.5 if pd.notna(close) else np.nan
            b.loc[i, ["home_score", "away_score", "result", "profit", "close_line", "clv_pts", "clv_prob", "status"]] = [
                hs, as_, result, round(profit, 3), close, clv, cp, "settled"]
            n += 1
    if n:
        save(b)
    return n


def status(b: pd.DataFrame | None = None) -> dict:
    """Per market: record, ROI, CLV and stake multiplier."""
    b = load() if b is None else b
    out = {}
    for mk, cfg in MARKETS.items():
        s = b[(b["market"] == mk) & (b["status"] == "settled")]
        w, l, p = (s["result"] == "W").sum(), (s["result"] == "L").sum(), (s["result"] == "P").sum()
        n = w + l
        post = (cfg["backtest"] * PRIOR_BETS + w) / (PRIOR_BETS + n)
        mult = float(np.clip((post - BREAKEVEN) / (cfg["backtest"] - BREAKEVEN), 0, 1))
        clv = s["clv_pts"].dropna()
        if len(clv) >= MIN_CLV_BETS and clv.mean() < 0:
            mult = min(mult, 0.5)
        staked = s["stake"].astype(float).sum()
        out[mk] = {"bets": int(len(s)), "w": int(w), "l": int(l), "p": int(p), "win": (w / n) if n else None,
                   "units": round(float(s["profit"].astype(float).sum()), 2),
                   "roi": round(float(s["profit"].astype(float).sum() / staked), 4) if staked else None,
                   "clv_pts": round(float(clv.mean()), 2) if len(clv) else None,
                   "clv_prob": round(float(s["clv_prob"].dropna().mean()), 4) if s["clv_prob"].notna().any() else None,
                   "beat_close": round(float((clv > 0).mean()), 3) if len(clv) else None,
                   "multiplier": round(mult, 2), "open": int(((b["market"] == mk) & (b["status"] == "open")).sum())}
    return out


def recent(n: int = 30) -> list[dict]:
    b = load()
    b = b[b["status"] == "settled"].sort_values(["date", "logged_at"], ascending=False).head(n)
    cols = ["date", "home", "away", "market", "pick", "book", "odds", "close_line", "clv_pts", "home_score",
            "away_score", "result", "profit"]
    return b[cols].to_dict("records")


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=1))
