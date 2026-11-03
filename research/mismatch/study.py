"""Early-season mismatch study (research/mismatch/PLAN.md, pre-registered Nov 3, 2026). Research only.

    python -m research.mismatch.study        # -> research/mismatch/out/report.txt
"""
from __future__ import annotations

import glob
import math
import os

import numpy as np
import pandas as pd

from research.persistent_disagreement import common

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
ERAS = {"2014-17": range(2014, 2018), "2024-26": range(2024, 2027), "all 2014-26": range(2014, 2027)}
EARLY_DAYS, BIG, THR, B, SEED = 14, 17.5, 2.5, 2000, 7


def frame() -> pd.DataFrame:
    d = common.baseline()
    if "swapped" in d:
        d = d[~d["swapped"].fillna(False).astype(bool)]
    d = d.dropna(subset=["final_margin", "margin"]).copy()
    d["day"] = (d["date"] - d.groupby("season")["date"].transform("min")).dt.days
    d["period"] = np.where(d["day"] < EARLY_DAYS, "early", "later")
    return d


def slope(x: pd.DataFrame) -> float:
    if len(x) < 3:
        return np.nan
    m, a = x["final_margin"].to_numpy(float), x["margin"].to_numpy(float)
    m = m - m.mean()
    return float((m * (a - a.mean())).sum() / (m * m).sum())


def boot(d: pd.DataFrame, stat, b: int = B, seed: int = SEED) -> tuple[float, float]:
    """95% interval, resampling game dates (games on one date move together)."""
    rng = np.random.default_rng(seed)
    days = d["date"].unique()
    by = {k: g for k, g in d.groupby("date")}
    vals = []
    for _ in range(b):
        pick = rng.choice(days, size=len(days), replace=True)
        vals.append(stat(pd.concat([by[k] for k in pick], ignore_index=True)))
    v = np.array([x for x in vals if np.isfinite(x)])
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) else (np.nan, np.nan)


def wilson(w: int, n: int) -> tuple[float, float]:
    if not n:
        return (np.nan, np.nan)
    p, z = w / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (c - h), 100 * (c + h))


def h1(d: pd.DataFrame, L: list) -> dict:
    L.append("H1. Calibration slope: actual home margin on the model's home margin (above 1 = margins understated)")
    out = {}
    for era, ss in ERAS.items():
        y = d[d["season"].isin(ss)]
        e, l = y[y["period"] == "early"], y[y["period"] == "later"]
        diff = lambda z: slope(z[z["period"] == "early"]) - slope(z[z["period"] == "later"])
        lo, hi = boot(y, diff)
        out[era] = (diff(y), lo, hi)
        L.append(f"  {era:11s} early slope {slope(e):.3f} (n={len(e)})  later {slope(l):.3f} (n={len(l)})  "
                 f"early minus later {diff(y):+.3f}  95% [{lo:+.3f}, {hi:+.3f}]")
    return out


def h2(d: pd.DataFrame, L: list) -> dict:
    L.append("\nH2. Big lines (|opener| >= 17.5), from the favorite's side: lean = model - market, outcome = actual - market")
    out = {}
    for era, ss in list(ERAS.items())[:2]:
        y = d[d["season"].isin(ss) & d["open_home_spread"].notna() & (d["open_home_spread"].abs() >= BIG)].copy()
        fav = np.sign(-y["open_home_spread"])
        y["lean"] = fav * (y["final_margin"] + y["open_home_spread"])
        y["outc"] = fav * (y["margin"] + y["open_home_spread"])
        y["lean_c"] = fav * (y["final_margin"] + y["home_spread"])
        y["outc_c"] = fav * (y["margin"] + y["home_spread"])
        for per in ("early", "later"):
            z = y[y["period"] == per]
            gap = lambda q: float(q["outc"].mean() - q["lean"].mean())
            lo, hi = boot(z, gap)
            out[(era, per)] = (z["lean"].mean(), z["outc"].mean())
            L.append(f"  {era} {per:5s} n={len(z):4d}  vs opener: lean {z['lean'].mean():+.2f}, outcome {z['outc'].mean():+.2f}, "
                     f"outcome minus lean {gap(z):+.2f} 95% [{lo:+.2f}, {hi:+.2f}]  |  vs close: lean {z['lean_c'].mean():+.2f}, "
                     f"outcome {z['outc_c'].mean():+.2f}")
    return out


def h3(d: pd.DataFrame, L: list) -> dict:
    L.append("\nH3. v1 plays at the opener (edge >= 2.5), graded at the opener")
    y = d[d["open_home_spread"].notna()].copy()
    y["e"] = y["final_margin"] + y["open_home_spread"]
    y = y[y["e"].abs() >= THR]
    side = np.sign(y["e"])
    y["line"] = np.where(side > 0, y["open_home_spread"], -y["open_home_spread"])
    y["res"] = side * (y["margin"] + y["open_home_spread"])
    y = y[y["res"] != 0]
    y["grp"] = np.select([y["line"] >= BIG, y["line"] > 0, y["line"] <= -BIG], ["underdog 17.5+", "underdog < 17.5", "favorite 17.5+"],
                         "favorite < 17.5")
    out = {}
    for era, ss in list(ERAS.items())[:2] + [("both eras", list(range(2014, 2018)) + list(range(2024, 2027)))]:
        L.append(f"  {era}")
        z = y[y["season"].isin(ss)]
        for g in ("underdog 17.5+", "underdog < 17.5", "favorite 17.5+", "favorite < 17.5"):
            for per in ("early", "later"):
                q = z[(z["grp"] == g) & (z["period"] == per)]
                w, n = int((q["res"] > 0).sum()), len(q)
                lo, hi = wilson(w, n)
                out[(era, g, per)] = (w, n)
                L.append(f"    {g:16s} {per:5s} n={n:4d}  win {100 * w / n if n else float('nan'):5.1f}%  95% [{lo:4.1f}, {hi:4.1f}]")
    return out


def live(L: list) -> None:
    L.append("\nLive reference (2026-27 cards so far): model minus close for the favorite, games with a close")
    cl = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_2026-1*.csv"))):
        day = os.path.basename(f)[4:14]
        c = pd.read_csv(f, usecols=lambda k: k in ("game_id", "home_id", "away_id", "model_margin"))
        x = cl[cl["date"] == day]
        for _, r in c.iterrows():
            g = x[((x["home_id"] == r["home_id"]) & (x["away_id"] == r["away_id"])) |
                  ((x["home_id"] == r["away_id"]) & (x["away_id"] == r["home_id"]))]
            hs = pd.Series(np.where(g["home_id"] == r["home_id"], g["home_spread"], -g["home_spread"])).dropna()
            if len(hs) and pd.notna(r["model_margin"]):
                rows.append({"day": day, "close": float(hs.median()), "model": float(r["model_margin"])})
    v = pd.DataFrame(rows)
    if not len(v):
        L.append("  no closes yet")
        return
    v["fav"] = np.sign(-v["close"])
    v["lean"] = v["fav"] * (v["model"] + v["close"])
    for lab, m in (("|close| >= 17.5", v["close"].abs() >= BIG), ("7-17", (v["close"].abs() >= 7) & (v["close"].abs() < BIG)),
                   ("< 7", v["close"].abs() < 7)):
        L.append(f"  {lab:15s} n={int(m.sum()):3d}  lean {v[m]['lean'].mean():+.2f}  (days: {', '.join(sorted(v[m]['day'].unique()))})")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    d = frame()
    L = [f"Early-season mismatch study (research/mismatch/PLAN.md). Early = days 0-{EARLY_DAYS - 1} of each season; "
         f"bootstrap by game date, {B} draws, seed {SEED}.\n"]
    a, b_, c = h1(d, L), h2(d, L), h3(d, L)
    live(L)
    ok_a = all(a[e][1] > 0 for e in ("2014-17", "2024-26"))
    ok_b = all(b_[(e, "early")][0] < b_[(e, "early")][1] for e in ("2014-17", "2024-26"))
    w, n = c[("both eras", "underdog 17.5+", "early")]
    ok_c = n > 0 and 100 * w / n < 52.4
    L.append("\nDecision rule (PLAN.md): propose a change only if (a), (b) and (c) all hold")
    L.append(f"  (a) H1 early-minus-later slope above 0, interval excluding 0, both eras: {'yes' if ok_a else 'no'}")
    L.append(f"  (b) H2 early lean below early outcome, both eras: {'yes' if ok_b else 'no'}")
    L.append(f"  (c) H3 early big-underdog plays under 52.4% pooled: {'yes' if ok_c else 'no'} ({w}/{n})")
    L.append(f"  -> {'all hold: a pre-registered change proposal goes to Chad' if ok_a and ok_b and ok_c else 'not all hold: no reliable evidence; nothing changes'}")
    txt = "\n".join(L)
    open(os.path.join(OUT, "report.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
