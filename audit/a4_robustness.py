"""Audit steps 5-6 on the production backtest: seasons, edge buckets, clustered uncertainty, prices, slippage,
drawdown, baselines, and the opener data itself. Read-only.

    python -m audit.a4_robustness
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from audit.common import bets, frame, record
from cbb import lines_hist

RNG = np.random.default_rng(7)


def pay(odds):
    return 100 / -odds if odds < 0 else odds / 100


def units(res, odds=-110):
    return np.where(res > 0, pay(odds), np.where(res < 0, -1.0, 0.0))


def cluster_ci(b, res="res", odds=-110, n=2000):
    """Percentile bootstrap over game dates (all plays on a date resampled together; spread and total plays on the
    same game, and same-day market-wide errors, stay together)."""
    b = b.assign(u=units(b[res].to_numpy(), odds), w=(b[res] > 0).astype(int), d=(b[res] != 0).astype(int))
    g = b.groupby("date")[["u", "w", "d"]].sum().assign(n=b.groupby("date").size())
    arr = g[["u", "w", "d", "n"]].to_numpy()
    idx = RNG.integers(0, len(arr), size=(n, len(arr)))
    s = arr[idx].sum(axis=1)
    win = s[:, 1] / s[:, 2] * 100
    roi = s[:, 0] / s[:, 3] * 100
    return np.percentile(win, [2.5, 97.5]).round(1).tolist(), np.percentile(roi, [2.5, 97.5]).round(1).tolist()


def drawdown(b, odds=-110):
    u = pd.Series(units(b.sort_values(["date", "game_id"])[ "res"].to_numpy(), odds)).cumsum()
    return round(float((u.cummax() - u).max()), 1)


def regrade(b, worse, market):
    """Hypothetical: the same play at a number `worse` points worse than the opener."""
    if market == "spread":
        line = np.where(b["side"] == "home", b["line"] - worse, b["line"] + worse)
        res = np.sign(b["margin"] + line) * np.where(b["side"] == "home", 1, -1)
    else:
        line = np.where(b["side"] == "over", b["line"] + worse, b["line"] - worse)
        res = np.sign(b["points"] - line) * np.where(b["side"] == "over", 1, -1)
    return b.assign(res=res)


if __name__ == "__main__":
    w = frame()
    pd.set_option("display.width", 260)
    cohorts = {(mk, ss): bets(w, mk, "open", thr, ss) for mk, thr in (("spread", 2.5), ("total", 3.0))
               for ss in ((2015, 2017), (2024, 2026))}

    print("== Uncertainty (clustered by game date), drawdown, price and slippage sensitivity ==")
    rows = []
    for (mk, ss), b in cohorts.items():
        ci_w, ci_r = cluster_ci(b)
        r = {"cohort": f"{mk} {ss[0]}-{ss[1]}", "plays": len(b), "win%": round(record(b)["win%"], 1), "95% CI win%": ci_w,
             "ROI% -110": record(b)["ROI%"], "95% CI ROI%": ci_r, "max drawdown u": drawdown(b)}
        for o in (-115, -120):
            r[f"ROI% {o}"] = round(units(b["res"].to_numpy(), o).mean() * 100, 2)
        for k in (0.5, 1.0, 1.5):
            bb = regrade(b, k, mk)
            r[f"ROI% {k} pt worse"] = round(units(bb["res"].to_numpy()).mean() * 100, 2)
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== By season ==")
    rows = []
    for (mk, ss), b in cohorts.items():
        for s, g in b.groupby("season"):
            r = record(g)
            rows.append({"market": mk, "season": s, "plays": r["plays"], "win%": round(r["win%"], 1), "ROI%": r["ROI%"],
                         "mean move": round(g["clv"].mean(), 2), "same plays at close win%": round(record(g, "res_at_close")["win%"], 1)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== By edge bucket ==")
    rows = []
    for (mk, ss), b in cohorts.items():
        bins = [2.5, 3, 4, 6, 99] if mk == "spread" else [3, 4, 6, 8, 99]
        for lab, g in b.groupby(pd.cut(b["edge"], bins, right=False), observed=True):
            r = record(g)
            rows.append({"cohort": f"{mk} {ss[0]}-{ss[1]}", "edge": str(lab), "plays": r["plays"], "win%": round(r["win%"], 1),
                         "ROI%": r["ROI%"], "mean move": round(g["clv"].mean(), 2)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== Concentration: share of units from the best 10% of dates; month split ==")
    for (mk, ss), b in cohorts.items():
        u = b.assign(u=units(b["res"].to_numpy())).groupby("date")["u"].sum().sort_values(ascending=False)
        top = u.head(max(1, len(u) // 10)).sum()
        m = b.assign(u=units(b["res"].to_numpy()), mo=b["date"].dt.month).groupby("mo")["u"].agg(["count", "sum"]).round(1)
        print(f"{mk} {ss}: total {u.sum():.1f}u, best 10% of dates {top:.1f}u; by month {m.to_dict('index')}")

    print("\n== Baselines vs the same openers (plays at the same thresholds) ==")
    w2 = w.copy()
    w2["mkt_margin_only"] = w2["mkt_m"]   # ratings fit to earlier closing lines (dates before the game), weighted
    base = {"final model": ("final_margin", "final_total"), "stage-1 ratings only": ("pred_margin", "pred_total"),
            "KenPom FanMatch only": ("kp_margin", "kp_total"), "Barttorvik only": ("bt_margin", "bt_total")}
    rows = []
    for name, (mc, tc) in base.items():
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            for ss in ((2015, 2017), (2024, 2026)):
                b = bets(w2, mk, "open", thr, ss, margin_col=mc, total_col=tc)
                r = record(b)
                rows.append({"baseline": name, "market": mk, "seasons": f"{ss[0]}-{ss[1]}", "plays": r["plays"],
                             "win%": round(r["win%"], 1), "ROI%": r["ROI%"], "mean move": round(b["clv"].mean(), 2)})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== The opener data ==")
    for s in (2015, 2016, 2017, 2024, 2025, 2026):
        raw = pd.read_csv(f"{lines_hist.OUT}/espn_{s}.csv")
        l = raw[~raw["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})]
        agg = l.groupby("game_id").agg(o=("open_home_spread", "median"), c=("home_spread", "median"))
        op = raw[raw["book"] == "Opening"].drop_duplicates("game_id").set_index("game_id")["home_spread"]
        agg["o"] = agg["o"].fillna(op)
        flipped = ((agg.o + agg.c).abs() < (agg.o - agg.c).abs()) & (agg.c.abs() >= 2)
        src = "ESPN 'Opening' pseudo-book" if raw["open_home_spread"].notna().sum() == 0 else \
            ", ".join(f"{k} ({v})" for k, v in l[l.open_home_spread.notna()].groupby("book").game_id.nunique().nlargest(3).items())
        d = (agg.o - agg.c).dropna()
        print(f"{s}: games with opener {agg.o.notna().sum()} of {len(agg)}; dropped as 'flipped' using the close: {int(flipped.sum())}; "
              f"opener == close {100 * (d == 0).mean():.0f}%, median |move| {d.abs().median():.1f}; source: {src}")
