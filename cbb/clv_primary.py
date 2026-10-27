"""Closing-line value at the forward-test protocol's primary close (FORWARD_TEST_PROTOCOL.md section 7), for display:
the record page and the weekly chart show this, so they agree with the protocol's reads to the decimal.

The close is computed by the protocol's own code (audit/forward_eval.py: tip_cutoff, strict_close, to_side,
line_value), imported read-only: per eligible book, the last valid observation (available, feed timestamp at most
300 seconds old) made within 15 minutes before the tip cutoff; consensus = median across books. A play with no
valid observation in that window has no primary close (NaN), as in the protocol, and is counted as missing.

Read only: bets/bets.csv (and its grader's clv_pts, the per-book benchmark close) is never changed here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def primary(b: pd.DataFrame, obs: pd.DataFrame | None = None, closing: pd.DataFrame | None = None) -> pd.DataFrame:
    """bet_id, close_primary (signal's side), clv_primary (points, + = beat the close), books_primary."""
    from audit import forward_eval as fe
    import os
    if closing is None:
        p = os.path.join(fe.ROOT, "lines", "closing.csv")
        closing = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(
            columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])
    o = fe.load_obs(obs)
    by_game = dict(tuple(o.groupby("game_key", sort=False))) if len(o) and "game_key" in o else {}
    rows = []
    for _, r in b.iterrows():
        key = f"{r['date']}|{min(int(r['home_id']), int(r['away_id']))}|{max(int(r['home_id']), int(r['away_id']))}"
        og = by_game.get(key, o.iloc[0:0])
        cutoff, _ = fe.tip_cutoff(og, fe.fallback_start(closing, r))
        sc = fe.strict_close(og, r["market"], cutoff)
        close = fe.to_side(r, sc["close"])
        rows.append({"bet_id": r["bet_id"], "close_primary": close, "clv_primary": fe.line_value(r, close),
                     "books_primary": sc["books"]})
    return pd.DataFrame(rows, columns=["bet_id", "close_primary", "clv_primary", "books_primary"])


def attach(b: pd.DataFrame) -> pd.DataFrame:
    """The bet log with clv_pts and close_line replaced by the primary-close values (display copy only). Settled
    plays without a primary close show none. If the observations cannot be read, the copy is returned unchanged
    and marked, so a page never fails on it."""
    b = b.copy()
    try:
        p = primary(b).set_index("bet_id")
    except Exception as e:                       # never stop a page; say so
        print(f"Primary close unavailable ({e}); showing the grader's close.")
        b.attrs["clv_source"] = "grader"
        return b
    b["close_line"] = b["bet_id"].map(p["close_primary"])
    b["clv_pts"] = b["bet_id"].map(p["clv_primary"])
    b.loc[b["status"] != "settled", ["close_line", "clv_pts"]] = np.nan
    b.attrs["clv_source"] = "primary"
    return b
