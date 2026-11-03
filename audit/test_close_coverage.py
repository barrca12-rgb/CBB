"""Closing-line coverage fixes (Chad, Nov 3; approved the extra SGO pulls):
1. A game the feed starts after midnight ET is filed under the next day's key; its quotes now count for the bet
   (Nov 2: Hawai'i-Seattle U, 11:59 pm ET on ESPN, had no close).
2. Games in their last 20 minutes that The Odds API does not carry are polled from SportsGameOdds by event id
   (Nov 2: six plays on SGO-only games had no close).

    python -m pytest -q audit/test_close_coverage.py
"""
import pandas as pd

from audit import forward_eval as fe
from cbb import poll_targets, quotelog


def test_next_day_key_is_read_for_the_bet():
    o = fe.load_obs(pd.DataFrame([{"observed_at": "2026-11-03T04:50:00Z", "source": "sgo", "event_id": "x",
                                   "game_key": "2026-11-03|62|2547", "start": "2026-11-03T05:00:00Z", "book": "BetMGM",
                                   "market": "total", "side": "over", "line": 142.5, "price": -110,
                                   "source_updated_at": "2026-11-03T04:49:30Z", "quote_age_s": 30, "status": "available"}]))
    by = dict(tuple(o.groupby("game_key", sort=False)))
    bet = {"date": "2026-11-02", "home_id": 62, "away_id": 2547}
    assert len(fe.game_obs(by, bet, o.iloc[0:0])) == 1
    assert len(fe.game_obs(by, dict(bet, date="2026-11-01"), o.iloc[0:0])) == 0     # never two days apart
    assert quotelog.next_day_key("2026-11-02|62|2547") == "2026-11-03|62|2547"


def test_sgo_close_poll_asks_only_the_games_the_odds_api_lacks(monkeypatch):
    from cbb import odds
    t = pd.Timestamp("2026-11-02T23:15:00Z")
    monkeypatch.setattr(quotelog, "now", lambda: t)
    monkeypatch.setattr(quotelog, "_signal_starts", lambda: {"2026-11-02|150|349": pd.Timestamp("2026-11-02T23:30:00Z"),
                                                           "2026-11-02|1|2": pd.Timestamp("2026-11-02T23:30:00Z"),
                                                           "2026-11-02|3|4": pd.Timestamp("2026-11-03T02:00:00Z")})
    monkeypatch.setattr(poll_targets, "_sgo_events", lambda keys: {k: "EV" + k.split("|")[1] for k in keys})
    asked, logged = [], []

    def fake_fetch(api_key=None, max_events=1500, event_ids=None):
        asked.append(event_ids)
        odds.fetch.events, odds.fetch.observations, odds.fetch.observed_at, odds.fetch.usage = len(event_ids), [], t, {}
    monkeypatch.setattr(odds, "fetch", fake_fetch)
    monkeypatch.setattr(quotelog, "poll", lambda *a, **k: "pid")
    monkeypatch.setattr(quotelog, "observations", lambda rows, pid, at, games: logged.append(sorted(games)) or 0)
    oa = [{"game_key": "2026-11-02|1|2", "status": "available", "line": 140.5}]       # The Odds API carries game 1|2
    poll_targets._sgo_close({"2026-11-02|150|349", "2026-11-02|1|2", "2026-11-02|3|4"}, oa)
    assert asked == [["EV150"]]                        # only the SGO-only game inside its last 20 minutes
    assert logged == [["2026-11-02|150|349"]]


def test_sgo_close_poll_stands_down_if_the_event_filter_is_ignored(monkeypatch):
    from cbb import odds
    t = pd.Timestamp("2026-11-02T23:15:00Z")
    monkeypatch.setattr(quotelog, "now", lambda: t)
    monkeypatch.setattr(quotelog, "_signal_starts", lambda: {"2026-11-02|150|349": pd.Timestamp("2026-11-02T23:30:00Z")})
    monkeypatch.setattr(poll_targets, "_sgo_events", lambda keys: {k: "EV" for k in keys})
    polls, logged = [], []

    def fake_fetch(api_key=None, max_events=1500, event_ids=None):
        odds.fetch.events, odds.fetch.observations, odds.fetch.observed_at, odds.fetch.usage = 140, [{}], t, {}
    monkeypatch.setattr(odds, "fetch", fake_fetch)
    monkeypatch.setattr(quotelog, "poll", lambda src, status, *a, **k: polls.append((src, status)) or "pid")
    monkeypatch.setattr(quotelog, "observations", lambda *a, **k: logged.append(1) or 0)
    poll_targets._sgo_close({"2026-11-02|150|349"}, [])
    assert polls == [("sgo-targeted", "error")] and logged == []
