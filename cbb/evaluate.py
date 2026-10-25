"""Score the walk-forward backtest against closing lines and KenPom's FanMatch predictions.

    python -m cbb.evaluate --start 2013 --end 2026     # needs cbb/output/backtest_<start>_<end>.csv; writes BACKTEST.md

Sections:
  * accuracy: average miss on margin and total for the model, the closing line and KenPom
  * how much the model adds to the line: regression of the result on (line, model - line)
  * against the spread / over-under vs the closing line, by size of disagreement, month and season,
    with thresholds chosen on the first half of the seasons and checked on the second half
  * line movement (2014-2017 and 2024-2026 openers): does the model predict which way the line moves?
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from . import kenpom, lines_hist

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
REPORT = os.path.join(os.path.dirname(__file__), "..", "BACKTEST.md")
BREAKEVEN = 0.5238  # -110


SUMMARY = """## Summary (first, untuned version)

* **No edge yet.** Against closing lines the model's side wins 49-52% at every size of disagreement, in both
  halves of the data (break-even 52.4%). Totals are the same.
* **Accuracy:** the model is as good as KenPom (margin miss 8.83 vs 8.85 points) but behind the closing line
  (8.71). Closing lines in college basketball are hard to beat with ratings alone.
* **Opening lines** (the NFL model's lesson): the line moves toward the model's side 60-75% of the time, so the model
  does see something the opener misses. Betting it at the opener won 54.5% at 3+ points in 2014-2017 but only
  51.4% in 2024-2026 (break-even 52.4%): the recent market corrects faster and the edge isn't there yet.
* **Data cleaning that mattered:** projection sites in ESPN's feed (numberfire, teamrankings) and openers stored
  from the wrong team's side both produced fake 70-85% win rates until removed.

Next: tune the model (decay, prior strength, blowout compression, per-team home edge, KenPom/Barttorvik blend)
and re-run this report. The threshold for betting anything is a result that holds in both halves of the data."""


def load(start: int, end: int) -> pd.DataFrame:
    b = pd.read_csv(os.path.join(OUT_DIR, f"backtest_{start}_{end}.csv"), parse_dates=["date"])
    lines = []
    for s in range(start, end + 1):
        path = os.path.join(lines_hist.OUT, f"espn_{s}.csv")
        if os.path.exists(path):
            lines.append(lines_hist.consensus(pd.read_csv(path)))
    if lines:
        b = b.merge(pd.concat(lines), on="game_id", how="left")
    b = b.merge(fanmatch(b), on="game_id", how="left")
    b["margin"] = b["home_pts"] - b["away_pts"]
    b["points"] = b["home_pts"] + b["away_pts"]
    b["line_margin"] = -b["home_spread"]          # line's expected home margin
    b["month"] = b["date"].dt.month
    return b


def fanmatch(b: pd.DataFrame) -> pd.DataFrame:
    """KenPom's predicted home margin and total for each game (orientation matched to ESPN's home team)."""
    rows = []
    for d in sorted(b["date"].dt.strftime("%Y-%m-%d").unique()):
        path = os.path.join(kenpom.CACHE, f"endpoint-fanmatch_d-{d}.json")
        if os.path.exists(path):
            rows.append(kenpom.fanmatch(d))
    if not rows:
        return pd.DataFrame(columns=["game_id", "kp_margin", "kp_total"])
    f = pd.concat(rows, ignore_index=True)
    f["date"] = pd.to_datetime(f["DateOfGame"])
    f["kp_margin"] = f["HomePred"] - f["VisitorPred"]
    f["kp_total"] = f["HomePred"] + f["VisitorPred"]
    g = b[["game_id", "date", "home_id", "away_id"]]
    same = g.merge(f, left_on=["date", "home_id", "away_id"], right_on=["date", "home_espn_id", "visitor_espn_id"])
    flip = g.merge(f, left_on=["date", "home_id", "away_id"], right_on=["date", "visitor_espn_id", "home_espn_id"])
    flip["kp_margin"] = -flip["kp_margin"]
    out = pd.concat([same, flip])[["game_id", "kp_margin", "kp_total"]]
    return out.drop_duplicates("game_id")


def ats(d: pd.DataFrame, edge_col: str, result_col: str, line_col: str) -> pd.Series:
    """Record betting the model's side whenever it disagrees with the line (pushes excluded)."""
    side = np.sign(d[edge_col])
    res = np.sign(d[result_col] - d[line_col]) * side
    res = res[(res != 0) & (side != 0)]
    n = len(res)
    w = int((res > 0).sum())
    return pd.Series({"bets": n, "win%": w / n if n else np.nan,
                      "roi%": 100 * (w * 100 / 110 - (n - w)) / n if n else np.nan})


def table(rows: dict) -> str:
    df = pd.DataFrame(rows).T
    cols = list(df.columns)
    out = ["| | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
    for k, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("" if pd.isna(v) else (f"{v:.1%}" if c == "win%" else
                                                 f"{int(v):,}" if c in ("bets", "games") else f"{v:.2f}"))
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def bad_months(b: pd.DataFrame, limit: float = 0.03) -> pd.Series:
    """Data check: share of games per (season, month) where the closing line and KenPom favor different teams by
    3+ points each. Normally 0-1%; Nov 2013 is 8% (mismatched lines in ESPN's feed). Months above `limit` are
    dropped from the betting results. Uses KenPom, not our model, so it doesn't favor the model."""
    d = b.dropna(subset=["home_spread", "kp_margin"])
    flip = (np.sign(d["line_margin"]) != np.sign(d["kp_margin"])) & (d["line_margin"].abs() > 3) & \
           (d["kp_margin"].abs() > 3)
    r = flip.groupby([d["season"], d["month"]]).mean()
    return r[r > limit]


def report(b: pd.DataFrame, start: int, end: int) -> str:
    bad = bad_months(b)
    drop = b.set_index(["season", "month"]).index.isin(bad.index)
    b = b.copy()
    b.loc[drop, ["home_spread", "total", "open_home_spread", "open_total", "line_margin"]] = np.nan
    L = b.dropna(subset=["home_spread"]).copy()
    L["edge"] = L["pred_margin"] - L["line_margin"]        # + = model likes home more than the line
    T = b.dropna(subset=["total"]).copy()
    T["tedge"] = T["pred_total"] - T["total"]
    mid = (start + end + 1) // 2
    md = [f"# Backtest {start}-{end}", "", SUMMARY, "",
          "Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from "
          "KenPom's preseason ratings. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch "
          "predicted score. Records are against the closing line at -110 (break-even 52.4%).", "",
          "Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of "
          "games): " + (", ".join(f"{pd.Timestamp(2000, m, 1):%b} {s - (m >= 11)} ({v:.0%})"
                                  for (s, m), v in bad.items()) or "none") + ".", ""]

    # 1. accuracy on games that have all three
    A = L.dropna(subset=["kp_margin"])
    md += ["## Accuracy (games with a line and a KenPom prediction)", "",
           table({
               "model": {"games": len(A), "margin MAE": (A["pred_margin"] - A["margin"]).abs().mean(),
                         "total MAE": (A["pred_total"] - A["points"]).abs().mean()},
               "closing line": {"games": len(A), "margin MAE": (A["line_margin"] - A["margin"]).abs().mean(),
                                "total MAE": (A["total"] - A["points"]).abs().mean()},
               "KenPom": {"games": len(A), "margin MAE": (A["kp_margin"] - A["margin"]).abs().mean(),
                          "total MAE": (A["kp_total"] - A["points"]).abs().mean()},
           }), ""]

    # 2. how much of the model's disagreement shows up in results
    def slope(d, res, line, model):
        x = d[model] - d[line]
        y = d[res] - d[line]
        return (x * y).sum() / (x * x).sum()
    md += ["## How much of the model's disagreement with the line shows up in the result", "",
           "Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; "
           "1 = trust the model fully. Same idea as the NFL model's blend weight.", "",
           "| season | margin | total |", "|---|---:|---:|"]
    for s, d in L.groupby("season"):
        t = T[T["season"] == s]
        md.append(f"| {s} | {slope(d, 'margin', 'line_margin', 'pred_margin'):.2f} | "
                  f"{slope(t, 'points', 'total', 'pred_total'):.2f} |")
    md += [f"| all | {slope(L, 'margin', 'line_margin', 'pred_margin'):.2f} | "
           f"{slope(T, 'points', 'total', 'pred_total'):.2f} |", ""]

    # 3. ATS / OU by edge size, train vs test
    for name, D, e, res, line in [("Spreads", L, "edge", "margin", "line_margin"),
                                  ("Totals", T, "tedge", "points", "total")]:
        rows = {}
        for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 99)]:
            for part, P in [(f"{start}-{mid - 1}", D[D["season"] < mid]), (f"{mid}-{end}", D[D["season"] >= mid])]:
                sel = P[(P[e].abs() >= lo) & (P[e].abs() < hi)]
                rows[f"edge {lo}-{hi if hi < 99 else '+'} pts, {part}"] = ats(sel, e, res, line)
        md += [f"## {name}: betting the model's side vs the closing line, by size of disagreement", "",
               table(rows), ""]
        rows = {}
        for m in [11, 12, 1, 2, 3]:
            sel = D[(D["month"] == m) & (D[e].abs() >= 3)]
            rows[pd.Timestamp(2000, m, 1).strftime("%b")] = ats(sel, e, res, line)
        md += [f"### {name}, edge 3+ points, by month", "", table(rows), ""]
        rows = {s: ats(d[d[e].abs() >= 3], e, res, line) for s, d in D.groupby("season")}
        md += [f"### {name}, edge 3+ points, by season", "", table(rows), ""]

    # 4. line movement
    M = L.dropna(subset=["open_home_spread"])
    M = M[M["open_home_spread"] != M["home_spread"]]
    if len(M):
        oedge = M["pred_margin"] + M["open_home_spread"]            # model vs opener
        moved = (M["open_home_spread"] - M["home_spread"])          # + = line moved toward home
        hit = (np.sign(oedge) == np.sign(moved))
        md += ["## Line movement: does the model predict which way the opener moves?", "",
               f"{len(M):,} games where the line moved (seasons {', '.join(map(str, sorted(M['season'].unique())))}). "
               f"The line moved toward the model's side in {hit.mean():.1%}; "
               f"{hit[oedge.abs() >= 3].mean():.1%} when the model disagreed with the opener by 3+.", ""]
        Mo = M.assign(oedge=oedge)
        rows = {}
        for lo in [0, 2, 3, 4, 6]:
            sel = Mo[Mo["oedge"].abs() >= lo]
            rows[f"edge vs opener {lo}+"] = ats(sel.assign(line_o=-sel["open_home_spread"]), "oedge", "margin", "line_o")
        md += ["Betting the model's side at the **opening** number:", "", table(rows), ""]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    md = report(load(a.start, a.end), a.start, a.end)
    with open(REPORT, "w") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
