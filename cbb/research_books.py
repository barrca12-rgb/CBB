"""One-off check: which bookmaker keys The Odds API returns for college basketball (regions us and us2), so new books
can be added by their exact key. About 2 credits. Writes data/research/books_check.json."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "research", "books_check.json")


REQ = os.path.join(os.path.dirname(__file__), "..", "data", "research", "books_request.txt")
PINNACLE_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "research", "pinnacle_check.json")


def pinnacle():
    """Does The Odds API price college basketball at Pinnacle (EU book)? Spreads and totals for Pinnacle, with
    DraftKings as a control, by bookmaker key (one group of books: 2 markets = about 2 credits)."""
    q = {"apiKey": os.environ["ODDS_API_KEY"], "bookmakers": "pinnacle,draftkings", "markets": "spreads,totals",
         "oddsFormat": "american"}
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cbb-model"}), timeout=60) as r:
        ev = json.load(r)
        used, left = r.headers.get("x-requests-last"), r.headers.get("x-requests-remaining")
    cnt = {"pinnacle": {"spreads": 0, "totals": 0}, "draftkings": {"spreads": 0, "totals": 0}}
    sample = []
    for e in ev:
        for b in e.get("bookmakers") or []:
            for m in b.get("markets") or []:
                if b["key"] in cnt and m["key"] in cnt[b["key"]]:
                    cnt[b["key"]][m["key"]] += 1
                    if b["key"] == "pinnacle" and len(sample) < 6:
                        sample.append({"game": f"{e.get('away_team')} at {e.get('home_team')}", "start": e.get("commence_time"),
                                       "market": m["key"], "last_update": m.get("last_update") or b.get("last_update"),
                                       "outcomes": m.get("outcomes")})
    out = {"events": len(ev), "credits": used, "remaining": left, "games_priced": cnt, "pinnacle_sample": sample}
    os.makedirs(os.path.dirname(PINNACLE_OUT), exist_ok=True)
    json.dump(out, open(PINNACLE_OUT, "w"), indent=1)
    print(json.dumps(out, indent=1))


def main():
    if os.path.exists(REQ) and "pinnacle" in open(REQ).read().lower():
        return pinnacle()
    q = {"apiKey": os.environ["ODDS_API_KEY"], "regions": "us,us2,us_ex", "markets": "spreads", "oddsFormat": "american"}
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cbb-model"}), timeout=60) as r:
        ev = json.load(r)
        used = r.headers.get("x-requests-last")
    books = {}
    for e in ev:
        for b in e.get("bookmakers") or []:
            books.setdefault(b["key"], {"title": b.get("title"), "games": 0})["games"] += 1
    out = {"events": len(ev), "credits": used, "books": books}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
