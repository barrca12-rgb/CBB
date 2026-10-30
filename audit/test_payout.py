"""Payout sign check (helper note, Oct 31): the totals-band research script first had the payout sign wrong for
negative prices (100 / -abs(price)). The live paths do not share it. Each is checked at -110, -125 and +105 for a win
and a loss: the grader's profit (tracker.settle), the +2% EV rule (run_day.ev), the forward test (forward_eval), the
record page's units (record_page.summary) and the card's JavaScript payout.

    python -m pytest -q audit/test_payout.py
"""
import re

import pandas as pd
import pytest

from cbb import record_page, report_html, run_day, tracker
from audit import forward_eval

WIN = {-110: 100 / 110, -125: 0.8, 105: 1.05}


@pytest.mark.parametrize("odds", [-110, -125, 105])
def test_win_and_loss_units(odds):
    assert tracker.payout(odds) == pytest.approx(WIN[odds])
    assert forward_eval.payout(odds) == pytest.approx(WIN[odds])
    assert forward_eval.units("W", odds) == pytest.approx(WIN[odds]) and forward_eval.units("L", odds) == -1.0
    assert run_day.ev(1.0, odds) == pytest.approx(WIN[odds])          # a sure win pays the price
    assert run_day.ev(0.0, odds) == pytest.approx(-1.0)               # a sure loss costs the stake


def test_grader_and_record_page(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    monkeypatch.setattr(tracker, "CLOSING", str(tmp_path / "closing.csv"))
    monkeypatch.setattr(tracker, "save", lambda b: b.to_csv(tracker.BETS, index=False))
    rows = []
    for k, (odds, side) in enumerate([(-110, "home"), (-125, "home"), (105, "home"), (-110, "away"), (-125, "away"), (105, "away")]):
        rows.append({c: None for c in tracker.COLS} | {"bet_id": f"2020-01-01|{k}|spread|{side}", "date": "2020-01-01",
                     "game_id": k, "market": "spread", "side": side, "home_id": 1, "away_id": 2, "line": -1.5, "odds": odds,
                     "book": "DraftKings", "stake": 1.0, "status": "open"})
    pd.DataFrame(rows, columns=tracker.COLS).to_csv(tracker.BETS, index=False)
    scores = pd.DataFrame({"game_id": range(6), "home_score": [80] * 6, "away_score": [70] * 6, "state": ["post"] * 6})
    assert tracker.settle(scores) == 6
    b = pd.read_csv(tracker.BETS).set_index("game_id")
    assert list(b["result"]) == ["W", "W", "W", "L", "L", "L"]
    assert list(b["profit"]) == pytest.approx([0.909, 0.8, 1.05, -1.0, -1.0, -1.0])
    s = record_page.summary(b.reset_index())
    assert s["units"] == pytest.approx(0.909 + 0.8 + 1.05 - 3.0)


def test_card_javascript_payout():
    src = open(report_html.__file__).read()
    pays = re.findall(r"const pay = \(o\) => (.+?);", src)
    assert pays and all("100 / -o" in p and "o / 100" in p and "abs" not in p for p in pays)
