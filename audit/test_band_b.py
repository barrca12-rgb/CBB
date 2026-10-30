"""Band B (protocol appendix B, approved Oct 29): a 2.2-point spread signal is band B at 0.5 unit, a 2.5-point one is
v1 at its usual stake, and band B never enters v1's log view, record, stake multiplier or forward-test signals.

    python -m pytest -q audit/test_band_b.py
"""
import pandas as pd
import pytest

from audit import forward_eval as fe
from cbb import run_day, tracker


def _card(margin: float, total: float = 140.0) -> pd.DataFrame:
    """One game against one book at -110 both ways: home -10, total 140."""
    f = pd.DataFrame([{"game_id": 1, "start": "2026-11-05T00:00:00Z", "home": "Home", "away": "Away", "home_id": 10,
                       "away_id": 20, "neutral": False, "state": "pre", "final_margin": margin, "final_total": total}])
    lines = pd.DataFrame([{"home_id": 10, "away_id": 20, "book": "DraftKings", "home_spread": -10.0,
                           "home_spread_odds": -110, "away_spread_odds": -110, "total": 140.0, "over_odds": -110,
                           "under_odds": -110}])
    return run_day.plays(f, lines)


@pytest.fixture
def log(monkeypatch, tmp_path):
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    return tmp_path


def test_a_2_2_point_spread_signal_is_band_b_at_half_a_unit(log):
    c = _card(12.2)                                   # home -10, model 12.2: edge 2.2 on the home side
    g = c.iloc[0]
    assert g["spread_edge"] == pytest.approx(2.2) and g["spread_side"] == "home"
    assert g["spread_verdict"] == "WATCH" and g["spread_units"] == 0.0     # v1 unchanged: not a v1 play
    assert g["spread_bandb"] == True
    assert tracker.log(c, pd.Timestamp("2026-11-04"), {"spread": 1.0, "total": 1.0}) == []
    new = tracker.log_band_b(c, pd.Timestamp("2026-11-04"))
    assert len(new) == 1
    b = new[0]
    assert b["stake"] == 0.5 and b["bet_type"] == "bandB" and b["market"] == "spread"
    assert b["bet_id"] == "2026-11-04|1|spread|home|bandB"
    assert len(tracker.load()) == 0 and len(tracker.load("bandB")) == 1 and len(tracker.load("all")) == 1
    assert tracker.log_band_b(c, pd.Timestamp("2026-11-04")) == []          # logged once


def test_a_2_5_point_spread_signal_is_v1_and_never_band_b(log):
    c = _card(12.5)
    g = c.iloc[0]
    assert g["spread_verdict"] == "BET" and g["spread_units"] == 1.0
    assert g["spread_bandb"] == False
    new = tracker.log(c, pd.Timestamp("2026-11-04"), {"spread": 1.0, "total": 1.0})
    assert len(new) == 1 and new[0]["stake"] == 1.0
    assert tracker.log_band_b(c, pd.Timestamp("2026-11-04")) == []
    assert len(tracker.load()) == 1 and len(tracker.load("bandB")) == 0


def test_band_b_needs_the_ev_rule_and_stops_below_2():
    assert _card(11.9).iloc[0]["spread_bandb"] == False                   # edge 1.9
    f = _card(12.2)
    assert f.iloc[0]["spread_bandb"] == True
    assert run_day._band_b("spread", 2.2, 0.019, "WATCH") is False          # under +2% EV
    assert run_day._band_b("spread", 2.49, 0.03, "WATCH") is True
    assert run_day._band_b("spread", 2.6, 0.03, "BET") is False


def test_totals_band_b_is_built_but_switched_off():
    c = _card(10.0, total=142.6)                       # over by 2.6: in the totals band, but switched off
    g = c.iloc[0]
    assert g["total_verdict"] == "WATCH" and g["total_bandb"] == False
    assert tracker.BAND_B_ON == {"spread": True, "total": False}


def test_v1_figures_ignore_band_b_rows(log):
    c = _card(12.5)
    tracker.log(c, pd.Timestamp("2026-11-04"), {"spread": 1.0, "total": 1.0})
    before = (tracker.load().to_csv(index=False), tracker.status(), tracker.recent())
    tracker.log_band_b(_card(12.2).assign(game_id=2, home_id=11, away_id=21), pd.Timestamp("2026-11-04"))
    assert len(tracker.load("all")) == 2
    assert (tracker.load().to_csv(index=False), tracker.status(), tracker.recent()) == before
    b = pd.read_csv(tracker.BETS)
    s, _ = fe.load_signals("v1", bets=b.assign(logged_at="2026-10-30T00:00:00+00:00", date="2026-11-04"))
    assert list(s["bet_type"].fillna("")) == [""]
    s, _ = fe.load_signals("bandB", bets=b.assign(logged_at="2026-10-30T00:00:00+00:00", date="2026-11-04"))
    assert list(s["bet_type"]) == ["bandB"]


def test_a_game_v1_already_bet_is_never_also_band_b(log):
    tracker.log(_card(12.5), pd.Timestamp("2026-11-04"), {"spread": 1.0, "total": 1.0})
    assert tracker.log_band_b(_card(12.2), pd.Timestamp("2026-11-04")) == []   # the line moved; v1 holds the game


def test_a_band_b_game_later_bet_by_v1_is_reported_as_its_own_cell(log):
    from audit import band_b_read
    tracker.log_band_b(_card(12.2), pd.Timestamp("2026-11-04"))          # band B first, home +10 at edge 2.2
    import time; time.sleep(1.1)                                          # logged_at has one-second resolution
    tracker.log(_card(12.6), pd.Timestamp("2026-11-04"), {"spread": 1.0, "total": 1.0})   # model moved: v1 joins
    m = band_b_read.overlaps(tracker.load("all"))
    assert len(m) == 1 and bool(m.iloc[0]["same_side"]) and m.iloc[0]["combined_stake"] == 1.5
    assert len(tracker.load()) == 1 and len(tracker.load("bandB")) == 1  # both stand, each in its own record
