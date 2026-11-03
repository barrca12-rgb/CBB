"""Spread CLV from the bet's side when the odds feed lists the other team as home (Nov 2: Miami-Florida at a neutral
site read Florida -5.5 against Miami's +6.5 and showed CLV -12; the close was Florida -6.5, CLV +1).

    python -m pytest -q audit/test_clv_orientation.py
"""
import numpy as np
import pandas as pd

from audit import forward_eval as fe
from cbb import clv_primary, tracker

KEY = "2026-11-02|57|2390"           # Florida 57 (ESPN home), Miami 2390 (the feed's home)


def _obs(rows):
    return pd.DataFrame([{"observed_at": t, "source": "oddsapi", "event_id": "oa:x", "game_key": KEY,
                          "start": "2026-11-02T23:00:00Z", "book": bk, "market": "spread", "side": sd, "line": ln,
                          "price": -110, "source_updated_at": t, "quote_age_s": 0, "status": "available"}
                         for t, bk, sd, ln in rows])


def test_feed_home_is_read_from_the_line_log():
    o = fe.load_obs(_obs([("2026-11-02T22:50:00Z", "FanDuel", "home", 6.5), ("2026-11-02T22:50:00Z", "FanDuel", "away", -6.5)]))
    moves = pd.DataFrame([{"pulled_at": "2026-11-02T22:40:00Z", "game_key": KEY, "book": "FanDuel", "lo_id": 57,
                           "hi_id": 2390, "spread": -6.5}])            # the lower id (Florida) is -6.5
    assert set(fe._feed_home(o, moves).dropna()) == {2390.0}       # "home" +6.5 is Miami's side
    # no line-log evidence, or a pick'em: nothing is relabelled
    assert fe._feed_home(o, moves.assign(spread=0.0)).isna().all()
    assert fe._feed_home(o, moves.iloc[0:0]).isna().all()


def test_orient_swaps_sides_only_when_the_feed_home_is_the_bets_away_team():
    og = pd.DataFrame({"market": ["spread", "spread", "total"], "side": ["home", "away", "over"], "feed_home": [2390.0] * 3})
    bet = {"home_id": 57, "away_id": 2390}
    assert fe.orient(og, bet)["side"].tolist() == ["away", "home", "over"]
    assert fe.orient(og.assign(feed_home=57.0), bet)["side"].tolist() == ["home", "away", "over"]
    assert fe.orient(og.assign(feed_home=np.nan), bet)["side"].tolist() == ["home", "away", "over"]


def test_the_florida_play_reads_florida_minus_six_and_a_half():
    b = tracker.load("all")
    r = clv_primary.primary(b[b["bet_id"] == "2026-11-02|401906769|spread|home"]).iloc[0]
    assert (r["close_primary"], r["clv_primary"]) == (-6.5, 1.0)
