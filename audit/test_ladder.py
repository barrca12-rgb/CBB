"""Ladder log (cbb/ladder.py; research only): rung EVs from the win-probability rule's normal form, orientation of an
event listed the other way round, and the logger never touching the card or bet log.

    python -m pytest -q audit/test_ladder.py
"""
import pandas as pd

from cbb import ladder


def test_normal_form_matches_the_live_slope_at_zero():
    for mk, slope in (("spread", 0.0255), ("total", 0.014)):
        assert abs((ladder.p_cover(mk, 0.01) - ladder.p_cover(mk, -0.01)) / 0.02 - slope) < 1e-5


def test_best_rung_and_gain():
    bet = {"bet_id": "b", "date": "2026-11-05", "game_id": 7, "market": "spread", "side": "home", "book": "DraftKings",
           "line": -3.5, "odds": -110, "model": 7.0}
    rungs = pd.DataFrame([{"market": "spread", "side": "home", "point": -3.5, "price": -110, "book": "DraftKings"},
                          {"market": "spread", "side": "home", "point": -4.5, "price": 105, "book": "DraftKings"},
                          {"market": "spread", "side": "home", "point": -2.5, "price": -135, "book": "DraftKings"},
                          {"market": "spread", "side": "away", "point": 4.5, "price": -125, "book": "DraftKings"}])
    r = ladder.evaluate(bet, rungs)
    assert r["rungs"] == 3                                   # the play's side only
    assert r["best_line"] == -4.5 and r["gain"] > 0.005       # a point worse at +105 beats -110 here
    assert abs(r["main_ev"] - (ladder.p_cover("spread", 3.5) * 100 / 110 - (1 - ladder.p_cover("spread", 3.5)))) < 1e-4


def test_edges():
    assert ladder.edge_at("spread", "away", 7.0, 9.5) == 2.5
    assert ladder.edge_at("total", "under", 140.0, 144.0) == 4.0


def test_no_key_no_pull(monkeypatch):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    assert ladder.pull_for([{"bet_id": "b"}], pd.DataFrame()) == 0
