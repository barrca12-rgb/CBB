"""Venue check of the neutral flag (cbb/venue.py; Chad's Oct 30 brief, item 1): one confirmed, one conflict and one
unknown case through the classifier, the edge cases, the card renders the mark, and v1's output is unchanged with
the mark on and off (the mark lives only in the rendered page).

    python -m pytest -q audit/test_venue.py
"""
import json
import re

import pandas as pd

from cbb import report_html, venue

SETS = {1: {100}, 2: {200}, 3: set()}          # team -> home arena ids
CITY = {1: "springfield", 2: "shelbyville"}


def test_confirmed_conflict_unknown():
    assert venue.classify(False, 100, "Springfield", 1, 2, SETS, CITY)[0] == "confirmed"        # home at home's arena
    assert venue.classify(True, 999, "Elsewhere", 1, 2, SETS, CITY)[0] == "confirmed"            # neutral, nobody's arena
    st, why, _ = venue.classify(True, 100, "Springfield", 1, 2, SETS, CITY)                     # neutral at home's arena
    assert st == "conflict" and "home team's arena" in why
    assert venue.classify(None if False else True, None, None, 1, 2, SETS, CITY)[0] == "unknown"  # no venue
    assert venue.classify(True, 999, "X", 1, 3, SETS, CITY)[0] == "unknown"                      # a team has no arena on file


def test_edge_cases():
    assert venue.classify(False, 200, "Shelbyville", 1, 2, SETS, CITY) == ("conflict", "home game at the listed away team's arena", "reversed")
    assert venue.classify(True, 999, "Springfield", 1, 2, SETS, CITY)[2] == "home city"         # neutral in home's city
    assert venue.classify(False, 999, "Springfield", 1, 2, SETS, CITY) == ("conflict", "home game at an arena belonging to neither team", "home city")
    assert venue.classify(True, 300, "X", 1, 2, SETS, CITY, home_team_venue=300)[0] == "conflict"  # feed's team venue counts


def _card():
    return pd.DataFrame([{"game_id": 7, "start": "2026-11-05T00:00:00Z", "home": "Home U", "away": "Away U", "home_id": 1,
                          "away_id": 2, "neutral": True, "state": "pre", "n_books": 1, "model_margin": 3.0, "model_total": 140.0,
                          "model_home_spread": -3.0, "spread_pick": "Home U", "spread_side": "home", "spread_line": 2.0,
                          "spread_book": "DraftKings", "spread_odds": -110, "spread_edge": 5.0, "spread_p": 0.58,
                          "spread_ev": 0.1, "spread_verdict": "BET", "spread_units": 1.0, "book_lines": []}])


def _games(html):
    d = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
    return d["games"]


def test_card_mark_and_v1_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(venue, "CACHE", str(tmp_path / "venue_{}.csv"))
    rt = pd.DataFrame({"net": [1.0], "adj_oe": [1.0], "adj_de": [1.0], "adj_tempo": [1.0], "team": ["X"]}, index=[1])
    card = _card()
    before = card.copy()
    off = report_html.build(card, rt, pd.Timestamp("2026-11-05"), 2027)              # no venue file: mark off (unknown)
    pd.DataFrame([{"game_id": 7, "date": "2026-11-05", "home_id": 1, "away_id": 2, "neutral": True, "venue_id": 100,
                   "venue": "Home Arena", "city": "Springfield", "state": "IL", "event": "Classic", "home_venue_id": 100,
                   "away_venue_id": 200, "venue_state": "conflict", "reason": "flagged neutral at the home team's arena",
                   "edge": ""}]).to_csv(venue.CACHE.format("2026-11-05"), index=False)
    on = report_html.build(card, rt, pd.Timestamp("2026-11-05"), 2027)
    pd.testing.assert_frame_equal(card, before)                                       # the card (and its CSV) untouched
    strip = lambda gs: [{k: v for k, v in g.items() if not k.startswith("venue_")} for g in gs]
    assert strip(_games(on)) == strip(_games(off))                                    # every v1 field identical
    assert _games(on)[0]["venue_state"] == "conflict" and _games(off)[0]["venue_state"] == "unknown"
    assert "venueTag" in on and "Home Arena" in on
