"""A feed start-time correction arriving before, during and after the closing window (audit/CLV_VERIFICATION.md,
section 2): what the protocol's cutoff and close do (frozen, audit/forward_eval.py, through cbb/clv_primary.py), and
whether polling (cbb/quotelog.watched_games) follows the revised time. A missing window must come out unavailable,
never filled from quotes that were not captured. Synthetic data only.

    python -m pytest -q audit/test_tip_correction.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from audit.test_clv_primary import EMPTY_CLOSING, bet, ob
from cbb import clv_primary, quotelog

T0 = pd.Timestamp("2026-11-01T14:30:00Z")        # the feed's original start
T1 = T0 + pd.Timedelta(hours=1)                  # the corrected start
NOW = T1 + pd.Timedelta(hours=4)


def at(minute_offset_from_t0, start, line=147.5, book="DraftKings"):
    """An available, 30-second-old under quote observed at T0 + offset, carrying the feed's start `start`."""
    r = ob(book, "under", line, -110, 0, 30, start=start)
    t = T0 + pd.Timedelta(minutes=minute_offset_from_t0)
    r["observed_at"] = t.isoformat()
    r["source_updated_at"] = (t - pd.Timedelta(seconds=30)).isoformat()
    return r


def close(obs, closing=EMPTY_CLOSING):
    return clv_primary.primary(pd.DataFrame([bet()]), obs=pd.DataFrame(obs), closing=closing, now=NOW).iloc[0]


def closing_with(start):
    return pd.DataFrame([{"date": "2026-11-01", "home_id": 222, "away_id": 87, "book": "DraftKings", "home_spread": 7.5,
                          "total": 148.5, "start": start.isoformat(), "pulled_at": T0.isoformat()}])


# ---- the close ----------------------------------------------------------------------------------------------------
def test_correction_before_the_window_moves_the_cutoff_and_uses_the_new_window():
    obs = [at(-120, T0, 149.0), at(-60, T1, 148.5),                 # correction seen 60 min before the old start
           at(50, T1, 147.0), at(52, T1, 147.0, "Caesars")]         # 8-10 min before the new start
    r = close(obs)
    assert pd.Timestamp(r["cutoff"]) == T1 and r["close_primary"] == 147.0 and r["books_primary"] == 2


def test_correction_during_the_window_never_reuses_the_old_windows_quotes():
    obs = [at(-10, T0, 149.0), at(-8, T0, 149.0, "Caesars"),        # inside the OLD window
           at(-5, T1, 148.0)]                                       # correction arrives 5 min before the old start
    r = close(obs)                                                  # ... and nothing is captured near the new start
    assert pd.Timestamp(r["cutoff"]) == T1
    assert np.isnan(r["close_primary"]) and r["clv_status"] == "unavailable"
    assert r["clv_reason"] == "no quote observed in the 15 minutes before the tip cutoff"


def test_correction_during_the_window_with_the_new_window_captured():
    obs = [at(-10, T0, 149.0), at(-5, T1, 148.0), at(48, T1, 146.5), at(55, T1, 146.5, "Fanatics")]
    r = close(obs)
    assert pd.Timestamp(r["cutoff"]) == T1 and r["close_primary"] == 146.5 and r["books_primary"] == 2


def test_correction_after_the_old_start_seen_by_a_later_observation_moves_the_cutoff_without_inventing_quotes():
    obs = [at(-10, T0, 149.0), at(-4, T0, 149.0, "Caesars"),        # old window captured
           at(20, T1, 148.0)]                                       # feed relists with the new start 20 min after T0
    r = close(obs)                                                  # nothing captured in [T1-15, T1)
    assert pd.Timestamp(r["cutoff"]) == T1
    assert np.isnan(r["close_primary"]) and "no quote observed" in r["clv_reason"]


def test_correction_only_in_closing_csv_leaves_the_protocol_cutoff_and_is_flagged_as_a_conflict():
    """The protocol's cutoff is the start carried by the latest pregame OBSERVATION; a newer start that only reached
    closing.csv does not move it (frozen rule). The play is closed at the old window and flagged."""
    obs = [at(-10, T0, 149.0), at(-4, T0, 149.0, "Caesars")]
    r = close(obs, closing=closing_with(T1))
    assert pd.Timestamp(r["cutoff"]) == T0 and r["close_primary"] == 149.0
    assert r["tip_check"] == "conflict" and r["feed_gap_min"] == -60
    assert "latest reported start" in r["clv_reason"]


# ---- polling --------------------------------------------------------------------------------------------------------
@pytest.fixture
def world(tmp_path, monkeypatch):
    (tmp_path / "lines").mkdir()
    (tmp_path / "bets").mkdir()
    pd.DataFrame([dict(bet(), status="open", game_id=1)]).to_csv(tmp_path / "bets" / "bets.csv", index=False)
    monkeypatch.setattr(quotelog, "ROOT", str(tmp_path))
    monkeypatch.setattr(quotelog, "LINES", str(tmp_path / "lines"))
    monkeypatch.setattr(quotelog, "ALERTS", str(tmp_path / "bets" / "alert_log.csv"))

    def set_start(start):
        closing_with(start).to_csv(tmp_path / "lines" / "closing.csv", index=False)
    return set_start


KEY = "2026-11-01|87|222"


def watched(t):
    return KEY in quotelog.watched_games(t)


def test_polling_follows_a_correction_made_before_the_window(world):
    world(T1)                                                        # the card pull stored the corrected start
    assert not watched(T0 - pd.Timedelta(minutes=10))               # the old window is no longer polled
    assert watched(T1 - pd.Timedelta(minutes=15)) and watched(T1 - pd.Timedelta(minutes=1))
    assert not watched(T1)                                           # stops at the (new) start


def test_polling_switches_mid_window_when_the_correction_arrives(world):
    world(T0)
    assert watched(T0 - pd.Timedelta(minutes=10))                    # polling the old window
    world(T1)                                                        # correction stored 5 min before the old start
    assert not watched(T0 - pd.Timedelta(minutes=5))                 # pauses until the new window
    assert watched(T1 - pd.Timedelta(minutes=12))


def test_polling_resumes_after_the_old_start_once_the_new_start_is_stored(world):
    world(T0)
    assert not watched(T0 + pd.Timedelta(minutes=5))                 # treated as started
    world(T1)                                                        # a card pull 20 min after T0 stores T1
    assert watched(T1 - pd.Timedelta(minutes=10))


def test_without_a_stored_correction_polling_stops_at_the_old_start(world):
    world(T0)
    assert not watched(T1 - pd.Timedelta(minutes=10))                # nothing is polled near an unknown new start


# ---- tip-time conflict: polling and the diagnostic close at ESPN's start (Chad, Oct 28, option 2) ------------------
def espn_says(tmp, start):
    (tmp / "reports").mkdir(exist_ok=True)
    pd.DataFrame([{"game_id": 1, "start": start.isoformat()}]).to_csv(tmp / "reports" / "cbb_2026-11-01.csv", index=False)


@pytest.fixture
def conflict(world, tmp_path):
    world(T0)                                                        # the feed says T0
    espn_says(tmp_path, T1)                                          # ESPN says an hour later
    return tmp_path


def test_conflict_polls_the_window_before_espns_start_as_well(conflict):
    assert watched(T0 - pd.Timedelta(minutes=10))                    # the protocol's (feed) window, unchanged
    assert not watched(T0 + pd.Timedelta(minutes=10))                # between the two windows
    assert watched(T1 - pd.Timedelta(minutes=20)) and watched(T1 - pd.Timedelta(minutes=1))
    assert not watched(T1)                                           # stops at ESPN's start


def test_a_gap_under_30_minutes_adds_no_window(world, tmp_path):
    world(T0)
    espn_says(tmp_path, T0 + pd.Timedelta(minutes=20))
    assert not watched(T0 + pd.Timedelta(minutes=10))


def test_diagnostic_close_at_espns_start_leaves_the_protocol_close_unchanged(monkeypatch, tmp_path):
    from audit import forward_eval as fe
    espn_says(tmp_path, T1)
    monkeypatch.setattr(fe, "ROOT", str(tmp_path))
    obs = [at(-10, T0, 149.0), at(-4, T0, 149.0, "Caesars"),        # the feed's window (protocol close)
           at(48, T0, 146.5), at(52, T0, 146.0, "Fanatics")]       # the real window; quotes still carry the feed's T0
    r = close(obs)
    assert pd.Timestamp(r["cutoff"]) == T0 and r["close_primary"] == 149.0 and r["clv_primary"] == 0.5
    assert r["tip_check"] == "conflict" and r["books_espn_start"] == 2
    assert r["close_espn_start"] == 146.25 and r["clv_espn_start"] == pytest.approx(3.25)
    assert "diagnostic close at ESPN's start" in r["clv_reason"] and "not the protocol's CLV" in r["clv_reason"]


def test_diagnostic_close_is_unavailable_when_the_real_window_was_not_captured(monkeypatch, tmp_path):
    from audit import forward_eval as fe
    espn_says(tmp_path, T1)
    monkeypatch.setattr(fe, "ROOT", str(tmp_path))
    r = close([at(-10, T0, 149.0), at(-4, T0, 149.0, "Caesars")])
    assert r["close_primary"] == 149.0 and np.isnan(r["close_espn_start"]) and r["books_espn_start"] == 0
