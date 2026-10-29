"""CollegeBasketballData (api.collegebasketballdata.com) coverage check: betting lines and lineup data.

Research only. Raw responses are saved to OUT (default ../cbb-data/research/cbbd/coverage_2026-10-29, the private
data repo); CBBD's terms forbid redistributing raw data, so nothing raw goes in this public repo. Auth: the agent
proxy injects the key for the host, or CBBD_API_KEY is sent if set. The key is never written anywhere.
Saved responses are reused, so a rerun spends no calls.

    python -m research.cbbd.coverage [OUT] [--max-calls N]
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://api.collegebasketballdata.com"
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[2] / "cbb-data" / "research" / "cbbd" / "coverage_2026-10-29"
SEASONS = range(2014, 2027)                       # CBBD season = year the season ends
LINEUP_SEASONS = [2016, 2019, 2022, 2024, 2025, 2026]


class Client:
    def __init__(self, out: Path, max_calls: int):
        self.out, self.max_calls, self.calls, self.remaining, self.log = out, max_calls, 0, None, []

    def get(self, name: str, path: str):
        f = self.out / f"{name}.json"
        if f.exists():
            return json.loads(f.read_text())
        if self.calls >= self.max_calls:
            raise SystemExit(f"call budget {self.max_calls} reached")
        req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
        if os.environ.get("CBBD_API_KEY"):
            req.add_header("Authorization", f"Bearer {os.environ['CBBD_API_KEY']}")
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                status, hdr, body = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, hdr, body = e.code, e.headers, e.read()
        self.remaining = hdr.get("X-Calllimit-Remaining", self.remaining)
        self.log.append({"name": name, "path": path, "status": status, "remaining": self.remaining})
        if status in (401, 403):
            raise SystemExit(f"{path}: HTTP {status}; stopping")
        try:
            data = json.loads(body)
        except ValueError:
            data = {"_status": status, "_body": body[:300].decode("utf-8", "replace")}
        if status != 200 and isinstance(data, dict):
            data["_status"] = status
        f.write_text(json.dumps(data))
        return data


def line_stats(games: list) -> dict:
    close_s = sum(any(l.get("spread") is not None for l in g.get("lines") or []) for g in games)
    close_t = sum(any(l.get("overUnder") is not None for l in g.get("lines") or []) for g in games)
    open_s = sum(any(l.get("spreadOpen") is not None for l in g.get("lines") or []) for g in games)
    open_t = sum(any(l.get("overUnderOpen") is not None for l in g.get("lines") or []) for g in games)
    prov, prov_open = Counter(), Counter()
    for g in games:
        for l in g.get("lines") or []:
            prov[l["provider"]] += 1
            prov_open[l["provider"]] += l.get("spreadOpen") is not None
    return {"games": len(games), "with_lines": sum(bool(g.get("lines")) for g in games), "close_spread": close_s,
            "close_total": close_t, "open_spread": open_s, "open_total": open_t, "providers": dict(prov),
            "providers_with_open": {k: v for k, v in prov_open.items() if v}}


def describe(d) -> dict:
    if isinstance(d, dict):
        return {"status": d.get("_status", 200), "keys": sorted(d)[:15]}
    if not d:
        return {"status": 200, "n": 0}
    return {"status": 200, "n": len(d), "keys": sorted(d[0])[:25] if isinstance(d[0], dict) else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(DEFAULT_OUT))
    ap.add_argument("--max-calls", type=int, default=40)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c = Client(out, a.max_calls)
    summary = {"providers": c.get("providers", "/lines/providers"), "lines": {}, "lineups": {}}
    games = {}
    for s in SEASONS:
        # sample: Jan 14-16 of the season's end year
        g = c.get(f"lines_{s}", f"/lines?season={s}&startDateRange={s}-01-14&endDateRange={s}-01-16")
        games[s] = g if isinstance(g, list) else []
        summary["lines"][s] = line_stats(games[s]) if isinstance(g, list) else describe(g)
    for s in LINEUP_SEASONS:
        lined = [x for x in games.get(s, []) if x.get("lines")]
        if not lined:
            continue
        gid = lined[0]["gameId"]
        res = {"gameId": gid, "game": f"{lined[0]['awayTeam']} @ {lined[0]['homeTeam']} {lined[0]['startDate'][:10]}"}
        for ep in ("lineups", "substitutions", "plays"):
            d = c.get(f"{ep}_{s}_{gid}", f"/{ep}/game/{gid}")
            res[ep] = describe(d)
            if ep == "plays" and isinstance(d, list) and d and isinstance(d[0], dict):
                res["plays_onfloor_rows"] = sum(bool(p.get("onFloor")) for p in d)
        summary["lineups"][s] = res
    summary["calls_this_run"], summary["remaining"], summary["log"] = c.calls, c.remaining, c.log
    (out / "_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"calls_this_run": c.calls, "remaining": c.remaining}))


if __name__ == "__main__":
    main()
