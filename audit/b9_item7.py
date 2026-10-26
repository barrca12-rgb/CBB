"""Protocol item 7: historical reporting corrections, on the production model's walk-forward frame (audit/out).

1. Opener orientation without the close: each opener is checked against the moneylines stored with it
   (lines_hist.orient_openers; 2024-26 from audit/b8_open_meta.py, 2014-17 from the "Opening" row). Reports the
   cases resolved, the unresolved residue, and spreads/totals vs the opener under each rule, beside the original
   close-based cleaning (shown only for comparison).
2. Referee correction (evaluation only): totals vs the opener with crew inputs set to 0 under the existing walk-forward
   weights (no refit), because crews are not posted when openers are.

    python -m audit.b9_item7   -> audit/out/item7_*.csv and audit/out/item7.md
"""
from __future__ import annotations

import os

import pandas as pd

from audit.a2_timing import score
from audit.common import OUT, frame
from cbb import lines_hist

SEASONS = [2014, 2015, 2016, 2017, 2024, 2025, 2026]
RULES = {"close": "original cleaning (uses the later close; comparison only)",
         "none": "no orientation check (plausibility drop only)",
         "flip": "moneyline orientation: mis-oriented openers corrected",
         "drop": "moneyline orientation: mis-oriented openers dropped",
         "drop_residue": "moneyline orientation: mis-oriented and uncheckable openers dropped"}


def meta(s: int) -> pd.DataFrame | None:
    p = os.path.join(OUT, f"espn_open_meta_{s}.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def openers(rule: str) -> tuple[pd.DataFrame, list]:
    parts, counts = [], []
    for s in SEASONS:
        l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{s}.csv"))
        if rule == "none":   # no moneylines given, so nothing is checkable: plausibility drop only
            c, n = lines_hist.consensus(l.assign(home_ml=float("nan"), away_ml=float("nan")), "flip", None), None
        else:
            c = lines_hist.consensus(l, rule, meta(s))
            n = getattr(lines_hist.consensus, "counts", None) if rule != "close" else None
        if n is not None and rule == "flip":
            counts.append({"season": s, **n})
        parts.append(c[["game_id", "open_home_spread", "open_total"]])
    return pd.concat(parts, ignore_index=True), counts


def with_openers(w: pd.DataFrame, op: pd.DataFrame) -> pd.DataFrame:
    return w.drop(columns=["open_home_spread", "open_total"]).merge(op, on="game_id", how="left")


if __name__ == "__main__":
    base = frame(tag="base")
    rz = pd.read_pickle(os.path.join(OUT, "wf_refs_zero_at_open.pkl"))
    rows, counts = [], []
    for rule, label in RULES.items():
        op, n = openers(rule)
        counts += n
        rows += [dict(r, rule=rule, crews="as recorded") for r in score(with_openers(base, op), label)]
        rows += [dict(r, rule=rule, crews="0 at the open") for r in score(with_openers(rz, op), label) if r["market"] == "total"]
        print(rule, "done", flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "item7_rules.csv"), index=False)
    c = pd.DataFrame(counts)
    c.to_csv(os.path.join(OUT, "item7_orientation_counts.csv"), index=False)
    md = ["# Item 7: opener orientation and the referee correction", "",
          "## Openers checked against their own moneylines (no close used)", "", c.to_string(index=False), "",
          "## Spreads and totals vs the opener under each rule (production model)", "",
          t[["market", "seasons", "rule", "crews", "plays", "win%", "ROI%@-110"]].to_string(index=False), ""]
    with open(os.path.join(OUT, "item7.md"), "w") as f:
        f.write("\n".join(md))
    print("\n".join(md))
