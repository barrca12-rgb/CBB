"""Kalshi quote logger (research/kalshi/PLAN.md). Run after each card run by .github/workflows/kalshi_quotes.yml.

Reads Kalshi's public market data (no account, no key) for the card's BET / WATCH games and games with an open
logged bet, and appends changed quotes on the spread and total ladders to research/kalshi/data/quotes.csv. Never
touches the card, the picks, bets/, lines/ or any frozen file.

    python -m research.kalshi.logger            # log one snapshot
    python -m research.kalshi.logger --check    # match today's Kalshi winner markets to the cards; print only
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time
import urllib.error
import urllib.request

import pandas as pd

from cbb import teams

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DIR = os.path.join(os.path.dirname(__file__), "data")
QUOTES = os.path.join(DIR, "quotes.csv")
STATE = os.path.join(DIR, "last_quote.json")      # ticker -> last logged (bid, ask, bid size, ask size)
UNMATCHED = os.path.join(DIR, "unmatched.csv")
ALIASES = os.path.join(os.path.dirname(__file__), "aliases.csv")   # Kalshi names -> ESPN id (data/team_aliases.csv is frozen)
RUNS = os.path.join(DIR, "runs.csv")
API = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = {"spread": "KXNCAAMBSPREAD", "total": "KXNCAAMBTOTAL"}
WINDOW = 6.0                                      # rungs within this many points of the card's number
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
COLS = ["fetched_at", "date", "game_id", "market", "event_ticker", "ticker", "subject", "subject_id", "strike",
        "yes_bid", "yes_ask", "yes_bid_size", "yes_ask_size", "volume", "card_line"]


def get(path: str) -> dict:
    for i in range(5):
        try:
            with urllib.request.urlopen(f"{API}/{path}", timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 4:
                raise
            time.sleep(3 * (i + 1))


def open_events(series: str) -> list[dict]:
    out, cur = [], ""
    while True:
        d = get(f"events?series_ticker={series}&status=open&with_nested_markets=true&limit=200" + (f"&cursor={cur}" if cur else ""))
        out += d.get("events", [])
        cur = d.get("cursor")
        if not cur:
            return out
        time.sleep(0.5)


def event_date(ticker: str) -> str | None:
    """'KXNCAAMBSPREAD-26NOV02OSUBYU' -> '2026-11-02'."""
    m = re.match(r"^[A-Z0-9]+-(\d\d)([A-Z]{3})(\d\d)", ticker)
    return f"20{m.group(1)}-{MONTHS[m.group(2)]:02d}-{m.group(3)}" if m and m.group(2) in MONTHS else None


def event_teams(title: str) -> list[str]:
    """'Tulsa at Auburn: Spread' / 'Ohio St. vs BYU' -> both names."""
    t = title.split(":")[0]
    return [p.strip() for p in re.split(r"\s+(?:at|vs\.?)\s+", t, maxsplit=1)]


def name_key() -> dict[str, int]:
    """Normalized name -> ESPN id, from the team table's names and research/kalshi/aliases.csv."""
    t = teams.load()
    out = {}
    for col in [c for c in t.columns if c != "espn_id"]:
        for n, i in zip(t[col], t["espn_id"]):
            if isinstance(n, str) and pd.notna(i):
                out.setdefault(teams.norm(n), int(i))
    a = pd.read_csv(ALIASES)
    out.update({teams.norm(n): int(i) for n, i in zip(a["name"], a["espn_id"])})
    return out


def card_games(today: str) -> pd.DataFrame:
    """Today's and later card games with a BET or WATCH in either market, plus open logged bets' games."""
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_20*.csv"))):
        d = os.path.basename(f)[4:14]
        if d < today:
            continue
        c = pd.read_csv(f)
        keep = c[c.get("spread_verdict").isin(["BET", "WATCH"]) | c.get("total_verdict").isin(["BET", "WATCH"])] \
            if "spread_verdict" in c else c.iloc[0:0]
        b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
        open_ids = set(b[(b["status"] == "open") & (b["date"] == d)]["game_id"].astype(int))
        keep = pd.concat([keep, c[c["game_id"].astype(int).isin(open_ids)]]).drop_duplicates("game_id")
        for _, r in keep.iterrows():
            rows.append({"date": d, "game_id": int(r["game_id"]), "home_id": int(r["home_id"]), "away_id": int(r["away_id"]),
                         "home": r["home"], "away": r["away"], "spread": r.get("line_home_spread"), "total": r.get("line_total")})
    return pd.DataFrame(rows, columns=["date", "game_id", "home_id", "away_id", "home", "away", "spread", "total"])


def match(events: list[dict], games: pd.DataFrame, key: dict) -> tuple[list[tuple[dict, pd.Series]], list[dict]]:
    """Pair Kalshi events with card games by date and both teams. Returns (pairs, unmatched events on card dates)."""
    pairs, miss = [], []
    by = {(r["date"], frozenset((r["home_id"], r["away_id"]))): r for _, r in games.iterrows()}
    dates = set(games["date"])
    for e in events:
        d = event_date(e["event_ticker"])
        if d not in dates:
            continue
        names = event_teams(e.get("title", ""))
        ids = [key.get(teams.norm(n)) for n in names]
        g = by.get((d, frozenset(ids))) if None not in ids and len(ids) == 2 else None
        if g is not None:
            pairs.append((e, g))
        elif any(i in set(games[games["date"] == d][["home_id", "away_id"]].to_numpy().ravel()) for i in ids if i):
            miss.append({"date": d, "event_ticker": e["event_ticker"], "title": e.get("title"),
                         "unmatched_names": "; ".join(n for n, i in zip(names, ids) if i is None)})
    return pairs, miss


def rungs(e: dict, g: pd.Series, market: str, key: dict) -> list[dict]:
    line = g["total"] if market == "total" else g["spread"]
    out = []
    for m in e.get("markets") or []:
        k = m.get("floor_strike")
        if k is None:
            continue
        subject, sid = None, None
        if market == "spread":
            subject = re.split(r"\s+wins by over", m.get("yes_sub_title") or "")[0].strip()
            sid = key.get(teams.norm(subject))
            # the card's spread is the home team's number; the subject's equivalent number is -k (subject) / +k (other)
            ref = abs(float(line)) if pd.notna(line) else None
        else:
            ref = float(line) if pd.notna(line) else None
        if ref is not None and abs(float(k) - ref) > WINDOW:
            continue
        out.append({"market": market, "event_ticker": e["event_ticker"], "ticker": m["ticker"], "subject": subject,
                    "subject_id": sid, "strike": float(k), "yes_bid": m.get("yes_bid_dollars"),
                    "yes_ask": m.get("yes_ask_dollars"), "yes_bid_size": m.get("yes_bid_size_fp"),
                    "yes_ask_size": m.get("yes_ask_size_fp"), "volume": m.get("volume_fp"), "card_line": line})
    return out


def main(check: bool = False) -> None:
    now = pd.Timestamp.now(tz="UTC")
    today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
    games, key = card_games(today), name_key()
    if check:
        ev = open_events("KXNCAAMBGAME")
        allg = []
        for f in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_20*.csv"))):
            if os.path.basename(f)[4:14] >= today:
                c = pd.read_csv(f)
                allg.append(c.assign(date=os.path.basename(f)[4:14])[["date", "game_id", "home_id", "away_id", "home", "away"]])
        allg = pd.concat(allg) if allg else games
        pairs, miss = match(ev, allg, key)
        print(f"Kalshi winner events on card dates matched: {len(pairs)}; unmatched: {len(miss)}")
        for m in miss[:40]:
            print("  ", m)
        return
    os.makedirs(DIR, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    rows, misses, n_events = [], [], 0
    if len(games):
        for market, series in SERIES.items():
            ev = open_events(series)
            n_events += len(ev)
            pairs, miss = match(ev, games, key)
            misses += miss
            for e, g in pairs:
                for r in rungs(e, g, market, key):
                    q = [r["yes_bid"], r["yes_ask"], r["yes_bid_size"], r["yes_ask_size"]]
                    if state.get(r["ticker"]) == q:
                        continue
                    state[r["ticker"]] = q
                    rows.append({"fetched_at": now.isoformat(timespec="seconds"), "date": g["date"],
                                 "game_id": g["game_id"], **r})
    if rows:
        pd.DataFrame(rows, columns=COLS).to_csv(QUOTES, mode="a", header=not os.path.exists(QUOTES), index=False)
    json.dump(state, open(STATE, "w"))
    if misses:
        m = pd.DataFrame(misses)
        if os.path.exists(UNMATCHED):
            m = pd.concat([pd.read_csv(UNMATCHED), m]).drop_duplicates("event_ticker")
        m.to_csv(UNMATCHED, index=False)
    pd.DataFrame([{"run_at": now.isoformat(timespec="seconds"), "card_games": len(games), "kalshi_events": n_events,
                   "rows_written": len(rows), "unmatched": len(misses)}]).to_csv(
        RUNS, mode="a", header=not os.path.exists(RUNS), index=False)
    print(f"{len(games)} card games, {n_events} open Kalshi spread/total events, {len(rows)} quote rows, {len(misses)} unmatched")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    main(ap.parse_args().check)
