"""Structured miss review (pre-registered in LOG.md).

    python -m research.misses.m_review
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from cbb import player_ratings as pr
from research.originator.d2_tiers import tiers
from research.originator.d_common import oriented_openers

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
SEASONS = {2026: "2025-26 (primary)", 2025: "2024-25 (check)"}


def absences(season: int) -> pd.DataFrame:
    """Per team-game: minutes a game of rotation players (20+ mpg over the team's previous 5 games) missing."""
    p = pr.player_games(season)
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        games = [(gid, dict(zip(g["athlete_id"], g["min"]))) for gid, g in tg.sort_values("date").groupby("game_id", sort=False)]
        for i, (gid, now) in enumerate(games):
            prev = games[max(0, i - 5):i]
            if len(prev) < 3:
                out.append((gid, team, 0.0))
                continue
            avg = pd.DataFrame([m for _, m in prev]).fillna(0).mean()
            rot = avg[avg >= 20]
            out.append((gid, team, float(rot[[a not in now for a in rot.index]].sum())))
    return pd.DataFrame(out, columns=["game_id", "team_id", "missing_min"])


def plays(w: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sp = w.dropna(subset=["open_home_spread", "home_spread"])
    e = sp["final_margin"] + sp["open_home_spread"]
    s = sp[e.abs() >= 2.5].assign(edge=e.abs(), home_side=e > 0)
    s["lv"] = np.where(s["home_side"], s["open_home_spread"] - s["home_spread"], s["home_spread"] - s["open_home_spread"])
    m = (s["home_pts"] - s["away_pts"] + s["open_home_spread"]) * np.where(s["home_side"], 1, -1)
    s["res"] = np.sign(m)
    kpe = (s["kp_margin"] + s["open_home_spread"]) * np.where(s["home_side"], 1, -1)
    s["kp_disagrees"] = kpe < 1
    s["our_miss"] = np.where(s["home_side"], s["h_missing"], s["a_missing"])
    s["opp_miss"] = np.where(s["home_side"], s["a_missing"], s["h_missing"])
    s["big"] = s["edge"] >= 5
    rows.append(s.assign(market="spread"))
    to = w.dropna(subset=["open_total", "total"])
    e = to["final_total"] - to["open_total"]
    t = to[e.abs() >= 3].assign(edge=e.abs(), over=e > 0)
    t["lv"] = np.where(t["over"], t["total"] - t["open_total"], t["open_total"] - t["total"])
    t["res"] = np.sign((t["home_pts"] + t["away_pts"] - t["open_total"]) * np.where(t["over"], 1, -1))
    kpe = (t["kp_total"] - t["open_total"]) * np.where(t["over"], 1, -1)
    t["kp_disagrees"] = kpe < 1
    t["our_miss"] = np.maximum(t["h_missing"], t["a_missing"])   # totals: either team
    t["opp_miss"] = 0.0
    t["big"] = t["edge"] >= 6
    rows.append(t.assign(market="total"))
    d = pd.concat(rows, ignore_index=True)
    d["absence_ours"] = d["our_miss"] >= 20
    d["absence_other"] = d["opp_miss"] >= 20
    d["early"] = d["games_before"] < 5
    d["low_major"] = d["tier"] == "low"
    d["neutral_site"] = d["neutral"].astype(bool)
    d["miss"] = d["lv"] <= -1.5
    cause = np.select([d["absence_ours"], d["absence_other"], d["early"], d["kp_disagrees"], d["low_major"]],
                      ["absence (our side)", "absence (other side)", "early season", "KenPom disagrees", "low-major"],
                      "none of these")
    d["primary_cause"] = cause
    return d


TAGS = ["absence_ours", "absence_other", "early", "kp_disagrees", "low_major", "neutral_site", "big"]


def table(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    allm = d["miss"].mean()
    for tag in ["(all plays)"] + TAGS:
        x = d if tag == "(all plays)" else d[d[tag]]
        if not len(x):
            continue
        dec = x[x["res"] != 0]
        share = len(x) / len(d)
        share_m = (x["miss"].sum() / d["miss"].sum()) if d["miss"].sum() else np.nan
        rows.append({"tag": tag, "plays": len(x), "share of plays": round(share, 3), "miss rate": round(x["miss"].mean(), 3),
                     "lift (share of misses / share of plays)": round(share_m / share, 2) if tag != "(all plays)" else 1.0,
                     "mean line value": round(x["lv"].mean(), 2), "win% at opener": round(100 * (dec["res"] > 0).mean(), 1),
                     "win% when missed": round(100 * (dec[dec["miss"]]["res"] > 0).mean(), 1) if dec["miss"].any() else np.nan})
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = oriented_openers(w[w["season"].isin(list(SEASONS))])
    w = w[~evaluate.swapped(w.assign(pred_margin=w["final_margin"]))]
    ab = pd.concat([absences(s) for s in SEASONS])
    w = w.merge(ab.rename(columns={"team_id": "home_id", "missing_min": "h_missing"}), on=["game_id", "home_id"], how="left") \
         .merge(ab.rename(columns={"team_id": "away_id", "missing_min": "a_missing"}), on=["game_id", "away_id"], how="left")
    w[["h_missing", "a_missing"]] = w[["h_missing", "a_missing"]].fillna(0.0)
    w = w.assign(tier=tiers(w))
    d = plays(w)
    d.to_csv(os.path.join(OUT, "m_plays.csv.gz"), index=False)
    pd.set_option("display.width", 250)
    for s, lab in SEASONS.items():
        for mk in ("spread", "total"):
            x = d[(d["season"] == s) & (d["market"] == mk)]
            print(f"\n== {lab} · {mk}s: {len(x)} plays, {x['miss'].sum()} misses ({100 * x['miss'].mean():.1f}%)")
            t = table(x)
            print(t.to_string(index=False))
            t.assign(season=s, market=mk).to_csv(os.path.join(OUT, f"m_tags_{s}_{mk}.csv"), index=False)
            pc = x[x["miss"]]["primary_cause"].value_counts(normalize=True).mul(100).round(1)
            base = x["primary_cause"].value_counts(normalize=True).mul(100).round(1)
            print("primary cause of misses, % (vs % of all plays):",
                  {k: f"{pc.get(k, 0)} ({base.get(k, 0)})" for k in base.index})


if __name__ == "__main__":
    main()
