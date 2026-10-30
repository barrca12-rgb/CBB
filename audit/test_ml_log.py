"""Moneyline log (cbb/card_features.py, research/moneyline/PLAN.md): every book's moneyline from the card's own pull,
change-only, and the card's plays are exactly what run_day.plays returns.

    python -m pytest -q audit/test_ml_log.py
"""
import pandas as pd

from cbb import card_features, run_day

T0 = pd.Timestamp("2026-11-01T15:00:00Z")


def _lines(dk_home=-218.0):
    return pd.DataFrame([{"book": "DraftKings", "start": "2026-11-02T23:00:00Z", "date": "2026-11-02", "home_id": 57,
                          "away_id": 2390, "home_spread": -5.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0,
                          "total": 159.5, "over_odds": -110.0, "under_odds": -110.0, "home_ml": dk_home, "away_ml": 180.0,
                          "pulled_at": T0.isoformat()},
                         {"book": "BetMGM", "start": "2026-11-02T23:00:00Z", "date": "2026-11-02", "home_id": 57,
                          "away_id": 2390, "home_spread": -5.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0,
                          "total": 159.5, "over_odds": -110.0, "under_odds": -110.0, "home_ml": None, "away_ml": None,
                          "pulled_at": T0.isoformat()}])


def test_change_only_log(tmp_path, monkeypatch):
    monkeypatch.setattr(card_features, "ML_DIR", str(tmp_path))
    assert card_features.log_moneylines(_lines(), T0) == 1                          # BetMGM has no moneyline: skipped
    assert card_features.log_moneylines(_lines(), T0 + pd.Timedelta(minutes=10)) == 0   # unchanged: nothing new
    assert card_features.log_moneylines(_lines(-225.0), T0 + pd.Timedelta(minutes=20)) == 1
    d = pd.read_csv(tmp_path / "2026-11-01.csv")
    assert list(d.columns) == card_features.ML_COLS and list(d["home_ml"]) == [-218.0, -225.0]


def test_card_plays_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(card_features, "ML_DIR", str(tmp_path))
    f = pd.DataFrame([{"game_id": 1, "date": pd.Timestamp("2026-11-02"), "start": "x", "home": "Florida", "away": "Miami",
                       "home_id": 57, "away_id": 2390, "neutral": False, "state": "pre", "final_margin": 9.0, "final_total": 160.0}])
    a = run_day.plays(f, _lines())
    b = card_features._plays_and_log(f, _lines())     # the wrapped call the card makes
    pd.testing.assert_frame_equal(a, b)
    assert (tmp_path / "latest.csv").exists()
