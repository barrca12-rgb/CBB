"""Check 2: residual persistence by team (LOG.md).

    python -m research.calibration.c2_persist
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import player_ratings as pr
from research.calibration.common import OUT, TEST, base, cluster_ols
from research.originator.d2_tiers import tiers

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def team_rows(w: pd.DataFrame) -> pd.DataFrame:
    h = w[["game_id", "date", "season", "home_id", "res"]].rename(columns={"home_id": "team_id"})
    a = w[["game_id", "date", "season", "away_id", "res"]].rename(columns={"away_id": "team_id"}).assign(res=lambda d: -d["res"])
    t = pd.concat([h, a]).sort_values(["team_id", "season", "date", "game_id"])
    g = t.groupby(["team_id", "season"])["res"]
    t["prev5"] = g.transform(lambda s: s.shift(1).rolling(5, min_periods=5).mean())
    t["n"] = g.cumcount()
    return t


def events(t: pd.DataFrame) -> pd.DataFrame:
    co = pd.read_csv(os.path.join(ROOT, "data", "research", "coaches.csv"))
    new = set(zip(co.loc[co["new"].astype(bool), "team_id"], co.loc[co["new"].astype(bool), "season"]))
    t["coach_change"] = [((tid, s) in new) and n < 10 for tid, s, n in zip(t["team_id"], t["season"], t["n"])]
    first_abs, low_cont = {}, set()
    for s in sorted(t["season"].unique()):
        p = pr.player_games(s)
        prev = pr.player_games(s - 1) if s > 2013 else None
        last_roster = set(zip(prev["team_id"], prev["athlete_id"])) if prev is not None else set()
        for team, tg in p.groupby("team_id", sort=False):
            games = [(gid, dict(zip(g["athlete_id"], g["min"]))) for gid, g in tg.sort_values("date").groupby("game_id", sort=False)]
            first5 = games[:5]
            tot = sum(sum(m.values()) for _, m in first5)
            ret = sum(v for _, m in first5 for a_, v in m.items() if (team, a_) in last_roster)
            if tot and last_roster and ret / tot < 0.4:
                low_cont.add((team, s))
            for i, (gid, now) in enumerate(games):
                if i < 5:
                    continue
                avg = pd.DataFrame([m for _, m in games[i - 5:i]]).fillna(0).mean()
                rot = avg[avg >= 20]
                if any(a_ not in now for a_ in rot.index):
                    first_abs[(team, s)] = gid
                    break
    # games after the first absence: the 5 team games following it
    t["after_absence"] = False
    for (team, s), gid in first_abs.items():
        idx = t.index[(t["team_id"] == team) & (t["season"] == s)]
        sub = t.loc[idx]
        pos = np.where(sub["game_id"].to_numpy() == gid)[0]
        if len(pos):
            t.loc[sub.index[pos[0] + 1:pos[0] + 6], "after_absence"] = True
    t["transfer_heavy"] = [((tid, s) in low_cont) and n < 10 for tid, s, n in zip(t["team_id"], t["season"], t["n"])]
    return t


def fit(d: pd.DataFrame, label: str) -> dict:
    d = d.dropna(subset=["prev5"])
    if len(d) < 200:
        return {"subset": label, "n": len(d)}
    b, se = cluster_ols(d["prev5"], d["res"], d["date"].astype(str))
    return {"subset": label, "n": len(d), "coef": round(b[1], 4), "interval": f"[{b[1]-1.96*se[1]:.4f}, {b[1]+1.96*se[1]:.4f}]",
            "verdict": "candidate" if (b[1] >= 0.05 and b[1] - 1.96 * se[1] > 0) else "closed"}


def main() -> None:
    w = base()
    w = w[w["season"].between(2014, 2026)].dropna(subset=["res"])
    tier = tiers(w)
    t = team_rows(w)
    tm = pd.concat([w[["game_id", "home_id"]].assign(tier=tier.values).rename(columns={"home_id": "team_id"}),
                    w[["game_id", "away_id"]].assign(tier=tier.values).rename(columns={"away_id": "team_id"})])
    t = t.merge(tm, on=["game_id", "team_id"], how="left")
    t = events(t)
    rows = [fit(t, "all 2014-26")]
    # out of sample: coefficient from earlier seasons, R2 on 2020-26
    pred = []
    for s in TEST:
        tr = t[(t["season"] < s)].dropna(subset=["prev5"])
        b = np.polyfit(tr["prev5"], tr["res"], 1)
        te = t[t["season"] == s].dropna(subset=["prev5"])
        pred.append(pd.DataFrame({"y": te["res"], "yhat": b[1] + b[0] * te["prev5"]}))
    pp = pd.concat(pred)
    r2 = 1 - ((pp["y"] - pp["yhat"]) ** 2).sum() / ((pp["y"] - pp["y"].mean()) ** 2).sum()
    for mo, lab in ((11, "Nov"), (12, "Dec"), (1, "Jan"), (2, "Feb"), (3, "Mar")):
        rows.append(fit(t[pd.to_datetime(t["date"]).dt.month == mo], f"month {lab}"))
    for tr_ in ("high", "mid", "low"):
        rows.append(fit(t[t["tier"] == tr_], f"tier {tr_}"))
    for ev, lab in (("coach_change", "first 10 games, new coach"), ("after_absence", "5 games after first absence"),
                    ("transfer_heavy", "first 10 games, <40% returning minutes")):
        rows.append(fit(t[t[ev]], lab))
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(OUT, "c2_result.csv"), index=False)
    pd.set_option("display.width", 200)
    print(r.to_string(index=False))
    print(f"out-of-sample R2 on 2020-26: {r2:.5f}")


if __name__ == "__main__":
    main()
