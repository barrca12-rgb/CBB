"""Pull CBBD play-by-play by UTC date (on-floor players included from 2023-24) and reduce it at once to lineup
stints. Research only (PLAN.md). The raw plays are not kept (several GB per season); only the derived stints and
player-game seconds are saved, to the private data repo (../cbb-data/research/player_impact/).

A stint is a run of consecutive plays in one game with the same players on the floor. The source sometimes lists
4 or 6 for a side (substitution logging errors); sides with 4-6 are kept with their count (nh, na) so the model can
weight each listed player 5/n; plays with fewer than 4 or more than 6 on a side are counted and credited to the
stint in progress (their points, seconds and events are kept), so a game's stints add up to its final score. Per stint: seconds, each side's points (score changes) and
possessions (FGA - ORB + TOV + 0.475 FTA from the side's own events).

    python -m research.player_impact.pull 2024 2025 2026     # seasons by end year; resumes, skips saved dates
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

BASE = "https://api.collegebasketballdata.com"
OUT = Path(__file__).resolve().parents[3] / "cbb-data" / "research" / "player_impact"
FLOOR = 300                     # stop if the month's remaining calls would fall below this
FGA = {"JumpShot", "LayUpShot", "DunkShot", "TipShot", "Three Point Jump Shot", "Shot"}


def fetch(day: str):
    req = urllib.request.Request(f"{BASE}/plays/date?date={day}", headers={"Accept": "application/json"})
    if os.environ.get("CBBD_API_KEY"):
        req.add_header("Authorization", f"Bearer {os.environ['CBBD_API_KEY']}")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()), r.headers.get("X-Calllimit-Remaining")


def reduce(plays: list, season: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    stints, pgs, bad = [], {}, 0
    by_game = {}
    for p in plays:
        by_game.setdefault(p["gameId"], []).append(p)
    for gid, ps in by_game.items():
        ps.sort(key=lambda x: x["id"])
        home = next((x["team"] for x in ps if x.get("isHomeTeam") is True), None)
        away = next((x["team"] for x in ps if x.get("isHomeTeam") is False), None)
        if home is None or away is None:
            continue
        src = int(ps[0]["gameSourceId"]) if str(ps[0].get("gameSourceId", "")).isdigit() else None
        cur, acc = "start", None
        prev_h, prev_a, prev_sec, prev_per = 0, 0, None, None

        def flush():
            if acc is not None and acc["key"] is not None:
                stints.append({k: v for k, v in acc.items() if k != "key"})
        for p in ps:
            fl = p.get("onFloor") or []
            hs = sorted(x["id"] for x in fl if x["team"] == home)
            as_ = sorted(x["id"] for x in fl if x["team"] == away)
            key = (tuple(hs), tuple(as_)) if 4 <= len(hs) <= 6 and 4 <= len(as_) <= 6 else None
            if key is None:
                bad += 1
            per, sec = p["period"], p.get("secondsRemaining")
            if key is None and acc is not None:
                key = cur                      # irregular listing: keep crediting the current stint
            if key != cur:
                flush()
                cur = key
                acc = {"key": key, "season": season, "cbbd_game_id": gid, "game_id": src, "date": p["gameStartDate"][:10],
                       "home": home, "away": away, "nh": len(hs), "na": len(as_), **({f"h{i}": v for i, v in enumerate(hs)} if key else {}),
                       **({f"a{i}": v for i, v in enumerate(as_)} if key else {}),
                       "secs": 0.0, "home_pts": 0, "away_pts": 0, "home_fga": 0, "away_fga": 0, "home_orb": 0,
                       "away_orb": 0, "home_tov": 0, "away_tov": 0, "home_fta": 0, "away_fta": 0}
            if prev_sec is not None and per == prev_per and sec is not None:
                acc["secs"] += max(prev_sec - sec, 0)
            h, a = p.get("homeScore") or 0, p.get("awayScore") or 0
            acc["home_pts"] += max(h - prev_h, 0)
            acc["away_pts"] += max(a - prev_a, 0)
            prev_h, prev_a, prev_sec, prev_per = h, a, sec, per
            side = "home" if p.get("isHomeTeam") is True else "away" if p.get("isHomeTeam") is False else None
            if side:
                t = p["playType"]
                if t == "MadeFreeThrow":
                    acc[f"{side}_fta"] += 1
                elif t in FGA or (p.get("shootingPlay") and "FreeThrow" not in t):
                    acc[f"{side}_fga"] += 1
                elif t == "Offensive Rebound":
                    acc[f"{side}_orb"] += 1
                elif "Turnover" in t:
                    acc[f"{side}_tov"] += 1
        flush()
    s = pd.DataFrame(stints)
    for side in ("home", "away"):
        if len(s):
            s[f"{side}_poss"] = s[f"{side}_fga"] - s[f"{side}_orb"] + s[f"{side}_tov"] + 0.475 * s[f"{side}_fta"]
    # player-game seconds and team
    rows = []
    if len(s):
        for side, pre in (("home", "h"), ("away", "a")):
            for i in range(6):
                if f"{pre}{i}" not in s:
                    continue
                rows.append(pd.DataFrame({"cbbd_game_id": s["cbbd_game_id"], "game_id": s["game_id"], "date": s["date"],
                                          "team": s[side], "player": s[f"{pre}{i}"], "secs": s["secs"]}))
        pg = pd.concat(rows).groupby(["cbbd_game_id", "game_id", "date", "team", "player"], dropna=False)["secs"].sum().reset_index()
    else:
        pg = pd.DataFrame()
    names = {}
    for p in plays:
        for x in p.get("onFloor") or []:
            names[x["id"]] = (x["name"], x["team"])
    return s, pg, {"bad_plays": bad, "names": names}


def season_dates(season: int):
    d, end = date(season - 1, 11, 1), date(season, 4, 10)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def main() -> None:
    seasons = [int(x) for x in sys.argv[1:]] or [2024, 2025, 2026]
    log_path = OUT / "pull_log.csv"
    for season in seasons:
        sd = OUT / "stints" / str(season)
        sd.mkdir(parents=True, exist_ok=True)
        names_path = OUT / f"players_{season}.json"
        names = json.loads(names_path.read_text()) if names_path.exists() else {}
        for day in season_dates(season):
            f = sd / f"{day}.parquet"
            if f.exists():
                continue
            t0 = time.time()
            plays, remaining = fetch(day)
            s, pg, info = reduce(plays if isinstance(plays, list) else [], season)
            s.to_parquet(f, index=False)
            pg.to_parquet(sd / f"{day}_players.parquet", index=False)
            names.update({str(k): v for k, v in info["names"].items()})
            names_path.write_text(json.dumps(names))
            line = f"{season},{day},{len(plays) if isinstance(plays, list) else -1},{s['cbbd_game_id'].nunique() if len(s) else 0},{len(s)},{info['bad_plays']},{remaining},{time.time() - t0:.1f}\n"
            with open(log_path, "a") as fh:
                fh.write(line)
            print(line.strip(), flush=True)
            if remaining is not None and int(remaining) < FLOOR:
                print(f"stopping: remaining calls {remaining} below floor {FLOOR}")
                return


if __name__ == "__main__":
    main()
