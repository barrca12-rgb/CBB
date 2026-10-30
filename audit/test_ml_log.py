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
    assert card_features.log_moneylines(_lines(), T0) == 2      # BetMGM quotes the game with no moneyline: "missing"
    assert card_features.log_moneylines(_lines(), T0 + pd.Timedelta(minutes=10)) == 0   # unchanged: nothing new
    assert card_features.log_moneylines(_lines(-225.0), T0 + pd.Timedelta(minutes=20)) == 1
    d = pd.read_csv(tmp_path / "2026-11-01.csv")
    assert list(d.columns) == card_features.ML_COLS
    assert list(d["status"]) == ["ok", "missing", "ok"] and d.loc[1, "home_ml"] != d.loc[1, "home_ml"]   # NaN, never a price
    assert list(d.loc[d["book"] == "DraftKings", "home_ml"]) == [-218.0, -225.0]
    assert d["pulled_at"].notna().all() and (d["date"] == "2026-11-02").all()


def test_card_plays_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(card_features, "ML_DIR", str(tmp_path))
    f = pd.DataFrame([{"game_id": 1, "date": pd.Timestamp("2026-11-02"), "start": "x", "home": "Florida", "away": "Miami",
                       "home_id": 57, "away_id": 2390, "neutral": False, "state": "pre", "final_margin": 9.0, "final_total": 160.0}])
    a = run_day.plays(f, _lines())
    b = card_features._plays_and_log(f, _lines())     # the wrapped call the card makes
    pd.testing.assert_frame_equal(a, b)
    assert (tmp_path / "latest.csv").exists()


def test_opener_favorites_logged_once_at_first_price(tmp_path, monkeypatch):
    """Only a book's FIRST priced moneyline on a game can be a signal; favorites only; EV +5% at Phi(margin / 11)."""
    monkeypatch.setattr(card_features, "ML_DIR", str(tmp_path))
    monkeypatch.setattr(card_features, "OPENER_FAV", str(tmp_path / "opener_fav.csv"))
    f = pd.DataFrame([{"game_id": 1, "date": pd.Timestamp("2026-11-02"), "home_id": 57, "away_id": 2390, "final_margin": 9.0}])
    # the log already holds DraftKings for this game; FanDuel posts its first moneyline now
    pd.DataFrame([{"home_id": 57, "away_id": 2390, "book": "DraftKings", "home_ml": -218.0, "away_ml": 180.0, "status": "ok"}]).to_csv(
        tmp_path / "latest.csv", index=False)
    lines = _lines().assign(book=["DraftKings", "FanDuel"], home_ml=[-218.0, -220.0], away_ml=[180.0, 180.0])
    before = card_features._priced_keys()
    assert card_features.log_opener_favs(f, lines, before, T0) == 1          # FanDuel only (DraftKings is not new)
    o = pd.read_csv(tmp_path / "opener_fav.csv")
    assert o.loc[0, "book"] == "FanDuel" and o.loc[0, "team_id"] == 57 and o.loc[0, "price"] == -220
    from scipy.stats import norm
    p = norm.cdf(9 / 11)
    assert abs(o.loc[0, "ev"] - (p * (100 / 220) - (1 - p))) < 1e-4
    assert card_features.log_opener_favs(f.assign(final_margin=2.0), lines, before, T0) == 0   # EV under +5%: nothing
    flipped = lines.assign(home_id=2390, away_id=57, home_ml=[180.0, 180.0], away_ml=[-218.0, -220.0])  # feed lists the teams the other way
    assert card_features.log_opener_favs(f, flipped, set(), T0) == 0       # no prior log: nothing counts as an opener
    assert card_features.log_opener_favs(f, flipped, {(2390, 57, "DraftKings")}, T0) == 1


def test_opener_favorites_graded(tmp_path, monkeypatch):
    from research.moneyline.opener_fav import run as ofr
    from research.moneyline.shadow import run as shadow
    pd.DataFrame([{"run_at": "2026-11-01T15:00:00+00:00", "date": "2026-11-02", "game_id": 1, "start": "2026-11-02T23:00:00Z",
                   "book": "FanDuel", "team_id": 57, "opp_id": 2390, "price": -220, "opp_price": 180, "p_model": 0.79, "ev": 0.15,
                   "model_margin": 9.0},
                  {"run_at": "2026-11-01T15:10:00+00:00", "date": "2026-11-02", "game_id": 1, "start": "2026-11-02T23:00:00Z",
                   "book": "Caesars", "team_id": 57, "opp_id": 2390, "price": -210, "opp_price": 175, "p_model": 0.79, "ev": 0.16,
                   "model_margin": 9.0}]).to_csv(tmp_path / "of.csv", index=False)
    pd.DataFrame([{"game_id": 1, "home_id": 2390, "away_id": 57, "home_score": 60, "away_score": 75, "state": "post"}]).to_csv(
        tmp_path / "cbb_2026-11-02.csv", index=False)
    ml = tmp_path / "ml"
    ml.mkdir()
    pd.DataFrame([{"observed_at": "2026-11-02T22:50:00+00:00", "home_id": 2390, "away_id": 57, "book": "FanDuel",
                   "home_ml": 200, "away_ml": -245, "status": "ok", "start": "2026-11-02T23:00:00Z"}]).to_csv(ml / "2026-11-02.csv", index=False)
    monkeypatch.setattr(ofr, "LOG", str(tmp_path / "of.csv"))
    monkeypatch.setattr(ofr, "REPORTS", str(tmp_path))
    monkeypatch.setattr(shadow, "ML", str(ml))
    s, unit = ofr.build()
    assert len(s) == 2 and len(unit) == 1 and unit.iloc[0]["book"] == "FanDuel"   # the first qualifying quote per game-side
    assert unit.iloc[0]["won"] == 1 and abs(unit.iloc[0]["profit"] - 100 / 220) < 1e-9   # Florida (away in the report) won
    assert unit.iloc[0]["clv_pp"] > 0                                             # -220 closed near -245
