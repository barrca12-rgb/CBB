"""Sharp-market shadow: orientation of the gap, and Novig's empty ladder rungs are ignored."""
import pandas as pd

from cbb import shadow_sharp as ss


def test_gap_orientation():
    s = pd.Series({"home_spread": -24.5, "total": 152.5})
    assert ss.gap(pd.Series({"market": "spread", "side": "home", "line": -23.5}), s) == 1.0   # we lay 1 fewer
    assert ss.gap(pd.Series({"market": "spread", "side": "away", "line": 26.5}), s) == 2.0    # we get 2 more
    assert ss.gap(pd.Series({"market": "total", "side": "under", "line": 154.5}), s) == 2.0
    assert ss.gap(pd.Series({"market": "total", "side": "over", "line": 151.5}), s) == 1.0


def test_empty_ladder_rungs_dropped(tmp_path, monkeypatch):
    lines = tmp_path / "lines"
    lines.mkdir()
    pd.DataFrame([
        {"book": "Novig", "event_id": "e", "start": "2026-11-07T00:30:00Z", "home_id": 1, "away_id": 2,
         "home_spread": -24.5, "home_spread_odds": -111, "away_spread_odds": 100, "total": 131.5,
         "over_odds": -100000, "under_odds": -9900, "last_update": "x", "pulled_at": "2026-11-06T03:30:37+00:00"},
    ]).to_csv(lines / "novig_log.csv", index=False)
    monkeypatch.setattr(ss, "ROOT", str(tmp_path))
    q = ss.quotes()
    assert q["home_spread"].iloc[0] == -24.5      # real market kept
    assert pd.isna(q["total"].iloc[0])            # -9900 / -100000 rung dropped
