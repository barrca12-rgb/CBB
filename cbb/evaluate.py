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


SUMMARY = """## Summary

**Promising historical results; live profitability and execution remain unverified.** The 2026-27 forward test
(FORWARD_TEST_PROTOCOL.md) is the evidence that counts; these tables come from seasons reused to design the model.

Model: ratings with 3-point luck regressed, plus KenPom, Barttorvik, Four Factors, rest, home edge, missing
players, market ratings from earlier closing lines, altitude, and referee crews.

Against the opener at the live card's cutoffs (spread edge 2.5+, total edge 3+; audit/b9_item7.py):

| | 2015-2017 | 2024-2026 |
|---|---:|---:|
| Spreads vs the opener, openers oriented by their own moneylines | 57.5% (2,039) | 58.1% (2,297) |
| Totals vs the opener, referee crews unknown at the open (inputs 0, weights unchanged) | 57.9% (3,611) | 56.2% (3,993) |

The spreads row sits in a **historical spread filtering-sensitivity range of about 56-58.7%**. That range spans
the two opener seasons sets above, the opener-orientation rules (57.5-58.7%: correcting, dropping, or dropping
uncheckable openers; 58.7% is 2024-26 with no orientation check, which is not stronger evidence), and the model
timing variants in audit/AUDIT_v2.md (56.2-57.6%). It is not a confidence interval, an expected live win rate, or
a result for totals.

| Against the closing line | Result | Bets |
|---|---:|---:|
| ATS vs closing line, edge 3+, 2020-2026 | 53.6% | 3,347 |
| Over/under vs closing line, edge 4+, 2020-2026 | 54.7% | 6,323 |
| Average miss on margin, 2020-2026 (model / closing line) | 8.88 / 8.84 | |
| Average miss on total, 2020-2026 (model / closing line) | 13.09 / 13.00 | |

Break-even at -110 is 52.4%. Closing lines exclude projection services listed as books (accuscore and others, Oct
2026 cleanup).

* **Openers:** since Oct 26, 2026 each opener is checked against the moneylines recorded with it (the shorter
  moneyline marks the favourite). An opener that favours the other team is corrected; nothing uses the later
  close. Openers within 1 point or without moneylines cannot be checked and are kept (counts in
  audit/out/item7.md). The earlier rule dropped openers that sat nearer the mirrored close.
* **Referees:** crews are usually posted near tip, after the openers, so opener tables for totals use crew inputs
  of 0 under the existing weights (no refit). With crews as recorded, totals vs the opener read 58.4% / 57.4%.
* **Caveats:** openers carry low limits; openers exist only for 2014-2017 and 2024-2026; historical opener plays
  were not priced, timed or filled; data cleaning removed several fake 70-85% edges, so treat anything above
  ~60% with suspicion."""


OPEN_META = os.path.join(os.path.dirname(__file__), "..", "audit", "out", "espn_open_meta_{}.csv")


def load(start: int, end: int, opener_rule: str = "flip") -> pd.DataFrame:
    """opener_rule: how openers are oriented (lines_hist.consensus). "flip" (the reporting rule since Oct 26, 2026):
    each opener is checked against the moneylines stored with it, never against the later close."""
    b = pd.read_csv(os.path.join(OUT_DIR, f"backtest_{start}_{end}.csv"), parse_dates=["date"])
    lines = []
    for s in range(start, end + 1):
        path = os.path.join(lines_hist.OUT, f"espn_{s}.csv")
        if os.path.exists(path):
            mp = OPEN_META.format(s)
            meta = pd.read_csv(mp) if os.path.exists(mp) else None
            lines.append(lines_hist.consensus(pd.read_csv(path), opener_rule, meta))
    if lines:
        b = b.merge(pd.concat(lines), on="game_id", how="left")
    b = b.merge(fanmatch(b), on="game_id", how="left")
    b["margin"] = b["home_pts"] - b["away_pts"]
    b["points"] = b["home_pts"] + b["away_pts"]
    b["line_margin"] = -b["home_spread"]          # line's expected home margin
    b["month"] = b["date"].dt.month
    return b


def final(b: pd.DataFrame) -> pd.DataFrame:
    """Swap in the second-stage projection (projection.py) as the model's numbers. The ratings-only numbers are kept
    as raw_margin / raw_total. The first season only trains the second stage, so it has no final numbers."""
    from . import projection
    w = projection.walk_forward(projection.add_features(b))
    w["raw_margin"], w["raw_total"] = w["pred_margin"], w["pred_total"]
    w["pred_margin"], w["pred_total"] = w["final_margin"], w["final_total"]
    return w.dropna(subset=["pred_margin"])


def final_at_open(b: pd.DataFrame) -> pd.DataFrame:
    """final(), but predictions use what is known when openers post: referee crews are not posted yet, so the crew
    inputs are 0 (an average crew), as on the live card. The walk-forward weights are fit exactly as in final()."""
    from . import projection
    tr = projection.add_features(b)
    te = tr.assign(ref_fouls=0.0, ref_pts=0.0)
    for d in (tr, te):
        d["margin"] = d["home_pts"] - d["away_pts"]
        d["points"] = d["home_pts"] + d["away_pts"]
    te["final_margin"], te["final_total"] = np.nan, np.nan
    for s in sorted(tr["season"].unique()):
        fit = tr[(tr["season"] < s) & (tr["season"] >= 2013)]
        if not len(fit):
            continue
        m = te["season"] == s
        cm = projection.ridge(fit[projection.MARGIN_FEATURES].to_numpy(float), fit["margin"].to_numpy(float))
        ct = projection.ridge(fit[projection.TOTAL_FEATURES].to_numpy(float), fit["points"].to_numpy(float))
        te.loc[m, "final_margin"] = cm[0] + te.loc[m, projection.MARGIN_FEATURES].to_numpy(float) @ cm[1:]
        te.loc[m, "final_total"] = ct[0] + te.loc[m, projection.TOTAL_FEATURES].to_numpy(float) @ ct[1:]
    te["raw_margin"], te["raw_total"] = te["pred_margin"], te["pred_total"]
    te["pred_margin"], te["pred_total"] = te["final_margin"], te["final_total"]
    return te.dropna(subset=["pred_margin"])


def winners(b: pd.DataFrame, mid: int) -> str:
    """Straight-up winner % for the model, the closing-line favorite and KenPom (games with all three)."""
    d = b.dropna(subset=["home_spread", "kp_margin"])
    d = d[(d["margin"] != 0) & (d["home_spread"] != 0)]
    rows = {}
    for part, P in [(f"through {mid - 1}", d[d["season"] < mid]), (f"{mid} on", d[d["season"] >= mid]), ("all", d)]:
        rows[part] = {"games": len(P),
                      "model": (np.sign(P["pred_margin"]) == np.sign(P["margin"])).mean(),
                      "line favorite": (np.sign(-P["home_spread"]) == np.sign(P["margin"])).mean(),
                      "KenPom": (np.sign(P["kp_margin"]) == np.sign(P["margin"])).mean()}
    df = pd.DataFrame(rows).T
    out = ["| | games | model | line favorite | KenPom |", "|---|---:|---:|---:|---:|"]
    for k, r in df.iterrows():
        out.append(f"| {k} | {int(r['games']):,} | {r['model']:.1%} | {r['line favorite']:.1%} | {r['KenPom']:.1%} |")
    return "\n".join(out)


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
          "KenPom's and Barttorvik's preseason ratings averaged. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch "
          "predicted score. Records are against the closing line at -110 (break-even 52.4%).", "",
          "Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of "
          "games): " + (", ".join(f"{pd.Timestamp(2000, m, 1):%b} {s - (m >= 11)} ({v:.0%})"
                                  for (s, m), v in bad.items()) or "none") + ".", ""]

    md += ["## Winners picked (straight up, pick'em lines excluded)", "", winners(b, mid), ""]

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
               **({"ratings only (before 2nd stage)": {
                   "games": len(A), "margin MAE": (A["raw_margin"] - A["margin"]).abs().mean(),
                   "total MAE": (A["raw_total"] - A["points"]).abs().mean()}} if "raw_margin" in A else {}),
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
    raw = load(a.start, a.end)
    md = report(final(raw), a.start, a.end)
    # totals against the opener as bettable at the open: crews unknown (referee fix, audit/AUDIT_v2.md)
    o = final_at_open(raw)
    o = o[o["season"] >= a.end - 2].dropna(subset=["open_total"])
    e = o["pred_total"] - o["open_total"]
    md += ("\n## Totals vs the opener with crews unknown (as at the open)\n\n" +
           table({f"edge {lo}+ pts, {a.end - 2}-{a.end}": ats(o.assign(e=e)[e.abs() >= lo], "e", "points", "open_total")
                  for lo in (3, 4)}) + "\n")
    with open(REPORT, "w") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
