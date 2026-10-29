"""Grading step (PLAN.md): results joined to the hashed predictions; every pool; verdict.

    python -m research.player_impact.grade    # -> out/graded.csv, out/report.txt
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from cbb import data
from research.game_state.grade import boot, summary, transitions
from research.game_state.common import grade, select
from research.player_impact.ratings import OUT

L: list[str] = []
STRATS = ["baseline", "candidate", "v2"]


def say(s=""):
    L.append(s)
    print(s, flush=True)


def bets(p, strat, prices):
    pp = np.full(len(p), -110.0) if prices == "assumed" else p["price_pos"].to_numpy(float)
    pn = np.full(len(p), -110.0) if prices == "assumed" else p["price_neg"].to_numpy(float)
    edge = p[f"fc_{strat}"].to_numpy(float) + p["line"].to_numpy(float)
    bet, side, price = select(edge, pp, pn, "spread")
    u = np.where(bet, grade(np.where(bet, side, 1), p["cover"].to_numpy(float), price), 0.0)
    return pd.DataFrame({"bet": bet, "side": np.where(bet, side, 0), "units": u}, index=p.index)


def clustered_slope(x, y, groups):
    x, y = np.asarray(x, float), np.asarray(y, float)
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX = np.linalg.inv(X.T @ X)
    meat = np.zeros((2, 2))
    for gv in pd.unique(groups):
        m = groups == gv
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    V = XtX @ meat @ XtX
    return b[1], float(np.sqrt(V[1, 1]))


def report(pool, p, prices):
    say(f"\n{'=' * 100}\n{pool} | {'assumed -110' if prices == 'assumed' else 'recorded prices'} | opportunities {len(p)} "
        f"(coverage pool {int(p['coverage'].sum())}) | dates {p['date'].nunique()}")
    incs = {}
    for scope, q in (("full pool", p), ("coverage pool", p[p["coverage"]])):
        B = {s: bets(q, s, prices) for s in STRATS}
        say(f"-- {scope}")
        say(pd.DataFrame([summary(k, v, q["cover"]) for k, v in B.items()]).round(2).to_string(index=False))
        rows = []
        for a, b in (("candidate", "baseline"), ("candidate", "v2"), ("v2", "baseline")):
            est, lo, hi = boot((B[a]["units"] - B[b]["units"]).groupby(q["date"]).sum())
            rows.append({"difference": f"{a} - {b}", "units": est, "lo95": lo, "hi95": hi})
        inc = pd.DataFrame(rows).set_index("difference")
        say(inc.round(2).to_string())
        incs[scope] = inc
        if scope == "full pool":
            say("candidate vs baseline bets:\n" + transitions(B["baseline"], B["candidate"]).round(2).to_string())
            m = pd.DataFrame({k: v["units"] for k, v in B.items()}).groupby(q["date"].str[:7]).sum()
            say("monthly units:\n" + m.round(2).to_string())
            d = (B["candidate"]["units"] - B["baseline"]["units"]).groupby(q["date"]).sum()
            nz = d[d != 0]
            say(f"concentration: {len(nz)} dates differ" + (f"; best {d.idxmax()} {d.max():+.2f}; without it {d.sum() - d.max():+.2f}" if len(nz) else ""))
            out = q[["pool", "game_id", "date", "cover", "coverage"]].copy()
            for k, v in B.items():
                out[f"{k}_side"], out[f"{k}_units"] = v["side"], v["units"]
            out["prices"] = prices
    r = p["result"]
    say("accuracy (result - forecast): " + "; ".join(
        f"{s} MAE {(r - p[f'fc_{s}']).abs().mean():.3f} bias {(r - p[f'fc_{s}']).mean():+.3f}" for s in STRATS))
    adj = p["fc_candidate"] - p["fc_baseline"]
    if adj.abs().sum() > 0:
        b, se = clustered_slope(adj, p["cover"], p["date"].to_numpy())
        say(f"beyond-the-line coefficient of the adjustment (result vs this pool's line): {b:+.2f} (date-clustered SE {se:.2f}); "
            f"adjustment SD {adj.std():.3f}, nonzero {(adj != 0).mean():.3f}")
    return out, incs


def main() -> None:
    path = OUT / "predictions.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (OUT / "predictions.csv.sha256").read_text().split()[0]
    say("predictions.csv hash verified")
    fr = json.load(open(OUT / "frozen.json"))
    p = pd.read_csv(path, dtype={"date": str})
    g, _ = data.season_games(2026)
    g = g.set_index("game_id")
    p["result"] = p["game_id"].map(g["home_pts"] - g["away_pts"])
    p["cover"] = p["result"] + p["line"]
    say(f"results joined: missing {int(p['result'].isna().sum())}")
    a = p[p["pool"].str.startswith("B")]
    s = summary("baseline", bets(a, "baseline", "assumed"), a["cover"])
    say(f"reconciliation: live-like opener spreads baseline {s['W-L-P']} (target 462-335-0)")
    c = p[p["pool"].str.startswith("C")]
    s = summary("baseline", bets(c, "baseline", "recorded"), c["cover"])
    say(f"reconciliation: pool C baseline {s['bets']} bets {s['W-L-P']} {s['units']:+.2f} (target 43, 27-16-0, +7.89)")
    graded, incs = [], {}
    for pool, q in p.groupby("pool"):
        for prices in (("assumed",) if not pool.startswith("C") else ("recorded", "assumed")):
            o, inc = report(pool, q, prices)
            graded.append(o)
            incs[(pool[0], prices)] = inc
    pd.concat(graded).to_csv(OUT / "graded.csv", index=False)
    # descriptive totals: does the offense/defense absence term line up with results vs the closing total?
    from research.persistent_disagreement.common import baseline
    w = baseline()
    w = w[w["season"] == 2026].set_index("game_id")
    A = p[p["pool"].str.startswith("A")].set_index("game_id")
    tt = (w.loc[A.index, "home_pts"] + w.loc[A.index, "away_pts"] - w.loc[A.index, "total"]).dropna()
    if A["T_desc"].abs().sum() > 0 and len(tt):
        b, se = clustered_slope(A.loc[tt.index, "T_desc"], tt, A.loc[tt.index, "date"].to_numpy())
        say(f"\ntotals (descriptive): (points - closing total) on the absence total term: slope {b:+.2f} (SE {se:.2f}), n {len(tt)}")
    full, cov = incs[("A", "assumed")]["full pool"], incs[("A", "assumed")]["coverage pool"]
    c1 = fr["choice"] != "none"
    d = full.loc["candidate - baseline"]
    c2 = d["units"] > 0 and d["lo95"] > 0
    c3 = cov.loc["candidate - baseline", "units"] > 0
    c4 = full.loc["candidate - v2", "units"] > 0
    say(f"\nVERDICT (frozen rule): (1) choice not 'none': {c1}; (2) candidate - baseline {d['units']:+.2f} [{d['lo95']:+.2f}, "
        f"{d['hi95']:+.2f}]: {c2}; (3) coverage pool {cov.loc['candidate - baseline', 'units']:+.2f}: {c3}; (4) candidate - lineup v2 "
        f"{full.loc['candidate - v2', 'units']:+.2f}: {c4}  =>  {'ADDS NET UNITS (exploratory)' if all((c1, c2, c3, c4)) else 'NO'}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
