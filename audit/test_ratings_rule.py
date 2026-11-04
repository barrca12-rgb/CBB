"""Complete-ratings rule (Chad, Nov 4; protocol v2.6 Appendix D): a play for a game on ET date D is logged and alerted
only once the ratings include every game before D. Before that it is pending: shown, never logged or alerted.

    python -m pytest -q audit/test_ratings_rule.py
"""
import pandas as pd
import pytest

from cbb import freshness, run_day, tracker

T = pd.Timestamp


def test_when_a_day_is_ready():
    first = T("2026-11-01")
    assert not run_day.ratings_ready("2026-11-04", T("2026-11-04T04:00Z"), "2026-11-03", first)   # 11 pm ET the night before
    assert not run_day.ratings_ready("2026-11-04", T("2026-11-04T10:30Z"), "2026-11-03", first)   # 5:30 am ET
    assert run_day.ratings_ready("2026-11-04", T("2026-11-04T11:30Z"), "2026-11-03", first)       # 6:30 am ET, file for D-1
    assert not run_day.ratings_ready("2026-11-04", T("2026-11-04T11:30Z"), "2026-11-02", first)   # file for D-1 not posted
    assert run_day.ratings_ready("2026-11-04", T("2026-11-04T15:05Z"), "2026-11-02", first)       # 10:05 am ET fallback
    assert run_day.ratings_ready("2026-11-01", T("2026-10-25T12:00Z"), None, first)               # opening day


def _f():
    return pd.DataFrame([{"game_id": 1, "date": "2026-11-05", "start": "2026-11-06T00:00:00Z", "home": "Home", "away": "Away",
                          "home_id": 20, "away_id": 10, "neutral": False, "state": "pre", "final_margin": 12.6,
                          "final_total": 140.0}])


def _lines():
    return pd.DataFrame([{"home_id": 20, "away_id": 10, "book": "DraftKings", "start": "2026-11-06T00:00:00Z",
                          "home_spread": -10.0, "home_spread_odds": -110, "away_spread_odds": -110, "total": 140.0,
                          "over_odds": -110, "under_odds": -110}])


@pytest.fixture
def rule_on(monkeypatch, tmp_path):
    monkeypatch.setattr(run_day, "RATINGS_RULE", True)
    monkeypatch.setattr(run_day, "OPENER_RULE", False)
    monkeypatch.setattr(run_day, "_season_first_day", lambda d: T("2026-11-01"))
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    monkeypatch.setitem(freshness.SEEN, "barttorvik", {"snapshot": "2026-11-04"})


def _at(monkeypatch, ts):
    real = pd.Timestamp.now
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: T(ts) if tz else T(ts).tz_localize(None)))


def test_the_night_before_a_play_is_pending_and_not_logged(rule_on, monkeypatch):
    _at(monkeypatch, "2026-11-05T02:00:00Z")                         # 9 pm ET Nov 4, the evening before
    c = run_day.plays(_f(), _lines(), fq=run_day.first_quotes("/nonexistent"))
    r = c.iloc[0]
    assert (r["spread_verdict"], r["spread_units"], r["spread_gate"]) == ("WATCH", 0.0, "ratings update")
    assert tracker.log(c, T("2026-11-05"), {"spread": 1.0, "total": 1.0}) == []


def test_game_morning_it_is_a_play(rule_on, monkeypatch):
    _at(monkeypatch, "2026-11-05T11:30:00Z")                         # 6:30 am ET on game day, Barttorvik for Nov 4 in use
    c = run_day.plays(_f(), _lines(), fq=run_day.first_quotes("/nonexistent"))
    assert c.iloc[0]["spread_verdict"] == "BET"
    assert len(tracker.log(c, T("2026-11-05"), {"spread": 1.0, "total": 1.0})) == 1
