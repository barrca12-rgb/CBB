"""Independent checks (PLAN.md, Verification). Written separately from common.py's feature and grading code.

    python -m research.persistent_disagreement.verify    # -> out/verify.txt
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import OUT, ROOT, baseline

L: list[str] = []
FAIL: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def check(ok: bool, what: str):
    say(f"  [{'ok' if ok else 'FAIL'}] {what}")
    if not ok:
        FAIL.append(what)


def brute_history(w: pd.DataFrame, i: int, lag: int) -> dict:
    """From scratch, for row i: every eligible same-season game of either team dated before the cutoff, once each,
    spread quantities oriented to today's home team (full-season window, the frozen N)."""
    r = w.loc[i]
    cut = r["date"] - pd.Timedelta(days=lag)
    prior = w[(w["season"] == r["season"]) & (w["date"] < cut) & ~w["swapped"] & w["home_spread"].notna() & w["total"].notna()
              & w["final_margin"].notna() & w["final_total"].notna()
              & (w["home_id"].isin([r["home_id"], r["away_id"]]) | w["away_id"].isin([r["home_id"], r["away_id"]]))]
    assert prior["game_id"].is_unique
    assert prior["points"].notna().all() and (prior["date"] < r["date"]).all()   # completed, earlier games only
    # +1 if the prior game's home team is today's home team or today's away team was the prior away team
    o = np.where((prior["home_id"] == r["home_id"]) | (prior["away_id"] == r["away_id"]), 1.0, -1.0)
    d, rr = (prior["final_margin"] + prior["home_spread"]) * o, (prior["margin"] + prior["home_spread"]) * o
    td, tr = prior["final_total"] - prior["total"], prior["points"] - prior["total"]
    return {"n": len(prior), "sd_s": d.sum(), "sdr_s": (d * rr).sum(), "sdd_s": (d * d).sum(),
            "sd_t": td.sum(), "sdr_t": (td * tr).sum(), "sdd_t": (td * td).sum(),
            "latest": prior["date"].max() if len(prior) else pd.NaT, "cut": cut}


def units(edge, cover, pp, pn, thr, slope, cap):
    """Plain re-implementation of the fixed rule and 1-unit grading."""
    tot, n = 0.0, 0
    for e, c, a, b in zip(edge, cover, pp, pn):
        if np.isnan(e) or abs(e) < thr:
            continue
        price = a if e > 0 else b
        pay = price / 100 if price > 0 else 100 / -price
        p = min(max(0.5 + slope * abs(e), 0.5), cap)
        if p * pay - (1 - p) < 0.02:
            continue
        n += 1
        s = c if e > 0 else -c
        tot += pay if s > 0 else (-1.0 if s < 0 else 0.0)
    return n, tot


def main() -> None:
    path = os.path.join(OUT, "predictions.csv")
    p = pd.read_csv(path, dtype={"date": str})
    say("1. predictions hash")
    check(hashlib.sha256(open(path, "rb").read()).hexdigest() == open(path + ".sha256").read().split()[0],
          "predictions.csv matches the hash written before grading")
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    check(max(fz["total"]["train_seasons"]) <= 2025 and max(fz["spread"]["train_seasons"]) <= 2025,
          "frozen fits use seasons <= 2025 only")
    log = subprocess.run(["git", "log", "--format=%h %s", "--", "research/persistent_disagreement/out/frozen.json",
                          "research/persistent_disagreement/out/predictions.csv"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    say("  commit order (newest first): " + " | ".join(x for x in log if x))

    w = baseline()
    say("\n2. feature timing (brute force on a random sample, both lags)")
    h = {lag: pd.read_pickle(os.path.join(OUT, f"history_lag{lag}.pkl"))["all"] for lag in (0, 1)}
    rng = np.random.default_rng(7)
    s26 = w.index[(w["season"] == 2026) & ~w["swapped"]].to_numpy()
    early = w.index[w["season"].isin([2016, 2017, 2024, 2025]) & ~w["swapped"]].to_numpy()
    sample = np.concatenate([rng.choice(s26, 250, replace=False), rng.choice(early, 150, replace=False)])
    worst, late = 0.0, 0
    for lag in (0, 1):
        for i in sample:
            b = brute_history(w, i, lag)
            for k in ("n", "sd_s", "sdr_s", "sdd_s", "sd_t", "sdr_t", "sdd_t"):
                worst = max(worst, abs(float(h[lag].loc[i, k]) - float(b[k])))
            late += int(pd.notna(b["latest"]) and b["latest"] >= b["cut"])
    check(worst < 1e-8, f"{len(sample)} games x 2 lags: cached history sums equal brute force (max abs diff {worst:.2e})")
    check(late == 0, "every prior game used is dated before the cutoff (D for totals, D-1 for spreads)")
    # rematch: a game whose two teams met earlier counts that game once, and the orientation agrees from both sides
    rem = 0
    for i in s26[:3000]:
        r = w.loc[i]
        pr = w[(w["season"] == 2026) & (w["date"] < r["date"]) & (((w["home_id"] == r["home_id"]) & (w["away_id"] == r["away_id"]))
                                                               | ((w["home_id"] == r["away_id"]) & (w["away_id"] == r["home_id"])))]
        if len(pr):
            rem += 1
    say(f"  ({rem} of the first 3,000 2025-26 games are rematches; covered by the brute-force union above, which de-duplicates by game)")
    # the prediction file's S/V columns come from those sums
    wi = w.reset_index().set_index("game_id")
    for pool, lag, suf, k in (("A", 0, "_t", fz["total"]["k"]), ("B", 1, "_s", fz["spread"]["k"])):
        q = p[p["pool"].str.startswith(pool)]
        hh = h[lag].loc[wi.loc[q["game_id"], "index"].to_numpy()]
        S = (hh[f"sd{suf}"] / (hh["n"] + 4)).to_numpy()
        V = (hh[f"sdr{suf}"] / (hh[f"sdd{suf}"] + k)).to_numpy()
        check(np.allclose(S, q["S"]) and np.allclose(V, q["V"]), f"pool {pool}: S and V in predictions.csv recomputed from the sums")

    say("\n3. pool C quote timing (DraftKings rows rebuilt independently)")
    rt = pd.read_csv(os.path.join(ROOT, "research", "rotation_totals", "out", "predictions_A.csv"), parse_dates=["decision_at", "tip"])
    rt = rt[rt["season"] == 2026].set_index("game_id")
    c = p[p["pool"].str.startswith("C")].set_index("game_id")
    check(set(c.index) == set(rt.index), f"pool C games = the {len(rt)} eligible dated-sample games")
    check((rt.loc[c.index, "decision_at"] < rt.loc[c.index, "tip"]).all(), "every decision snapshot is before tip")
    bad = 0
    from research.market.s1_sample_report import lookup
    from cbb import teams
    lk = lookup()
    for date, g in c.groupby("date"):
        qd = pd.read_csv(os.path.join(ROOT, "research", "market", "data", f"quotes_{date}.csv.gz"))
        qd = qd[(qd["book"] == "draftkings") & (qd["market"] == "spreads")]
        qd["snapshot"] = pd.to_datetime(qd["snapshot"], utc=True, format="ISO8601")
        for gid, r in g.iterrows():
            ev = rt.loc[gid]
            x = qd[(qd["event_id"] == ev["event_id"]) & (qd["snapshot"] <= ev["decision_at"])]
            home = wi.loc[gid, "home_id"]
            hx = x[x["outcome"].map(lambda n: lk.get(teams.norm(n or ""))) == home].sort_values("snapshot")
            ok = len(hx) and hx["status"].iloc[-1] != "absent" and hx["point"].iloc[-1] == r["line"] and hx["price"].iloc[-1] == r["price_pos"]
            bad += int(not ok)
    check(bad == 0, f"pool C: home spread and price equal the latest DraftKings row at or before the decision snapshot ({bad} mismatches)")
    et = rt.loc[c.index, "decision_at"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    lagd = (pd.to_datetime(c["date"]) - et).dt.days
    say(f"  decision day relative to game day: {lagd.value_counts().sort_index().to_dict()} (1 = day before; strict KenPom D-2 / Torvik D-3 inputs)")

    say("\n4. baseline reconciliation (from the frame, not from predictions.csv)")
    s = w[(w["season"] == 2026) & ~w["swapped"]]
    a = s[s["total"].notna() & s["final_total"].notna()]
    e = a["final_total"] - a["total"]
    pl = a[e.abs() >= 3]
    won = np.sign(pl["points"] - pl["total"]) * np.sign(e[pl.index])
    check(len(pl) == 1478 and round(100 * (won > 0).sum() / ((won != 0).sum()), 2) == 48.71,
          f"A: {len(pl)} plays at {100 * (won > 0).sum() / (won != 0).sum():.2f}% (target 1,478 at 48.71%, quant3 variants.csv row v1)")
    b = s[s["open_home_spread"].notna() & s["home_spread"].notna() & s["final_margin"].notna()]
    e = b["final_margin"] + b["open_home_spread"]
    pl = b[e.abs() >= 2.5]
    won = np.sign(pl["margin"] + pl["open_home_spread"]) * np.sign(e[pl.index])
    rec = f"{(won > 0).sum()}-{(won < 0).sum()}-{(won == 0).sum()}"
    check(rec == "462-335-0", f"B: {rec} (target 462-335-0, stage2_stability compare.txt R0)")
    check(np.allclose(p.loc[p["pool"].str.startswith("A"), "edge_baseline"].to_numpy(), (a["final_total"] - a["total"]).to_numpy())
          and np.allclose(p.loc[p["pool"].str.startswith("B"), "edge_baseline"].to_numpy(), e.to_numpy()),
          "baseline edges in predictions.csv equal the frame's")

    say("\n5. grading recomputed (plain loop, results joined fresh)")
    g = pd.read_csv(os.path.join(OUT, "graded.csv"), dtype={"date": str})
    res = {"A": wi["points"], "B": wi["margin"], "C": wi["margin"]}
    for pool, q in p.groupby("pool"):
        r = res[pool[0]].loc[q["game_id"]].to_numpy()
        cover = r - q["line"].to_numpy() if pool[0] == "A" else r + q["line"].to_numpy()
        thr, slope, cap = (3.0, 0.014, 0.565) if pool[0] == "A" else (2.5, 0.0255, 0.58)
        for prices in (("assumed",) if pool[0] != "C" else ("recorded", "assumed")):
            pp = np.full(len(q), -110.0) if prices == "assumed" else q["price_pos"].to_numpy()
            pn = np.full(len(q), -110.0) if prices == "assumed" else q["price_neg"].to_numpy()
            gg = g[(g["pool"] == pool) & (g["prices"] == prices)]
            for strat in ("baseline", "comparator", "candidate", "existing") + (("C2",) if pool[0] == "A" else ()):
                n, u = units(q[f"edge_{strat.lower()}"].to_numpy(float), cover, pp, pn, thr, slope, cap)
                ok = n == int((gg[f"{strat}_side"] != 0).sum()) and abs(u - gg[f"{strat}_units"].sum()) < 1e-9
                check(ok, f"{pool[:2]} {prices:8s} {strat:10s} {n:5d} bets {u:+8.2f} units")

    say("\n6. production and shadows untouched")
    out = subprocess.run(["git", "diff", "--name-only", "b60047f^", "--", ".", ":!research/persistent_disagreement"],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    gi = subprocess.run(["git", "diff", "-U0", "b60047f^", "--", ".gitignore"], cwd=ROOT, capture_output=True,
                        text=True).stdout
    added = [x[1:] for x in gi.splitlines() if x.startswith("+") and not x.startswith("+++")]
    removed = [x for x in gi.splitlines() if x.startswith("-") and not x.startswith("---")]
    say(f"  files changed outside the folder since the study began (any author): {out}")
    check(set(out) <= {".gitignore"} and added == ["research/persistent_disagreement/out/*.pkl"] and not removed,
          "only change outside the folder is one .gitignore line for this study's feature caches")
    st = subprocess.run(["git", "status", "--porcelain", "--", ".", ":!research/persistent_disagreement"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
    check(st == "", "no uncommitted change outside the folder")
    fr = subprocess.run(["git", "diff", "--name-only", "b60047f^", "--", "MODEL_FREEZE.md", "cbb/", "bets/", "shadow/",
                         ".github/"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check(fr == [], "cbb/, bets/, shadow/, .github/ and MODEL_FREEZE.md unchanged since the study began")

    say(f"\n{'ALL CHECKS PASSED' if not FAIL else 'FAILURES: ' + '; '.join(FAIL)}")
    open(os.path.join(OUT, "verify.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
