"""Morning shadow collection (research/morning_shadow/PLAN.md section 2): window, readiness, fallback, no decision,
hard failures, no re-logging; and the comparison's grading and cells."""
import pandas as pd
import pytest

from cbb import morning_shadow as ms

DAY = "2026-11-10"
READY = {"ready_barttorvik": True, "ready_kenpom": True, "ready_box_scores": True, "ready_injuries": True,
         "barttorvik_file": "2026-11-09", "kenpom_source": "FanMatch 2026-11-10", "box_scores_last_final": "2026-11-09",
         "missing": ""}
LATE = dict(READY, ready_barttorvik=False, barttorvik_file="2026-11-08", missing="barttorvik")


def et(h, m=0, day=DAY):
    return (pd.Timestamp(day) + pd.Timedelta(hours=h, minutes=m)).tz_localize("America/New_York").tz_convert("UTC")


def card(tip_h=19, book="FanDuel", verdict="BET"):
    return pd.DataFrame([{
        "game_id": 1, "home_id": 10, "away_id": 20, "home": "Home U", "away": "Away St", "start": et(tip_h).isoformat(),
        "model_margin": 6.0, "model_total": 150.0,
        "spread_verdict": verdict, "spread_side": "home", "spread_pick": "Home U", "spread_line": -2.5, "spread_odds": -110,
        "spread_book": book, "spread_edge": 3.5, "spread_ev": 0.05, "spread_gate": None,
        "total_verdict": "PASS", "total_pick": "Over", "total_line": 149.5, "total_odds": -110, "total_book": book,
        "total_edge": 0.5, "total_ev": -0.03, "total_gate": None}])


@pytest.fixture
def log(tmp_path, monkeypatch):
    p = tmp_path / "shadow_morning.csv"
    monkeypatch.setattr(ms, "LOG", str(p))
    return p


def rows(p):
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def test_window_deadline_is_noon_or_half_an_hour_before_tip():
    op, dl, tip = ms.window(DAY, et(19).isoformat())
    assert op == et(9) and dl == et(12) and tip == et(19)
    _, dl, _ = ms.window(DAY, et(12, 15).isoformat())
    assert dl == et(11, 45)


def test_nothing_before_the_window_opens(log):
    assert ms.collect(card(), DAY, now=et(8, 50), ready=READY, stakes={"spread": 1.0, "total": 1.0}) == 0
    assert not log.exists()


def test_first_ready_run_decides_once_with_the_cards_own_verdict(log):
    assert ms.collect(card(), DAY, now=et(9, 10), ready=READY, stakes={"spread": 0.5, "total": 1.0}) == 2
    r = rows(log).set_index("market")
    assert r.loc["spread", "decision"] == "BET" and r.loc["spread", "decision_kind"] == "ready"
    assert r.loc["spread", "book"] == "FanDuel" and r.loc["spread", "line"] == -2.5 and r.loc["spread", "stake"] == 0.5
    assert r.loc["total", "decision"] == "NO BET" and r.loc["total", "reason"] == "card verdict PASS"
    # a later run never re-decides
    assert ms.collect(card(verdict="PASS"), DAY, now=et(10), ready=READY, stakes={}) == 0
    assert len(rows(log)) == 2


def test_late_update_waits_until_the_deadline_then_falls_back_with_what_is_missing(log):
    assert ms.collect(card(), DAY, now=et(10), ready=LATE, stakes={"spread": 1.0, "total": 1.0}) == 0
    assert ms.collect(card(), DAY, now=et(12, 5), ready=LATE, stakes={"spread": 1.0, "total": 1.0}) == 2
    r = rows(log)
    assert set(r["decision_kind"]) == {"fallback"} and set(r["missing"]) == {"barttorvik"}


def test_no_run_before_tip_is_logged_as_no_decision(log):
    assert ms.collect(card(tip_h=8), DAY, now=et(9), ready=READY, stakes={}) == 2
    r = rows(log)
    assert set(r["decision_kind"]) == {"no decision"} and set(r["decision"]) == {"NO BET"}


def test_hard_failure_no_named_book_quote_is_a_no_bet_with_reason(log):
    ms.collect(card(book=None), DAY, now=et(9, 10), ready=READY, stakes={})
    r = rows(log).set_index("market")
    assert r.loc["spread", "decision"] == "NO BET"
    assert r.loc["spread", "reason"].startswith("hard failure: no named-book quote")


def test_box_scores_ready_only_when_every_d1_game_of_the_day_before_is_in():
    sch = pd.DataFrame({"game_id": [1, 2, 3], "date": ["2026-11-10T00:00Z", "2026-11-10T01:00Z", "2026-11-10T02:00Z"],
                        "status_type_name": ["STATUS_FINAL", "STATUS_FINAL", "STATUS_POSTPONED"],
                        "status_type_completed": [True, True, False],
                        "home_conference_id": [1, 1, 1], "away_conference_id": [2, 2, 2]})
    hist = pd.DataFrame({"game_id": [1, 2], "date": ["2026-11-09", "2026-11-09"], "home_pts": [70, 80]})
    assert ms.box_ready(DAY, sch, hist) == (True, "2026-11-09")
    assert ms.box_ready(DAY, sch, hist.iloc[:1])[0] is False          # a final game not in the box scores yet
    live = sch.assign(status_type_name=["STATUS_FINAL", "STATUS_IN_PROGRESS", "STATUS_POSTPONED"],
                      status_type_completed=[True, False, False])
    assert ms.box_ready(DAY, live, hist)[0] is False                  # a game of the day before still going


def test_comparison_grades_from_the_plays_own_home_team():
    from research.morning_shadow import compare
    p = pd.DataFrame([{"game_id": 1, "home_id": 10, "away_id": 20, "market": "spread", "side": "home", "line": -2.5,
                       "odds": -110, "stake": 1.0}])
    assert compare.grade(p, {1: (10, 80.0, 70.0)})["result"].iloc[0] == "W"
    # the card relisted the play's away team as home: scores are read from the play's side
    g = compare.grade(p, {1: (20, 70.0, 80.0)})
    assert g["result"].iloc[0] == "W" and round(g["flat"].iloc[0], 4) == round(100 / 110, 4)
