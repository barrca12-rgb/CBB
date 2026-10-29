"""Independent checks (PLAN.md, Verification).

    python -m research.player_impact.verify     # -> out/verify.txt
"""
from __future__ import annotations

import hashlib
import json
import subprocess

import numpy as np
import pandas as pd

from cbb import data
from research.player_impact import ratings as R

L: list[str] = []
FAIL: list[str] = []
ROOT = R.OUT.parents[2]


def say(s=""):
    L.append(s)
    print(s, flush=True)


def check(ok, what):
    say(f"  [{'ok' if ok else 'FAIL'}] {what}")
    if not ok:
        FAIL.append(what)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    say("1. stint accounting")
    dbs = {}
    for s in R.SEASONS:
        st, pg, info = R.load(s)
        dbs[s] = (st, pg, info)
        _, t = data.season_games(s)
        box = t.groupby("game_id")["poss"].first()
        sp = st.groupby("game_id")[["home_poss", "away_poss", "secs"]].sum()
        ratio = ((sp["home_poss"] + sp["away_poss"]) / 2 / box.reindex(sp.index)).dropna()
        cov = info["games_with_stints"] / info["games_schedule"]
        say(f"  {s}: {info}; possessions vs box estimate mean {ratio.mean():.3f} (sd {ratio.std():.3f}); seconds/game median {sp['secs'].median():.0f}")
        check(cov > 0.85 and info["final_mismatch"] / max(info["games_with_stints"], 1) < 0.05 and abs(ratio.mean() - 1) < 0.05,
              f"{s}: coverage {cov:.3f}, mismatches {info['final_mismatch']}, possession ratio {ratio.mean():.3f}")

    say("\n2. timing: perturb everything on or after a date; features for earlier-dated games must not move")
    fr = json.load(open(R.OUT / "frozen.json"))
    lam, rho = (fr["lam"], fr["rho"]) if fr["choice"] != "none" else (1000.0, 0.0)
    st, pg, info = dbs[2025]
    X = pd.Timestamp("2025-01-15")
    base = R.run_variant(lam, 0.0, {2025: dbs[2025]})
    st2, pg2 = st.copy(), pg.copy()
    fut = st2["espn_date"] >= X
    st2.loc[fut, "home_pts"] = st2.loc[fut, "home_pts"] * 3 + 7
    st2.loc[fut, "away_pts"] = 0
    pg2.loc[pg2["espn_date"] >= X, "secs"] = 0.0
    pert = R.run_variant(lam, 0.0, {2025: (st2, pg2, info)})
    g = R.games(2025).set_index("game_id")
    early = base["game_id"].map(g["date"]) <= X
    diff = (base.loc[early, ["D_home", "D_away"]].to_numpy() - pert.loc[early, ["D_home", "D_away"]].to_numpy())
    later = (base.loc[~early, ["D_home", "D_away"]].to_numpy() != pert.loc[~early, ["D_home", "D_away"]].to_numpy()).any(axis=1).mean()
    check(np.abs(diff).max() < 1e-9, f"{int(early.sum())} games dated on or before {X.date()}: max change {np.abs(diff).max():.1e} "
                                     f"(control: {later:.0%} of later games do change)")

    say("\n3. order and hashes")
    p = R.OUT / "predictions.csv"
    check(hashlib.sha256(p.read_bytes()).hexdigest() == (R.OUT / "predictions.csv.sha256").read_text().split()[0], "prediction hash")
    tf = int(git("log", "--reverse", "--format=%ct", "--", "research/player_impact/out/frozen.json").split()[0])
    tp = int(git("log", "--reverse", "--format=%ct", "--", "research/player_impact/out/predictions.csv").split()[0])
    f26 = R.DATA / "features_2026_frozen.parquet"
    m26 = f26.stat().st_mtime if f26.exists() else tf + 1
    check(tf < m26 <= tp + 60, "frozen.json committed before 2025-26 features were computed, predictions committed after")

    say("\n4. grading recomputed (plain loop)")
    q = pd.read_csv(p, dtype={"date": str})
    gr = pd.read_csv(R.OUT / "graded.csv", dtype={"date": str})
    gs, _ = data.season_games(2026)
    res = gs.set_index("game_id").eval("home_pts - away_pts")
    n_ok = 0
    for pool, x in q.groupby("pool"):
        for prices in (("assumed",) if not pool.startswith("C") else ("recorded", "assumed")):
            G = gr[(gr["pool"] == pool) & (gr["prices"] == prices)]
            for st_ in ("baseline", "candidate", "v2"):
                tot, n = 0.0, 0
                for _, r in x.iterrows():
                    e = r[f"fc_{st_}"] + r["line"]
                    if np.isnan(e) or abs(e) < 2.5:
                        continue
                    pr = -110.0 if prices == "assumed" else (r["price_pos"] if e > 0 else r["price_neg"])
                    pay = pr / 100 if pr > 0 else 100 / -pr
                    pw = min(max(0.5 + 0.0255 * abs(e), 0.5), 0.58)
                    if pw * pay - (1 - pw) < 0.02:
                        continue
                    c = (res[r["game_id"]] + r["line"]) * (1 if e > 0 else -1)
                    n += 1
                    tot += pay if c > 0 else (-1.0 if c < 0 else 0.0)
                ok = n == int((G[f"{st_}_side"] != 0).sum()) and abs(tot - G[f"{st_}_units"].sum()) < 1e-9
                n_ok += ok
                if not ok:
                    check(False, f"{pool} {prices} {st_}: {n} bets {tot:+.2f}")
    check(not any("bets" in f for f in FAIL), f"{n_ok} pool x price x strategy results recomputed exactly")

    say("\n5. untouched")
    start = git("log", "--reverse", "--format=%h", "--", "research/player_impact/PLAN.md").split()[0]
    out = [f for f in git("diff", "--name-only", f"{start}^", "--", ".", ":!research/player_impact").split() if f]
    say(f"  files changed outside the folder since the study began (any author): {out}")
    check(git("diff", "--name-only", f"{start}^", "--", "cbb/", "bets/", ".github/", "MODEL_FREEZE.md") == "",
          "cbb/, bets/, .github/ and MODEL_FREEZE.md unchanged")
    check(git("status", "--porcelain", "--", ".", ":!research/player_impact") == "", "no uncommitted change outside the folder")
    say(f"\n{'ALL CHECKS PASSED' if not FAIL else 'FAILURES: ' + '; '.join(FAIL)}")
    (R.OUT / "verify.txt").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
