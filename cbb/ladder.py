"""Alternate-line ladder at the opener, logged for the card's plays only (Chad's Nov 1 brief, item 2; plan:
research/ladder/PLAN.md). Reads only: never shown on the card, never changes a pick, price, stake or log.

When a play is first logged (v1 or band B), its game's alternate spreads and totals are pulled once from The Odds
API's per-event endpoint, at the play's book and the best-price book for the main number (2 credits: two markets,
one region). Every rung goes to lines/ladder/ladders.csv; the play's main-number EV, best-rung EV, rung and price
go to lines/ladder/plays.csv, from the live win-probability rule's normal form (cover probability
= Phi(edge / sigma), sigma set so the slope at 0 equals the rule's: spreads 15.6, totals 28.5 points; the capped rule's
EV is a secondary column).

Guards: a pull reported at more than MAX_COST credits switches the logger off; no pull below MIN_BALANCE (before
Nov 25) or the 50,000 research floor (from Nov 25); state.json "on": false stops it (the Nov 23 stop rule).
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request

import pandas as pd

from . import odds_api, run_day, teams

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "lines", "ladder")     # committed by the card workflow (it adds lines/); plan in research/ladder
LADDERS = os.path.join(DIR, "ladders.csv")
PLAYS = os.path.join(DIR, "plays.csv")
STATE = os.path.join(DIR, "state.json")
EVENT = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/events/{}/odds"
MAX_COST = 2
MIN_BALANCE = 20_000
RENEWAL, RESEARCH_FLOOR = pd.Timestamp("2026-11-25", tz="America/New_York"), 50_000
SIGMA = {"spread": 0.3989423 / 0.0255, "total": 0.3989423 / 0.014}      # 15.6 and 28.5 points
KEYS = {v: k for k, v in odds_api.BOOKS.items()}
PLAY_COLS = ["bet_id", "date", "game_id", "market", "side", "book", "main_line", "main_price", "model", "main_edge", "main_p",
             "main_ev", "main_ev_rule", "rungs", "best_book", "best_line", "best_price", "best_ev", "best_ev_rule", "gain",
             "whole_number", "pulled_at", "cost"]


def _state() -> dict:
    return json.load(open(STATE)) if os.path.exists(STATE) else {"on": True}


def _balance_ok() -> bool:
    u = json.load(open(odds_api.USAGE)) if os.path.exists(odds_api.USAGE) else {}
    left = u.get("remaining")
    if left is None:
        return False
    floor = RESEARCH_FLOOR if pd.Timestamp.now(tz="America/New_York") >= RENEWAL else MIN_BALANCE
    return left >= floor


def payout(odds: float) -> float:
    return odds / 100 if odds > 0 else 100 / -odds


def p_cover(market: str, edge: float) -> float:
    return 0.5 * (1 + math.erf(edge / SIGMA[market] / math.sqrt(2)))


def edge_at(market: str, side: str, model: float, line: float) -> float:
    if market == "spread":
        return model + line if side == "home" else line - model
    return model - line if side == "over" else line - model


def _event_id(lines: pd.DataFrame, h: int, a: int) -> str | None:
    if lines is None or not len(lines) or "sgo_event" not in lines:
        return None
    m = lines[(((lines["home_id"] == h) & (lines["away_id"] == a)) | ((lines["home_id"] == a) & (lines["away_id"] == h)))
              & lines["sgo_event"].astype(str).str.startswith("oa:")]
    return m["sgo_event"].iloc[0][3:] if len(m) else None


def _best_book(lines: pd.DataFrame, bet: dict) -> str | None:
    """The book with the best price at the play's main number on the play's side."""
    h, a, mk, sd = int(bet["home_id"]), int(bet["away_id"]), bet["market"], str(bet["side"]).lower()
    m = lines[((lines["home_id"] == h) & (lines["away_id"] == a))]
    best, top = None, -1.0
    for _, r in m.iterrows():
        if mk == "spread":
            hs = r.get("home_spread")
            num = None if hs is None or pd.isna(hs) else (hs if sd == "home" else -hs)
            price = r.get(f"{sd}_spread_odds")
        else:
            num, price = r.get("total"), r.get(f"{sd}_odds")
        if num is None or pd.isna(num) or pd.isna(price) or float(num) != float(bet["line"]):
            continue
        if payout(float(price)) > top:
            best, top = r["book"], payout(float(price))
    return best


def _rows(ev: dict, bet: dict, pulled_at: str) -> list[dict]:
    """Every rung returned, oriented to our home and away ids."""
    look = odds_api._lookup()
    hn, an = ev.get("home_team"), ev.get("away_team")
    hid, aid = look.get(teams.norm(hn or "")), look.get(teams.norm(an or ""))
    side_of = {hn: "home" if hid == int(bet["home_id"]) else "away", an: "away" if aid == int(bet["away_id"]) else "home"}
    out = []
    for bk in ev.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            mk = {"alternate_spreads": "spread", "alternate_totals": "total"}.get(m.get("key"))
            if not mk:
                continue
            for o in m.get("outcomes") or []:
                sd = side_of.get(o.get("name")) if mk == "spread" else str(o.get("name")).lower()
                out.append({"bet_id": bet["bet_id"], "game_id": bet["game_id"], "book": odds_api.BOOKS.get(bk.get("key"), bk.get("key")),
                            "market": mk, "side": sd, "point": o.get("point"), "price": o.get("price"),
                            "last_update": m.get("last_update") or bk.get("last_update"), "pulled_at": pulled_at,
                            "start": ev.get("commence_time")})
    return out


def evaluate(bet: dict, rungs: pd.DataFrame) -> dict:
    """The play's main number vs the best rung on its side, at the books pulled."""
    mk, sd, model = bet["market"], str(bet["side"]).lower(), float(bet["model"])
    e0 = edge_at(mk, sd, model, float(bet["line"]))
    p0 = p_cover(mk, e0)
    ev0 = p0 * payout(float(bet["odds"])) - (1 - p0)
    r = rungs[(rungs["market"] == mk) & (rungs["side"] == sd)].dropna(subset=["point", "price"]).copy()
    out = {"bet_id": bet["bet_id"], "date": bet["date"], "game_id": bet["game_id"], "market": mk, "side": sd,
           "book": bet.get("book"), "main_line": float(bet["line"]), "main_price": float(bet["odds"]), "model": model,
           "main_edge": round(e0, 3), "main_p": round(p0, 4), "main_ev": round(ev0, 4),
           "main_ev_rule": round(run_day.ev(run_day.win_prob(mk, e0), float(bet["odds"])), 4), "rungs": len(r)}
    if not len(r):
        return out
    r["edge"] = [edge_at(mk, sd, model, float(x)) for x in r["point"]]
    r["p"] = [p_cover(mk, e) for e in r["edge"]]
    r["ev"] = [p * payout(float(o)) - (1 - p) for p, o in zip(r["p"], r["price"])]
    r["ev_rule"] = [run_day.ev(run_day.win_prob(mk, e), float(o)) for e, o in zip(r["edge"], r["price"])]
    b = r.sort_values("ev", ascending=False).iloc[0]
    out.update(best_book=b["book"], best_line=float(b["point"]), best_price=float(b["price"]), best_ev=round(float(b["ev"]), 4),
               best_ev_rule=round(float(b["ev_rule"]), 4), gain=round(float(b["ev"]) - ev0, 4),
               whole_number=float(b["point"]) == int(float(b["point"])))
    return out


def pull_for(new_bets: list[dict], lines: pd.DataFrame | None) -> int:
    """One ladder pull per newly logged play (shared by plays on the same game in the same run). Returns pulls made.
    Never raises; never touches the card or the bet log."""
    try:
        st = _state()
        key = os.environ.get("ODDS_API_KEY", "")
        if not new_bets or not st.get("on", True) or not key or lines is None:
            return 0
        done = set(pd.read_csv(PLAYS, dtype=str)["bet_id"]) if os.path.exists(PLAYS) else set()
        os.makedirs(DIR, exist_ok=True)
        pulled, made = {}, 0
        for bet in new_bets:
            if bet["bet_id"] in done:
                continue
            h, a = int(bet["home_id"]), int(bet["away_id"])
            eid = _event_id(lines, h, a)
            if eid is None:
                print(f"Ladder: no Odds API event for {bet['bet_id']}; skipped.")
                continue
            if eid not in pulled:
                if not _balance_ok():
                    print("Ladder: Odds API balance below the floor; no pull.")
                    return made
                books = [b for b in dict.fromkeys([bet.get("book"), _best_book(lines, bet)]) if b in KEYS]
                if not books:
                    continue
                q = {"apiKey": key, "regions": "us", "markets": "alternate_spreads,alternate_totals", "oddsFormat": "american",
                     "bookmakers": ",".join(KEYS[b] for b in books)}
                req = urllib.request.Request(EVENT.format(eid) + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "cbb-model"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    ev = json.load(r)
                    cost = r.headers.get("x-requests-last")
                made += 1
                at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
                if cost is not None and float(cost) > MAX_COST:
                    json.dump({"on": False, "why": f"pull cost {cost} credits (> {MAX_COST})", "at": at}, open(STATE, "w"))
                    print(f"Ladder: pull cost {cost} credits; logger switched off.")
                pulled[eid] = (ev, at, cost)
            ev, at, cost = pulled[eid]
            rungs = pd.DataFrame(_rows(ev, bet, at))
            if len(rungs):
                rungs.to_csv(LADDERS, mode="a", header=not os.path.exists(LADDERS), index=False)
            if pd.isna(bet.get("odds")) or pd.isna(bet.get("model")):
                row = {"bet_id": bet["bet_id"], "date": bet["date"], "game_id": bet["game_id"], "market": bet["market"], "rungs": len(rungs)}
            else:
                row = evaluate(bet, rungs if len(rungs) else pd.DataFrame(columns=["market", "side", "point", "price", "book"]))
            row.update(pulled_at=at, cost=cost)
            pd.DataFrame([row]).reindex(columns=PLAY_COLS).to_csv(PLAYS, mode="a", header=not os.path.exists(PLAYS), index=False)
            done.add(bet["bet_id"])
        return made
    except Exception as e:
        print(f"Ladder pull failed ({e}); continuing.")
        return 0
