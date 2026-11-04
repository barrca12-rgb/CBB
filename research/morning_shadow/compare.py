"""Morning shadow vs the live strategy (research/morning_shadow/PLAN.md, sections 3-4). Research only.

    python -m research.morning_shadow.compare [--through YYYY-MM-DD]   # -> research/morning_shadow/out/compare.txt
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from cbb import clv_primary, tracker

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(HERE, "out")
START, END, B, SEED, MIN_DISAGREE = "2026-11-04", "2027-03-14", 2000, 7, 200


def finals(dates) -> dict:
    """game_id -> (home_id, home_score, away_score) for final games: ESPN's scoreboard (run_day.slate, as the bet log's
    grader uses), else the day's saved card."""
    from cbb import run_day
    out = {}
    for d in sorted(set(dates)):
        try:
            c = run_day.slate(pd.Timestamp(d))
        except Exception:
            p = os.path.join(ROOT, "reports", f"cbb_{d}.csv")
            if not os.path.exists(p):
                continue
            c = pd.read_csv(p, usecols=lambda k: k in ("game_id", "home_id", "state", "home_score", "away_score"))
        for r in c.itertuples():
            if getattr(r, "state", None) == "post" and pd.notna(r.home_score) and pd.notna(r.away_score):
                out[int(r.game_id)] = (int(r.home_id), float(r.home_score), float(r.away_score))
    return out


def grade(p: pd.DataFrame, fin: dict) -> pd.DataFrame:
    """result / flat profit (1 unit risked) / staked profit for plays with bet-log columns."""
    p = p.copy()
    res, flat, staked = [], [], []
    for r in p.itertuples():
        f = fin.get(int(r.game_id))
        if f is None:
            res.append(None); flat.append(np.nan); staked.append(np.nan)
            continue
        hid, hs, as_ = f
        if hid == int(r.away_id):             # the card's home team is the play's away team: read from the play's side
            hs, as_ = as_, hs
        if r.market == "spread":
            v = ((hs - as_) if r.side == "home" else (as_ - hs)) + float(r.line)
        else:
            v = (hs + as_ - float(r.line)) * (1 if r.side == "over" else -1)
        w = "W" if v > 0 else "L" if v < 0 else "P"
        pay = tracker.payout(r.odds)
        res.append(w)
        flat.append(pay if w == "W" else -1.0 if w == "L" else 0.0)
        st = float(r.stake) if pd.notna(r.stake) else 1.0
        staked.append(st * pay if w == "W" else -st if w == "L" else 0.0)
    return p.assign(result=res, flat=flat, staked=staked)


def frame(through: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    """(universe with cells, C plays, M plays, C plays outside the universe), graded, with CLV."""
    end = min(through or END, END)
    s = pd.read_csv(os.path.join(ROOT, "bets", "shadow_morning.csv"), dtype={"date": str})
    s = s[(s["date"] >= START) & (s["date"] <= end)].drop_duplicates(["date", "game_id", "market"], keep="first")
    fin = finals(s["date"])
    s = s[s["game_id"].astype(int).isin(fin)]                     # games with a final score only
    c = tracker.load("v1")
    c = c[(c["status"] != "void") & (c["date"] >= START) & (c["date"] <= end)].copy()
    key = lambda d: list(zip(d["game_id"].astype(int), d["market"]))
    uni = set(key(s))
    c["in_universe"] = [k in uni for k in key(c)]
    m = s[s["decision"] == "BET"].copy()
    m["bet_id"] = "M|" + m["date"] + "|" + m["game_id"].astype(str) + "|" + m["market"] + "|" + m["side"].astype(str)
    m["logged_at"], m["status"] = m["decided_at"], "open"
    c_in = grade(c[c["in_universe"]], fin)
    m = grade(m, fin)
    for p in (c_in, m):
        if len(p):
            cl = clv_primary.primary(p).set_index("bet_id")
            p["clv"] = p["bet_id"].map(cl["clv_primary"])
    cs = {k: v for k, v in zip(key(c_in), c_in["side"])}
    ms = {k: v for k, v in zip(key(m), m["side"])}
    def cell(k):
        a, b = cs.get(k), ms.get(k)
        if a and b:
            return "both, same side" if a == b else "both, opposite sides"
        return "C only" if a else "M only" if b else "neither"
    u = s[["date", "game_id", "market", "decision_kind"]].copy()
    u["cell"] = [cell(k) for k in key(u)]
    return u, c_in, m, int((~c["in_universe"]).sum())


def _stats(p: pd.DataFrame) -> dict:
    g = p[p["result"].notna()]
    risked = float(len(g))                      # flat: 1 unit risked per graded play (a push returns it)
    cl = p["clv"].dropna() if "clv" in p else pd.Series(dtype=float)
    return {"bets": len(p), "graded": len(g), "W-L-P": f"{(g['result'] == 'W').sum()}-{(g['result'] == 'L').sum()}-{(g['result'] == 'P').sum()}",
            "risked (flat)": risked, "profit (flat)": round(float(g["flat"].sum()), 2),
            "ROI (flat)": f"{100 * g['flat'].sum() / risked:+.1f}%" if risked else "-",
            "risked (staked)": round(float(g["stake"].fillna(1.0).sum()), 2), "profit (staked)": round(float(g["staked"].sum()), 2),
            "with close": len(cl), "mean CLV": round(float(cl.mean()), 2) if len(cl) else np.nan,
            "beat close": f"{100 * (cl > 0).mean():.0f}%" if len(cl) else "-"}


def boot(c: pd.DataFrame, m: pd.DataFrame, b: int = B, seed: int = SEED) -> dict:
    """95% intervals for M minus C: flat profit, and mean CLV per play; resampling game dates."""
    dates = sorted(set(c["date"]) | set(m["date"]))
    if not dates:
        return {}
    rng = np.random.default_rng(seed)
    cp = c.groupby("date")["flat"].sum().reindex(dates, fill_value=0.0).to_numpy()
    mp = m.groupby("date")["flat"].sum().reindex(dates, fill_value=0.0).to_numpy()
    cc = c.dropna(subset=["clv"]).groupby("date")["clv"].agg(["sum", "count"]).reindex(dates, fill_value=0) if "clv" in c else None
    mc = m.dropna(subset=["clv"]).groupby("date")["clv"].agg(["sum", "count"]).reindex(dates, fill_value=0) if "clv" in m else None
    dp, dc = [], []
    for _ in range(b):
        i = rng.integers(0, len(dates), len(dates))
        dp.append(mp[i].sum() - cp[i].sum())
        if cc is not None and mc is not None:
            n1, n0 = mc["count"].to_numpy()[i].sum(), cc["count"].to_numpy()[i].sum()
            if n1 and n0:
                dc.append(mc["sum"].to_numpy()[i].sum() / n1 - cc["sum"].to_numpy()[i].sum() / n0)
    q = lambda v: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) else (np.nan, np.nan)
    return {"profit": (float(mp.sum() - cp.sum()), *q(dp)), "clv": q(dc)}


def main(through: str | None = None) -> str:
    if not os.path.exists(os.path.join(ROOT, "bets", "shadow_morning.csv")):
        return "Morning shadow: no rows yet (collection starts at 9 am ET on the first game day after Nov 4)."
    u, c, m, out = frame(through)
    L = [f"Morning shadow vs live v1 (research/morning_shadow/PLAN.md), games {START} to {min(through or END, END)}"]
    L.append(f"Universe: {len(u)} game-markets with a final score; decision kinds: "
             + ", ".join(f"{k} {v}" for k, v in u["decision_kind"].value_counts().items()))
    L.append(f"C plays outside the universe (no shadow row, or no final score yet): {out}")
    L.append("\nCells: " + ", ".join(f"{k} {v}" for k, v in u["cell"].value_counts().items()))
    L.append("\n" + pd.DataFrame({"C (live)": _stats(c), "M (morning)": _stats(m)}).to_string())
    bt = boot(c, m)
    dis = int(u["cell"].isin(["C only", "M only", "both, opposite sides"]).sum())
    if bt:
        d, lo, hi = bt["profit"]
        clo, chi = bt["clv"]
        L.append(f"\nPrimary: M minus C, flat profit {d:+.2f} u, 95% [{lo:+.2f}, {hi:+.2f}] (bootstrap by game date, {B} draws)")
        L.append(f"M minus C, mean CLV per play: 95% [{clo:+.2f}, {chi:+.2f}]")
        L.append(f"Disagreeing game-markets: {dis} (decision needs {MIN_DISAGREE})")
        final = (through or END) >= END
        if not final:
            L.append("This read is descriptive only (PLAN.md section 4): no decision.")
        elif dis >= MIN_DISAGREE and lo > 0 and not (chi < 0):
            L.append("Decision (Mar 14 review): M better -> a proposal goes to Chad; nothing switches automatically.")
        elif dis >= MIN_DISAGREE and hi < 0:
            L.append("Decision (Mar 14 review): C better -> the current strategy stays.")
        else:
            L.append("Decision (Mar 14 review): inconclusive -> nothing changes.")
    txt = "\n".join(L)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "compare.txt"), "w").write(txt + "\n")
    return txt


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    print(main(ap.parse_args().through))
