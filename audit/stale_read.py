"""Stale-input cell (Chad's Nov 1 brief, item 1): logged plays split by the freshness stamp they were built on
(bets/inputs.csv, cbb/freshness.py), each state its own cell: record, units and CLV at the primary close
(clv_primary.attach, as in audit/band_b_read.py; shown under "Alert CLV"). v1 and band B
are reported separately; plays logged before the stamp existed (no row in bets/inputs.csv) are "not stamped". The
Jan 15 and Mar 14 reads report it. Read-only.

    python -m audit.stale_read [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

from cbb import clv_primary, freshness, tracker
from audit.band_b_read import _rec


def read(through: str | None = None) -> dict:
    b = tracker.load("all")
    if through:
        b = b[b["date"] <= through]
    b = clv_primary.attach(b) if len(b) else b
    b = b[b["status"] != "void"]
    st = pd.read_csv(freshness.INPUTS, dtype=str) if os.path.exists(freshness.INPUTS) else pd.DataFrame(columns=freshness.INPUT_COLS)
    st = st.drop_duplicates("bet_id", keep="first")
    b = b.merge(st[["bet_id", "state", "stale_inputs"]], on="bet_id", how="left")
    b["state"] = b["state"].fillna("not stamped")
    out = {"through": through or "all"}
    for lab, sub in (("v1", b[b["bet_type"].fillna("") != tracker.BAND_B]), ("band B", b[b["bet_type"].fillna("") == tracker.BAND_B])):
        cells = {}
        for s in ("fresh", "stale", "unknown", "not stamped"):
            x = sub[sub["state"] == s]
            r = _rec(x)
            if s == "stale" and len(x):
                r["stale inputs"] = x["stale_inputs"].fillna("").str.split("; ").explode().str.split(" ").str[0].value_counts().to_dict()
            cells[s] = r
        out[lab] = cells
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    print(json.dumps(read(ap.parse_args().through), indent=1, default=str))
