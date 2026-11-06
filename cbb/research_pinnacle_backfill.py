"""One-off backfill (Chad, Nov 6: "Yes run it", about 1,050 credits approved): Pinnacle's spread and total just before
each tip of the season's finished plays, from The Odds API's historical snapshots (10 credits per market per call;
spreads + totals = 20 per snapshot). Writes lines/pinnacle_hist.csv (same columns as lines/pinnacle_log.csv) and
data/research/pinnacle_backfill.json. Stops at CAP credits.

    ODDS_API_KEY=... python -m cbb.research_pinnacle_backfill
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

from . import odds_api, teams

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "lines", "pinnacle_hist.csv")
INFO = os.path.join(ROOT, "data", "research", "pinnacle_backfill.json")
API = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/odds"
CAP = 1200


def tip_times() -> list[pd.Timestamp]:
    """Distinct feed starts (else card starts) of non-void plays whose games have started."""
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(b["status"] != "void") & (b["date"].astype(str) >= "2026-11-01")]
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"), usecols=["home_id", "away_id", "start"]).drop_duplicates(["home_id", "away_id"])
    m = b.merge(c, on=["home_id", "away_id"], how="left")
    cards = []
    for d in sorted(set(b["date"].astype(str))):
        p = os.path.join(ROOT, "reports", f"cbb_{d}.csv")
        if os.path.exists(p):
            cards.append(pd.read_csv(p, usecols=["game_id", "start"]))
    if cards:
        cs = pd.concat(cards).drop_duplicates("game_id").set_index("game_id")["start"]
        m["start"] = m["start"].fillna(m["game_id"].map(cs))
    st = pd.to_datetime(m["start"], utc=True, errors="coerce", format="ISO8601").dropna()
    now = pd.Timestamp.now(tz="UTC")
    return sorted(set(t for t in st if t < now))


def main() -> None:
    key = os.environ["ODDS_API_KEY"]
    lookup = odds_api._lookup()
    rows, used, calls, left = [], 0, 0, None
    for tip in tip_times():
        if used + 20 > CAP:
            print("credit cap reached")
            break
        when = (tip - pd.Timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q = {"apiKey": key, "bookmakers": "pinnacle", "markets": "spreads,totals", "oddsFormat": "american", "date": when}
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "cbb-model"})
        with urllib.request.urlopen(req, timeout=90) as r:
            js = json.load(r)
            used += int(float(r.headers.get("x-requests-last") or 0))
            left = r.headers.get("x-requests-remaining")
        calls += 1
        snap = js.get("timestamp")
        for ev in js.get("data") or []:
            hn, an = ev.get("home_team"), ev.get("away_team")
            h, a = lookup.get(teams.norm(hn or "")), lookup.get(teams.norm(an or ""))
            if h is None or a is None:
                continue
            for bk in ev.get("bookmakers") or []:
                if bk.get("key") != "pinnacle":
                    continue
                row = {"event_id": ev.get("id"), "start": ev.get("commence_time"), "home_id": h, "away_id": a,
                       "observed_at": snap, "source": "historical"}
                for mk in bk.get("markets") or []:
                    upd = mk.get("last_update") or bk.get("last_update")
                    for o in mk.get("outcomes") or []:
                        name, price = o.get("name"), o.get("price")
                        if mk.get("key") == "spreads":
                            if name == hn:
                                row["home_spread"], row["home_spread_odds"], row["spread_updated"] = o.get("point"), price, upd
                            elif name == an:
                                row["away_spread_odds"] = price
                        elif mk.get("key") == "totals" and str(name).lower() in ("over", "under"):
                            row[f"{str(name).lower()}_odds"], row["total"], row["total_updated"] = price, o.get("point"), upd
                rows.append(row)
        print(f"{tip:%m-%d %H:%M} snapshot {snap}: {len(js.get('data') or [])} events, credits so far {used}", flush=True)
    d = pd.DataFrame(rows).reindex(columns=odds_api.PINNACLE_COLS).drop_duplicates()
    d.to_csv(OUT, index=False)
    info = {"calls": calls, "credits": used, "remaining": left, "rows": len(d), "tips": len(tip_times())}
    os.makedirs(os.path.dirname(INFO), exist_ok=True)
    json.dump(info, open(INFO, "w"), indent=1)
    print(info)


if __name__ == "__main__":
    main()
