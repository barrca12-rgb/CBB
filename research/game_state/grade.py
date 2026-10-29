"""Grading step (PLAN.md): joins 2025-26 results to the hashed predictions; reconciliation, every pool, verdict.

    python -m research.game_state.grade      # -> out/graded.csv, out/report.txt
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

from cbb import data
from research.game_state.common import OUT, fit_predict, forecast, frames, grade, select

L: list[str] = []
SEED, REPS = 20261029, 10_000


def say(s=""):
    L.append(s)
    print(s, flush=True)


def comparators(pool: str) -> list[str]:
    if pool.startswith("C-tot"):
        return ["E2", "C2", "rot"]
    return ["E2", "C2"] if "-tot" in pool else ["v2"]


def bets(p: pd.DataFrame, strat: str, prices: str) -> pd.DataFrame:
    market = p["market"].iloc[0]
    pp = np.full(len(p), -110.0) if prices == "assumed" else p["price_pos"].to_numpy(float)
    pn = np.full(len(p), -110.0) if prices == "assumed" else p["price_neg"].to_numpy(float)
    if strat == "rot":                                   # rotation classifier: its own frozen bets
        side = p["rot_side"].to_numpy(int)
        bet = side != 0
        price = np.where(side > 0, pp, pn)
    else:
        fc = p[f"fc_{strat}"].to_numpy(float)
        edge = fc - p["line"].to_numpy() if market == "total" else fc + p["line"].to_numpy()
        bet, side, price = select(edge, pp, pn, market)
    u = np.where(bet, grade(np.where(bet, side, 1), p["cover"].to_numpy(float), price), 0.0)
    return pd.DataFrame({"bet": bet, "side": np.where(bet, side, 0), "units": u}, index=p.index)


def summary(name, b, cover) -> dict:
    x = b[b["bet"]]
    won = np.sign(cover[x.index]) * x["side"]
    w, l, pu = int((won > 0).sum()), int((won < 0).sum()), int((won == 0).sum())
    return {"strategy": name, "bets": len(x), "W-L-P": f"{w}-{l}-{pu}", "win %": 100 * w / (w + l) if w + l else np.nan,
            "units": x["units"].sum(), "ROI %": 100 * x["units"].sum() / len(x) if len(x) else np.nan}


def boot(d: pd.Series) -> tuple[float, float, float]:
    v = d.to_numpy()
    if not len(v):
        return 0.0, 0.0, 0.0
    draws = v[np.random.default_rng(SEED).integers(0, len(v), size=(REPS, len(v)))].sum(axis=1)
    return float(v.sum()), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def transitions(a, b) -> pd.DataFrame:
    kind = np.select([a["bet"] & b["bet"] & (a["side"] == b["side"]), ~a["bet"] & b["bet"], a["bet"] & ~b["bet"],
                      a["bet"] & b["bet"] & (a["side"] != b["side"])], ["retained", "added", "dropped", "reversed"], "")
    t = pd.DataFrame({"kind": kind, "ref_units": a["units"], "new_units": b["units"]})[kind != ""]
    return t.groupby("kind").agg(n=("kind", "size"), ref_units=("ref_units", "sum"), new_units=("new_units", "sum")) \
        .reindex(["retained", "added", "dropped", "reversed"]).fillna(0)


def diagnostics(p: pd.DataFrame, strats) -> pd.DataFrame:
    """Accuracy and bias of each forecast vs the settled result, overall, by predicted size and in overtime games."""
    market = p["market"].iloc[0]
    rows = []
    size = p["fc_baseline"].abs() if market == "spread" else (p["fc_baseline"] - p["fc_baseline"].median()).abs()
    groups = {"all": np.ones(len(p), bool), "overtime games": p["ot"].to_numpy(),
              ("|pred margin| < 5" if market == "spread" else "|pred - median| < 5"): (size < 5).to_numpy(),
              ("|pred margin| 5-15" if market == "spread" else "|pred - median| 5-10"): ((size >= 5) & (size < (15 if market == "spread" else 10))).to_numpy(),
              ("|pred margin| >= 15" if market == "spread" else "|pred - median| >= 10"): (size >= (15 if market == "spread" else 10)).to_numpy()}
    for s in strats:
        if s == "rot":
            continue
        r = p["result"] - p[f"fc_{s}"]
        row = {"forecast": s}
        for g, m in groups.items():
            row[f"{g} n"] = int(m.sum())
            row[f"{g} MAE"] = float(r[m].abs().mean())
            row[f"{g} bias"] = float(r[m].mean())
        row["RMSE"] = float(np.sqrt((r ** 2).mean()))
        rows.append(row)
    rl = p["result"] - (p["line"] if market == "total" else -p["line"])
    rows.append({"forecast": "market line", **{f"{g} MAE": float(rl[m].abs().mean()) for g, m in groups.items()},
                 **{f"{g} bias": float(rl[m].mean()) for g, m in groups.items()}, "RMSE": float(np.sqrt((rl ** 2).mean()))})
    return pd.DataFrame(rows)


def report_pool(pool, p, prices, fr):
    market = p["market"].iloc[0]
    say(f"\n{'=' * 110}\n{pool} | prices: {'assumed -110' if prices == 'assumed' else 'recorded DraftKings'} | opportunities {len(p)} "
        f"(coverage pool {int(p['coverage'].sum())}) | dates {p['date'].nunique()} | {p['date'].min()} to {p['date'].max()}")
    key = "total" if market == "total" else "spread"
    say(f"F (fixed stage 2) = {fr[key]['families']['F']['variant']}; R (refit) = {fr[key]['families']['R']['variant']}; "
        f"decision family {fr[key]['decision_family']}")
    strats = ["baseline", "F", "Rctrl", "R"] + comparators(pool)
    out_inc = {}
    for scope, q in (("full pool", p), ("coverage pool", p[p["coverage"]])):
        B = {s: bets(q, s, prices) for s in strats}
        say(f"\n-- {scope} ({len(q)} opportunities)")
        say(pd.DataFrame([summary(k, v, q["cover"]) for k, v in B.items()]).round(2).to_string(index=False))
        comp_units = {c: B[c]["units"].sum() for c in comparators(pool)}
        strongest = max(comp_units, key=comp_units.get)
        say(f"strongest existing comparator on this pool: {strongest} ({comp_units[strongest]:+.2f})")
        rows = []
        for a, b in (("F", "baseline"), ("R", "Rctrl"), ("R", "baseline"), ("Rctrl", "baseline"), ("F", strongest), ("R", strongest)):
            est, lo, hi = boot((B[a]["units"] - B[b]["units"]).groupby(q["date"]).sum())
            rows.append({"difference": f"{a} - {b}", "units": est, "lo95": lo, "hi95": hi})
        inc = pd.DataFrame(rows)
        say("date-clustered paired bootstrap 95% (10,000 draws):")
        say(inc.round(2).to_string(index=False))
        out_inc[scope] = inc.set_index("difference")
        if scope == "full pool":
            for new, ref in (("F", "baseline"), ("R", "Rctrl")):
                say(f"\n{new} bets relative to {ref} (n, units under {ref}, units under {new}):")
                say(transitions(B[ref], B[new]).round(2).to_string())
            m = pd.DataFrame({k: v["units"] for k, v in B.items()}).groupby(q["date"].str[:7]).sum()
            m.insert(0, "F bets", B["F"]["bet"].groupby(q["date"].str[:7]).sum())
            m.insert(1, "baseline bets", B["baseline"]["bet"].groupby(q["date"].str[:7]).sum())
            say("\nmonthly units:")
            say(m.round(2).to_string())
            for new, ref in (("F", "baseline"), ("R", "Rctrl")):
                d = (B[new]["units"] - B[ref]["units"]).groupby(q["date"]).sum()
                nz = d[d != 0]
                top = nz.abs().sort_values(ascending=False).head(5).index
                say(f"concentration, {new} - {ref}: {len(nz)} dates differ; top: " + ", ".join(f"{x} {d[x]:+.2f}" for x in top)
                    + (f"; without its best date {d.sum() - d.max():+.2f}" if len(nz) else ""))
            graded = q[["pool", "game_id", "date", "cover", "coverage"]].copy()
            for k, v in B.items():
                graded[f"{k}_side"], graded[f"{k}_units"] = v["side"], v["units"]
            graded["prices"] = prices
    say("\naccuracy and bias vs the settled result (supporting diagnostics; result - forecast):")
    say(diagnostics(p, strats).round(3).T.to_string())
    return graded, out_inc


def main() -> None:
    path = os.path.join(OUT, "predictions.csv")
    want, got = open(path + ".sha256").read().split()[0], hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert want == got, "predictions.csv changed after hashing"
    say(f"predictions.csv sha256 verified {got}")
    fr = json.load(open(os.path.join(OUT, "frozen.json")))
    p = pd.read_csv(path, dtype={"date": str})
    g, _ = data.season_games(2026)
    g = g.set_index("game_id")
    margin, points = g["home_pts"] - g["away_pts"], g["home_pts"] + g["away_pts"]
    p["result"] = np.where(p["market"] == "total", p["game_id"].map(points), p["game_id"].map(margin))
    p["cover"] = np.where(p["market"] == "total", p["result"] - p["line"], p["result"] + p["line"])
    p["ot"] = p["game_id"].map(g["periods"] > 2).fillna(False).astype(bool)
    say(f"results joined: missing {int(p['result'].isna().sum())}")

    say("\nRECONCILIATION")
    a = p[p["pool"].str.startswith("A-tot")]
    s = summary("baseline", bets(a, "baseline", "assumed"), a["cover"])
    say(f"  A-tot baseline: {s['bets']} plays at {s['win %']:.2f}% (target 1,478 at 48.71%)")
    train, pred = frames()
    w = forecast(train, pred)
    w = w[(w["season"] == 2026) & ~w["swapped"]]
    nw = fit_predict(train, pred)
    nw = nw[(nw["season"] == 2026) & ~nw["swapped"]].assign(margin=lambda d: d["home_pts"] - d["away_pts"], points=lambda d: d["home_pts"] + d["away_pts"])

    def rec(d, fc, line, kind, thr):
        d = d.dropna(subset=[line])
        e = (d[fc] - d[line]) if kind == "total" else (d[fc] + d[line])
        c = ((d["points"] - d[line]) if kind == "total" else (d["margin"] + d[line]))[e.abs() >= thr] * np.sign(e[e.abs() >= thr])
        return f"{int((c > 0).sum())}-{int((c < 0).sum())}-{int((c == 0).sum())} ({100 * (c > 0).sum() / (c != 0).sum():.3f}%, n {int((c != 0).sum())})"
    say(f"  live-like opener spreads: {rec(w, 'final_margin', 'open_home_spread', 'spread', 2.5)} (target 462-335-0)")
    say(f"  live-like opener totals (opening-week rule): {rec(w, 'final_total', 'open_total', 'total', 3)} (target 1,407 at 55.51%)")
    say(f"  without the opening-week rule: close totals {rec(nw, 'final_total', 'total', 'total', 3)} (target 1,485 at 48.485%); "
        f"close spreads {rec(nw, 'final_margin', 'home_spread', 'spread', 2.5)} (target 861 at 50.987%); "
        f"opener totals {rec(nw, 'final_total', 'open_total', 'total', 3)} (target 1,417)")
    for pool, tgt in (("C-spr", "43 bets 27-16-0, +7.89"), ("C-tot", "64 bets 38-26-0, +8.56")):
        c = p[p["pool"].str.startswith(pool)]
        s = summary("baseline", bets(c, "baseline", "recorded"), c["cover"])
        say(f"  {pool} baseline at recorded prices: {s['bets']} bets {s['W-L-P']}, {s['units']:+.2f} (target {tgt})")
    c = p[p["pool"].str.startswith("C-tot")]
    s = summary("rot", bets(c, "rot", "recorded"), c["cover"])
    say(f"  C-tot rotation classifier: {s['bets']} bets {s['W-L-P']}, {s['units']:+.2f} (target 55 bets, +8.45)")

    graded, incs = [], {}
    for pool, q in p.groupby("pool", sort=True):
        for prices in (("assumed",) if not pool.startswith("C") else ("recorded", "assumed")):
            gr, inc = report_pool(pool, q, prices, fr)
            graded.append(gr)
            incs[(pool[:5], prices)] = inc
    pd.concat(graded).to_csv(os.path.join(OUT, "graded.csv"), index=False)

    say(f"\n{'=' * 110}\nVERDICT (frozen rule, PLAN.md): primary closing pools, decision family per market")
    for market, pk in (("total", "A-tot"), ("spread", "A-spr")):
        fam = fr[market]["decision_family"]
        var = fr[market]["families"][fam]["variant"]
        new, ctrl = ("F", "baseline") if fam == "F" else ("R", "Rctrl")
        full, cov = incs[(pk, "assumed")]["full pool"], incs[(pk, "assumed")]["coverage pool"]
        strongest = [i for i in full.index if i.startswith(f"{new} - ") and i not in (f"{new} - baseline", f"{new} - Rctrl")][0]
        c1 = var != "none"
        d = full.loc[f"{new} - {ctrl}"]
        c2 = d["units"] > 0 and d["lo95"] > 0
        c3 = cov.loc[f"{new} - {ctrl}", "units"] > 0
        c4 = full.loc[f"{new} - baseline", "units"] > 0
        c5 = full.loc[strongest, "units"] > 0
        say(f"{market}s: family {fam}, variant {var} -> (1) not 'none': {c1}; (2) {new} - {ctrl} {d['units']:+.2f} "
            f"[{d['lo95']:+.2f}, {d['hi95']:+.2f}]: {c2}; (3) coverage pool {cov.loc[f'{new} - {ctrl}', 'units']:+.2f}: {c3}; "
            f"(4) - baseline {full.loc[f'{new} - baseline', 'units']:+.2f}: {c4}; (5) {strongest} {full.loc[strongest, 'units']:+.2f}: {c5}"
            f"  =>  {'ADDS NET UNITS (exploratory)' if all((c1, c2, c3, c4, c5)) else 'NO'}")
    open(os.path.join(OUT, "report.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
