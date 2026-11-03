"""A game ESPN relists the other way round after a play is logged (Nov 2: Purdue +4.5 logged with Purdue at home;
ESPN then listed Gonzaga at home at the neutral site). The play is graded by team and shown from the card's side.

    python -m pytest -q audit/test_relisted_home.py
"""
import pandas as pd

from cbb import report_html, tracker

BID = "2026-11-02|7|spread|home"


def _log(tmp_path, monkeypatch):
    row = {c: None for c in tracker.COLS}
    row.update(bet_id=BID, date="2026-11-02", game_id=7, market="spread", pick="Purdue +4.5", side="home",
               home_id=2509, away_id=2250, home="Purdue", away="Gonzaga", line=4.5, alert_line=4.5, odds=-110.0,
               book="DraftKings", edge=2.6, model=-1.9, stake=1.0, placed="yes", logged_at="2026-10-26T02:28:35+00:00",
               status="open")
    p = tmp_path / "bets.csv"
    pd.DataFrame([row]).reindex(columns=tracker.COLS).to_csv(p, index=False)
    monkeypatch.setattr(tracker, "BETS", str(p))
    monkeypatch.setattr(tracker, "PRERULE", str(tmp_path / "none.csv"))


def test_graded_by_team_when_espn_relists_home(tmp_path, monkeypatch):
    _log(tmp_path, monkeypatch)
    sc = pd.DataFrame([{"game_id": 7, "state": "post", "home_id": 2250, "away_id": 2509, "home_score": 80, "away_score": 74}])
    assert tracker.settle(sc) == 1
    r = tracker.load("all").iloc[0]
    assert (r["home_score"], r["away_score"], r["result"]) == (74.0, 80.0, "L")   # Purdue lost by 6: +4.5 loses
    # unchanged when the scoreboard keeps the bet's own orientation
    _log(tmp_path, monkeypatch)
    tracker.settle(sc.assign(home_id=2509, away_id=2250, home_score=74, away_score=80))
    assert tracker.load("all").iloc[0]["result"] == "L"


def test_card_shows_the_team_actually_bet(tmp_path, monkeypatch):
    _log(tmp_path, monkeypatch)
    card = pd.DataFrame([{"game_id": 7, "home_id": 2250, "away_id": 2509, "home": "Gonzaga", "away": "Purdue",
                          "model_margin": 3.5, "spread_logged_side": "home", "spread_logged_line": 4.5,
                          "spread_logged_odds": -110.0, "spread_now_edge": 8.0}])
    c = report_html._logged_sides(card, pd.Timestamp("2026-11-02")).iloc[0]
    assert c["spread_logged_side"] == "away" and c["spread_logged_bid_side"] == "home"
    assert abs(c["spread_now_edge"] - 1.0) < 1e-9                                    # Purdue +4.5 vs model Purdue +3.5


def test_pages_built_before_the_fix_are_corrected(tmp_path, monkeypatch):
    from cbb import live_refresh
    _log(tmp_path, monkeypatch)
    data = {"games": [{"game_id": 7, "home_id": 2250, "away_id": 2509, "model_margin": 3.5, "spread_logged_side": "home",
                       "spread_logged_line": 4.5, "spread_logged_odds": -110.0, "spread_now_edge": 8.0}]}
    live_refresh._relisted(data, "2026-11-02")
    g = data["games"][0]
    assert g["spread_logged_side"] == "away" and g["spread_logged_bid_side"] == "home" and abs(g["spread_now_edge"] - 1.0) < 1e-9
    live_refresh._relisted(data, "2026-11-02")
    assert data["games"][0]["spread_logged_side"] == "away"                  # applied once, not flipped back
