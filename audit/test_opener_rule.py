"""Opener rule (Chad, Nov 2; protocol v2.4): a live signal is a play only if it also qualifies against the game's
opener with the current model. Signals that clear the live rule only because the line moved go to
research/linemove/signals.csv and are never logged, alerted or posted.

    python -m pytest -q audit/test_opener_rule.py
"""
import pandas as pd
import pytest

from cbb import card_features, run_day, tracker

DAY = pd.Timestamp("2026-11-05")
ST = {"spread": 1.0, "total": 1.0}
START = "2026-11-06T00:00:00Z"            # 7 pm ET Nov 5
COLS = ["pulled_at", "date", "game_key", "book", "lo_id", "hi_id", "spread", "spread_odds_lo", "spread_odds_hi",
        "total", "over_odds", "under_odds"]


def _f(margin: float, total: float = 140.0) -> pd.DataFrame:
    """One game: home (id 20) vs away (id 10), so the home team is the HIGH id (spreads in moves.csv are the lo team's)."""
    return pd.DataFrame([{"game_id": 1, "start": START, "home": "Home", "away": "Away", "home_id": 20, "away_id": 10,
                          "neutral": False, "state": "pre", "final_margin": margin, "final_total": total}])


def _lines(home_spread: float, total: float = 140.0, books=("DraftKings",)) -> pd.DataFrame:
    return pd.DataFrame([{"home_id": 20, "away_id": 10, "book": b, "start": START, "home_spread": home_spread,
                          "home_spread_odds": -110, "away_spread_odds": -110, "total": total, "over_odds": -110,
                          "under_odds": -110} for b in books])


def _moves(tmp_path, rows: list[dict]) -> pd.DataFrame:
    """A lines/moves.csv with the given first rows (home -s means the lo team, away id 10, is +s)."""
    m = pd.DataFrame([{"pulled_at": r.get("at", "2026-11-04T12:00:00+00:00"), "date": "2026-11-05",
                       "game_key": "2026-11-05|10|20", "book": r["book"], "lo_id": 10, "hi_id": 20,
                       "spread": -r["home_spread"] if r.get("home_spread") is not None else None,
                       "spread_odds_lo": r.get("odds", -110), "spread_odds_hi": r.get("odds", -110),
                       "total": r.get("total"), "over_odds": r.get("odds", -110), "under_odds": r.get("odds", -110)}
                      for r in rows], columns=COLS)
    p = tmp_path / "moves.csv"
    m.to_csv(p, index=False)
    return run_day.first_quotes(str(p))


@pytest.fixture
def log(monkeypatch, tmp_path):
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    monkeypatch.setattr(run_day, "LINEMOVE_SIGNALS", str(tmp_path / "signals.csv"))
    return tmp_path


def test_qualified_at_the_opener_is_logged(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 140.0}])
    c = run_day.plays(_f(12.6), _lines(-10.0), fq=fq)                    # opener and current: home -10, edge 2.6
    assert c.iloc[0]["spread_verdict"] == "BET" and not run_day.GATED
    assert [x["side"] for x in tracker.log(c, DAY, ST)] == ["home"]


def test_qualified_because_the_model_moved_is_logged(log):
    """The opener test uses the current model: an opener the old model didn't play, the new model does."""
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -9.5, "total": 140.0}])
    c = run_day.plays(_f(12.6), _lines(-9.0), fq=fq)                     # edge 3.1 at the opener, 3.6 now
    assert c.iloc[0]["spread_verdict"] == "BET" and not run_day.GATED
    assert len(tracker.log(c, DAY, ST)) == 1


def test_qualified_only_because_the_line_moved_is_research_only(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0}])
    c = run_day.plays(_f(12.6), _lines(-10.0), fq=fq)                    # edge 1.6 at the opener, 2.6 now
    r = c.iloc[0]
    assert r["spread_verdict"] == "PASS" and r["spread_units"] == 0 and r["spread_gate"] == "opener rule"
    assert tracker.log(c, DAY, ST) == [] and tracker.log_band_b(c, DAY) == []
    g = run_day.GATED
    assert len(g) == 1 and g[0]["bet_type"] == "v1" and g[0]["opener_line"] == -11.0 and g[0]["line"] == -10.0
    assert g[0]["move_pts"] == 1.0 and round(g[0]["edge_vs_opener"], 2) == 1.6
    run_day.log_linemove(run_day.GATED)
    run_day.log_linemove(run_day.GATED)                                  # the next run: written once
    s = pd.read_csv(run_day.LINEMOVE_SIGNALS)
    assert len(s) == 1 and s.iloc[0]["pick"] == "Home -10"


def test_a_game_already_held_is_not_a_research_signal(log):
    """The rule stops nothing on a game and market the log already holds (the log would refuse it anyway)."""
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 140.0}])
    tracker.log(run_day.plays(_f(12.6), _lines(-10.0), fq=fq), DAY, ST)       # home -10 logged at the opener
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0}])
    run_day.plays(_f(12.6), _lines(-10.0), fq=fq)
    assert len(run_day.GATED) == 1
    run_day.log_linemove(run_day.GATED)
    assert not (log / "signals.csv").exists()


def test_a_line_move_signal_is_not_a_missed_play(log, monkeypatch):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0}])
    monkeypatch.setattr(run_day, "first_quotes", lambda path=None: fq)
    lines = _lines(-10.0)
    c = run_day.plays(_f(12.6), lines, fq=fq)
    assert card_features.missed_plays(c, lines).empty


def test_a_book_missing_a_priced_first_quote_neither_passes_nor_fails_the_test(log):
    # DraftKings' opener qualifies; FanDuel's first row has no price: skipped, so the play stands
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 140.0},
                      {"book": "FanDuel", "home_spread": -8.0, "total": 140.0, "odds": None}])
    assert run_day.plays(_f(12.6), _lines(-10.0, books=("DraftKings", "FanDuel")), fq=fq).iloc[0]["spread_verdict"] == "BET"
    # DraftKings' opener fails; FanDuel's priceless first row (edge 4.6 if it counted) does not rescue it
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0},
                      {"book": "FanDuel", "home_spread": -8.0, "total": 140.0, "odds": None}])
    assert run_day.plays(_f(12.6), _lines(-10.0, books=("DraftKings", "FanDuel")), fq=fq).iloc[0]["spread_verdict"] == "PASS"


def test_a_book_first_seen_on_this_run_is_its_own_opener(log):
    """No earlier quote at all (new game, or the first-quote log is empty): this run's quotes are the openers."""
    c = run_day.plays(_f(12.6), _lines(-10.0), fq=run_day.first_quotes("/nonexistent"))
    assert c.iloc[0]["spread_verdict"] == "BET" and not run_day.GATED


def test_no_usable_first_quote_at_any_book_leaves_the_signal_standing(log):
    """Every first quote priceless (posted before the quote log kept prices): the test cannot be applied."""
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0, "odds": None}])
    c = run_day.plays(_f(12.6), _lines(-10.0), fq=fq)
    assert c.iloc[0]["spread_verdict"] == "BET" and not run_day.GATED


def test_an_off_market_first_quote_does_not_count(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -11.0, "total": 140.0},
                      {"book": "FanDuel", "home_spread": -11.0, "total": 140.0},
                      {"book": "Caesars", "home_spread": -11.0, "total": 140.0},
                      {"book": "BetMGM", "home_spread": -6.0, "total": 140.0}])   # 5 off the others: a broken row
    c = run_day.plays(_f(12.6), _lines(-10.0, books=("DraftKings", "FanDuel", "Caesars")), fq=fq)
    assert c.iloc[0]["spread_verdict"] == "PASS"


def test_band_b_goes_through_the_same_gate(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.5, "total": 140.0}])
    c = run_day.plays(_f(12.2), _lines(-10.0), fq=fq)                    # edge 1.7 at the opener, 2.2 now
    assert not bool(c.iloc[0]["spread_bandb"])
    assert [x["bet_type"] for x in run_day.GATED] == ["bandB"]
    assert tracker.log_band_b(c, DAY) == []
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 140.0}])
    c = run_day.plays(_f(12.1), _lines(-10.0), fq=fq)                    # edge 2.1 at the opener: band B stands
    assert bool(c.iloc[0]["spread_bandb"]) and not run_day.GATED
    assert len(tracker.log_band_b(c, DAY)) == 1


def test_totals_are_gated_the_same_way(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 142.0}])
    c = run_day.plays(_f(10.0, 146.0), _lines(-10.0, total=143.0), fq=fq)  # over: 4 at the opener (qualifies)
    assert c.iloc[0]["total_verdict"] == "BET"
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -10.0, "total": 144.0}])
    c = run_day.plays(_f(10.0, 146.0), _lines(-10.0, total=143.0), fq=fq)  # 2 at the opener, 3 now: research only
    assert c.iloc[0]["total_verdict"] == "PASS" and run_day.GATED[0]["market"] == "total"


def test_a_watch_the_gate_would_stop_is_not_shown_as_a_watch(log):
    fq = _moves(log, [{"book": "DraftKings", "home_spread": -12.0, "total": 140.0}])
    c = run_day.plays(_f(11.8), _lines(-10.0), fq=fq)                    # edge -0.2 at the opener, 1.8 now (WATCH)
    assert c.iloc[0]["spread_verdict"] == "PASS"
    assert not run_day.GATED                                             # a watch is not a signal: nothing logged


def test_replays_are_never_gated():
    fq = run_day.first_quotes("/nonexistent")
    a = run_day.plays(_f(12.6), _lines(-10.0), live=False, fq=fq)
    assert a.iloc[0]["spread_verdict"] == "BET" and "spread_gate" not in a
