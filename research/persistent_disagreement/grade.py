"""Grading step (PLAN.md): joins 2025-26 results to the hashed predictions and reports every pool.

    python -m research.persistent_disagreement.grade    # -> out/graded.csv, out/report.txt
"""
from __future__ import annotations

import hashlib
import os

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import OUT, baseline, grade, select

L: list[str] = []
SEED, REPS = 20261029, 10_000


def say(s=""):
    L.append(s)
    print(s, flush=True)


def strategies(pool: str) -> list[tuple[str, str]]:
    s = [("baseline", "edge_baseline"), ("comparator", "edge_comparator"), ("candidate", "edge_candidate"),
         ("existing", "edge_existing")]
    return s + [("C2", "edge_c2")] if pool.startswith("A") else s


def bets(p: pd.DataFrame, col: str, market: str, prices: str) -> pd.DataFrame:
    """bet flag, side (+1 over/home, -1 under/away), price and units for one strategy."""
    e = p[col].to_numpy(float)
    ok = ~np.isnan(e)
    pp = np.full(len(p), -110.0) if prices == "assumed" else p["price_pos"].to_numpy(float)
    pn = np.full(len(p), -110.0) if prices == "assumed" else p["price_neg"].to_numpy(float)
    bet, side, price = select(np.where(ok, e, 0.0), pp, pn, market)
    bet &= ok
    u = np.where(bet, grade(side, p["cover"].to_numpy(float), price), 0.0)
    return pd.DataFrame({"bet": bet, "side": np.where(bet, side, 0), "price": price, "units": u}, index=p.index)


def summary(name: str, b: pd.DataFrame, cover: pd.Series) -> dict:
    x = b[b["bet"]]
    won = np.sign(cover[x.index]) * x["side"]
    w, l, pu = int((won > 0).sum()), int((won < 0).sum()), int((won == 0).sum())
    n = len(x)
    return {"strategy": name, "bets": n, "W-L-P": f"{w}-{l}-{pu}", "win %": 100 * w / (w + l) if w + l else np.nan,
            "units": x["units"].sum(), "ROI %": 100 * x["units"].sum() / n if n else np.nan}


def boot(diff_by_date: pd.Series) -> tuple[float, float, float]:
    """Date-clustered paired bootstrap of a total-units difference: resample dates with replacement."""
    v = diff_by_date.to_numpy()
    rng = np.random.default_rng(SEED)
    draws = v[rng.integers(0, len(v), size=(REPS, len(v)))].sum(axis=1)
    return float(v.sum()), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def transitions(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Bets of strategy b relative to reference a: retained (same side), added, dropped, reversed."""
    kind = np.select([a["bet"] & b["bet"] & (a["side"] == b["side"]), ~a["bet"] & b["bet"], a["bet"] & ~b["bet"],
                      a["bet"] & b["bet"] & (a["side"] != b["side"])], ["retained", "added", "dropped", "reversed"], "")
    t = pd.DataFrame({"kind": kind, "ref_units": a["units"], "new_units": b["units"]})[kind != ""]
    g = t.groupby("kind").agg(n=("kind", "size"), ref_units=("ref_units", "sum"), new_units=("new_units", "sum"))
    return g.reindex(["retained", "added", "dropped", "reversed"]).fillna(0)


def report_pool(pool: str, p: pd.DataFrame, prices: str) -> pd.DataFrame:
    market = "total" if pool.startswith("A") else "spread"
    say(f"\n{'=' * 100}\n{pool}  |  prices: {'assumed -110' if prices == 'assumed' else 'recorded DraftKings'}  |  "
        f"opportunities {len(p)}  |  dates {p['date'].nunique()}  |  {p['date'].min()} to {p['date'].max()}")
    say(f"strongest existing candidate: {p['existing'].iloc[0]}")
    B = {name: bets(p, col, market, prices) for name, col in strategies(pool)}
    say(pd.DataFrame([summary(k, v, p["cover"]) for k, v in B.items()]).round(2).to_string(index=False))
    say("\nincremental units of the candidate, date-clustered paired bootstrap 95% (10,000 draws):")
    rows = []
    for ref in [k for k in B if k != "candidate"]:
        d = (B["candidate"]["units"] - B[ref]["units"]).groupby(p["date"]).sum()
        est, lo, hi = boot(d)
        rows.append({"candidate minus": ref, "units": est, "lo95": lo, "hi95": hi})
    d = (B["comparator"]["units"] - B["baseline"]["units"]).groupby(p["date"]).sum()
    est, lo, hi = boot(d)
    rows.append({"candidate minus": "(comparator minus baseline)", "units": est, "lo95": lo, "hi95": hi})
    inc = pd.DataFrame(rows)
    say(inc.round(2).to_string(index=False))
    for ref in ("baseline", "comparator", "existing"):
        say(f"\ncandidate bets relative to {ref} (n, units under {ref}, units under candidate):")
        say(transitions(B[ref], B["candidate"]).round(2).to_string())
    m = pd.DataFrame({k: v["units"] for k, v in B.items()}).groupby(p["date"].str[:7]).sum()
    m.insert(0, "candidate bets", B["candidate"]["bet"].groupby(p["date"].str[:7]).sum())
    say("\nmonthly units:")
    say(m.round(2).to_string())
    cd = B["candidate"]["units"].groupby(p["date"]).sum()
    top = cd.abs().sort_values(ascending=False).head(5).index
    say("\nconcentration (candidate): top 5 dates by |units|: " + ", ".join(f"{d} {cd[d]:+.2f}" for d in top))
    say(f"candidate units without its best date: {cd.sum() - cd.max():+.2f} (best {cd.idxmax()} {cd.max():+.2f}); "
        f"without its worst date: {cd.sum() - cd.min():+.2f}")
    cdiff = (B["candidate"]["units"] - B["comparator"]["units"]).groupby(p["date"]).sum()
    say(f"candidate minus comparator without its best date: {cdiff.sum() - cdiff.max():+.2f} (best {cdiff.idxmax()} {cdiff.max():+.2f})")
    out = p[["pool", "game_id", "date", "cover"]].copy()
    for k, v in B.items():
        out[f"{k}_side"], out[f"{k}_units"] = v["side"], v["units"]
    out["prices"] = prices
    p.attrs["inc"] = inc
    return out, inc, {k: summary(k, v, p["cover"]) for k, v in B.items()}


def main() -> None:
    path = os.path.join(OUT, "predictions.csv")
    want = open(path + ".sha256").read().split()[0]
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert got == want, f"predictions.csv changed after hashing: {got} != {want}"
    say(f"predictions.csv sha256 verified {got}")
    p = pd.read_csv(path, dtype={"date": str})
    w = baseline().set_index("game_id")
    res = {"A": w["points"], "B": w["margin"], "C": w["margin"]}
    p["result"] = [res[k[0]].get(g, np.nan) for k, g in zip(p["pool"], p["game_id"])]
    # cover from the positive side: over for totals (points - total), home for spreads (margin + home spread)
    p["cover"] = np.where(p["pool"].str.startswith("A"), p["result"] - p["line"], p["result"] + p["line"])
    say(f"results joined: missing {int(p['result'].isna().sum())}")
    # reconciliation of the baselines
    a = p[p["pool"].str.startswith("A")]
    ab = bets(a, "edge_baseline", "total", "assumed")
    sa = summary("baseline", ab, a["cover"])
    say(f"reconciliation A: baseline {sa['bets']} plays at {sa['win %']:.2f}% (target 1,478 at 48.71%)")
    b = p[p["pool"].str.startswith("B")]
    sb = summary("baseline", bets(b, "edge_baseline", "spread", "assumed"), b["cover"])
    say(f"reconciliation B: baseline {sb['W-L-P']} (target 462-335-0)")
    graded, incs, sums = [], {}, {}
    for pool, g in p.groupby("pool", sort=True):
        for prices in (("assumed",) if not pool.startswith("C") else ("recorded", "assumed")):
            if pool.startswith("C") and prices == "assumed":
                say("\n(pool C sensitivity: the same games graded at an assumed -110 instead of the recorded prices)")
            o, inc, s = report_pool(pool, g, prices)
            graded.append(o)
            incs[(pool[0], prices)], sums[(pool[0], prices)] = inc, s
    pd.concat(graded).to_csv(os.path.join(OUT, "graded.csv"), index=False)
    # verdict per the frozen rule (primary pools A and B; C cannot decide)
    say(f"\n{'=' * 100}\nVERDICT (frozen rule, PLAN.md): primary pools A (totals) and B (spreads)")
    for key, label in ((("A", "assumed"), "closing totals"), (("B", "assumed"), "early spreads")):
        inc = incs[key].set_index("candidate minus")
        c1 = inc.loc["comparator", "units"] > 0 and inc.loc["comparator", "lo95"] > 0
        c2 = inc.loc["baseline", "units"] > 0
        c3 = inc.loc["existing", "units"] > 0
        say(f"{label}: candidate - comparator {inc.loc['comparator', 'units']:+.2f} [{inc.loc['comparator', 'lo95']:+.2f}, "
            f"{inc.loc['comparator', 'hi95']:+.2f}] -> {'pass' if c1 else 'fail'}; candidate - baseline "
            f"{inc.loc['baseline', 'units']:+.2f} -> {'pass' if c2 else 'fail'}; candidate - existing "
            f"{inc.loc['existing', 'units']:+.2f} -> {'pass' if c3 else 'fail'}  =>  "
            f"{'ADDS VALUE' if c1 and c2 and c3 else 'NO'}")
    open(os.path.join(OUT, "report.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
