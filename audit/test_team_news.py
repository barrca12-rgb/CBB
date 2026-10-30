"""Team news on the card (cbb/team_news.py): league-wide stories ESPN tags with dozens of teams are left out, and an
article tagged with both teams of a game shows once, naming both.

    python -m pytest -q audit/test_team_news.py
"""
import io
import json

import pandas as pd

from cbb import team_news

NOW = pd.Timestamp("2026-10-30T15:00:00Z")


def _art(aid, head, team_ids):
    return {"id": aid, "headline": head, "description": "", "published": "2026-10-30T12:00:00Z",
            "categories": [{"type": "team", "teamId": t} for t in team_ids], "links": {"web": {"href": "u"}}}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_league_stories_dropped_and_shared_story_once(monkeypatch, tmp_path):
    feed = {"2390": [_art(1, "Coaches weigh in on eligibility chaos", list(range(100, 144)) + [2390, 57]),
                     _art(2, "Miami and Florida guard ruled out", [2390, 57])],
            "57": [_art(1, "Coaches weigh in on eligibility chaos", list(range(100, 144)) + [2390, 57]),
                   _art(2, "Miami and Florida guard ruled out", [2390, 57]),
                   _art(3, "Florida forward suspended", [57])]}
    monkeypatch.setattr(team_news.urllib.request, "urlopen",
                        lambda req, timeout=10: _Resp(json.dumps({"articles": feed[req.full_url.split("team=")[1].split("&")[0]]}).encode()))
    monkeypatch.setattr(team_news, "LOG", str(tmp_path / "log.csv"))
    monkeypatch.setattr(team_news, "WATCH", str(tmp_path / "none.csv"))
    card = pd.DataFrame([{"game_id": 1, "away_id": 2390, "home_id": 57, "spread_verdict": "BET", "total_verdict": "PASS"}])
    flag = team_news.annotate(card, NOW)["news_flag"].iloc[0]
    assert "eligibility chaos" not in flag
    assert flag.count("ruled out") == 1 and "suspended" in flag
