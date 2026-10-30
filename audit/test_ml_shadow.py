"""Opening-moneyline shadow (research/moneyline/shadow): the quote in force when a play is logged, either team
orientation, a missing quote never priced, Shin CLV against the close, and grading on the result.

    python -m pytest -q audit/test_ml_shadow.py
"""
import pandas as pd
import pytest

from cbb import tracker
from research.moneyline.shadow import run


def test_shadow_records_and_grades(tmp_path, monkeypatch):
    ml = tmp_path / "ml"
    ml.mkdir()
    # the feed lists Miami (2390) as home; our card has Florida (57) home. Florida is our side (home), -5.5.
    pd.DataFrame([
        {"observed_at": "2026-11-01T15:00:00+00:00", "start": "2026-11-02T23:00:00Z", "home_id": 2390, "away_id": 57, "book": "DraftKings", "home_ml": 180, "away_ml": -218, "status": "ok"},
        {"observed_at": "2026-11-01T15:00:00+00:00", "start": "2026-11-02T23:00:00Z", "home_id": 2390, "away_id": 57, "book": "BetMGM", "home_ml": None, "away_ml": None, "status": "missing"},
        {"observed_at": "2026-11-01T15:00:00+00:00", "start": "2026-11-02T23:00:00Z", "home_id": 2390, "away_id": 57, "book": "Caesars", "home_ml": 185, "away_ml": -210, "status": "ok"},
        {"observed_at": "2026-11-02T22:50:00+00:00", "start": "2026-11-02T23:00:00Z", "home_id": 2390, "away_id": 57, "book": "DraftKings", "home_ml": 200, "away_ml": -245, "status": "ok"},
        {"observed_at": "2026-11-02T22:50:00+00:00", "start": "2026-11-02T23:00:00Z", "home_id": 2390, "away_id": 57, "book": "Caesars", "home_ml": 200, "away_ml": -240, "status": "ok"},
    ]).to_csv(ml / "2026-11-01.csv", index=False)
    monkeypatch.setattr(run, "ML", str(ml))
    monkeypatch.setattr(run, "REPORTS", str(tmp_path))
    bets = pd.DataFrame([{c: None for c in tracker.COLS} | {
        "bet_id": "2026-11-02|9|spread|home", "date": "2026-11-02", "game_id": 9, "market": "spread", "pick": "Florida -5.5",
        "side": "home", "home_id": 57, "away_id": 2390, "line": -5.5, "odds": -110, "book": "BetMGM", "edge": 3.0, "model": 8.5,
        "stake": 1.0, "logged_at": "2026-11-01T16:00:00+00:00", "status": "settled", "home_score": 80, "away_score": 70,
        "profit": 0.909, "result": "W"}])
    monkeypatch.setattr(tracker, "load", lambda which="v1": bets)
    p = run.build().iloc[0]
    assert p["ml_state"] == "no quote at the play's book"          # BetMGM missing: never priced
    assert p["ml_best_price"] == -210 and p["ml_best_book"] == "Caesars"
    assert p["dog_fav"] == "favorite" and p["ml_won"] == True
    assert p["ml_best_units"] == pytest.approx(100 / 210)
    assert p["ml_best_clv_pp"] > 0                                   # Florida shortened to about -240 by the close
    assert p["p_conversion"] > 0.75 and p["p_margin"] > 0.75
