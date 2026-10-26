"""One-off research pull: real historical team-total lines for 2025-26 games, from The Odds API.

The proxy test (team total = (total -/+ spread) / 2 from the closing lines) won 55.5% at a 3+ point model edge,
2023-2026. Books shade team totals and charge more vig, so this checks the real lines and prices. Games come from
data/research/tt_candidates.csv (model edge 2.5+ against the proxy, biggest edges first).

For each game day: one historical events call (1 credit) to find The Odds API's event ids, then one historical
event-odds call per candidate for market team_totals about 45 minutes before tip (10 credits). Results append to
data/research/tt_lines.csv, so a rerun resumes where the last one stopped. Stops at CAP credits for this run or when
fewer than KEEP credits remain on the account (live line checks need them).

Runs on GitHub (where ODDS_API_KEY lives): .github/workflows/research.yml.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from . import odds_api, teams

BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab"
HERE = os.path.join(os.path.dirname(__file__), "..", "data", "research")
CANDIDATES = os.path.join(HERE, "tt_candidates.csv")
OUT = os.path.join(HERE, "tt_lines.csv")
CAP = int(os.environ.get("TT_CAP", "10500"))
KEEP = 3000


class Budget:
    def __init__(self):
        self.start_used = None
        self.used = self.remaining = None

    def update(self, hdr):
        if hdr.get("x-requests-used"):
            self.used = int(float(hdr["x-requests-used"]))
            self.remaining = int(float(hdr.get("x-requests-remaining", "0") or 0))
            if self.start_used is None:
                self.start_used = self.used - int(float(hdr.get("x-requests-last", "0") or 0))

    def spent(self):
        return 0 if self.start_used is None else self.used - self.start_used

    def stop(self):
        return self.used is not None and (self.spent() >= CAP or self.remaining < KEEP)


def _get(path: str, params: dict, budget: Budget):
    params = dict(params, apiKey=os.environ["ODDS_API_KEY"])
    req = urllib.request.Request(f"{BASE}{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "cbb-model"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                hdr = {k.lower(): v for k, v in r.headers.items()}
                budget.update(hdr)
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            print(f"HTTP {e.code} on {path}: {e.read()[:300]!r}", flush=True)
            return None
    return None


def main():
    cand = pd.read_csv(CANDIDATES)
    cand["start"] = pd.to_datetime(cand["start_utc"], utc=True, format="ISO8601")
    done = set(pd.read_csv(OUT)["game_id"]) if os.path.exists(OUT) else set()
    cand = cand[~cand["game_id"].isin(done)]
    print(f"{len(cand)} candidate games left ({len(done)} done before)", flush=True)
    lookup = odds_api._lookup()
    budget = Budget()
    # event ids, one events call per ET game day (snapshot 10:00 am ET that day)
    cand["day"] = cand["start"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    order = cand.groupby("day")["edge"].max().sort_values(ascending=False).index   # strongest days first
    rows, n_games, unmatched = [], 0, set()
    for day in order:
        if budget.stop():
            break
        snap = pd.Timestamp(day + " 10:00", tz="America/New_York").tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        ev = _get("/events", {"date": snap}, budget)
        if not ev:
            continue
        ids = {}
        for e in ev.get("data") or []:
            h, a = lookup.get(teams.norm(e.get("home_team", ""))), lookup.get(teams.norm(e.get("away_team", "")))
            if h is None or a is None:
                unmatched.update(n for n, i in ((e.get("home_team"), h), (e.get("away_team"), a)) if i is None)
                continue
            ids[frozenset((h, a))] = (e["id"], e.get("home_team"), e.get("away_team"), h)
        for _, g in cand[cand["day"] == day].iterrows():
            if budget.stop():
                break
            hit = ids.get(frozenset((int(g["home_id"]), int(g["away_id"]))))
            if not hit:
                rows.append({"game_id": g["game_id"], "status": "no event"})
                continue
            eid, hname, aname, oa_home = hit
            at = (g["start"] - pd.Timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
            od = _get(f"/events/{eid}/odds", {"date": at, "regions": "us", "markets": "team_totals",
                                              "oddsFormat": "american", "bookmakers": ",".join(odds_api.BOOKS)}, budget)
            n_games += 1
            data = (od or {}).get("data") or {}
            got = False
            for bk in data.get("bookmakers") or []:
                for m in bk.get("markets") or []:
                    if m.get("key") != "team_totals":
                        continue
                    per = {}
                    for o in m.get("outcomes") or []:
                        team = o.get("description")
                        tid = lookup.get(teams.norm(team or ""))
                        if tid is None:
                            continue
                        r = per.setdefault(tid, {"game_id": g["game_id"], "book": odds_api.BOOKS.get(bk["key"], bk["key"]),
                                                 "team_id": tid, "snapshot": od.get("timestamp"), "status": "ok"})
                        r["point"] = o.get("point")
                        r[f"{str(o.get('name')).lower()}_price"] = o.get("price")
                    rows += per.values()
                    got = got or bool(per)
            if not got:
                rows.append({"game_id": g["game_id"], "status": "no team totals"})
            if n_games % 50 == 0:
                print(f"{n_games} games, {budget.spent()} credits this run, {budget.remaining} left", flush=True)
                _save(rows)
                rows = []
            time.sleep(0.2)
    _save(rows)
    print(f"done: {n_games} games queried, {budget.spent()} credits this run, {budget.remaining} left on the account; "
          f"unmatched names: {sorted(unmatched)[:40]}", flush=True)


def _save(rows):
    if not rows:
        return
    new = pd.DataFrame(rows)
    old = pd.read_csv(OUT) if os.path.exists(OUT) else None
    (pd.concat([old, new], ignore_index=True) if old is not None else new).to_csv(OUT, index=False)


if __name__ == "__main__":
    sys.exit(main())
