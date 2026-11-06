"""Absences valued by learned player weights (PLAN.md, pre-registered Nov 6, 2026). Research only.

    python -m research.absence_values.backtest      # -> out/results.txt, out/*.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.a2_timing import score
from audit.common import frame
from cbb import player_ratings as pr
from cbb import projection as P
from research.roster_prior import build_v3 as v3

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
STAGE1 = os.path.join(HERE, "..", "own_ratings", "out", "stage1_base.csv")
SHRINK = 150.0
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def linear_weights(season: int) -> tuple[float, np.ndarray]:
    """(constant, per-stat weights) of the learned total value, fit on lineup seasons before `season`."""
    use = tuple(s for s in v3.LINEUP if s < season) or v3.LINEUP
    f = v3.spm(use)
    k = f.coef["off"] + f.coef["def"]
    w = k[1:] / f.sd
    return float(k[0] - (w * f.mu).sum()), w


def impact(season: int) -> pd.DataFrame:
    """Per team-game: miss_impact from games before it (PLAN.md)."""
    path = os.path.join(OUT, f"impact_{season}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    c0, w = linear_weights(season)
    p = pr.player_games(season)
    num = lambda c: pd.to_numeric(p[c], errors="coerce").fillna(0).to_numpy(float)
    S = np.column_stack([num("field_goals_attempted") - num("three_point_field_goals_attempted") if k == "fga2" else num(c)
                         for k, c in v3.STATS.items()])
    p = p.assign(_i=np.arange(len(p))).sort_values(["team_id", "date", "game_id"])
    out = []
    for team, tg in p.groupby("team_id", sort=False):
        cs, cp, cm, cg = {}, {}, {}, {}
        last: set = set()
        team_min = 0.0
        for gid, g in tg.groupby("game_id", sort=False):
            val = 0.0
            if last and team_min > 0 and cs:
                ids = list(cs)
                poss = np.array([cp[a] for a in ids])
                rates = np.array([cs[a] for a in ids]) * 100 / np.maximum(poss, 1)[:, None]
                v = c0 + rates @ w
                mins = np.array([cm[a] for a in ids])
                vt = float((v * mins).sum() / mins.sum())
                vs = (v * poss + vt * SHRINK) / (poss + SHRINK) - vt
                for a, rel, m in zip(ids, vs, mins):
                    if cg[a] >= 3 and a not in last:
                        val += m / team_min * rel
            out.append((int(gid), int(team), val))
            pl = g[g["min"] > 0]
            for a, i, m, op in zip(pl["athlete_id"], pl["_i"], pl["min"], pl["on_poss"]):
                cs[a] = cs.get(a, 0.0) + S[i]
                cp[a] = cp.get(a, 0.0) + op
                cm[a] = cm.get(a, 0.0) + m
                cg[a] = cg.get(a, 0) + 1
            team_min += pl["min"].sum()
            last = set(pl["athlete_id"])
    d = pd.DataFrame(out, columns=["game_id", "team_id", "miss_impact"])
    os.makedirs(OUT, exist_ok=True)
    d.to_parquet(path)
    return d


def add_feature(b: pd.DataFrame) -> pd.DataFrame:
    """miss_impact_diff (home minus away), each side as its excess over the team's own average so far."""
    a = pd.concat([impact(s) for s in sorted(b["season"].unique()) if s >= 2014])
    a = a.merge(b[["game_id", "season", "date"]].drop_duplicates("game_id"), on="game_id").sort_values("date")
    a["ex"] = a["miss_impact"] - a.groupby(["team_id", "season"])["miss_impact"].transform(
        lambda x: x.shift().expanding().mean()).fillna(0.0)
    ex = a.set_index(["game_id", "team_id"])["ex"]
    b = b.copy()
    h = ex.reindex(pd.MultiIndex.from_arrays([b["game_id"], b["home_id"]])).to_numpy()
    w = ex.reindex(pd.MultiIndex.from_arrays([b["game_id"], b["away_id"]])).to_numpy()
    b["miss_impact_diff"] = np.nan_to_num(h) - np.nan_to_num(w)
    return b


def build(tag: str, feats: list[str]) -> pd.DataFrame:
    old = P.MARGIN_FEATURES
    try:
        P.MARGIN_FEATURES = feats
        return frame(stage1=STAGE1, tag=tag, features=add_feature)
    finally:
        P.MARGIN_FEATURES = old


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    base = frame(stage1=STAGE1, tag="own_base")
    m1 = build("av_M1", P.MARGIN_FEATURES + ["miss_impact_diff"])
    m2 = build("av_M2", [f for f in P.MARGIN_FEATURES if f != "miss_diff"] + ["miss_impact_diff"])
    feat = m1[["game_id", "miss_impact_diff"]].set_index("game_id")["miss_impact_diff"]
    thr = feat[feat.index.isin(m1.loc[m1["season"] >= 2015, "game_id"])].abs().quantile(0.9)
    rows, plays = [], []
    for tag, w in (("M0 base", base), ("M1 + impact (primary)", m1), ("M2 impact replaces minutes", m2)):
        w = w[w["season"] >= 2015]
        big = w["game_id"].map(feat).abs() >= thr
        for lab, x in (("all", w), ("top 10% |impact|", w[big])):
            rows.append({"variant": tag, "games": lab, "n": len(x),
                         "margin MAE": round(float((x["final_margin"] - x["margin"]).abs().mean()), 4)})
        plays += [r for r in score(w, tag) if r["market"] == "spread"]
    A, Pl = pd.DataFrame(rows), pd.DataFrame(plays)
    pd.set_option("display.width", 250)
    say(f"Absence values (PLAN.md). Top-10% threshold |miss_impact_diff| = {thr:.2f}")
    say(A.to_string(index=False))
    say("\nOpener spreads at 2.5+:\n" + Pl.to_string(index=False))
    m0 = A[(A.variant == "M0 base") & (A.games == "all")]["margin MAE"].iat[0]
    m1v = A[(A.variant == "M1 + impact (primary)") & (A.games == "all")]["margin MAE"].iat[0]
    b0 = Pl[Pl.variant == "M0 base"].set_index("seasons")["win%"]
    b1 = Pl[Pl.variant == "M1 + impact (primary)"].set_index("seasons")["win%"]
    c1, c2, c3 = m1v < m0, all(b1[s] >= b0[s] - 0.3 for s in b0.index), any(b1[s] > b0[s] for s in b0.index)
    say(f"\nProposal rule (M1): margin miss lower {c1}; win % within 0.3 {c2}; higher somewhere {c3} -> "
        f"{'PASS' if c1 and c2 and c3 else 'no'}")
    A.to_csv(os.path.join(OUT, "accuracy.csv"), index=False)
    Pl.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
