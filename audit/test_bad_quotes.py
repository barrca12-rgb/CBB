"""Bad-quote guards (approved by Chad Oct 30, after a sign-flipped BetMGM row with no price was logged as Villanova
+7.5 on Oct 30 15:50 UTC). Live: a quote with no price on our side is never a play; a book 3+ points off the other
books' median (3+ books quoting) is skipped; an edge above 8 (spreads) or 10 (totals) is REVIEW, never a BET, band B
or alert. Replays of past days keep the -110 assumption.

    python -m pytest -q audit/test_bad_quotes.py
"""
import numpy as np
import pandas as pd
import pytest

from cbb import run_day, tracker

# The game as the card has it (ESPN: Villanova home), and the books as the feed had them (Notre Dame listed home)
F = pd.DataFrame([{"game_id": 401920982, "date": pd.Timestamp("2026-11-01"), "start": "2026-11-01T14:30:00Z",
                   "home": "Villanova", "away": "Notre Dame", "home_id": 222, "away_id": 87, "neutral": True,
                   "state": "pre", "final_margin": 7.3, "final_total": 139.8}])


def _book(book, nd_spread, nd_price, vu_price, total=147.5):
    return {"home_id": 87, "away_id": 222, "book": book, "home_spread": nd_spread, "home_spread_odds": nd_price,
            "away_spread_odds": vu_price, "total": total, "over_odds": -110.0, "under_odds": -110.0}


GOOD = [_book(b, 7.5, -110.0, -110.0) for b in ("DraftKings", "Caesars", "Fanatics", "FanDuel")]
BETMGM = _book("BetMGM", -7.5, -110.0, np.nan)            # the real row: sign flipped, no price on Villanova's side


def test_the_oct_30_betmgm_row_is_no_longer_a_play():
    c = run_day.plays(F, pd.DataFrame(GOOD + [BETMGM])).iloc[0]
    assert c["spread_book"] != "BetMGM" and c["spread_verdict"] != "BET"
    assert abs(c["spread_edge"]) < 1                        # Villanova -7.5 everywhere else vs model 7.3
    off = [b for b in run_day.BAD if b["reason"] == "off-market"]
    assert len(off) == 1 and off[0]["book"] == "BetMGM" and off[0]["median_others"] == -7.5 and off[0]["books"] == 5


def test_guard_1_no_price_means_no_play_live():
    """With too few books for the off-market guard, the missing price alone stops it."""
    lines = pd.DataFrame([GOOD[0], BETMGM])
    c = run_day.plays(F, lines).iloc[0]
    assert c["spread_book"] == "DraftKings" and c["spread_verdict"] != "BET"
    assert any(b["reason"] == "no price" and b["book"] == "BetMGM" for b in run_day.BAD)


def test_guard_1_replays_keep_the_minus_110_assumption():
    """ESPN's stored lines carry no prices: a replay prices them at -110, exactly as before."""
    espn = pd.DataFrame([{"home_id": 222, "away_id": 87, "book": "ESPN", "home_spread": -3.0, "total": 147.5}])
    c = run_day.plays(F, espn, live=False).iloc[0]
    assert c["spread_verdict"] == "BET" and c["spread_ev"] == pytest.approx(run_day.ev(run_day.win_prob("spread", 4.3), -110))


def test_guard_2_off_market_book_skipped_only_with_3_books():
    stale = _book("BetMGM", 3.5, -110.0, -110.0)            # 4 points off the other books' 7.5
    run_day.plays(F, pd.DataFrame(GOOD[:2] + [stale]))
    assert [b["book"] for b in run_day.BAD if b["reason"] == "off-market"] == ["BetMGM"]
    run_day.plays(F, pd.DataFrame(GOOD[:1] + [stale]))       # two books: no median to judge against
    assert not [b for b in run_day.BAD if b["reason"] == "off-market"]
    near = _book("BetMGM", 5.0, -110.0, -110.0)              # 2.5 off: a real price difference, kept
    run_day.plays(F, pd.DataFrame(GOOD[:2] + [near]))
    assert not [b for b in run_day.BAD if b["reason"] == "off-market"]


def test_guard_3_edge_above_the_maximum_is_review_not_bet(tmp_path, monkeypatch):
    f = F.assign(final_margin=-9.0, final_total=160.0)        # Notre Dame by 9 vs Villanova -7.5: edge 16.5; total edge 12.5
    c = run_day.plays(f, pd.DataFrame(GOOD))
    g = c.iloc[0]
    assert g["spread_verdict"] == "REVIEW" and g["spread_units"] == 0.0 and g["spread_bandb"] == False
    assert g["total_verdict"] == "REVIEW" and g["total_units"] == 0.0
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    assert tracker.log(c, pd.Timestamp("2026-11-01"), {"spread": 1.0, "total": 1.0}) == []      # never logged
    assert tracker.log_band_b(c, pd.Timestamp("2026-11-01")) == []
    assert {b["reason"] for b in run_day.BAD} == {"review: edge 16.5", "review: edge 12.5"}
    ok = run_day.plays(F.assign(final_margin=0.0), pd.DataFrame(GOOD)).iloc[0]   # edge 7.5: below the maximum
    assert ok["spread_verdict"] == "BET"


def test_skips_are_logged_once(tmp_path, monkeypatch):
    monkeypatch.setattr(run_day, "BAD_QUOTES", str(tmp_path / "bad.csv"))
    run_day.plays(F, pd.DataFrame(GOOD + [BETMGM]))
    run_day.log_bad_quotes(run_day.BAD)
    run_day.log_bad_quotes(run_day.BAD)                       # the next card run sees the same row: not repeated
    b = pd.read_csv(tmp_path / "bad.csv")
    assert list(b.columns) == run_day.BAD_COLS and len(b) == 1
    assert b.loc[0, "book"] == "BetMGM" and b.loc[0, "number"] == 7.5 and b.loc[0, "median_others"] == -7.5   # card orientation: Villanova home


def test_a_qualifying_quote_beats_a_better_priced_one_that_does_not_qualify():
    """Oct 31, Liberty-High Point (neutral): model High Point by 9.28. theScore -7.5 at +100 (edge 1.78, EV +9.07%)
    outscored DraftKings/Caesars -6.5 at -110 (edge 2.78, EV +8.98%) and the game fell to WATCH. The qualifying
    quote now wins."""
    f = pd.DataFrame([{"game_id": 401921000, "date": pd.Timestamp("2026-11-01"), "start": "2026-11-01T17:00:00Z",
                       "home": "High Point", "away": "Liberty", "home_id": 2272, "away_id": 2335, "neutral": True,
                       "state": "pre", "final_margin": 9.2775, "final_total": 154.1}])
    feed = [  # the feed lists Liberty home: home_spread +6.5 means High Point -6.5
        {"home_id": 2335, "away_id": 2272, "book": "DraftKings", "home_spread": 6.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "Caesars", "home_spread": 6.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "Fanatics", "home_spread": 7.0, "home_spread_odds": -105.0, "away_spread_odds": -115.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "theScore Bet", "home_spread": 7.5, "home_spread_odds": -120.0, "away_spread_odds": 100.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "FanDuel", "home_spread": 7.5, "home_spread_odds": -105.0, "away_spread_odds": -115.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0}]
    g = run_day.plays(f, pd.DataFrame(feed)).iloc[0]
    assert g["spread_verdict"] == "BET" and g["spread_book"] == "DraftKings" and g["spread_line"] == -6.5
    assert g["spread_edge"] == pytest.approx(2.7775, abs=1e-3) and g["spread_ev"] >= run_day.MIN_EV


def test_no_qualifying_quote_keeps_the_highest_ev_for_the_watch_list():
    f = F.assign(final_margin=9.2)            # Villanova by 9.2 vs -7.5 everywhere: edge 1.7, WATCH, nothing qualifies
    lines = pd.DataFrame([_book("DraftKings", 7.5, -110.0, -110.0), _book("Caesars", 7.5, -110.0, -105.0)])
    g = run_day.plays(f, lines).iloc[0]
    assert g["spread_verdict"] == "WATCH" and g["spread_book"] == "Caesars" and g["spread_odds"] == -105.0


def test_safety_net_flags_a_missed_qualifying_quote_and_is_silent_otherwise(tmp_path, monkeypatch):
    from cbb import card_features, notify
    f = pd.DataFrame([{"game_id": 401921000, "date": pd.Timestamp("2026-11-01"), "start": "2026-11-01T17:00:00Z",
                       "home": "High Point", "away": "Liberty", "home_id": 2272, "away_id": 2335, "neutral": True,
                       "state": "pre", "final_margin": 9.2775, "final_total": 154.1}])
    lines = pd.DataFrame([
        {"home_id": 2335, "away_id": 2272, "book": "DraftKings", "home_spread": 6.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "Caesars", "home_spread": 6.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0},
        {"home_id": 2335, "away_id": 2272, "book": "theScore Bet", "home_spread": 7.5, "home_spread_odds": -120.0, "away_spread_odds": 100.0, "total": 154.5, "over_odds": -110.0, "under_odds": -110.0}])
    card = run_day.plays(f, lines)
    assert card_features.missed_plays(card, lines).empty                     # fixed selection: nothing missed
    old = card.assign(spread_verdict="WATCH", spread_book="theScore Bet", spread_line=-7.5, spread_edge=1.78)   # the Oct 31 card
    miss = card_features.missed_plays(old, lines)
    assert set(miss["book"]) == {"DraftKings", "Caesars"} and (miss["line"] == -6.5).all() and (miss["side"] == "home").all()
    sent = []
    monkeypatch.setattr(notify, "message", lambda t, b, **k: sent.append(t) or True)
    monkeypatch.setattr(card_features, "MISSED", str(tmp_path / "m.csv"))
    monkeypatch.setattr(card_features, "MISSED_ALERTED", str(tmp_path / "a.json"))
    assert card_features.report_missed(miss, "2026-11-01") == 2
    assert card_features.report_missed(miss, "2026-11-01") == 0               # one alert per quote, not every run
    assert len(pd.read_csv(tmp_path / "m.csv")) == 4
