"""Option B: pull The Odds API's historical NCAAB snapshots in research/market/sample_plan.json (fixed beforehand).

Runs once, in GitHub Actions (.github/workflows/history_sample.yml), with the repository's ODDS_API_KEY. It never
touches the live card, the bet log or the forward-test logs.

Guards: stops before a call that would leave fewer than FLOOR credits (the live logger's allowance), and never
spends more than CAP credits in total. Resumable: snapshots already in the progress file are skipped.

Output, per date (research/market/data/):
  quotes_<date>.csv.gz   change log: one row whenever a (event, book, market, outcome) quote first appears,
                         changes number or price, or disappears ("absent"), at the snapshot it was seen in.
  snapshots_<date>.csv   every snapshot requested: requested time, the snapshot time served, events, credits left.
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

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
API = "https://api.the-odds-api.com/v4/historical/sports/basketball_ncaab/odds"
FLOOR = 50_000
CAP = 27_000


def get(params: dict) -> tuple[dict, dict]:
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cbb-research"}), timeout=60) as r:
                return json.load(r), {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 422) or attempt == 3:
                raise
        except Exception:
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def rows(snap: dict) -> dict:
    """(event, book, market, outcome) -> quote fields, for one snapshot."""
    out = {}
    for ev in snap.get("data") or []:
        for bk in ev.get("bookmakers") or []:
            for m in bk.get("markets") or []:
                for o in m.get("outcomes") or []:
                    k = (ev["id"], bk["key"], m["key"], o.get("name"))
                    out[k] = {"commence_time": ev.get("commence_time"), "home_team": ev.get("home_team"),
                              "away_team": ev.get("away_team"), "point": o.get("point"), "price": o.get("price"),
                              "last_update": m.get("last_update") or bk.get("last_update")}
    return out


def main() -> None:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        sys.exit("ODDS_API_KEY missing")
    plan = json.load(open(os.path.join(HERE, "sample_plan.json")))
    os.makedirs(DATA, exist_ok=True)
    spent, left = 0, None
    for d in plan["dates"]:
        qpath, spath = os.path.join(DATA, f"quotes_{d['date']}.csv.gz"), os.path.join(DATA, f"snapshots_{d['date']}.csv")
        done = pd.read_csv(spath) if os.path.exists(spath) else pd.DataFrame(columns=["requested"])
        if len(done) >= len(d["snapshots"]):
            print(d["date"], "already complete")
            continue
        prev, changes, snaps = {}, [], done.to_dict("records")
        if len(done):   # resume: rebuild the last state from the change log
            old = pd.read_csv(qpath)
            for r in old.to_dict("records"):
                k = (r["event_id"], r["book"], r["market"], r["outcome"])
                if r["status"] == "absent":
                    prev.pop(k, None)
                else:
                    prev[k] = {c: r[c] for c in ("commence_time", "home_team", "away_team", "point", "price", "last_update")}
            changes = old.to_dict("records")
        for ts in d["snapshots"][len(done):]:
            if left is not None and (left - plan["credits_per_snapshot"] < FLOOR or spent + plan["credits_per_snapshot"] > CAP):
                print(f"Stopping: {left} credits left, {spent} spent this run (floor {FLOOR}, cap {CAP}).")
                break
            snap, hdr = get({"apiKey": key, "regions": plan["regions"], "markets": plan["markets"],
                             "oddsFormat": "american", "date": ts})
            cost = int(float(hdr.get("x-requests-last", plan["credits_per_snapshot"])))
            spent += cost
            left = int(float(hdr["x-requests-remaining"])) if hdr.get("x-requests-remaining") else left
            cur = rows(snap)
            served = snap.get("timestamp")
            for k, v in cur.items():
                p = prev.get(k)
                if p is None or (p["point"], p["price"]) != (v["point"], v["price"]):
                    changes.append({"requested": ts, "snapshot": served, "event_id": k[0], "book": k[1], "market": k[2],
                                    "outcome": k[3], "status": "new" if p is None else "changed", **v})
            for k in set(prev) - set(cur):
                changes.append({"requested": ts, "snapshot": served, "event_id": k[0], "book": k[1], "market": k[2],
                                "outcome": k[3], "status": "absent", **{c: prev[k][c] for c in ("commence_time", "home_team", "away_team")}})
            prev = cur
            snaps.append({"requested": ts, "snapshot": served, "events": len(snap.get("data") or []), "cost": cost,
                          "credits_left": left})
        pd.DataFrame(changes).to_csv(qpath, index=False, compression={"method": "gzip", "mtime": 0})
        pd.DataFrame(snaps).to_csv(spath, index=False)
        print(f"{d['date']}: {len(snaps)}/{len(d['snapshots'])} snapshots, {len(changes)} change rows; "
              f"spent {spent} so far, {left} left", flush=True)
        if len(snaps) < len(d["snapshots"]):
            break
    print(f"Done: spent {spent} credits this run; {left} left.")


if __name__ == "__main__":
    main()
