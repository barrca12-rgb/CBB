"""Injury-report study (research/injury_reports/PLAN.md, pre-registered Oct 29, 2026). Research only: reads files the
card already writes and changes nothing live.

    python -m research.injury_reports.evaluate --plumbing            # counts only (Nov 20 plumbing run)
    python -m research.injury_reports.evaluate --read dec15|jan15|feb15

Definitions follow PLAN.md and are not re-specified after data:
- Listings: ESPN pulls in injuries/log.csv (the model's source). Other outlets (RotoWire, Covers) from
  injuries/sources/first_seen.csv, reported as a secondary split by source. Both files keep a row the first time a
  player+status+report date is seen, so "listed at time T" = the player's latest row seen at or before T, if that row
  was seen within LISTING_DAYS of T and is an injury status (P_MISS keys). A latest row of "cleared"/"available" means
  off the report; a stale listing is treated as cleared (neither file records removals otherwise).
- T-60: the last state at least 60 minutes before the verified tip (lines/tipoffs.csv). T-open: the state at the first
  logged quote for the game (lines/openers.csv first_seen). Games without a verified tip are excluded and listed.
- Minutes shares come only from games before each date, mirroring cbb/injuries.py: this season's share once a team
  has 3 games, else last season's share on the same team; a player counts only if he played the team's last game
  (before the team's 3rd game, anyone listed counts).
- J = live missing-minutes weight (data/projection.json margin coef miss_diff) x (home - away injury minutes).
- Q1 miss rate by status with Wilson 95% intervals; Q2 slopes with date-clustered SEs; Q3 totals; Q4 injury-moved plays.
- Reads: Dec 15 (games through Dec 12, Q2 at 99.9%), Jan 15 (through Jan 10, 95%), Feb 15 fallback (through Feb 12)
  if Q2 has fewer than 300 games with J != 0 on Jan 15.
"""
from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import pandas as pd

from cbb import data
from cbb.injuries import P_MISS

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SEASON = 2027
START = "2026-11-03"
LISTING_DAYS = 7
READS = {"dec15": ("2026-12-12", 0.999), "jan15": ("2027-01-10", 0.95), "feb15": ("2027-02-12", 0.95)}
MIN_GAMES_Q2, MIN_STATUS_Q1, SHRINK = 300, 40, 20
THRESH = {"spread": 2.5, "total": 3.0}
P = lambda *a: os.path.join(ROOT, *a)


# ---------------------------------------------------------------- inputs
def weight() -> float:
    return float(json.load(open(P("data", "projection.json")))["margin"]["miss_diff"])


def listings(source: str) -> tuple[pd.DataFrame, str]:
    """team_id, athlete_id, player, status (lower case, P_MISS keys), t (first seen). Second value: why empty."""
    cols = ["team_id", "athlete_id", "player", "status", "t"]
    if source == "espn":
        f = P("injuries", "log.csv")
        if not os.path.exists(f):
            return pd.DataFrame(columns=cols), "injuries/log.csv does not exist (ESPN feed returned no rows)"
        d = pd.read_csv(f).rename(columns={"pulled_at": "t"})
    else:
        f = P("injuries", "sources", "first_seen.csv")
        d = pd.read_csv(f)
        d = d[d["source"] == source].rename(columns={"first_seen": "t"})
    d = d.assign(status=d["status"].astype(str).str.lower(), t=pd.to_datetime(d["t"], utc=True, errors="coerce"),
                 team_id=pd.to_numeric(d["team_id"], errors="coerce"),
                 athlete_id=pd.to_numeric(d["athlete_id"], errors="coerce"))
    d = d.dropna(subset=["team_id", "athlete_id", "t"])
    return d[cols].reset_index(drop=True), ("" if len(d) else f"no matched {source} listings")


def state(lst: pd.DataFrame, team: int, at: pd.Timestamp) -> pd.DataFrame:
    """Players listed for a team at time `at`: latest row per athlete seen at or before `at`, within LISTING_DAYS."""
    x = lst[(lst["team_id"] == team) & (lst["t"] <= at) & (lst["t"] >= at - pd.Timedelta(days=LISTING_DAYS))]
    x = x.sort_values("t").groupby("athlete_id").tail(1)
    return x[x["status"].isin(P_MISS)]          # a latest status of "cleared"/"available" means off the report


def tips() -> pd.Series:
    t = pd.read_csv(P("lines", "tipoffs.csv"))
    t["tip"] = pd.to_datetime(t["actual_tip"], utc=True, errors="coerce")
    return t.dropna(subset=["tip"]).drop_duplicates("game_id", keep="last").set_index("game_id")["tip"]


def games(through: str) -> pd.DataFrame:
    """D-I games priced by v1 (shadow_v2 games_latest has v1's latest pregame margin), with scores, v1 total and the
    closing spread/total (median across books of each book's last quote before the tip)."""
    g = pd.read_csv(P("bets", "shadow_v2", "games_latest.csv"))
    g = g[(g["date"] >= START) & (g["date"] <= through)]
    cards = []
    for d in sorted(g["date"].unique()):
        f = P("reports", f"cbb_{d}.csv")
        if os.path.exists(f):
            cards.append(pd.read_csv(f, usecols=lambda c: c in {"game_id", "home_score", "away_score", "model_total"}))
    c = pd.concat(cards).drop_duplicates("game_id", keep="last") if cards else pd.DataFrame(columns=["game_id"])
    return g.merge(c, on="game_id", how="left")


def closes(g: pd.DataFrame, tp: pd.Series) -> pd.DataFrame:
    q = pd.read_csv(P("lines", "closing.csv"))
    q["t"] = pd.to_datetime(q["pulled_at"], utc=True, errors="coerce")
    out = []
    for r in g.itertuples():
        tip = tp.get(r.game_id)
        m = q[(q["home_id"] == r.home_id) & (q["away_id"] == r.away_id) & (q["date"] == r.date)]
        if tip is not None:
            m = m[m["t"] < tip]
        last = m.sort_values("t").groupby("book").tail(1)
        out.append({"game_id": r.game_id, "close_spread": last["home_spread"].median(),
                    "close_total": last["total"].median()})
    return pd.DataFrame(out)


def openers() -> pd.DataFrame:
    o = pd.read_csv(P("lines", "openers.csv"))
    o["t"] = pd.to_datetime(o["first_seen"], utc=True, format="mixed", errors="coerce")
    k = o["game_key"].str.split("|", expand=True)
    o = o.assign(date=k[0], home_id=pd.to_numeric(k[1]), away_id=pd.to_numeric(k[2]))
    return o.groupby(["date", "home_id", "away_id"])["t"].min().rename("t_open").reset_index()


_BOX: dict[int, pd.DataFrame] = {}


def box(season: int) -> pd.DataFrame:
    if season not in _BOX:
        p = data.fetch("player_box", season, refresh=(season == SEASON))
        p = p[p["athlete_id"].notna()].copy()
        p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
        p["athlete_id"] = pd.to_numeric(p["athlete_id"], errors="coerce")
        p["team_id"] = pd.to_numeric(p["team_id"], errors="coerce")
        p["game_date"] = pd.to_datetime(p["game_date"]).dt.strftime("%Y-%m-%d")
        _BOX[season] = p
    return _BOX[season]


def shares_before(team: int, date: str) -> pd.DataFrame:
    """athlete_id, share, played_last for one team using only games before `date` (mirrors injuries._shares)."""
    cur = box(SEASON)
    c = cur[(cur["team_id"] == team) & (cur["game_date"] < date) & (cur["min"] > 0)]
    if c["game_id"].nunique() >= 3:
        sh = (c.groupby("athlete_id")["min"].sum() / c["min"].sum()).rename("share").reset_index()
        last = c[c["game_date"] == c["game_date"].max()]["athlete_id"]
        return sh.assign(played_last=sh["athlete_id"].isin(set(last)))
    prev = box(SEASON - 1)
    p = prev[(prev["team_id"] == team) & (prev["min"] > 0)]
    if not len(p):
        return pd.DataFrame(columns=["athlete_id", "share", "played_last"])
    sh = (p.groupby("athlete_id")["min"].sum() / p["min"].sum()).rename("share").reset_index()
    return sh.assign(played_last=True)


# ---------------------------------------------------------------- build
def build(source: str, through: str) -> dict:
    lst, why = listings(source)
    tp = tips()
    g = games(through)
    excl = {}
    g["tip"] = g["game_id"].map(tp)
    excl["no verified tip"] = int(g["tip"].isna().sum())
    g = g.dropna(subset=["tip"])
    excl["no final score"] = int(g["home_score"].isna().sum())
    g = g.dropna(subset=["home_score"])
    g = g.merge(openers(), on=["date", "home_id", "away_id"], how="left").merge(closes(g, tp), on="game_id", how="left")
    w = weight()
    played = box(SEASON)
    played = played[played["min"] > 0].groupby("game_id")["athlete_id"].apply(set).to_dict()
    rows, q1 = [], []
    for r in g.itertuples():
        rec = {"game_id": r.game_id, "date": r.date}
        for when, at in (("t60", r.tip - pd.Timedelta(minutes=60)), ("topen", r.t_open)):
            for side, team in (("home", r.home_id), ("away", r.away_id)):
                if pd.isna(at) or not len(lst):
                    rec[f"{side}_{when}"] = 0.0
                    continue
                S = shares_before(team, r.date)
                S["athlete_id"] = pd.to_numeric(S["athlete_id"], errors="coerce")
                L = state(lst, team, at).merge(S, on="athlete_id", how="left")
                L["share"] = L["share"].fillna(0.0)
                L["played_last"] = L["played_last"].fillna(True).astype(bool)
                L["p_miss"] = L["status"].map(P_MISS).fillna(0.5)
                rec[f"{side}_{when}"] = float((L["p_miss"] * L["share"] * L["played_last"]).sum())
                if when == "t60":
                    for s in L.itertuples():
                        q1.append({"status": s.status, "missed": s.athlete_id not in played.get(r.game_id, set())})
        rows.append(rec)
    G = g.merge(pd.DataFrame(rows), on=["game_id", "date"], how="left") if rows else g
    if rows:
        G["J"] = w * (G["home_t60"] - G["away_t60"])
        G["J_open"] = w * (G["home_topen"] - G["away_topen"])
        G["margin"] = G["home_score"] - G["away_score"]
        G["res_model"] = G["margin"] - G["v1_margin"]
        G["res_close"] = G["margin"] + G["close_spread"]
        G["res_total"] = (G["home_score"] + G["away_score"]) - G["model_total"]
        G["inj_total"] = G["home_t60"] + G["away_t60"]
    return {"source": source, "listings": len(lst), "why_empty": why, "games": G, "q1": pd.DataFrame(q1),
            "exclusions": excl}


# ---------------------------------------------------------------- tests (only in a read, never in --plumbing)
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    c = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    m = (p + z * z / (2 * n)) / (1 + z * z / n)
    return (m - c, m + c)


def clustered_slope(y: pd.Series, x: pd.Series, cl: pd.Series) -> tuple[float, float, int]:
    d = pd.DataFrame({"y": y, "x": x, "c": cl}).dropna()
    if len(d) < 3 or d["x"].std() == 0:
        return (math.nan, math.nan, len(d))
    X = np.column_stack([np.ones(len(d)), d["x"].to_numpy()])
    b = np.linalg.lstsq(X, d["y"].to_numpy(), rcond=None)[0]
    e = d["y"].to_numpy() - X @ b
    bread = np.linalg.inv(X.T @ X)
    meat = sum(np.outer(X[i].T @ e[i], X[i].T @ e[i]) for i in d.groupby("c").indices.values())
    V = bread @ meat @ bread
    return (float(b[1]), float(math.sqrt(V[1, 1])), len(d))


def read(res: dict, level: float) -> None:
    z = {0.999: 3.29, 0.95: 1.96}[level]
    G, q1 = res["games"], res["q1"]
    print(f"\n== {res['source']}: Q1 miss rate by status at T-60")
    for st, grp in q1.groupby("status") if len(q1) else []:
        k, n = int(grp["missed"].sum()), len(grp)
        lo, hi = wilson(k, n)
        guess = P_MISS.get(st, 0.5)
        prop = (k + SHRINK * guess) / (n + SHRINK) if n >= MIN_STATUS_Q1 and not lo <= guess <= hi else None
        print(f"  {st}: {k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}] guess {guess}" + (f" -> propose {prop:.3f}" if prop else ""))
    nz = G[G["J"] != 0]
    for name, ycol, xcol in (("Q2a vs model", "res_model", "J"), ("Q2b vs close", "res_close", "J"),
                             ("Q2 T-open vs close", "res_close", "J_open"), ("Q3 totals", "res_total", "inj_total")):
        b, se, n = clustered_slope(G[ycol], G[xcol], G["date"])
        print(f"  {name}: slope {b:+.3f} (SE {se:.3f}), {level:.1%} [{b - z * se:+.3f}, {b + z * se:+.3f}], n {n}")
    print(f"  games with J != 0: {len(nz)} (minimum {MIN_GAMES_Q2})")


def plumbing(res: dict) -> None:
    G = res["games"]
    print(f"\n== {res['source']}: listings {res['listings']}" + (f" ({res['why_empty']})" if res["why_empty"] else ""))
    print(f"  games scored: {len(G)}; exclusions: {res['exclusions']}")
    if len(G) and "J" in G:
        print(f"  games with J != 0 at T-60: {int((G['J'] != 0).sum())}; at T-open: {int((G['J_open'] != 0).sum())}")
        print(f"  games with a close spread: {int(G['close_spread'].notna().sum())}; v1 total: {int(G['model_total'].notna().sum())}")
    print(f"  Q1 listings at T-60: {len(res['q1'])}" + (f", by status {res['q1']['status'].value_counts().to_dict()}" if len(res['q1']) else ""))


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--plumbing", action="store_true")
    a.add_argument("--read", choices=list(READS))
    a.add_argument("--through")
    o = a.parse_args()
    through = o.through or (READS[o.read][0] if o.read else pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d"))
    b = box(SEASON)
    print(f"2026-27 player box scores: {len(b)} rows, {b['game_id'].nunique()} games, through {b['game_date'].max()}")
    t = tips()
    print(f"verified tips: {len(t)}")
    for src in ("espn", "rotowire", "covers"):
        res = build(src, through)
        plumbing(res) if o.plumbing or not o.read else read(res, READS[o.read][1])


if __name__ == "__main__":
    main()
