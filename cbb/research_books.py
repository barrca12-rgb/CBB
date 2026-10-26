"""One-off check: which bookmaker keys The Odds API returns for college basketball (regions us and us2), so new books
can be added by their exact key. About 2 credits. Writes data/research/books_check.json."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "research", "books_check.json")


def main():
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
