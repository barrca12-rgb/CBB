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
and it's capped at 0.5 if a market averages negative CLV after 25 bets. That CLV is the forward-test protocol's primary
close (cbb/clv_primary.py), the figure every page shows (changed Oct 28, MODEL_FREEZE.md): bets without a primary
close are excluded and counted, the 25 counts only bets with one, and if the closes cannot be read the cap keeps its
last state (bets/stake_cap.json).
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
BETS = os.path.join(ROOT, "bets", "bets.csv")
CLOSING = os.path.join(ROOT, "lines", "closing.csv")
# backtest win rate at the opener for the current thresholds (spreads 2.5+, totals 3+), the stake shutoff's prior
MARKETS = {"spread": {"backtest": 0.571, "sd": 11.34}, "total": {"backtest": 0.565, "sd": 16.5}}
BREAKEVEN = 110 / 210
PRIOR_BETS = 100
MIN_CLV_BETS = 25
CLV_TARGET = 0.5 * (2 * BREAKEVEN - 1)
CAP_MULT = 0.5                    # the stake cap: multiplier held at this when primary-close CLV averages below 0 ...
STAKE_CAP_STATE = os.path.join(ROOT, "bets", "stake_cap.json")   # ... after MIN_CLV_BETS bets with a primary close
COLS = ["bet_id", "date", "game_id", "market", "pick", "side", "home_id", "away_id", "home", "away", "line", "alert_line", "odds",
        "book", "edge", "model", "stake", "placed", "logged_at", "close_line", "clv_pts", "clv_prob", "home_score",
        "away_score", "result", "profit", "status"]


def load() -> pd.DataFrame:
    if not os.path.exists(BETS):
        return pd.DataFrame(columns=COLS)
    b = pd.read_csv(BETS, dtype={"bet_id": str, "result": str, "status": str, "placed": str, "side": str})
    if "alert_line" not in b:   # bets logged before Oct 26 2026: the logged line is the alerted one
        b["alert_line"] = b["line"]
    return b.reindex(columns=COLS)


def save(b: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(BETS), exist_ok=True)
    b[COLS].to_csv(BETS, index=False)


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def payout(odds) -> float:
    o = -110.0 if odds is None or (isinstance(odds, float) and math.isnan(odds)) else float(odds)
    return o / 100 if o > 0 else 100 / -o


def log(card: pd.DataFrame, day: pd.Timestamp, stakes: dict | None = None) -> list[dict]:
    """Record today's BET plays that aren't logged yet. Returns the bets added."""
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
                        "away": g["away"], "line": g[f"{mk}_line"], "alert_line": g[f"{mk}_line"], "odds": g.get(f"{mk}_odds"), "book": g.get(f"{mk}_book"),
                        "edge": round(float(g[f"{mk}_edge"]), 2),
                        "model": round(float(g["model_margin"] if mk == "spread" else g["model_total"]), 2),
                        "stake": stakes.get(mk, 1.0), "placed": "", "logged_at": now, "status": "open"})
    if new:
        b = pd.concat([b, pd.DataFrame(new)], ignore_index=True) if len(b) else pd.DataFrame(new)
        save(b.reindex(columns=COLS))
    return new


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


VOID_ALERTED = os.path.join(ROOT, "bets", "void_alerted.json")


def alert_voided() -> int:
    """One phone alert per voided bet (status "void") not yet announced: the play was alerted, then cancelled.
    Returns alerts sent; a bet is marked announced only when its alert goes out."""
    from . import notify
    b = load()
    v = b[b["status"] == "void"]
    done = set(json.load(open(VOID_ALERTED))) if os.path.exists(VOID_ALERTED) else set()
    v = v[~v["bet_id"].isin(done)]
    sent = 0
    for _, r in v.iterrows():
        body = (f"CANCELLED: {r['pick']} ({r['away']} at {r['home']}, {r['date']}) is not a play. Don't bet it. "
                f"If you already did, tell Claude and it goes back on the record.")
        if notify.message(f"CBB play cancelled: {r['pick']}", body):
            done.add(r["bet_id"])
            sent += 1
    if sent:
        with open(VOID_ALERTED, "w") as fh:
            json.dump(sorted(done), fh)
    return sent


def _cap(s: pd.DataFrame, mk: str, last: dict) -> dict:
    """The stake cap for one market from the primary-close CLV of its settled bets s: on when at least MIN_CLV_BETS
    bets have a primary close and their mean is below 0. Missing closes are excluded and counted. If the closes
    cannot be read, the last recorded state is kept (state "held")."""
    try:
        from . import clv_primary
        p = clv_primary.primary(s).set_index("bet_id") if len(s) else None
        v = pd.to_numeric(s["bet_id"].map(p["clv_primary"]), errors="coerce") if p is not None else pd.Series(dtype=float)
    except Exception as e:
        on = bool(last.get(mk, {}).get("on", False))
        return {"on": on, "state": "held", "clv": None, "n": None, "settled": int(len(s)), "missing": None,
                "reason": f"primary closes could not be read ({e}); last state kept"}
    have = v.dropna()
    m = float(have.mean()) if len(have) else None
    on = bool(len(have) >= MIN_CLV_BETS and m < 0)
    return {"on": on, "state": "on" if on else "off", "clv": round(m, 2) if m is not None else None, "n": int(len(have)),
            "settled": int(len(s)), "missing": int(v.isna().sum()), "reason": ""}


def status(b: pd.DataFrame | None = None) -> dict:
    """Per market: record, ROI, same-book CLV (diagnostic), the stake cap (primary-close CLV) and stake multiplier."""
    b = load() if b is None else b
    try:
        last = json.load(open(STAKE_CAP_STATE)) if os.path.exists(STAKE_CAP_STATE) else {}
    except Exception:
        last = {}
    out, caps = {}, {}
    for mk, cfg in MARKETS.items():
        s = b[(b["market"] == mk) & (b["status"] == "settled")]
        w, l, p = (s["result"] == "W").sum(), (s["result"] == "L").sum(), (s["result"] == "P").sum()
        n = w + l
        post = (cfg["backtest"] * PRIOR_BETS + w) / (PRIOR_BETS + n)
        mult = float(np.clip((post - BREAKEVEN) / (cfg["backtest"] - BREAKEVEN), 0, 1))
        cap = _cap(s, mk, last)
        cap["refreshed_at"] = last.get("refreshed_at")   # last successful refresh of the persisted state
        if cap["on"]:
            mult = min(mult, CAP_MULT)
        caps[mk] = {"on": cap["on"]}
        clv = s["clv_pts"].dropna()   # the grader's same-book CLV: diagnostic only, not used by any rule
        staked = s["stake"].astype(float).sum()
        out[mk] = {"bets": int(len(s)), "w": int(w), "l": int(l), "p": int(p), "win": (w / n) if n else None,
                   "units": round(float(s["profit"].astype(float).sum()), 2),
                   "roi": round(float(s["profit"].astype(float).sum() / staked), 4) if staked else None,
                   "clv_same_book": round(float(clv.mean()), 2) if len(clv) else None,
                   "clv_prob_same_book": round(float(s["clv_prob"].dropna().mean()), 4) if s["clv_prob"].notna().any() else None,
                   "cap": cap, "multiplier": round(mult, 2),
                   "open": int(((b["market"] == mk) & (b["status"] == "open")).sum())}
    if all(c["state"] != "held" for c in (out[mk]["cap"] for mk in out)) or not os.path.exists(STAKE_CAP_STATE):
        caps["refreshed_at"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
        try:
            with open(STAKE_CAP_STATE, "w") as fh:
                json.dump(caps, fh)
            for mk in out:
                out[mk]["cap"]["refreshed_at"] = caps["refreshed_at"]
        except OSError:
            pass
    return out


# Tripwires (helpers' Round 4 answer, adopted Oct 2026): judged on CLV, never on win rate.
#   model:      trailing 150 settled bets with a primary close, mean CLV under +0.4 points -> review the projection;
#               under 0 -> pause. CLV is the forward-test protocol's primary close (cbb/clv_primary.py), the same
#               figure every page and Discord show (changed Oct 28, MODEL_FREEZE.md). Bets without a primary close
#               are excluded from the 150 and counted, never treated as zero; the tripwire cannot fire until
#               TRIP_MIN_CLOSES bets have one; if the closes cannot be read it reports "unavailable" and keeps its
#               last state.
#               (historical opener plays averaged about +1.0 to +1.3 with a standard error near 0.12 at 150 bets)
#   execution:  trailing 50 placed bets, the number you got averages 0.5+ points worse than the alerted number ->
#               review alerts and book coverage (needs `line` edited to the number actually bet; `alert_line` keeps
#               the alerted one)
# They only alert (phone + card); nothing stops automatically.
TRIP_MODEL_N, TRIP_REVIEW, TRIP_PAUSE = 150, 0.4, 0.0
TRIP_MIN_CLOSES = TRIP_MODEL_N   # bets with a primary close needed before the model tripwire can fire
TRIP_EXEC_N, TRIP_SLIP = 50, 0.5
TRIP_STATE = os.path.join(ROOT, "bets", "tripwire.json")


def _slippage(b: pd.DataFrame) -> pd.Series:
    """Points worse than the alert (+ = worse) for each bet: spreads and unders want a higher number, overs lower."""
    line, alert = pd.to_numeric(b["line"], errors="coerce"), pd.to_numeric(b["alert_line"], errors="coerce")
    worse_if_lower = (b["market"] == "spread") | (b["side"].astype(str) == "under")
    return np.where(worse_if_lower, alert - line, line - alert)


def tripwires(b: pd.DataFrame | None = None) -> dict:
    b = load() if b is None else b
    s = b[b["status"] == "settled"].sort_values(["date", "logged_at"])
    try:
        from . import clv_primary
        p = clv_primary.primary(s).set_index("bet_id") if len(s) else None
        all_clv = pd.to_numeric(s["bet_id"].map(p["clv_primary"]), errors="coerce") if p is not None else s["bet_id"].map(float)
        source = "primary"
    except Exception as e:
        all_clv, source = pd.Series(np.nan, index=s.index), f"unavailable: {e}"
    have = all_clv.dropna()
    clv = have.tail(TRIP_MODEL_N)
    m = {"n": int(len(clv)), "clv": round(float(clv.mean()), 2) if len(clv) else None,
         "with_close": int(len(have)), "missing": int(all_clv.isna().sum()), "min": TRIP_MIN_CLOSES, "source": source}
    m["state"] = ("unavailable" if source != "primary" else "collecting" if len(have) < TRIP_MIN_CLOSES
                  else "pause" if clv.mean() < TRIP_PAUSE else "review" if clv.mean() < TRIP_REVIEW else "ok")
    p = b[(b["placed"].astype(str).str.lower() != "no") & b.get("alert_line", pd.Series(dtype=float)).notna()]
    p = p.sort_values(["date", "logged_at"]).tail(TRIP_EXEC_N)
    slip = pd.Series(_slippage(p)).dropna() if len(p) else pd.Series(dtype=float)
    e = {"n": int(len(slip)), "slip": round(float(slip.mean()), 2) if len(slip) else None}
    e["state"] = "collecting" if len(slip) < TRIP_EXEC_N else "review" if slip.mean() >= TRIP_SLIP else "ok"
    return {"model": m, "execution": e}


def check_tripwires() -> dict:
    """Compute the tripwires and send a phone alert when either changes state (into or out of review/pause)."""
    import json
    t = tripwires()
    old = {}
    if os.path.exists(TRIP_STATE):
        with open(TRIP_STATE) as fh:
            old = json.load(fh)
    msgs = []
    if t["model"]["state"] != old.get("model") and t["model"]["state"] in ("review", "pause", "ok") and old.get("model"):
        m = t["model"]
        msgs.append({"review": f"Model review: last {m['n']} bets average {m['clv']:+.2f} pts CLV (under +{TRIP_REVIEW}).",
                     "pause": f"PAUSE opener bets: last {m['n']} bets average {m['clv']:+.2f} pts CLV (under 0).",
                     "ok": f"Model check back to OK: last {m['n']} bets average {m['clv']:+.2f} pts CLV."}[m["state"]])
    if t["execution"]["state"] != old.get("execution") and t["execution"]["state"] in ("review", "ok") and old.get("execution"):
        e = t["execution"]
        msgs.append(f"Execution review: last {e['n']} bets got {e['slip']:+.2f} pts worse than the alert on average."
                    if e["state"] == "review" else f"Execution back to OK: slippage {e['slip']:+.2f} pts.")
    if msgs:
        from . import notify
        notify.message("CBB: tripwire", " ".join(msgs))
        print("Tripwire:", " ".join(msgs))
    with open(TRIP_STATE, "w") as fh:   # an unreadable close keeps the last model state (no false change)
        json.dump({"model": t["model"]["state"] if t["model"]["state"] != "unavailable" else old.get("model"),
                   "execution": t["execution"]["state"]}, fh)
    return t


def recent(n: int = 30) -> list[dict]:
    b = load()
    b = b[b["status"] == "settled"].sort_values(["date", "logged_at"], ascending=False).head(n)
    cols = ["date", "home", "away", "market", "pick", "book", "odds", "close_line", "clv_pts", "home_score",
            "away_score", "result", "profit"]
    return b[cols].to_dict("records")


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=1))
