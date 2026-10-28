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


def test_parser_passes_a_started_games_quotes_to_the_log_but_never_to_the_card():
    """The Odds API keeps listing a game after the feed's start; the card never prices it, and the log receives its
    quotes (kept only inside a watch window; the protocol's close excludes them as observed after their own start)."""
    from cbb import odds_api
    now = pd.Timestamp.now(tz="UTC")
    def ev(i, start):
        return {"id": i, "commence_time": start.isoformat(), "home_team": "H", "away_team": "A",
                "bookmakers": [{"key": "draftkings", "last_update": now.isoformat(), "markets": [
                    {"key": "totals", "last_update": now.isoformat(), "outcomes": [
                        {"name": "Over", "point": 154.0, "price": -110}, {"name": "Under", "point": 154.0, "price": -110}]}]}]}
    rows, unmatched = odds_api.parse([ev("pre", now + pd.Timedelta(hours=1)), ev("live", now - pd.Timedelta(minutes=5))],
                                     lookup={"h": 1, "a": 2})
    assert list(rows["sgo_event"]) == ["oa:pre"]                    # the card: pregame only, as before
    assert {o["event_id"] for o in odds_api.parse.observations} == {"oa:pre", "oa:live"}
    assert not unmatched


# ---- pregame validity gate (diagnostic; the protocol's value is unchanged) -------------------------------------------
def _pg(before_s, tip, starts=None, cutoff=T0):
    return clv_primary.pregame(147.0, cutoff, before_s, starts or [cutoff], tip)[0]


def test_pregame_verified_when_the_last_quote_precedes_the_actual_tip():
    assert _pg([120, 300], T0 + pd.Timedelta(minutes=4)) == "verified"


def test_feed_start_a_few_minutes_late_is_caught_by_the_actual_tip():
    """Feed start T0, but the ball went up 5 minutes earlier: a quote 2 minutes before the feed's start is in play."""
    assert _pg([120, 600], T0 - pd.Timedelta(minutes=5)) == "in-play risk"
    assert _pg([120], T0 - pd.Timedelta(seconds=150)) == "in-play risk"      # inside the 60 s margin
    assert _pg([120], T0 - pd.Timedelta(seconds=59)) == "verified"       # last quote 61 s before the tip


def test_feed_start_an_hour_early_is_pregame_but_early():
    assert _pg([120], T0 + pd.Timedelta(minutes=62)) == "early"


def test_without_an_actual_tip_a_close_is_never_called_verified():
    assert _pg([120], None) == "unverified"
    assert _pg([120], None, starts=[T0, T0 - pd.Timedelta(minutes=5)]) == "in-play risk"   # ESPN 5 min earlier


def test_no_computed_close_is_not_checked():
    assert clv_primary.pregame(np.nan, T0, [], [T0], None)[0] == "n/a"


def test_first_play_wallclock_is_the_actual_tip():
    from cbb import tipoff
    s = {"plays": [{"wallclock": "2024-04-09T01:22:08Z", "period": {"number": 1}},
                   {"wallclock": "2024-04-09T01:21:33Z", "period": {"number": 1}},
                   {"wallclock": "2024-04-09T02:30:00Z", "period": {"number": 2}}]}
    assert tipoff.first_play(s) == pd.Timestamp("2024-04-09T01:21:33Z")
    assert tipoff.first_play({"plays": [{"period": {"number": 1}}]}) is None


def test_closing_file_fallback_supplies_a_start_only_and_never_a_close(tmp_path):
    """When no quote was observed before its own start, the independent trace takes the cutoff from closing.csv; no
    quote can then pass the in-play rule, so neither the trace nor the protocol has a close."""
    from audit import clv_example
    obs = pd.DataFrame([at(5, T0, 149.0), at(8, T0, 149.0, "Caesars")])          # all observed after T0
    (tmp_path / "obs").mkdir()
    obs.to_csv(tmp_path / "obs" / "2026-11-01.csv", index=False)
    closing_with(T0).to_csv(tmp_path / "closing.csv", index=False)
    rc = clv_example.recompute(bet(), KEY, lines_dir=str(tmp_path))
    assert rc["cutoff_source"].startswith("closing.csv") and rc["close"] is None and rc["books"] == 0
    r = close(obs.to_dict("records"), closing=closing_with(T0))
    assert np.isnan(r["close_primary"]) and r["cutoff_source"] == "closing.csv start"
