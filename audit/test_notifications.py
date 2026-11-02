"""Only main (v1) plays reach the notifications (Chad, Nov 2): Discord posts, cancellation alerts and new-play phone
alerts never carry band B or the pre-rule line-move plays. Both are still logged and graded on the record page.

    python -m pytest -q audit/test_notifications.py
"""
import inspect
import json

import pandas as pd
import pytest

from cbb import clv_primary, notify, record, run_day, tipoff, tracker


def _row(bid, bet_type="", status="open", result=None, profit=None):
    return {"bet_id": bid, "date": "2026-11-04", "game_id": int(bid.split("|")[1]), "market": "spread",
            "pick": f"Team {bid.split('|')[1]} -3", "side": "home", "home_id": 10, "away_id": 20, "home": "Home",
            "away": "Away", "line": -3.0, "alert_line": -3.0, "odds": -110.0, "book": "DraftKings", "edge": 3.0,
            "model": 6.0, "stake": 1.0 if not bet_type else 0.5, "placed": "yes", "logged_at": "2026-11-03T12:00:00+00:00",
            "status": status, "result": result, "profit": profit, "home_score": 80 if result else None,
            "away_score": 70 if result else None, "bet_type": bet_type or None}


@pytest.fixture
def log(monkeypatch, tmp_path):
    bets = pd.DataFrame([_row("2026-11-04|1|spread|home", status="settled", result="W", profit=0.909),
                         _row("2026-11-04|2|spread|home|bandB", "bandB", status="settled", result="W", profit=0.45),
                         _row("2026-11-04|3|spread|home", status="settled", result="W", profit=0.909),   # pre-rule line move
                         _row("2026-11-04|4|spread|home", status="void"),
                         _row("2026-11-04|5|spread|home|bandB", "bandB", status="void"),
                         _row("2026-11-04|6|spread|home", status="void")]).reindex(columns=tracker.COLS)  # 6: line move
    p = tmp_path / "bets.csv"
    bets.to_csv(p, index=False)
    pd.DataFrame({"bet_id": ["2026-11-04|3|spread|home", "2026-11-04|6|spread|home"]}).to_csv(tmp_path / "pre.csv", index=False)
    monkeypatch.setattr(tracker, "BETS", str(p))
    monkeypatch.setattr(tracker, "PRERULE", str(tmp_path / "pre.csv"))
    monkeypatch.setattr(tracker, "VOID_ALERTED", str(tmp_path / "void_alerted.json"))
    monkeypatch.setattr(record, "STATE", str(tmp_path / "posted.json"))
    monkeypatch.setattr(record, "ANNOUNCEMENTS", str(tmp_path / "ann.json"))
    monkeypatch.setattr(tipoff, "refresh", lambda b: None)
    monkeypatch.setattr(clv_primary, "attach", lambda b: b.assign(clv_pts=None, clv_reason=""))
    return tmp_path


def test_discord_posts_main_plays_only(log, monkeypatch):
    sent = []
    monkeypatch.setattr(record, "post", lambda payload, url=None: sent.append(json.dumps(payload)) or "1")
    monkeypatch.setattr(record, "_logged", lambda b: {"content": "logged " + b["bet_id"]})
    monkeypatch.setattr(record, "_settled", lambda b: {"content": "settled " + b["bet_id"]})
    record._sync("https://example.invalid")
    text = " ".join(sent)
    assert "|1|" in text and "|4|" in text                       # the main play's post and result; the main void
    for gid in ("|2|", "|3|", "|5|", "|6|"):                      # band B and line-move: never posted
        assert gid not in text


def test_cancellation_alerts_main_plays_only(log, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "message", lambda title, body, *a, **k: sent.append(body) or True)
    assert tracker.alert_voided() == 1
    assert "Team 4" in sent[0]


def test_new_band_b_plays_send_no_alert_or_post():
    src = inspect.getsource(run_day.build)
    i = src.index("new_b = tracker.log_band_b(card, day)")
    block = src[i:i + 1200]
    assert "notify.send(new_b" not in block and "public_record.sync()" not in block
