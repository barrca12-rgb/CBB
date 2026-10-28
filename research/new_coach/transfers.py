"""High-major new coaches who brought transfers with them (PLAN_transfers.md, pre-registered).

    python -m research.new_coach.transfers     # -> research/new_coach/out/transfers_result.csv, transfers_teams.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import player_ratings as pr
from research.new_coach.study import OUT, ROOT, diff, team_games

SEASONS = [2022, 2023, 2024, 2025, 2026]
SHARE = 0.20


def hires() -> pd.DataFrame:
    """Every new-coach team-season 2021-26 with the coach's previous team and the followers' minute share."""
    co = pd.read_csv(os.path.join(ROOT, "data", "research", "coaches.csv"))
    rows = []
    for s in SEASONS:
        now, prev = pr.player_games(s), pr.player_games(s - 1)
        prev = prev[prev["minutes"].fillna(0) > 0]
        now = now[now["minutes"].fillna(0) > 0]
        last = co[co["season"] == s - 1].set_index("coach")["team_id"]
        for _, h in co[(co["season"] == s) & co["new"].astype(bool)].iterrows():
            old = last.get(h["coach"])
            old = None if old is None or (isinstance(old, pd.Series)) or int(old) == int(h["team_id"]) else int(old)
            g = now[now["team_id"] == h["team_id"]].sort_values("game_date")
            first5 = g[g["game_id"].isin(g["game_id"].drop_duplicates().head(5))]
            follow = set(prev.loc[prev["team_id"] == old, "athlete_id"]) if old else set()
            f = first5[first5["athlete_id"].isin(follow)]
            share = f["minutes"].sum() / first5["minutes"].sum() if len(first5) and first5["minutes"].sum() else 0.0
            rows.append({"season": s, "team_id": int(h["team_id"]), "coach": h["coach"], "old_team_id": old,
                         "followers": int(g.loc[g["athlete_id"].isin(follow), "athlete_id"].nunique()),
                         "follower_share_first5": round(float(share), 3)})
    return pd.DataFrame(rows)


def main() -> None:
    t = team_games()
    t = t[t["season"].isin(SEASONS)]
    h = hires()
    names = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["espn_name"]
    h["team"], h["old_team"] = h["team_id"].map(names), h["old_team_id"].map(names)
    key = lambda d: list(zip(d["team_id"], d["season"]))
    tier = t.drop_duplicates(["team_id", "season"]).set_index(["team_id", "season"])["tier"]
    h["tier"] = [tier.get(k) for k in key(h)]
    h["A"] = (h["tier"] == "high") & h["old_team_id"].notna() & (h["follower_share_first5"] >= SHARE)
    h["A_sens"] = (h["tier"] == "high") & h["old_team_id"].notna() & (h["followers"] >= 2)
    A, A2 = set(key(h[h["A"]])), set(key(h[h["A_sens"]]))
    B = set(key(h[(h["tier"] == "high") & ~h["A"]]))
    t["grp"] = ["A" if k in A else "B" if k in B else ("other_new" if n else "C")
                for k, n in zip(key(t), t["new"])]
    out = []
    windows = {"1-10": (1, 10), "1-5": (1, 5), "6-10": (6, 10)}
    for pool, seasons in (("2021-26", SEASONS), ("2025-26", [2026])):
        p = t[t["season"].isin(seasons)]
        for wn, (a, b) in windows.items():
            q = p[p["n"].between(a, b)]
            for label, test, ref in (("A vs C", "A", "C"), ("A vs B", "A", "B")):
                x = q[q["grp"].isin([test, ref])].assign(new=lambda d: d["grp"] == test)
                for col in ("vs_model", "vs_close", "vs_open"):
                    out.append({"pool": pool, "window": wn, "compare": label, "outcome": col, **diff(x, col)})
            in2 = np.array([k in A2 for k in key(q)])
            x = q[in2 | (q["grp"] == "C").to_numpy()].assign(new=in2[in2 | (q["grp"] == "C").to_numpy()])
            for col in ("vs_model", "vs_close"):
                out.append({"pool": pool, "window": wn, "compare": "A(2+ followers) vs C", "outcome": col, **diff(x, col)})
    r = pd.DataFrame(out)
    per = (t[t["grp"].eq("A") & t["n"].between(1, 10)].groupby(["season", "team_id"])
           [["vs_model", "vs_close"]].agg(["mean", "size"]))
    per.columns = ["vs_model", "games", "vs_close", "_n"]
    per = per.drop(columns="_n").reset_index().merge(h, on=["season", "team_id"])
    os.makedirs(OUT, exist_ok=True)
    r.to_csv(os.path.join(OUT, "transfers_result.csv"), index=False)
    h.to_csv(os.path.join(OUT, "transfers_hires.csv"), index=False)
    per.to_csv(os.path.join(OUT, "transfers_teams.csv"), index=False)
    with pd.option_context("display.width", 220, "display.max_rows", 500):
        txt = (r.round(2).to_string(index=False) + "\n\nGroup A team-seasons, first 10 games:\n" +
               per[["season", "team", "coach", "old_team", "followers", "follower_share_first5", "games", "vs_model",
                    "vs_close"]].round(2).to_string(index=False) +
               f"\n\nHigh-major new-coach team-seasons: {int((h['tier'] == 'high').sum())}; group A: {len(A)}; "
               f"2+ followers: {len(A2)}\n")
    open(os.path.join(OUT, "transfers_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
