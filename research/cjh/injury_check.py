"""CJH Read 2: opening-week injury cross-check (research/cjh/PLAN.md, pre-registered Oct 29, 2026). Research only.

    python -m research.cjh.injury_check

Reads the latest CJH snapshot taken before the first 2026-27 tip from the private data repo (../cbb-data), checks its
sha256 against research/cjh/snapshots.csv, and prints player names, teams and our own numbers only. CJH's ratings
are never written to this public repo.

Definitions (fixed in PLAN.md):
- Players: everyone CJH lists as "out". Value: player_projections.json (BPM; minutes = roster_mpg, else mpg; a
  roster_mpg of 0 is the "out" override itself, so mpg is used), else the 2025-26 line in players_current.json by
  name+team, else by name alone when unique. Material: BPM >= +2 or >= 20 minutes per game.
- Per player: appeared in any 2026-27 box score Nov 3-9; on ESPN's report (injuries/log.csv) at T-60 before his
  team's first game.
- Teams with a material player out, first two games: mean (market margin - our projection) and (result - market
  margin), oriented to that team, vs all other opening-week team-games (Nov 3-9). Market margin = minus the closing
  home spread (median of each book's last quote before the verified tip, as in research/injury_reports/evaluate.py).
- Decision: build a preseason long-term-injury input only if material out-players were mostly absent from ESPN's report
  AND the close sat on average >= 1 point further against those teams than our projection. Else "not needed".
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import pandas as pd

from cbb import data, teams
from research.injury_reports import evaluate as ev

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PRIVATE = os.path.join(ROOT, "..", "cbb-data", "research", "cjh", "snapshots")
FIRST_TIP = pd.Timestamp("2026-11-01T14:34:14Z")   # first 2026-27 tip in lines/tipoffs.csv
WEEK = ("2026-11-03", "2026-11-09")
key = lambda s: re.sub(r"[^a-z]", "", str(s).lower().replace(" jr", "").replace(" iii", "").replace(" ii", ""))


def snapshot() -> tuple[str, dict, dict, list]:
    led = pd.read_csv(os.path.join(ROOT, "research", "cjh", "snapshots.csv"))
    led["t"] = pd.to_datetime(led["snapshot"], format="%Y-%m-%dT%H%MZ", utc=True)
    snap = led[led["t"] < FIRST_TIP]["snapshot"].max()
    files = {"inj": "manual_overrides/player_injuries_2026.json", "pp": "player_projections.json", "pc": "players_current.json"}
    out = {}
    for k, f in files.items():
        path = os.path.join(PRIVATE, snap, f.replace("/", "__"))
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        want = led[(led["snapshot"] == snap) & (led["file"] == f)]["sha256"].iloc[0]
        assert sha == want, f"sha256 mismatch for {f}"
        out[k] = json.load(open(path))
    return snap, out["inj"]["overrides"], out["pp"], out["pc"]


def value(o: dict, pp: dict, pc: list) -> dict:
    p = pp.get(f"{o['player']}|{o['team']}")
    if p:
        mpg = p.get("roster_mpg") or p.get("mpg")
        return {"source": "projection", "bpm": p.get("bpm"), "mpg": mpg}
    same = [x for x in pc if key(x.get("Player")) == key(o["player"])]
    exact = [x for x in same if key(x.get("Team")) == key(o["team"])]
    hit = exact or (same if len(same) == 1 else [])
    if hit:
        return {"source": "2025-26 line" + ("" if exact else f" ({hit[0].get('Team')})"), "bpm": hit[0].get("BPM"),
                "mpg": hit[0].get("MPG")}
    return {"source": "unvalued", "bpm": None, "mpg": None}


def main() -> None:
    snap, inj, pp, pc = snapshot()
    print(f"CJH snapshot {snap} (latest before the first tip {FIRST_TIP:%Y-%m-%d %H:%M} UTC); sha256 verified")
    kp = teams.id_lookup("kenpom")
    box = ev.box(2027)
    wk = box[(box["game_date"] >= WEEK[0]) & (box["game_date"] <= WEEK[1])]
    espn, why = ev.listings("espn")
    tp = ev.tips()
    g = ev.games(WEEK[1])
    g = g[g["date"] >= WEEK[0]]
    cards = pd.concat([pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{d}.csv"),
                                   usecols=lambda c: c in {"game_id", "model_margin"}) for d in sorted(g["date"].unique())
                       if os.path.exists(os.path.join(ROOT, "reports", f"cbb_{d}.csv"))]).drop_duplicates("game_id", keep="last")
    g = g.merge(cards, on="game_id", how="left").merge(ev.closes(g, tp), on="game_id", how="left")
    rows = []
    for r in g.itertuples():
        for side, team, opp, sgn in (("home", r.home_id, r.away_id, 1), ("away", r.away_id, r.home_id, -1)):
            rows.append({"game_id": r.game_id, "date": r.date, "team_id": team, "opp_id": opp,
                         "market_vs_model": sgn * (-r.close_spread - r.model_margin),
                         "result_vs_close": sgn * ((r.home_score - r.away_score) + r.close_spread)})
    tg = pd.DataFrame(rows).dropna(subset=["market_vs_model"])
    players = []
    for o in inj.values():
        tid = kp.get(teams.norm(o["team"]))
        v = value(o, pp, pc)
        material = v["bpm"] is not None and ((v["bpm"] or 0) >= 2 or (v["mpg"] or 0) >= 20)
        tb = wk[wk["team_id"] == tid]
        appeared = bool(len(tb[(tb["athlete_display_name"].map(key) == key(o["player"])) & (tb["min"] > 0)])) if "athlete_display_name" in tb else None
        first = g[(g["home_id"] == tid) | (g["away_id"] == tid)].sort_values("date")
        at = tp.get(first["game_id"].iloc[0]) - pd.Timedelta(minutes=60) if len(first) and first["game_id"].iloc[0] in tp else None
        on_espn = bool(len(espn)) and at is not None and len(ev.state(espn, tid, at))
        players.append({"player": o["player"], "team": o["team"], "team_id": tid, "value_from": v["source"],
                        "bpm": v["bpm"], "mpg": v["mpg"], "material": material, "appeared_nov3_9": appeared,
                        "on_espn_t60": on_espn})
    P = pd.DataFrame(players)
    print("\nCJH 'out' players (our check):")
    print(P.to_string(index=False))
    mat = P[P["material"]]
    mt = set(mat["team_id"].dropna().astype(int))
    first2 = tg[tg["team_id"].isin(mt)].sort_values("date").groupby("team_id").head(2)
    others = tg.drop(first2.index)
    print(f"\nESPN listings available: {len(espn)}" + (f" ({why})" if why else ""))
    print(f"teams with a material player out: {len(mt)}; their first two games: {len(first2)} team-games")
    for lab, d in (("material-out teams, first two games", first2), ("all other opening-week team-games", others)):
        print(f"  {lab}: n {len(d)}, mean market minus our projection {d['market_vs_model'].mean():+.2f}, "
              f"mean result minus close {d['result_vs_close'].mean():+.2f}")
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(b["status"] != "void") & b["game_id"].isin(first2["game_id"])]
    print(f"\nour logged plays on those games: {len(b)}")
    if len(b):
        print(b[["date", "pick", "book", "edge", "stake", "result", "profit", "bet_type"]].to_string(index=False))
    mostly_absent = len(mat) > 0 and (~mat["on_espn_t60"].astype(bool)).mean() > 0.5
    against = len(first2) > 0 and first2["market_vs_model"].mean() <= -1.0
    print(f"\ndecision: material players mostly absent from ESPN's report: {mostly_absent}; close >= 1 point further "
          f"against those teams than our projection: {against} -> "
          f"{'build a preseason long-term-injury input (proposal)' if mostly_absent and against else 'not needed'}")


if __name__ == "__main__":
    main()
