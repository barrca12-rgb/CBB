"""Input-failure hold (Chad, Nov 4): a box-score download failure never silently rates the card on the preseason
prior while it still sends plays. A failed download uses the last good copy; with no valid copy after games have
been played, the day's plays are held (not logged, alerted or posted) and one phone alert says why. Before the
season's first game, no box scores is normal and holds nothing.

    python -m pytest -q audit/test_input_hold.py
"""
import json

import pandas as pd
import pytest

from cbb import card_features, data, notify, run_day, tracker

T = pd.Timestamp
DAY = T("2026-11-05")
SCHED = pd.DataFrame({"date": ["2026-11-03T00:00Z", "2026-11-06T00:00Z"], "status_type_completed": [True, False]})
PRESEASON = SCHED.assign(status_type_completed=[False, False])


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(run_day, "INPUT_HOLD", {})


def fail(*a, **k):
    raise OSError("HTTP Error 503")


def test_games_played_before():
    assert run_day.games_played_before(SCHED, DAY)
    assert not run_day.games_played_before(PRESEASON, DAY)
    assert run_day.games_played_before(None, DAY)                   # cannot tell: never silent


def test_download_failure_uses_the_last_good_copy_and_holds_nothing(monkeypatch):
    calls = []
    def sg(season, refresh=False):
        calls.append(refresh)
        if refresh:
            raise OSError("HTTP Error 503")
        return "hist", "tg"
    monkeypatch.setattr(data, "season_games", sg)
    assert run_day.load_box_scores(2027, DAY, SCHED, refresh=True) == ("hist", "tg")
    assert calls == [True, False] and run_day.INPUT_HOLD == {}


def test_no_valid_box_scores_after_games_were_played_holds_the_day(monkeypatch):
    monkeypatch.setattr(data, "season_games", fail)
    assert run_day.load_box_scores(2027, DAY, SCHED, refresh=True) == (None, None)
    assert "box scores could not be loaded" in run_day.INPUT_HOLD["2026-11-05"]


def test_before_the_first_game_no_box_scores_is_normal(monkeypatch):
    monkeypatch.setattr(data, "season_games", fail)
    assert run_day.load_box_scores(2027, DAY, PRESEASON, refresh=True) == (None, None)
    assert run_day.INPUT_HOLD == {}


def _f():
    return pd.DataFrame([{"game_id": 1, "date": "2026-11-05", "start": "2026-11-06T00:00:00Z", "home": "Home", "away": "Away",
                          "home_id": 20, "away_id": 10, "neutral": False, "state": "pre", "final_margin": 12.6,
                          "final_total": 140.0}])


def _lines():
    return pd.DataFrame([{"home_id": 20, "away_id": 10, "book": "DraftKings", "start": "2026-11-06T00:00:00Z",
                          "home_spread": -10.0, "home_spread_odds": -110, "away_spread_odds": -110, "total": 140.0,
                          "over_odds": -110, "under_odds": -110}])


@pytest.fixture
def card_env(monkeypatch, tmp_path):
    monkeypatch.setattr(run_day, "OPENER_RULE", False)
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))


def test_a_held_day_shows_the_play_but_never_logs_it(card_env):
    run_day.INPUT_HOLD["2026-11-05"] = "box scores could not be loaded (503)"
    c = run_day.plays(_f(), _lines(), fq=run_day.first_quotes("/nonexistent"))
    r = c.iloc[0]
    assert (r["spread_verdict"], r["spread_units"], r["spread_gate"], bool(r["spread_bandb"])) == ("WATCH", 0.0, "input failure", False)
    assert tracker.log(c, DAY, {"spread": 1.0, "total": 1.0}) == []
    # the missed-play safety net never alerts a held play
    assert not len(card_features.missed_plays(c.assign(date="2026-11-05"), _lines()))


def test_without_a_hold_the_same_play_is_a_bet(card_env):
    c = run_day.plays(_f(), _lines(), fq=run_day.first_quotes("/nonexistent"))
    assert c.iloc[0]["spread_verdict"] == "BET"


def test_one_phone_alert_per_held_day(card_env, monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(notify, "message", lambda title, body: sent.append((title, body)) or True)
    monkeypatch.setattr(run_day, "HOLD_ALERTED", str(tmp_path / "held.json"))
    run_day.INPUT_HOLD["2026-11-05"] = "box scores could not be loaded (503)"
    c = run_day.plays(_f(), _lines(), fq=run_day.first_quotes("/nonexistent"))
    assert run_day.alert_input_hold(DAY, c) and not run_day.alert_input_hold(DAY, c)
    assert len(sent) == 1 and "held" in sent[0][0] and "Home -10" in sent[0][1] and "Don't bet" in sent[0][1]
    assert json.load(open(tmp_path / "held.json")) == {"2026-11-05": "box scores could not be loaded (503)"}
