"""Audit follow-up, item 2: opener cleaning without the close.

lines_hist.consensus() drops a spread opener when it sits closer to the mirrored close than to the close, which uses
information from after the opener. Here the openers are rebuilt with NO close-dependent filtering or correction, and
then filtered only by rules that use information available at selection time (drop only, never flip):

  none      no filtering at all
  A_range   spreads within +-60, totals within 100-200
  B_mkt5    A + drop a spread opener whose favorite disagrees with the market-rating line (closes before D-1, both
            teams 10+ earlier lined games) by 5+ points
  C_mkt8    A + drop a spread opener 8+ points from that market-rating line (either direction)
  D_kp      A + drop an opener 10+ points (spread) or 20+ points (total) from KenPom's line built from its archive of
            the day before

The rules were fixed before looking at any result below; none is preferred because of its returns. Production
(`current`) is shown for reference. Totals openers are unaffected by the close-based rule (it only touches spreads).

    python -m audit.b2_opener_cleaning
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import OUT, bets, frame, record
from cbb import context, lines_hist

DAY = pd.Timedelta(days=1)


def raw_openers(seasons) -> pd.DataFrame:
    """consensus() exactly as production, minus the close-dependent 'flipped' rule."""
    parts = []
    for s in seasons:
        lines = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{s}.csv"))
        l = lines[~lines["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})].copy()
        agg = l.groupby("game_id").agg(open_home_spread=("open_home_spread", "median"), open_total=("open_total", "median"))
        op = lines[lines["book"] == "Opening"].drop_duplicates("game_id").set_index("game_id")
        agg["open_home_spread"] = agg["open_home_spread"].fillna(op["home_spread"])
        agg["open_total"] = agg["open_total"].fillna(op["total"])
        parts.append(agg.reset_index())
    return pd.concat(parts, ignore_index=True)


def mkt_lagged(w: pd.DataFrame) -> pd.DataFrame:
    path = os.path.join(OUT, "mkt_prev_margin.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    keys = w[["game_id", "season", "date", "home_id", "away_id", "neutral"]].assign(date=lambda d: d["date"] - DAY)
    ctx = context.market(keys, context.backtest_closes(sorted(w["season"].unique())))[["game_id", "mkt_margin", "mkt_n"]]
    ctx.to_pickle(path)
    return ctx


def apply(w, raw, rule, mkt):
    d = w.drop(columns=["open_home_spread", "open_total"]).merge(raw, on="game_id", how="left")
    if rule == "none":
        return d, 0, 0
    s0, t0 = d["open_home_spread"].notna().sum(), d["open_total"].notna().sum()
    d.loc[d["open_home_spread"].abs() > 60, "open_home_spread"] = np.nan
    d.loc[~d["open_total"].between(100, 200), "open_total"] = np.nan
    if rule in ("B_mkt5", "C_mkt8"):
        m = d[["game_id"]].merge(mkt, on="game_id", how="left")
        ok = (m["mkt_n"] >= 10).to_numpy()
        mline = -m["mkt_margin"].to_numpy()               # market-rating home spread
        o = d["open_home_spread"].to_numpy()
        if rule == "B_mkt5":
            bad = ok & (np.sign(o) * np.sign(mline) < 0) & (np.abs(o - mline) >= 5)
        else:
            bad = ok & (np.abs(o - mline) >= 8)
        d.loc[bad, "open_home_spread"] = np.nan
    if rule == "D_kp":
        d.loc[(d["open_home_spread"] + d["kp_margin"]).abs() >= 10, "open_home_spread"] = np.nan
        d.loc[(d["open_total"] - d["kp_total"]).abs() >= 20, "open_total"] = np.nan
    return d, int(s0 - d["open_home_spread"].notna().sum()), int(t0 - d["open_total"].notna().sum())


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    rows, excl = [], []
    for tag in ("safe_lag1", "base"):
        w = frame(tag=tag)
        raw = raw_openers(sorted(w["season"].unique()))
        mkt = mkt_lagged(w)
        if tag == "safe_lag1":   # KenPom rule needs the day-before KenPom line: the safe_lag1 frame carries it
            kpw = w[["game_id", "kp_margin", "kp_total"]]
        variants = {"current (close-based flip rule)": w}
        for rule in ("none", "A_range", "B_mkt5", "C_mkt8", "D_kp"):
            ww = w if tag == "safe_lag1" else w.drop(columns=["kp_margin", "kp_total"]).merge(kpw, on="game_id")
            d, xs, xt = apply(ww, raw, rule, mkt)
            if tag == "base":   # restore production KenPom columns after the rule is applied (rule uses day-before KenPom)
                d = d.drop(columns=["kp_margin", "kp_total"]).merge(w[["game_id", "kp_margin", "kp_total"]], on="game_id")
            variants[rule] = d
            if tag == "safe_lag1":
                for ss in ((2015, 2017), (2024, 2026)):
                    dd = d[d["season"].between(*ss)]
                    excl.append({"rule": rule, "seasons": f"{ss[0]}-{ss[1]}",
                                 "spread openers kept": int(dd["open_home_spread"].notna().sum()),
                                 "total openers kept": int(dd["open_total"].notna().sum())})
        for name, d in variants.items():
            for mk, thr in (("spread", 2.5), ("total", 3.0)):
                for ss in ((2015, 2017), (2024, 2026)):
                    b = bets(d, mk, "open", thr, ss)
                    r = record(b)
                    rows.append({"model": tag, "openers": name, "market": mk, "seasons": f"{ss[0]}-{ss[1]}",
                                 "selections": r["plays"], "W": r["W"], "L": r["L"], "P": r["P"], "win%": round(r["win%"], 2),
                                 "ROI%@-110 (assumed)": r["ROI%"], "mean line value": round(b["clv"].mean(), 3)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "opener_cleaning.csv"), index=False)
    e = pd.DataFrame(excl)
    e.to_csv(os.path.join(OUT, "opener_cleaning_counts.csv"), index=False)
    print(e.to_string(index=False))
    print(t.to_string(index=False))
