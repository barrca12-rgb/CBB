"""Input freshness stamp (cbb/freshness.py; Chad's Nov 1 brief, item 1): fresh, stale and unknown cases; the wrappers
pass every result through unchanged; v1's card columns are byte-identical with the stamp on and off; the sidecar
bets/inputs.csv round-trips.

    python -m pytest -q audit/test_freshness.py
"""
import pandas as pd
import pytest

from cbb import barttorvik, context, data, freshness, injuries, kenpom, odds

NOW = pd.Timestamp("2026-11-05T18:00:00Z")


def test_fresh_stale_unknown():
    ok = {"kenpom": NOW - pd.Timedelta(hours=2), "barttorvik": NOW - pd.Timedelta(hours=20),
          "injuries": NOW - pd.Timedelta(hours=1), "schedule": NOW - pd.Timedelta(hours=1), "lines": NOW - pd.Timedelta(minutes=5)}
    assert freshness.judge(ok, NOW) == ("fresh", "")
    st, why = freshness.judge(dict(ok, barttorvik=NOW - pd.Timedelta(hours=40)), NOW)
    assert st == "stale" and why == "Barttorvik 40h"
    st, why = freshness.judge(dict(ok, lines=NOW - pd.Timedelta(minutes=25)), NOW)
    assert st == "stale" and why == "line 25m"
    st, why = freshness.judge(dict(ok, injuries=None), NOW)
    assert st == "unknown" and "injury report" in why
    assert freshness.judge(dict(ok, barttorvik=None), NOW) == ("unknown", "no Barttorvik ratings yet, KenPom used in their place")
    assert freshness.judge(dict(ok, injuries=None, kenpom=NOW - pd.Timedelta(hours=50)), NOW)[0] == "stale"   # stale wins


@pytest.fixture
def wrapped(monkeypatch):
    calls = {}
    monkeypatch.setattr(kenpom, "get", lambda endpoint, cache=True, **p: [{"DataThrough": "2026-11-04", "TeamName": "X"}])
    monkeypatch.setattr(barttorvik, "snapshot", lambda day: pd.DataFrame({"a": [1]}) if pd.Timestamp(day) <= pd.Timestamp("2026-11-03") else None)
    monkeypatch.setattr(barttorvik, "current", lambda season: None)
    monkeypatch.setattr(injuries, "fetch", lambda: pd.DataFrame({"p": [1]}))
    monkeypatch.setattr(data, "fetch", lambda kind, season, refresh=False: pd.DataFrame({"k": [kind]}))
    monkeypatch.setattr(context, "live_officials", lambda ids: pd.DataFrame({"game_id": [7], "official": ["Ref"]}))
    monkeypatch.setattr(freshness, "SEEN", {})
    freshness.watch()
    return calls


def test_wrappers_pass_results_through_and_record(wrapped):
    assert kenpom.get("ratings", cache=False, y=2027) == [{"DataThrough": "2026-11-04", "TeamName": "X"}]
    assert freshness.SEEN["kenpom"]["data_through"] == "2026-11-04"
    for k in range(1, 8):                                     # barttorvik.before's look-back, through the wrapper
        if barttorvik.snapshot(pd.Timestamp("2026-11-05") - pd.Timedelta(days=k)) is not None:
            break
    assert freshness.SEEN["barttorvik"]["snapshot"] == "2026-11-03"       # the file actually used: two days back
    assert list(injuries.fetch()["p"]) == [1] and freshness.SEEN["injuries"]["ok"]
    assert list(data.fetch("schedule", 2027)["k"]) == ["schedule"]
    assert set(context.live_officials([7])["game_id"]) == {7} and 7 in freshness.SEEN["referees"]["games"]


def _card():
    return pd.DataFrame([{"game_id": 7, "home_id": 1, "away_id": 2, "spread_book": "DraftKings", "spread_verdict": "BET",
                          "total_book": "FanDuel", "total_verdict": "BET", "model_margin": 3.0}])


def test_card_columns_unchanged_and_sidecar_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(freshness, "INPUTS", str(tmp_path / "inputs.csv"))
    monkeypatch.setattr(freshness, "SEEN", {"kenpom": {"at": NOW - pd.Timedelta(hours=1), "data_through": "2026-11-04"},
                                            "barttorvik": {"snapshot": "2026-11-03"},
                                            "injuries": {"ok": True, "at": NOW - pd.Timedelta(hours=1)},
                                            "hoopr": {("schedule", 2027): {"ok": True, "at": NOW - pd.Timedelta(hours=1)}},
                                            "referees": {"at": NOW, "games": {7}}})
    monkeypatch.setattr(odds.pull, "pulled_at", (NOW - pd.Timedelta(minutes=4)).isoformat(), raising=False)
    lines = pd.DataFrame([{"home_id": 1, "away_id": 2, "book": "DraftKings", "pulled_at": None},          # this run's pull
                          {"home_id": 1, "away_id": 2, "book": "FanDuel", "pulled_at": (NOW - pd.Timedelta(minutes=40)).isoformat()}])
    card = _card()
    fr = freshness.stamp(card, pd.Timestamp("2026-11-05"), lines, run_at=NOW)
    r = fr.iloc[0]
    assert r["spread_fresh"] == "stale" and "Barttorvik" in r["spread_stale_inputs"]      # snapshot ended Nov 3: 42h
    assert "line 40m" in r["total_stale_inputs"]
    on = freshness.trail(card, fr)
    pd.testing.assert_frame_equal(on[card.columns], card)                                 # every v1 column unchanged
    assert list(on.columns[:len(card.columns)]) == list(card.columns)                      # stamp only trails
    assert on.drop(columns=card.columns).columns.str.contains("fresh|_line_|stale").all()
    freshness.log_inputs([{"bet_id": "2026-11-05|7|spread|home", "game_id": 7, "market": "spread"},
                          {"bet_id": "2026-11-05|7|total|over", "game_id": 7, "market": "total"}], fr)
    back = pd.read_csv(freshness.INPUTS, dtype=str)
    assert list(back.columns) == freshness.INPUT_COLS and len(back) == 2
    assert freshness.for_bet("2026-11-05|7|spread|home")["state"] == "stale"
    assert back.loc[1, "line_book"] == "FanDuel" and back.loc[1, "referees_at"] != ""


def test_missing_feed_alerts_once_after_24h(tmp_path, monkeypatch):
    monkeypatch.setattr(freshness, "ALERTED", str(tmp_path / "a.json"))
    sent = []
    from cbb import notify
    monkeypatch.setattr(notify, "message", lambda t, b, **k: sent.append(t) or True)
    monkeypatch.setattr(freshness, "LAST", {"inputs": {"barttorvik": None}})
    freshness.alert_stale(NOW)                                   # first miss: starts the clock
    freshness.alert_stale(NOW + pd.Timedelta(hours=25))          # 25h missing: one alert
    freshness.alert_stale(NOW + pd.Timedelta(hours=30))          # still missing: no repeat
    assert sent == ["CBB: Barttorvik stale"]
