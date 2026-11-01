"""The card builds the whole coming week every run, lines or not (Chad, Oct 31), and the live fetches repeated by each
day's build are made once per run (cbb/card_features.memoize_run_fetches).

    python -m pytest -q audit/test_week_ahead.py
"""
import sys

import pandas as pd

from cbb import card_features, injuries, kenpom, players, run_day


def test_auto_run_builds_the_next_seven_days(monkeypatch):
    today = pd.Timestamp("2026-11-02")
    built = []
    monkeypatch.setattr(run_day, "today_et", lambda: today)
    monkeypatch.setattr(run_day, "slate", lambda d: pd.DataFrame() if d == today + pd.Timedelta(days=3) else
                        (_ for _ in ()).throw(OSError("ESPN down")) if d == today + pd.Timedelta(days=5) else pd.DataFrame([{"game_id": 1}]))
    monkeypatch.setattr(run_day, "build", lambda d, games, lines, replay=False, current=True: built.append((f"{d:%m-%d}", current)))
    monkeypatch.setattr(run_day.odds, "pull", lambda: pd.DataFrame(columns=["book", "start", "home_id", "away_id", "home_spread", "total"]))
    for name in ("settle", "alert_voided"):
        monkeypatch.setattr(run_day.tracker, name, lambda *a, **k: 0)
    monkeypatch.setattr(run_day.public_record, "sync", lambda: 0)
    monkeypatch.setattr(run_day.record_page, "write", lambda: None)
    monkeypatch.setattr(run_day.injury_watch, "check", lambda: None)
    monkeypatch.setenv("KENPOM_API_KEY", "x")
    monkeypatch.setattr(run_day.pd.Timestamp, "now", classmethod(lambda cls, tz=None: pd.Timestamp("2026-11-02 12:00", tz=tz)))
    monkeypatch.setattr(sys, "argv", ["run_day", "--auto"])
    run_day.main()
    # today current; Nov 3, 4, 6, 7, 8, 9 built (Nov 5 has no games; Nov 7's schedule failed and is skipped)
    assert built == [("11-02", True), ("11-03", False), ("11-04", False), ("11-06", False), ("11-08", False), ("11-09", False)]


def test_repeat_fetches_happen_once_per_run(monkeypatch):
    calls = {"kp": 0, "inj": 0, "av": 0}
    monkeypatch.setattr(kenpom, "get", lambda endpoint, cache=True, **p: calls.__setitem__("kp", calls["kp"] + 1) or [{"x": 1}])
    monkeypatch.setattr(injuries, "fetch", lambda: calls.__setitem__("inj", calls["inj"] + 1) or pd.DataFrame())
    monkeypatch.setattr(players, "availability", lambda season, upcoming=False, refresh=False: calls.__setitem__("av", calls["av"] + 1) or pd.DataFrame())
    card_features.memoize_run_fetches()
    for _ in range(7):                                 # seven days' builds
        kenpom.get("ratings", cache=False, y=2027)
        injuries.fetch()
        players.availability(2027, upcoming=True, refresh=True)
    kenpom.get("archive", d="2026-11-01")              # cached endpoints pass straight through
    kenpom.get("archive", d="2026-11-01")
    assert calls == {"kp": 3, "inj": 1, "av": 1}
