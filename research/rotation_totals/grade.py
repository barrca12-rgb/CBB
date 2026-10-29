"""Grade the hashed predictions (PLAN.md "Scoring" and "Reporting"). Reads out/predictions_<stage>.csv only after
checking its sha256, joins final scores, and writes per-bet results and the report.

    python -m research.rotation_totals.grade A     # -> out/bets_A.csv, out/report_A.txt
"""
from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
SEASON = {2025: "2024-25", 2026: "2025-26"}


def units(won: float, odds: float) -> float:
    """1 unit risked: win pays at the American price, loss -1, push 0."""
    if won == 0.5:
        return 0.0
    return (odds / 100 if odds > 0 else 100 / -odds) if won == 1 else -1.0


def boot(d: pd.DataFrame, col: str, cluster: str, n=10000, seed=20261029) -> tuple[float, float]:
    """95% interval of the sum of `col`, resampling clusters (within each season, so season sizes are kept)."""
    rng = np.random.default_rng(seed)
    tot = np.zeros(n)
    for _, g in d.groupby("season"):
        s = g.groupby(cluster)[col].sum().to_numpy()
        tot += s[rng.integers(0, len(s), (n, len(s)))].sum(1)
    return tuple(np.quantile(tot, [.025, .975]))


def record(b: pd.DataFrame, side: str, odds: str, res: str) -> dict:
    x = b[b[res].notna()]
    w, l, p = int((x[res] == 1).sum()), int((x[res] == 0).sum()), int((x[res] == 0.5).sum())
    u = float(x["u"].sum())
    return {"bets": len(x), "W-L-P": f"{w}-{l}-{p}", "win% (no pushes)": round(100 * w / (w + l), 2) if w + l else np.nan,
            "units": round(u, 2), "ROI%": round(100 * u / len(x), 2) if len(x) else np.nan}


def drawdown(u: pd.Series) -> float:
    c = u.cumsum()
    return float((np.maximum.accumulate(np.maximum(c, 0)) - c).max()) if len(c) else 0.0


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "A"
    path = os.path.join(OUT, f"predictions_{stage}.csv")
    want = open(path + ".sha256").read().split()[0]
    have = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert want == have, "predictions file changed after it was hashed"
    p = pd.read_csv(path, parse_dates=["decision_at"])
    fr = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_safe_lag1.pkl")).set_index("game_id")
    p["final"] = p["game_id"].map(fr["home_pts"] + fr["away_pts"])
    assert p["final"].notna().all()
    rows = []
    for who in ("base", "cand"):
        x = p[p[f"{who}_bet"]].copy()
        over = x[f"{who}_side"] == "over"
        diff = x["final"] - x["dk_total"]
        x["won"] = np.where(diff == 0, 0.5, np.where(over == (diff > 0), 1.0, 0.0))
        x["u"] = [units(w, o) for w, o in zip(x["won"], x[f"{who}_price"])]
        x["model"] = who
        x["side"], x["price"] = x[f"{who}_side"], x[f"{who}_price"]
        rows.append(x[["game_id", "date", "season", "decision_at", "left_censored", "model", "side", "price", "dk_total", "final", "won", "u"]])
    bets = pd.concat(rows, ignore_index=True)
    bets.to_csv(os.path.join(OUT, f"bets_{stage}.csv"), index=False)
    L = [f"predictions_{stage}.csv sha256 verified: {have}", ""]
    # ---- per game paired units (0 when a model passes)
    g = p[["game_id", "date", "season", "left_censored"]].copy()
    for who in ("base", "cand"):
        b = bets[bets["model"] == who].set_index("game_id")
        g[f"u_{who}"] = g["game_id"].map(b["u"]).fillna(0.0)
        g[f"side_{who}"] = g["game_id"].map(b["side"])
    g["d"] = g["u_cand"] - g["u_base"]
    periods = [(SEASON[s], [s]) for s in (2025, 2026)] + [("pooled", [2025, 2026])]
    L.append("Results at first-observed DraftKings quotes (1 unit risked per bet, recorded prices, pushes 0)")
    for name, ss in periods:
        for subset, m in (("all eligible", g["season"].isin(ss)), ("excluding left-censored", g["season"].isin(ss) & ~g["left_censored"])):
            gg = g[m]
            L.append(f"\n{name}, {subset}: {len(gg)} games on {gg['date'].nunique()} dates")
            for who, lab in (("base", "baseline (current model, historical)"), ("cand", "candidate (rotation classifier)")):
                bb = bets[(bets["model"] == who) & bets["game_id"].isin(gg["game_id"])].sort_values("decision_at")
                r = record(bb, "side", "price", "won")
                L.append(f"  {lab:38s} bets {r['bets']:3d}  W-L-P {r['W-L-P']:9s} win% {r['win% (no pushes)']:6}  units {r['units']:+7.2f}  "
                         f"ROI {r['ROI%']:+6.2f}%  max drawdown {drawdown(bb['u']):.2f}")
            inc = gg["d"].sum()
            lo, hi = boot(gg, "d", "date")
            lo2, hi2 = boot(gg.assign(one=np.arange(len(gg))), "d", "one")
            L.append(f"  incremental (candidate - baseline) {inc:+.2f} units; date-clustered 95% [{lo:+.2f}, {hi:+.2f}] "
                     f"({gg['date'].nunique()} dates); game-level 95% (ignores date dependence) [{lo2:+.2f}, {hi2:+.2f}]")
    # ---- selection changes
    L.append("\nSelection changes vs baseline (units: candidate's for shared/added/flipped, baseline's for dropped)")
    for name, ss in periods:
        gg = g[g["season"].isin(ss)]
        sb, sc = gg["side_base"], gg["side_cand"]
        grp = {"shared (same side)": sb.notna() & sc.notna() & (sb == sc), "flipped (opposite side)": sb.notna() & sc.notna() & (sb != sc),
               "added (candidate only)": sb.isna() & sc.notna(), "dropped (baseline only)": sb.notna() & sc.isna()}
        parts = []
        for k, mk in grp.items():
            x = gg[mk]
            parts.append(f"{k}: n {len(x)}, candidate {x['u_cand'].sum():+.2f}u, baseline {x['u_base'].sum():+.2f}u, net {x['d'].sum():+.2f}u")
        L.append(f"  {name}: " + "; ".join(parts))
    # ---- concentration by date
    L.append("\nBy date (units): baseline / candidate / incremental; games; left-censored")
    byd = g.groupby(["season", "date"]).agg(base=("u_base", "sum"), cand=("u_cand", "sum"), inc=("d", "sum"), games=("d", "size"),
                                             lc=("left_censored", "sum")).reset_index()
    for _, r in byd.iterrows():
        L.append(f"  {r['date']} ({SEASON[r['season']]}): {r['base']:+.2f} / {r['cand']:+.2f} / {r['inc']:+.2f}; {r['games']} games; {r['lc']} left-censored")
    best = byd.loc[byd["inc"].idxmax()]
    L.append(f"  pooled incremental without the best date ({best['date']}, {best['inc']:+.2f}): {byd['inc'].sum() - best['inc']:+.2f}")
    for s in (2025, 2026):
        b2 = byd[byd["season"] == s]
        bb = b2.loc[b2["inc"].idxmax()]
        L.append(f"  {SEASON[s]} incremental without its best date ({bb['date']}): {b2['inc'].sum() - bb['inc']:+.2f}")
    # ---- decision rule
    inc_s = {s: g[g["season"] == s]["d"].sum() for s in (2025, 2026)}
    lo, hi = boot(g, "d", "date")
    cand_units = bets[bets["model"] == "cand"]["u"].sum()
    pooled_inc = g["d"].sum()
    if pooled_inc <= 0 or cand_units <= 0:
        verdict = "FAILED"
    elif all(v > 0 for v in inc_s.values()) and lo > 0:
        verdict = "SUPPORTED for prospective evaluation"
    else:
        verdict = "INCONCLUSIVE"
    L.append(f"\nDecision rule: incremental 2024-25 {inc_s[2025]:+.2f}, 2025-26 {inc_s[2026]:+.2f}; pooled candidate units {cand_units:+.2f}; "
             f"pooled incremental {pooled_inc:+.2f} [date-clustered 95% {lo:+.2f}, {hi:+.2f}] -> {verdict} (Stage {stage})")
    open(os.path.join(OUT, f"report_{stage}.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
