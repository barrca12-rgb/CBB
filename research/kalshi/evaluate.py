"""Kalshi price read (research/kalshi/PLAN.md, pre-registered Oct 28, 2026). Research only.

    python -m research.kalshi.evaluate

For each card BET (cohort v1: main plays, not void) logged while the logger ran, the first Kalshi snapshot within 15
minutes after logged_at (quotes are change-only: the state at a time is each rung's latest row at or before it). Our
side at the same number or better: favorite -k = our team "wins by over k" YES; underdog +k = the other team "wins by
over k" NO; totals Over N YES, Under N NO. Taker cost = ask (YES) or 1 - yes bid (NO) plus 0.07 p (1 - p); maker
(upper bound) = bid (YES) or 1 - yes ask (NO) plus 0.0175 p (1 - p). EV per unit risked with run_day.win_prob for the
edge at each number; gain = max(0, EV Kalshi - EV at the logged book), 0 with no Kalshi market.
Bar: mean gain >= +0.5% per play, date-clustered 95% interval above 0, at least 40 plays.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from cbb.run_day import ev, win_prob

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
D = os.path.join(ROOT, "research", "kalshi", "data")
WINDOW = pd.Timedelta(minutes=15)
# Maker bound only: a resting bid on a rung with no real market (e.g. bid 0.03 / ask 0.97) is not a price anyone
# would fill, so the maker bound uses rungs whose bid-ask spread is at most 10 cents. Added Nov 23 after the first run
# showed the unfiltered bound was meaningless (+193% per play); the taker test, the bar, is unchanged.
MAX_SPREAD = 0.10


def kalshi_ev(p_win: float, cost: float, fee_rate: float) -> float:
    c = cost + fee_rate * cost * (1 - cost)
    return (p_win - c) / c if 0 < c < 1 else -math.inf


def best(b: pd.Series, snap: pd.DataFrame, maker: bool) -> float | None:
    fee = 0.0175 if maker else 0.07
    side_margin = (b["model"] if b["side"] == "home" else -b["model"]) if b["market"] == "spread" else None
    our_id = b["home_id"] if b["side"] == "home" else b["away_id"]
    out = []
    for r in snap.itertuples():
        yes_cost = r.yes_bid if maker else r.yes_ask
        no_cost = 1 - (r.yes_ask if maker else r.yes_bid)
        if b["market"] == "spread":
            L = float(b["line"])
            if r.subject_id == our_id and r.strike <= -L:            # our team wins by over k  (line -k), YES
                out.append(kalshi_ev(win_prob("spread", side_margin - r.strike), yes_cost, fee))
            elif r.subject_id != our_id and r.strike >= L:           # other team wins by over k NO (line +k)
                out.append(kalshi_ev(win_prob("spread", side_margin + r.strike), no_cost, fee))
        else:
            N = float(b["line"])
            if b["side"] == "over" and r.strike <= N:
                out.append(kalshi_ev(win_prob("total", b["model"] - r.strike), yes_cost, fee))
            elif b["side"] == "under" and r.strike >= N:
                out.append(kalshi_ev(win_prob("total", r.strike - b["model"]), no_cost, fee))
    out = [x for x in out if np.isfinite(x)]
    return max(out) if out else None


def clustered_ci(x: pd.Series, cl: pd.Series) -> tuple[float, float]:
    m, n = x.mean(), len(x)
    g = (x - m).groupby(cl).sum()
    se = math.sqrt((g ** 2).sum()) / n
    return m - 1.96 * se, m + 1.96 * se


def main() -> None:
    q = pd.read_csv(os.path.join(D, "quotes.csv"))
    q["t"] = pd.to_datetime(q["fetched_at"], utc=True)
    runs = pd.read_csv(os.path.join(D, "runs.csv"))
    r0, r1 = pd.to_datetime(runs["run_at"], utc=True).agg(["min", "max"])
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[b["bet_type"].isna() & (b["status"] != "void")].copy()
    b["t"] = pd.to_datetime(b["logged_at"], utc=True)
    b = b[(b["t"] >= r0) & (b["t"] <= r1)]
    open_t = q.groupby(["game_id", "market"])["t"].min()
    rows = []
    for _, x in b.iterrows():
        g = q[(q["game_id"] == x["game_id"]) & (q["market"] == x["market"])]
        w = g[(g["t"] >= x["t"]) & (g["t"] <= x["t"] + WINDOW)]
        p_book = win_prob(x["market"], float(x["edge"]))
        ev_book = ev(p_book, x["odds"])
        rec = {"bet_id": x["bet_id"], "date": x["date"], "market": x["market"], "ev_book": ev_book,
               "kalshi_open_before_alert": bool((x["game_id"], x["market"]) in open_t and open_t[(x["game_id"], x["market"])] <= x["t"]),
               "kalshi_open_lead_h": ((x["t"] - open_t[(x["game_id"], x["market"])]).total_seconds() / 3600
                                      if (x["game_id"], x["market"]) in open_t else np.nan)}
        if len(w):
            at = w["t"].min()
            snap = g[g["t"] <= at].sort_values("t").groupby("ticker").tail(1)
            live = snap[(snap["yes_ask"] - snap["yes_bid"]) <= MAX_SPREAD]     # two-sided rungs only, for the maker bound
            for kind, mk, sn in (("taker", False, snap), ("maker", True, live)):
                k = best(x, sn, mk)
                rec[f"ev_{kind}"] = k
                rec[f"gain_{kind}"] = max(0.0, k - ev_book) if k is not None else 0.0
            rec["market_seen"] = rec["ev_taker"] is not None
        else:
            rec.update(ev_taker=None, ev_maker=None, gain_taker=0.0, gain_maker=0.0, market_seen=False)
        rows.append(rec)
    R = pd.DataFrame(rows)
    n = len(R)
    print(f"logger ran {r0:%Y-%m-%d %H:%M} to {r1:%Y-%m-%d %H:%M} UTC; v1 plays logged in that window: {n}")
    print(f"plays with a Kalshi market on our side at the alert: {R['market_seen'].sum()} ({R['market_seen'].mean():.0%})")
    better = R["gain_taker"] > 0
    print(f"plays where Kalshi (taker) beat the logged book: {better.sum()} ({better.mean():.0%})")
    for kind in ("taker", "maker"):
        lo, hi = clustered_ci(R[f"gain_{kind}"], R["date"])
        print(f"{kind}: mean EV gain per play {R[f'gain_{kind}'].mean():+.2%} (date-clustered 95% [{lo:+.2%}, {hi:+.2%}])"
              + ("  <- upper bound, fills not guaranteed" if kind == "maker" else ""))
    for mk, g in R.groupby("market"):
        print(f"  {mk}: n {len(g)}, Kalshi market {g['market_seen'].mean():.0%}, taker gain {g['gain_taker'].mean():+.2%}, maker {g['gain_maker'].mean():+.2%}")
    seen = R["market_seen"]
    if seen.any():
        d = (R.loc[seen, "ev_taker"] - R.loc[seen, "ev_book"])
        print(f"where Kalshi had a market: Kalshi minus book EV, median {d.median():+.2%}, mean {d.mean():+.2%}")
    print(f"Kalshi line open before our alert: {R['kalshi_open_before_alert'].mean():.0%} of plays; "
          f"median lead when open {R.loc[R['kalshi_open_before_alert'], 'kalshi_open_lead_h'].median():.1f} h")
    lo, _ = clustered_ci(R["gain_taker"], R["date"])
    ok = n >= 40 and R["gain_taker"].mean() >= 0.005 and lo > 0
    print(f"BAR (mean >= +0.5%, CI above 0, n >= 40): {'CLEARS' if ok else 'does not clear'}")


if __name__ == "__main__":
    main()
