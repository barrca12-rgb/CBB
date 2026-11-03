"""Tip-time conflicts (Chad, Nov 2: "sure up any remaining tip time conflicts"; protocol v2.5): the actual tip is
known while a game is on, a verified actual tip earlier than the scheduled cutoff ends the close there, and a play
whose actual tip is known reads "resolved".

    python -m pytest -q audit/test_tip_cutoff.py
"""
import pandas as pd

from audit import forward_eval as fe
from cbb import tipoff


def _plays(minutes: float):
    """A clean period-1 record: tip at 01:19:17, then one play per 20 game-seconds for `minutes` of wall clock."""
    t0 = pd.Timestamp("2026-11-03T01:19:17Z")
    n = int(minutes * 3) + 1
    return pd.DataFrame({"sequence_number": range(n), "period_number": 1,
                         "clock_display_value": [f"{(1200 - 20 * i) // 60}:{(1200 - 20 * i) % 60:02d}" for i in range(n)],
                         "type_text": ["Jumpball"] + ["Shot"] * (n - 1), "text": ["won"] + [""] * (n - 1),
                         "wallclock": [(t0 + pd.Timedelta(seconds=20 * i)).isoformat() for i in range(n)]})


def test_a_game_in_progress_has_a_usable_tip():
    sched = pd.Timestamp("2026-11-03T01:00:00Z")
    live = tipoff.classify(_plays(30), sched, final=False)
    assert live["quality"] == "jump ball" and live["tip"] == pd.Timestamp("2026-11-03T01:19:17Z")
    # a finished game still needs 60+ minutes on the wall clock
    assert tipoff.classify(_plays(30), sched, final=True)["quality"] == "ambiguous"


def test_an_earlier_actual_tip_becomes_the_cutoff_a_later_one_never_does():
    og = pd.DataFrame({"t": [pd.Timestamp("2026-11-03T01:00:00Z")], "st": [pd.Timestamp("2026-11-03T01:30:00Z")]})
    assert fe.tip_cutoff(og, None) == (pd.Timestamp("2026-11-03T01:30:00Z"), "latest pregame report")
    early = pd.Timestamp("2026-11-03T01:19:17Z")
    assert fe.tip_cutoff(og, None, early) == (early, "actual tip (ESPN play-by-play)")
    assert fe.tip_cutoff(og, None, pd.Timestamp("2026-11-03T01:45:00Z"))[0] == pd.Timestamp("2026-11-03T01:30:00Z")
    assert fe.tip_cutoff(og, None, pd.NaT)[0] == pd.Timestamp("2026-11-03T01:30:00Z")


def test_refresh_asks_for_started_open_games(tmp_path, monkeypatch):
    monkeypatch.setattr(tipoff, "CACHE", str(tmp_path / "tipoffs.csv"))
    asked = []
    monkeypatch.setattr(tipoff, "fetch", lambda g: asked.append(g) or {"tip": None, "quality": "missing", "reason": "x"})
    b = pd.DataFrame({"game_id": [1, 2, 3], "status": ["open", "open", "settled"], "date": ["2026-11-02"] * 3})
    sl = lambda d: pd.DataFrame({"game_id": [1, 2], "state": ["in", "pre"]})
    now = pd.Timestamp("2026-11-03T02:00:00Z")
    tipoff.refresh(b, now, slate=sl)
    assert sorted(asked) == [1, 3]                       # started open game and settled game; not the one yet to tip
    asked.clear()
    tipoff.refresh(b, now + pd.Timedelta(minutes=2), slate=sl)
    assert asked == []                                   # asked again only after RETRY_LIVE (5 min) / RETRY (1 h)
    tipoff.refresh(b, now + pd.Timedelta(minutes=6), slate=sl)
    assert asked == [1]
