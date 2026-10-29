"""Stake-by-band backtest (PLAN.md). Research only; nothing live changes.

    python -m research.stake_bands.backtest     # -> out/results.txt, out/summary.csv, out/bands.csv, out/plays.csv

Plays: v1 (spreads 2.5+, totals 3+) and band B (spreads 2.0-2.49, totals 2.0-2.99) at the ESPN opener, +2% EV at an
assumed -110, from research/persistent_disagreement/common.baseline(). Schedules (a), (b), (b'), (c), (d) per PLAN.md.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import baseline, payout

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
PERIODS = {"2024-26": [2024, 2025, 2026], "2014-17": [2014, 2015, 2016, 2017]}
WIN_PROB = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}     # cbb/run_day.WIN_PROB (frozen)
MIN_EV = 0.02
V1 = {"spread": 2.5, "total": 3.0}
FLOOR, TOP = 2.0, 4.0
STAKE = {"B": 0.5, "core": 1.0, "top": 1.25}
TRAIL, HALVE_BELOW, RESTORE_ABOVE, HALF = 150, 0.4, 0.7, 0.5
SEED, REPS = 20261029, 10_000
WIN_PAY = payout(-110.0)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def ev(edge: np.ndarray, market: str, price: np.ndarray) -> np.ndarray:
    slope, cap = WIN_PROB[market]
    p = np.minimum(np.maximum(0.5 + slope * np.abs(edge), 0.5), cap)
    return p * np.array([payout(o) for o in price]) - (1 - p)


def band(ae: np.ndarray, market: str) -> np.ndarray:
    return np.where(ae < V1[market], "B", np.where(ae < TOP, "core", "top"))


def opener_plays(w: pd.DataFrame) -> pd.DataFrame:
    """Every candidate play (edge >= 2.0 and +2% EV at -110) at the ESPN opener, both markets, chronological."""
    w = w[~w["swapped"]]
    out = []
    for mk, mcol, open_, close, res in (("spread", "final_margin", "open_home_spread", "home_spread", "margin"),
                                        ("total", "final_total", "open_total", "total", "points")):
        d = w.dropna(subset=[mcol, open_, res]).copy()
        e = (d[mcol] + d[open_]) if mk == "spread" else (d[mcol] - d[open_])
        side = np.sign(e)
        cover = side * ((d[res] + d[open_]) if mk == "spread" else (d[res] - d[open_]))
        clv = side * ((d[open_] - d[close]) if mk == "spread" else (d[close] - d[open_]))
        price = np.full(len(d), -110.0)
        evv = ev(e.to_numpy(), mk, price)
        p = pd.DataFrame({"season": d["season"], "date": d["date"], "game_id": d["game_id"], "market": mk,
                          "edge": e.abs(), "side": side, "line": d[open_], "cover": cover, "clv": clv, "ev": evv})
        p["ev_drop"] = (p["edge"] >= FLOOR) & (p["ev"] < MIN_EV)
        out.append(p[p["edge"] >= FLOOR])
    p = pd.concat(out)
    p["band"] = [band(np.array([a]), m)[0] for a, m in zip(p["edge"], p["market"])]
    p["v1"] = p["band"] != "B"
    p["mkord"] = (p["market"] == "total").astype(int)
    return p.sort_values(["date", "game_id", "mkord"], kind="mergesort").reset_index(drop=True)


def grade(cover: np.ndarray, stake: np.ndarray, win_pay=WIN_PAY) -> np.ndarray:
    return np.where(cover > 0, stake * win_pay, np.where(cover < 0, -stake, 0.0))


def drawdown_mult(p: pd.DataFrame) -> np.ndarray:
    """Per-play multiplier under the drawdown rule: state for date D from the trailing 150 plays (with a close)
    dated before D; full -> half below +0.4, half -> full above +0.7, else carry over; full until 150 exist."""
    mult = np.ones(len(p))
    state, hist = "full", []
    dates = p["date"].to_numpy()
    clv = p["clv"].to_numpy()
    i = 0
    while i < len(p):
        j = i
        while j < len(p) and dates[j] == dates[i]:
            j += 1
        have = [c for c in hist if not np.isnan(c)]
        if len(have) >= TRAIL:
            m = float(np.mean(have[-TRAIL:]))
            if state == "full" and m < HALVE_BELOW:
                state = "half"
            elif state == "half" and m > RESTORE_ABOVE:
                state = "full"
        mult[i:j] = HALF if state == "half" else 1.0
        hist.extend(clv[i:j])
        i = j
    return mult


def schedules(p: pd.DataFrame) -> dict[str, np.ndarray]:
    """Stake per play under each schedule (0 = not played)."""
    base = p["band"].map(STAKE).to_numpy(float)
    s = {"(a) flat 1, v1 only": np.where(p["v1"], 1.0, 0.0),
         "(b) flat 1, v1 + band B": np.ones(len(p)),
         "(b') v1 1 + band B 0.5": np.where(p["v1"], 1.0, 0.5),
         "(c) schedule": base}
    s["(d) schedule + drawdown"] = base * drawdown_mult(p)
    return s


def max_dd(units: np.ndarray) -> float:
    cum = np.concatenate([[0.0], np.cumsum(units)])
    return float((np.maximum.accumulate(cum) - cum).max())


def metrics(p: pd.DataFrame, stake: np.ndarray) -> dict:
    on = stake > 0
    x, st = p[on], stake[on]
    u = grade(x["cover"].to_numpy(), st)
    w, l = int((x["cover"] > 0).sum()), int((x["cover"] < 0).sum())
    risked = float(st.sum())
    dd = max_dd(u)
    return {"plays": int(on.sum()), "risked": risked, "won": float(u.sum()), "per_risked": u.sum() / risked if risked else np.nan,
            "win%": 100 * w / (w + l) if w + l else np.nan, "clv": float(x["clv"].mean()), "max_dd": dd,
            "dd_per_avg_stake": dd / (risked / on.sum()) if on.sum() else np.nan}


def boot_diff(p: pd.DataFrame, sa: np.ndarray, sb: np.ndarray) -> tuple[float, float, float]:
    """Date-clustered bootstrap of (units/risked under sa) - (units/risked under sb)."""
    ua, ub = grade(p["cover"].to_numpy(), sa), grade(p["cover"].to_numpy(), sb)
    g = pd.DataFrame({"d": p["date"].to_numpy(), "ua": ua, "ra": sa, "ub": ub, "rb": sb}).groupby("d").sum()
    v = g.to_numpy()
    est = v[:, 0].sum() / v[:, 1].sum() - v[:, 2].sum() / v[:, 3].sum()
    idx = np.random.default_rng(SEED).integers(0, len(v), size=(REPS, len(v)))
    s = v[idx].sum(axis=1)
    d = s[:, 0] / s[:, 1] - s[:, 2] / s[:, 3]
    return est, float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def report_period(name: str, p: pd.DataFrame) -> list[dict]:
    say(f"\n{'=' * 110}\n{name}: {p['date'].min().date()} to {p['date'].max().date()} | candidate plays {len(p)} "
        f"(spreads {int((p['market'] == 'spread').sum())}, totals {int((p['market'] == 'total').sum())}) | assumed -110")
    S = schedules(p)
    rows = []
    for scope in ("all", "spread", "total"):
        m = np.ones(len(p), bool) if scope == "all" else (p["market"] == scope).to_numpy()
        say(f"\n  [{scope}]  {'schedule':28s} {'plays':>6s} {'risked':>8s} {'won':>8s} {'won/risk':>9s} {'win%':>6s} "
            f"{'CLV':>6s} {'maxDD':>7s} {'DD/avg stake':>12s}")
        for k, st in S.items():
            r = metrics(p[m], st[m])
            rows.append({"period": name, "market": scope, "schedule": k, **r})
            say(f"  [{scope}]  {k:28s} {r['plays']:6d} {r['risked']:8.1f} {r['won']:+8.1f} {100 * r['per_risked']:+8.2f}% "
                f"{r['win%']:6.2f} {r['clv']:+6.2f} {r['max_dd']:7.1f} {r['dd_per_avg_stake']:12.1f}")
    mult = S["(d) schedule + drawdown"] / np.where(S["(c) schedule"] > 0, S["(c) schedule"], 1)
    half = mult < 1
    changes = int((np.diff(half.astype(int)) != 0).sum())
    say(f"\n  drawdown rule: {100 * half.mean():.1f}% of plays at half stake; {changes} state changes")
    if half.any():
        hd = p.loc[half, "date"]
        runs = (pd.Series(half).astype(int).diff().fillna(half[0]).ne(0)).cumsum()[half]
        spans = pd.DataFrame({"d": hd.to_numpy(), "r": runs.to_numpy()}).groupby("r")["d"].agg(["min", "max", "size"])
        for _, s in spans.iterrows():
            say(f"    half from {s['min'].date()} to {s['max'].date()} ({s['size']} plays)")
    for scope in ("all", "spread", "total"):
        m = np.ones(len(p), bool) if scope == "all" else (p["market"] == scope).to_numpy()
        for ref in ("(b') v1 1 + band B 0.5", "(b) flat 1, v1 + band B"):
            est, lo, hi = boot_diff(p[m], S["(c) schedule"][m], S[ref][m])
            say(f"  (c) minus {ref:24s} [{scope:6s}] won/risked {100 * est:+.2f} pts, 95% {100 * lo:+.2f} to {100 * hi:+.2f} (date-clustered)")
    return rows


def by_band(name: str, p: pd.DataFrame) -> pd.DataFrame:
    g = []
    for (mk, b), x in p.groupby(["market", "band"]):
        w, l = int((x["cover"] > 0).sum()), int((x["cover"] < 0).sum())
        u = grade(x["cover"].to_numpy(), np.ones(len(x)))
        c = x["clv"].dropna()
        g.append({"period": name, "market": mk, "band": b, "plays": len(x), "win%": 100 * w / (w + l),
                  "roi_1u%": 100 * u.mean(), "clv_mean": c.mean(), "clv_sd": c.std(), "clv_n": len(c)})
    t = pd.DataFrame(g)
    say(f"\n  by band ({name}, 1 unit each):")
    say("  " + t.drop(columns="period").round(3).to_string(index=False).replace("\n", "\n  "))
    return t


def recorded_sample(w: pd.DataFrame) -> None:
    """2025-26 dated DraftKings sample (persistent_disagreement pool C): spread plays at recorded prices."""
    path = os.path.join(HERE, "..", "persistent_disagreement", "out", "predictions.csv")
    say(f"\n{'=' * 110}\nRecorded-price size check: DraftKings first-observed spreads, 2025-11-08 / 2026-01-10 / "
        f"2026-03-07 (pool C, strict pre-quote inputs). Totals not in the sample.")
    if not os.path.exists(path):
        say("  predictions.csv not found; skipped")
        return
    c = pd.read_csv(path, dtype={"date": str})
    c = c[c["pool"].str.startswith("C")].copy()
    c["margin"] = c["game_id"].map(w.set_index("game_id")["margin"])
    e = c["edge_baseline"].to_numpy(float)
    side = np.sign(e)
    price = np.where(side > 0, c["price_pos"], c["price_neg"]).astype(float)
    keep = (np.abs(e) >= FLOOR) & (ev(e, "spread", price) >= MIN_EV) & c["margin"].notna().to_numpy()
    c = c[keep].assign(edge=np.abs(e[keep]), side=side[keep], price=price[keep])
    c["cover"] = c["side"] * (c["margin"] + c["line"])
    c["band"] = band(c["edge"].to_numpy(), "spread")
    say(f"  games {int(len(keep))}; plays {len(c)} (band B {int((c['band'] == 'B').sum())}, core "
        f"{int((c['band'] == 'core').sum())}, top {int((c['band'] == 'top').sum())})")
    for k, st in {"(a)": np.where(c["band"] != "B", 1.0, 0.0), "(b)": np.ones(len(c)),
                  "(b')": np.where(c["band"] != "B", 1.0, 0.5), "(c)": c["band"].map(STAKE).to_numpy(float)}.items():
        pay = np.array([payout(o) for o in c["price"]])
        u = np.where(c["cover"] > 0, st * pay, np.where(c["cover"] < 0, -st, 0.0))
        say(f"  {k:5s} plays {int((st > 0).sum()):3d} risked {st.sum():6.2f} won {u.sum():+6.2f} won/risked {100 * u.sum() / st.sum():+6.1f}%")


def jan15_counts(p: pd.DataFrame) -> None:
    """Band-B plays a season produces from its start to Jan 14 (how soon 300 live plays arrive)."""
    say(f"\n{'=' * 110}\nBand-B plays from season start to Jan 14, by season (live pace check):")
    for s, x in p[p["band"] == "B"].groupby("season"):
        cut = pd.Timestamp(f"{s}-01-15")
        say(f"  {s}: before Jan 15 {int((x['date'] < cut).sum())} (spreads {int(((x['date'] < cut) & (x['market'] == 'spread')).sum())}, "
            f"totals {int(((x['date'] < cut) & (x['market'] == 'total')).sum())}); season {len(x)}")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    allp, rows, bands = [], [], []
    for name, ss in PERIODS.items():
        p = opener_plays(w[w["season"].isin(ss)])
        say(f"\n{name}: totals edges 2.0+ dropped by the +2% EV rule at -110: {int(p.loc[(p['market'] == 'total'), 'ev_drop'].sum())} "
            f"(all under 2.45); spreads dropped: {int(p.loc[(p['market'] == 'spread'), 'ev_drop'].sum())}")
        p = p[p["ev"] >= MIN_EV].reset_index(drop=True)
        rec = p[p["v1"]]
        ref = ("stage2_stability compare.txt, R-frozen (reference) 2024-26: spreads 1310-958-8, totals 2028-1608-9"
               if name == "2024-26" else "no stored reference for this period")
        say(f"{name}: reconciliation, v1 plays W-L-P spreads "
            f"{int(((rec['market'] == 'spread') & (rec['cover'] > 0)).sum())}-{int(((rec['market'] == 'spread') & (rec['cover'] < 0)).sum())}-"
            f"{int(((rec['market'] == 'spread') & (rec['cover'] == 0)).sum())}, totals "
            f"{int(((rec['market'] == 'total') & (rec['cover'] > 0)).sum())}-{int(((rec['market'] == 'total') & (rec['cover'] < 0)).sum())}-"
            f"{int(((rec['market'] == 'total') & (rec['cover'] == 0)).sum())} ({ref})")
        rows += report_period(name, p)
        bands.append(by_band(name, p))
        if name == "2024-26":
            jan15_counts(p)
        allp.append(p.assign(period=name))
    recorded_sample(w)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "summary.csv"), index=False)
    pd.concat(bands).to_csv(os.path.join(OUT, "bands.csv"), index=False)
    pd.concat(allp).drop(columns=["mkord"]).to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
