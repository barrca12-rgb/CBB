"""Independent checks (PLAN.md, Verification), written separately from the build, scoring and grading code.

    python -m research.game_state.verify     # -> out/verify.txt
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

import numpy as np
import pandas as pd

from cbb import backtest, data, ratings
from research.game_state.common import OUT, ROOT
from research.game_state.stage1 import VARIANTS, deltas as stage1_deltas

L: list[str] = []
FAIL: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def check(ok, what):
    say(f"  [{'ok' if ok else 'FAIL'}] {what}")
    if not ok:
        FAIL.append(what)


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    say("1. hashes and order")
    path = os.path.join(OUT, "predictions.csv")
    check(hashlib.sha256(open(path, "rb").read()).hexdigest() == open(path + ".sha256").read().split()[0],
          "predictions.csv matches the hash written before grading")
    t_plan = int(git("log", "--reverse", "--format=%ct", "--", "research/game_state/PLAN.md").split()[0])
    t_frozen = int(git("log", "--reverse", "--format=%ct", "--", "research/game_state/out/frozen.json").split()[0])
    t_pred = int(git("log", "--reverse", "--format=%ct", "--", "research/game_state/out/predictions.csv").split()[0])
    m26 = min(os.path.getmtime(os.path.join(OUT, f"s1_lag{l}_2026.parquet")) for l in (0, 1))
    check(t_plan <= t_frozen < m26 < t_pred + 1,
          "PLAN committed, then frozen.json committed, then 2025-26 adjusted stage 1 computed, then predictions committed")
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    v = pd.read_csv(os.path.join(OUT, "validation.csv"))
    check(len(v) == 2 * len(VARIANTS), f"validation.csv records all {len(VARIANTS)} variants in both families")

    say("\n2. possession accounting (independent recomputation from the stored possessions and raw play-by-play)")
    rng = np.random.default_rng(11)
    bad_state, bad_tau, bad_pts, bad_box, n_games = 0, 0, 0, [], 0
    for s in (2015, 2019, 2023, 2026):
        P = pd.read_parquet(os.path.join(OUT, f"poss_{s}.parquet"))
        G = pd.read_parquet(os.path.join(OUT, f"games_{s}.parquet"))
        ids = rng.choice(G.loc[G["valid"], "game_id"].to_numpy(), 60, replace=False)
        raw = pd.read_parquet(os.path.join(ROOT, "cbb", "cache", "pbp", f"play_by_play_{s}.parquet"),
                              columns=["game_id", "type_text", "text", "team_id", "home_team_id", "shooting_play", "home_score", "away_score"])
        raw = raw[raw["game_id"].isin(ids)]
        for gid in ids:
            n_games += 1
            p = P[P["game_id"] == gid].reset_index(drop=True)
            g = G[G["game_id"] == gid].iloc[0]
            home = g["home_id"]
            # state before each possession = signed sum of all earlier possessions' points (+ stray points)
            sgn = np.where(p["offense"] == home, 1.0, -1.0)
            hpts = np.where(sgn > 0, p["pts"], p["stray_pts"])
            apts = np.where(sgn > 0, p["stray_pts"], p["pts"])
            cum_h = np.r_[0.0, np.cumsum(hpts)[:-1]]
            cum_a = np.r_[0.0, np.cumsum(apts)[:-1]]
            bad_state += int((np.abs(sgn * (cum_h - cum_a) - p["margin"]) > 1e-9).sum())
            bad_pts += int(hpts.sum() != g["home_pts"] or apts.sum() != g["away_pts"])
            # clock: tau = 1200 + clock in period 1, clock otherwise; each period starts at 20:00 / 5:00; non-increasing
            for per, q in p.groupby("period"):
                full = 1200.0 if per <= 2 else 300.0
                tau = q["start"] + (1200 if per == 1 else 0)
                bad_tau += int(q["start"].iloc[0] != full) + int((np.diff(q["start"].to_numpy()) > 0).sum()) + int((tau != q["tau"]).sum())
            # box-score possessions from the raw events (FGA - ORB + TOV + 0.475 FTA), per team, vs reconstructed counts
            r = raw[raw["game_id"] == gid]
            tt, tx = r["type_text"].astype(str), r["text"].astype(str)
            ft = tt.eq("MadeFreeThrow") | tx.str.contains("Free Throw", regex=False)
            for team in (home, g["away_id"]):
                m = r["team_id"] == team
                fga = (m & r["shooting_play"].fillna(False).astype(bool) & ~ft).sum()
                est = fga - (m & tt.eq("Offensive Rebound")).sum() + (m & tt.str.contains("Turnover")).sum() + 0.475 * (m & ft).sum()
                bad_box.append((p["offense"] == team).sum() / est)
    check(bad_state == 0, f"{n_games} games: margin before every possession equals the signed sum of earlier possessions' points (no later information)")
    check(bad_tau == 0, "periods start at 20:00 (5:00 in overtime), possession start clocks never increase, tau defined from the start clock")
    check(bad_pts == 0, "possession points (plus technical-free-throw strays) sum to each team's final")
    bb = np.array(bad_box)
    check(abs(bb.mean() - 1) < 0.02, f"possessions vs per-team event-count estimate: mean ratio {bb.mean():.4f}, SD {bb.std():.4f}")

    say("\n3. feature timing and stage-1 arithmetic (production cbb/ratings.fit, which filters date < asof)")
    worst = 0.0
    for season, lag, days in ((2019, 0, 3), (2026, 0, 3), (2026, 1, 3)):
        g, t = data.season_games(season)
        dl = stage1_deltas(season)
        S = pd.read_parquet(os.path.join(OUT, f"s1_lag{lag}_{season}.parquet")).set_index("game_id")
        ids = sorted(set(t["team_id"]))
        pr = backtest.preseason_prior(season)
        league = ratings.league_averages(data.season_games(season - 1)[1])
        cand_days = sorted(g["date"].unique())
        for day in [cand_days[i] for i in np.random.default_rng(season + lag).choice(len(cand_days), days, replace=False)]:
            gd = g[g["date"] == day]
            asof = pd.Timestamp(day) - pd.Timedelta(days=lag)
            cfg = ratings.RatingConfig(fit_factors=False)
            r0 = ratings.fit(t, asof, ids, pr, cfg, league)
            for name in ("foul", "k2.0_a0.25", "k8.0_a0.25"):
                tv = t.merge(dl[["game_id", "team_id", f"ppp_{name}", f"pace_{name}"]], on=["game_id", "team_id"], how="left")
                tv["ppp"] = tv["ppp"] + tv[f"ppp_{name}"].fillna(0)
                tv["pace"] = tv["pace"] + tv[f"pace_{name}"].fillna(0)
                # a future game with absurd targets must not move today's forecast
                fut = tv["date"] >= asof
                tv.loc[fut, "ppp"], tv.loc[fut, "pace"] = 500.0, 500.0
                r = ratings.fit(tv, asof, ids, pr, cfg, league)
                r = {**r, "b0": r0["b0"], "p0": r0["p0"]}
                pp = ratings.predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
                worst = max(worst, float(np.abs(pp["margin"].to_numpy() - S.loc[gd["game_id"], f"m_{name}"].to_numpy()).max()),
                            float(np.abs(pp["total"].to_numpy() - S.loc[gd["game_id"], f"t_{name}"].to_numpy()).max()))
    check(worst < 1e-8, f"9 sampled days x 3 variants: stored forecasts equal production ratings.fit on adjusted targets with every "
                        f"game on or after the cutoff set to absurd values (max diff {worst:.1e})")
    b = backtest.season(2026).set_index("game_id")
    S = pd.read_parquet(os.path.join(OUT, "s1_lag0_2026.parquet")).set_index("game_id")
    d = max(float((S["m_none"] - b["pred_margin"].loc[S.index]).abs().max()), float((S["t_none"] - b["pred_total"].loc[S.index]).abs().max()))
    check(d < 1e-8, f"alpha = 0 reproduces production stage 1 for 2025-26 (max diff {d:.1e})")
    lag1 = pd.read_csv(os.path.join(ROOT, "audit", "out", "backtest_lag1_2013_2026.csv")).set_index("game_id")
    S1 = pd.read_parquet(os.path.join(OUT, "s1_lag1_2026.parquet")).set_index("game_id")
    d = float((S1["m_none"] - lag1["pred_margin"].loc[S1.index]).abs().max())
    check(d < 1e-8, f"lag-1 alpha = 0 reproduces the audit's lag-1 stage-1 file (max diff {d:.1e})")
    p = pd.read_csv(path, dtype={"date": str})
    for pool, m in (("A-spr", "fc_F"), ("B-spr", "fc_F"), ("C-spr", "fc_F")):
        q = p[p["pool"].str.startswith(pool)]
        check(np.allclose(q[m], q["fc_baseline"]), f"{pool}: frozen F variant 'none' gives the baseline forecast exactly")

    say("\n4. reconciliation (independent baseline code: research/persistent_disagreement)")
    from research.persistent_disagreement.common import baseline
    w = baseline()
    s = w[(w["season"] == 2026) & ~w["swapped"] & w["total"].notna()].set_index("game_id")
    q = p[p["pool"].str.startswith("A-tot")].set_index("game_id")
    check(np.allclose(q["fc_baseline"], s.loc[q.index, "final_total"]), "A-tot baseline forecasts equal persistent_disagreement.baseline()")
    e = s["final_total"] - s["total"]
    pl = s[e.abs() >= 3]
    won = np.sign(pl["points"] - pl["total"]) * np.sign(e[pl.index])
    check(len(pl) == 1478 and round(100 * (won > 0).sum() / (won != 0).sum(), 2) == 48.71, f"A-tot: {len(pl)} plays at {100 * (won > 0).sum() / (won != 0).sum():.2f}%")

    say("\n5. grading recomputed (plain loop)")
    gr = pd.read_csv(os.path.join(OUT, "graded.csv"), dtype={"date": str})
    checked = 0
    g, _ = data.season_games(2026)
    g = g.set_index("game_id")
    for pool, q in p.groupby("pool"):
        res = (g["home_pts"] + g["away_pts"]) if "-tot" in pool else (g["home_pts"] - g["away_pts"])
        thr, slope, cap = (3.0, 0.014, 0.565) if "-tot" in pool else (2.5, 0.0255, 0.58)
        for prices in (("assumed",) if not pool.startswith("C") else ("recorded", "assumed")):
            G_ = gr[(gr["pool"] == pool) & (gr["prices"] == prices)]
            strats = [c[3:] for c in q.columns if c.startswith("fc_") and q[c].notna().any()] + (["rot"] if pool.startswith("C-tot") else [])
            for st in strats:
                tot, n = 0.0, 0
                for _, r in q.iterrows():
                    y = res[r["game_id"]]
                    cov = (y - r["line"]) if "-tot" in pool else (y + r["line"])
                    pp = -110.0 if prices == "assumed" else r["price_pos"]
                    pn = -110.0 if prices == "assumed" else r["price_neg"]
                    if st == "rot":
                        if r["rot_side"] == 0:
                            continue
                        sd = r["rot_side"]
                    else:
                        e = (r[f"fc_{st}"] - r["line"]) if "-tot" in pool else (r[f"fc_{st}"] + r["line"])
                        if np.isnan(e) or abs(e) < thr:
                            continue
                        sd = 1 if e > 0 else -1
                        price = pp if sd > 0 else pn
                        pay = price / 100 if price > 0 else 100 / -price
                        pr_ = min(max(0.5 + slope * abs(e), 0.5), cap)
                        if pr_ * pay - (1 - pr_) < 0.02:
                            continue
                    price = pp if sd > 0 else pn
                    pay = price / 100 if price > 0 else 100 / -price
                    n += 1
                    tot += pay if cov * sd > 0 else (-1.0 if cov * sd < 0 else 0.0)
                ok = n == int((G_[f"{st}_side"] != 0).sum()) and abs(tot - G_[f"{st}_units"].sum()) < 1e-9
                checked += 1
                if not ok:
                    check(False, f"{pool} {prices} {st}: {n} bets {tot:+.2f} vs graded")
    check(not any("graded" in f for f in FAIL), f"{checked} pool x price basis x strategy results recomputed and matched exactly")

    say("\n6. production and shadows untouched")
    start = git("log", "--reverse", "--format=%h", "--", "research/game_state/PLAN.md").split()[0]
    out = git("diff", "--name-only", f"{start}^", "--", ".", ":!research/game_state").split()
    gi = git("diff", "-U0", f"{start}^", "--", ".gitignore")
    added = [x[1:] for x in gi.splitlines() if x.startswith("+") and not x.startswith("+++")]
    say(f"  files changed outside the folder since the study began: {out}")
    check(set(out) <= {".gitignore"} and added == ["research/game_state/out/*.parquet"],
          "only change outside the folder is one .gitignore line for this study's large parquet caches")
    check(git("status", "--porcelain", "--", ".", ":!research/game_state") == "", "no uncommitted change outside the folder")
    check(git("diff", "--name-only", f"{start}^", "--", "cbb/", "bets/", ".github/", "MODEL_FREEZE.md") == "",
          "cbb/, bets/, .github/ and MODEL_FREEZE.md unchanged")

    say(f"\n{'ALL CHECKS PASSED' if not FAIL else 'FAILURES: ' + '; '.join(FAIL)}")
    open(os.path.join(OUT, "verify.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
