"""Novig is show-only (Chad, Oct 30, option 2): its quotes ride the card's Odds API call but never reach the card's
lines, the quote log or a close; they are kept apart for display beside each play.

    python -m pytest -q audit/test_novig.py
"""
import pandas as pd

from cbb import notify, odds_api

LOOK = {"homeu": 10, "awayu": 20}   # teams.norm("Home U"), teams.norm("Away U")


def _event(start="2099-01-01T00:00:00Z"):
    def book(key, hs, hp, ap, t, op, up):
        return {"key": key, "title": key, "last_update": pd.Timestamp.now(tz="UTC").isoformat(), "markets": [
            {"key": "spreads", "outcomes": [{"name": "Home U", "price": hp, "point": hs}, {"name": "Away U", "price": ap, "point": -hs}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": op, "point": t}, {"name": "Under", "price": up, "point": t}]}]}
    return {"id": "e1", "commence_time": start, "home_team": "Home U", "away_team": "Away U",
            "bookmakers": [book("draftkings", -4.5, -110, -110, 140.5, -110, -110), book("novig", -4.5, -102, -104, 140.5, -101, -105)]}


def test_novig_never_reaches_the_card_lines_or_the_quote_log():
    df, _ = odds_api.parse([_event()], LOOK)
    assert list(df["book"]) == ["DraftKings"]
    assert {o["book"] for o in odds_api.parse.observations} == {"DraftKings"}
    d = odds_api.parse_display([_event()], LOOK)
    assert list(d["book"]) == ["Novig"] and d.iloc[0]["home_spread_odds"] == -102


def test_display_quote_orients_to_our_home_and_away(tmp_path):
    d = odds_api.parse_display([_event()], LOOK)
    q = odds_api.display_quote(10, 20, d)
    assert odds_api.display_side(q, "spread", "home") == (-4.5, -102)
    f = odds_api.display_quote(20, 10, d)                      # our card lists the game the other way round
    assert odds_api.display_side(f, "spread", "away") == (-4.5, -102)
    assert odds_api.display_side(f, "total", "over") == (140.5, -101)


def test_change_log_appends_only_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(odds_api, "NOVIG_LATEST", str(tmp_path / "latest.csv"))
    monkeypatch.setattr(odds_api, "NOVIG_LOG", str(tmp_path / "log.csv"))
    d = odds_api.parse_display([_event()], LOOK)
    odds_api.save_display(d)
    odds_api.save_display(d)
    assert len(pd.read_csv(odds_api.NOVIG_LOG)) == 1


def test_compare_labels():
    assert notify.compare("spread", "home", -4.5, -102, -4.5, -110) == "better price"
    assert notify.compare("spread", "away", 5.0, -110, 4.5, -110) == "better number"
    assert notify.compare("total", "over", 140.0, -115, 140.5, -110) == "better number, worse price"
    assert notify.compare("total", "under", 140.5, -115, 140.5, -110) == ""
