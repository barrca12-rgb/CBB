"""The injury timing report survives two jobs pulling ESPN in the same second (Nov 2: health.csv got two ESPN rows
with one stamp at 17:30 UTC, and every timing report after failed on the duplicate). No network.

    python -m pytest -q audit/test_injury_timing.py
"""
import pandas as pd

from cbb import injury_sources


def _h(rows):
    return pd.DataFrame(rows, columns=["pulled_at", "source", "ok", "rows"])


def test_duplicate_espn_stamps_do_not_break_the_working_check():
    h = _h([("2026-11-02T17:20:00+00:00", "espn", True, 12), ("2026-11-02T17:20:00+00:00", "cbs", True, 5),
            ("2026-11-02T17:30:39+00:00", "espn", True, 13), ("2026-11-02T17:30:39+00:00", "espn", True, 14),
            ("2026-11-02T17:30:39+00:00", "cbs", True, 0)])
    on = injury_sources._online(h)
    # CBS empty while ESPN (larger count at the duplicated stamp) listed 14: a broken pull, so CBS is not online
    assert on["espn"] == pd.Timestamp("2026-11-02T17:20:00Z") and "cbs" not in on


def test_one_row_per_stamp_is_unchanged():
    h = _h([("2026-11-02T17:20:00+00:00", "espn", True, 12), ("2026-11-02T17:20:00+00:00", "cbs", True, 5)])
    on = injury_sources._online(h)
    assert on["cbs"] == pd.Timestamp("2026-11-02T17:20:00Z") and on["espn"] == pd.Timestamp("2026-11-02T17:20:00Z")
