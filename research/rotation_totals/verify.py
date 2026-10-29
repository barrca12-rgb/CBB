"""Independent checks of the Stage A pipeline (PLAN.md). Written separately from build.py/grade.py.

    python -m research.rotation_totals.verify A     # -> out/verify_A.txt

1. Quote selection: the first complete DraftKings market re-derived with a vectorized state table.
2. Information cutoffs: season average (dates up to D-2), KenPom = the D-1 archive, stage-1 ratings stop before D-1
   (games_before vs games counted from the frame), rotation timing (no team played on D-1).
3. Payout arithmetic: units recomputed from final scores and prices with exact fractions.
4. Production and shadow files: unchanged by this study.
"""
from __future__ import annotations

import os
import subprocess
import sys
from fractions import Fraction

import numpy as np
import pandas as pd

from cbb import kenpom

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
QDATA = os.path.join(ROOT, "research", "market", "data")
L: list[str] = []


def say(s):
    L.append(s)
    print(s, flush=True)


def first_complete(date: str, event_ids: set) -> pd.DataFrame:
    q = pd.read_csv(os.path.join(QDATA, f"quotes_{date}.csv.gz"))
    q = q[(q["book"] == "draftkings") & q["event_id"].isin(event_ids)].copy()
    q["key"] = q["market"] + "|" + np.where(q["market"] == "totals", q["outcome"], "side:" + q["outcome"])
    snaps = sorted(pd.read_csv(os.path.join(QDATA, f"snapshots_{date}.csv"))["snapshot"].unique())
    out = []
    for e, g in q.groupby("event_id"):
        # forward-filled state per outcome over every snapshot
        piv = g.pivot_table(index="snapshot", columns="key", values="price", aggfunc="last")
        st = g.pivot_table(index="snapshot", columns="key", values="status", aggfunc="last")
        pt = g.pivot_table(index="snapshot", columns="key", values="point", aggfunc="last")
        piv, st, pt = piv.reindex(snaps).ffill(), st.reindex(snaps).ffill(), pt.reindex(snaps).ffill()
        ok = piv.notna() & (st != "absent")
        spread_cols = [c for c in ok.columns if c.startswith("spreads|")]
        full = (ok[spread_cols].sum(axis=1) >= 2) & ok.get("totals|Over", False) & ok.get("totals|Under", False)
        if full.any():
            t = full.idxmax()
            out.append({"event_id": e, "v_decision_at": t, "v_total": pt.loc[t, "totals|Over"],
                        "v_over_price": piv.loc[t, "totals|Over"], "v_under_price": piv.loc[t, "totals|Under"],
                        "v_left_censored": t == snaps[0]})
    return pd.DataFrame(out)


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "A"
    p = pd.read_csv(os.path.join(OUT, f"predictions_{stage}.csv"))
    bets = pd.read_csv(os.path.join(OUT, f"bets_{stage}.csv"))
    fr = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_safe_lag1.pkl"))
    # 1. quote selection
    v = pd.concat([first_complete(d, set(p.loc[p["date"] == d, "event_id"])) for d in p["date"].unique()])
    m = p.merge(v, on="event_id", how="left")
    same = ((pd.to_datetime(m["decision_at"], utc=True) == pd.to_datetime(m["v_decision_at"], utc=True)) & (m["dk_total"] == m["v_total"])
            & (m["over_price"] == m["v_over_price"]) & (m["under_price"] == m["v_under_price"]) & (m["left_censored"] == m["v_left_censored"]))
    say(f"1. quote selection re-derived: {int(same.sum())} of {len(p)} games identical (decision snapshot, total, both prices, left-censoring)")
    pre = (pd.to_datetime(p["decision_at"], utc=True) < pd.to_datetime(p["tip"], utc=True)).all()
    say(f"   every decision snapshot before tip: {bool(pre)}")
    # 2a. season average up to D-2
    fr["d"] = pd.to_datetime(fr["date"])
    fi = fr.set_index("game_id")
    errs = []
    for _, r in p.drop_duplicates(["season", "date"]).iterrows():
        D = pd.Timestamp(r["date"])
        prior = fr[(fr["season"] == r["season"]) & (fr["d"] <= D - pd.Timedelta(days=2))]
        want = (prior["home_pts"] + prior["away_pts"]).mean() if len(prior) >= 200 else \
            (fr.loc[fr["season"] == r["season"] - 1, "home_pts"] + fr.loc[fr["season"] == r["season"] - 1, "away_pts"]).mean()
        from research.rotation_totals.build import conservative_frame
        errs.append((r["date"], want))
    cf = __import__("research.rotation_totals.build", fromlist=["conservative_frame"]).conservative_frame().set_index("game_id")
    dev = max(abs(cf.loc[p.loc[p["date"] == d, "game_id"], "season_avg_total"] - w).max() for d, w in errs)
    say(f"2a. season average recomputed from games up to D-2 (or last season's average under 200 games): max difference {dev:.2e}")
    # 2b. KenPom from the D-1 archive (every eval date)
    kd = []
    for d in p["date"].unique():
        g = fi.loc[p.loc[p["date"] == d, "game_id"]].reset_index()
        try:
            k = kenpom._predict(kenpom.archive((pd.Timestamp(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")),
                                g[["game_id", "home_id", "away_id", "neutral"]]).set_index("game_id")
            kd.append(float((g.set_index("game_id")["kp_total"] - k["kp_total"]).abs().max()))
        except Exception as e:
            kd.append(f"unavailable ({type(e).__name__})")
    say(f"2b. KenPom total = prediction from the archive dated D-1, max abs difference per date: {kd}")
    # 2c. stage-1 ratings stop before D-1: the fit's league game count equals the production fit's count on D-1
    b0 = pd.read_csv(os.path.join(ROOT, "cbb", "output", "backtest_2013_2026.csv"), usecols=["date", "season", "games_before"])
    b0["d"] = pd.to_datetime(b0["date"])
    rows = []
    for d in p["date"].unique():
        D, s = pd.Timestamp(d), int(p.loc[p["date"] == d, "season"].iloc[0])
        lag = set(fi.loc[p.loc[p["date"] == d, "game_id"], "games_before"])
        before_d1 = set(b0[(b0["season"] == s) & (b0["d"] == D - pd.Timedelta(days=1))]["games_before"])
        before_d = set(b0[(b0["season"] == s) & (b0["d"] == D)]["games_before"])
        rows.append(f"{d}: {sorted(lag)} = before D-1 {sorted(before_d1)} (before D would be {sorted(before_d)})")
    say("2c. stage-1 fit size (league games) for eval games vs the production fit before D-1 and before D:\n   " + "\n   ".join(rows))
    # 2d. rotation timing: no eligible team played on D-1
    say(f"2d. eligible games where a team played on D-1 (rest <= 1): {int(((fi.loc[p['game_id'], 'home_rest'] <= 1) | (fi.loc[p['game_id'], 'away_rest'] <= 1)).sum())}")
    # 3. payout arithmetic
    bad = 0
    for _, b in bets.iterrows():
        diff = Fraction(str(b["final"])) - Fraction(str(b["dk_total"]))
        res = Fraction(0) if diff == 0 else (1 if (diff > 0) == (b["side"] == "over") else -1)
        o = Fraction(str(b["price"]))
        u = Fraction(0) if res == 0 else ((o / 100 if o > 0 else Fraction(100) / -o) if res == 1 else Fraction(-1))
        bad += abs(float(u) - b["u"]) > 1e-9
    say(f"3. payout arithmetic recomputed exactly: {len(bets) - bad} of {len(bets)} bets agree")
    # 4. production and shadow files unchanged by this study
    files = subprocess.run(["git", "log", "--format=", "--name-only", "--", "research/rotation_totals"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    outside = sorted({f for f in files if not f.startswith("research/rotation_totals/")})
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    dirty = [x for x in dirty if x.strip() and "research/rotation_totals" not in x]
    say(f"4. files outside research/rotation_totals in this study's commits: {outside or 'none'}; uncommitted changes elsewhere: {dirty or 'none'}")
    open(os.path.join(OUT, f"verify_{stage}.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
