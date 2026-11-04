"""Input snapshots per alert (cbb/snapshots.py): wrappers pass results through unchanged, each input behind a logged
play gets a manifest row with its hash and times, public tables are stored by hash in the repo, and KenPom's
licensed tables never land in the public repo."""
import gzip
import hashlib
import os

import pandas as pd
import pytest

from cbb import barttorvik, context, data, freshness, injuries, kenpom, run_day, snapshots

ROOT = os.path.join(os.path.dirname(__file__), "..")
DAY = pd.Timestamp("2026-11-10")


@pytest.fixture
def snap(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "MANIFEST", str(tmp_path / "input_snapshots.csv"))
    monkeypatch.setattr(snapshots, "PUBLIC", str(tmp_path / "snapshots"))
    monkeypatch.setattr(snapshots, "SEEN", str(tmp_path / "snapshots" / "seen.csv"))
    monkeypatch.setattr(snapshots, "PRIVATE", str(tmp_path / "cache" / "snapshots"))
    monkeypatch.setattr(snapshots, "ROOT", str(tmp_path))
    monkeypatch.setattr(snapshots, "STATE", {"day": None, "installed": False, "seen": None})
    monkeypatch.setattr(snapshots, "CAP", {})
    monkeypatch.setattr(kenpom, "CACHE", str(tmp_path / "kp"))
    rt = pd.DataFrame({"adj_o": [1.0, 2.0]}, index=pd.Index([10, 20], name="team_id"))
    f = pd.DataFrame({"game_id": [1], "date": [DAY], "home_id": [10], "away_id": [20], "kp_margin": [3.0],
                      "bt_margin": [2.0], "model_margin": [4.0]})
    bt = pd.DataFrame({"team": ["A", "B"], "adj_oe": [110.0, 100.0], "adj_de": [95.0, 105.0], "adj_tempo": [68.0, 70.0]})
    kp_rows = [{"TeamName": "A", "AdjOE": 110.0, "DataThrough": "Monday, November 9"}]
    lines = pd.DataFrame({"home_id": [10, 30], "away_id": [20, 40], "book": ["FanDuel", "FanDuel"], "home_spread": [-2.5, 1.0]})

    def fake_project(day, games):
        kenpom.get("ratings", cache=False, y=2027)
        barttorvik.before(day)
        injuries.adjustment(2027)
        context.live_referees(games["game_id"], "x")
        context.market(games, pd.DataFrame())
        return f, rt
    monkeypatch.setattr(run_day, "project", fake_project)
    monkeypatch.setattr(run_day, "plays", lambda f_, l_, live=True: f_.assign(spread_verdict="BET"))
    monkeypatch.setattr(kenpom, "get", lambda endpoint, cache=True, **p: kp_rows)
    monkeypatch.setattr(barttorvik, "before", lambda day: (barttorvik.LAST.update(file="2026-11-09"), bt)[1])
    monkeypatch.setattr(barttorvik, "current", lambda season: None)
    monkeypatch.setattr(data, "season_games", lambda season, refresh=False: (pd.DataFrame({"date": [], "home_pts": []}), None))
    monkeypatch.setattr(injuries, "adjustment", lambda season: (pd.DataFrame({"team_id": [10], "injury_missing": [0.2]}), pd.DataFrame()))
    monkeypatch.setattr(context, "live_referees", lambda ids, path: pd.DataFrame({"game_id": [1], "ref_fouls": [0.1], "ref_pts": [0.3], "crew": ["X"]}))
    monkeypatch.setattr(context, "market", lambda keys, closes: pd.DataFrame({"game_id": [1], "mkt_margin": [0.0]}))
    monkeypatch.setattr(freshness, "log_inputs", lambda new, fr: None)
    snapshots.install()
    out = run_day.project(DAY, pd.DataFrame({"game_id": [1]}))
    card = run_day.plays(out[0], lines, live=True)
    return {"f": f, "rt": rt, "bt": bt, "kp": kp_rows, "card": card, "out": out, "tmp": tmp_path}


BET = {"bet_id": "2026-11-10|1|spread|home", "date": "2026-11-10", "game_id": 1, "home_id": 10, "away_id": 20,
       "market": "spread", "side": "home"}


def test_wrappers_pass_results_through_unchanged(snap):
    assert snap["out"][0] is snap["f"] and snap["out"][1] is snap["rt"]
    assert list(snap["card"]["spread_verdict"]) == ["BET"]


def test_each_input_behind_a_logged_play_is_recorded_with_hash_and_times(snap):
    freshness.log_inputs([BET], None)          # the card's call when a play is logged
    m = snapshots.for_bet(BET["bet_id"])
    got = set(m["input"])
    assert {"kenpom_ratings", "barttorvik", "stage1_ratings", "injuries", "referees", "market_context", "features",
            "lines", "config:data/projection.json"} <= got
    assert set(m["provider_published_at"]) == {"unknown"}
    bt = m[m["input"] == "barttorvik"].iloc[0]
    assert bt["source_date"] == "2026-11-09" and bt["storage"] == "repo"
    raw = snapshots.load(bt["path"])
    assert hashlib.sha256(raw).hexdigest() == bt["sha256"]
    assert pd.read_csv(pd.io.common.BytesIO(raw)).equals(snap["bt"])        # the actual table, not only its hash
    assert bt["first_observed_at"] != ""                                   # seen.csv got it on the plays() run
    lines = pd.read_csv(pd.io.common.BytesIO(snapshots.load(m[m["input"] == "lines"].iloc[0]["path"])))
    assert set(lines["home_id"]) == {10}                                   # only the play's game


def test_kenpom_tables_stay_out_of_the_public_store(snap):
    freshness.log_inputs([BET], None)
    m = snapshots.for_bet(BET["bet_id"])
    kp = m[m["input"] == "kenpom_ratings"].iloc[0]
    assert kp["storage"] == "private runner cache" and kp["path"].startswith("cache/snapshots/kenpom/")
    assert kp["source_date"] == "Monday, November 9"
    pub = snap["tmp"] / "snapshots"
    assert not any("kenpom" in str(p.relative_to(pub)).lower() for p in pub.rglob("*"))
    with gzip.open(snap["tmp"] / kp["path"]) as fh:
        assert b"AdjOE" in fh.read()


def test_a_table_is_stored_once(snap):
    freshness.log_inputs([BET], None)
    freshness.log_inputs([dict(BET, bet_id="2026-11-10|1|total|over", market="total", side="over")], None)
    files = list((snap["tmp"] / "snapshots" / "barttorvik").glob("*.gz"))
    assert len(files) == 1


def test_no_kenpom_file_is_committed_under_bets():
    d = os.path.join(ROOT, "bets", "snapshots")
    if os.path.isdir(d):
        for base, dirs, files in os.walk(d):
            assert "kenpom" not in base.lower() and not any("kenpom" in f.lower() for f in files)
