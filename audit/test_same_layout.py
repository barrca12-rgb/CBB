"""Every date's card is built from the same template with the same sections and controls (Chad, Nov 1: "make sure
all dates have the same set up"), and Novig is no longer shown anywhere on the card.

    python -m pytest -q audit/test_same_layout.py
"""
import json
import os
import re

from cbb import report_html

REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
DATA = re.compile(r'<script id="data" type="application/json">.*?</script>', re.S)


def _layout(path: str) -> str:
    """The page with its own data, title and build time taken out: what is left is the layout."""
    s = DATA.sub("", open(path).read())
    s = re.sub(r"<title>.*?</title>", "", s, flags=re.S)
    s = re.sub(r'<meta property="og:title" content="[^"]*">', "", s)
    return re.sub(r'<meta name="otg-built" content="[^"]*">', "", s)


def test_today_and_every_future_date_have_the_same_layout():
    dj = json.load(open(os.path.join(REPORTS, "days.json")))
    days = [d for d in dj["days"] if d >= dj["current"]]   # today and the coming week (past days are never rebuilt)
    pages = [os.path.join(REPORTS, f"cbb_{d}.html") for d in days if os.path.exists(os.path.join(REPORTS, f"cbb_{d}.html"))]
    layouts = {os.path.basename(p): _layout(p) for p in pages}
    first = next(iter(layouts.values()))
    assert all(v == first for v in layouts.values()), [k for k, v in layouts.items() if v != first]


def test_no_novig_on_the_card():
    assert "novig" not in report_html.TEMPLATE.lower()
    assert not hasattr(report_html, "_novig_view")


def test_past_days_get_final_scores_the_current_record_and_todays_layout(tmp_path):
    """refresh_past: a past day's page takes the final scores, today's record block and today's layout; picks and
    logged numbers are untouched; a second run with nothing new rewrites nothing; today and later are left alone."""
    import shutil
    import pandas as pd
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    d = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1))
    g0 = d["games"][0]
    d["games"][0] = dict(g0, state="pre", home_score=0, away_score=0)
    d["record"] = {"status": "stale"}
    old_page = src.replace(re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1),
                           json.dumps(d).replace("</", "<\\/")).replace("rephead", "oldbar")
    (tmp_path / "cbb_2026-10-31.html").write_text(old_page)
    shutil.copy(os.path.join(REPORTS, "cbb_2026-11-02.html"), tmp_path / "cbb_2026-11-02.html")
    json.dump({"days": ["2026-10-31", "2026-11-02"], "current": "2026-11-02"}, open(tmp_path / "days.json", "w"))
    scores = lambda day: pd.DataFrame([{"game_id": g0["game_id"], "state": "post", "home_score": 81, "away_score": 77}])
    today = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1))["record"]
    assert report_html.refresh_past(scores, reports=str(tmp_path)) == ["2026-10-31"]
    new = (tmp_path / "cbb_2026-10-31.html").read_text()
    nd = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', new, re.S).group(1))
    g = nd["games"][0]
    assert (g["state"], g["home_score"], g["away_score"]) == ("post", 81, 77)
    assert nd["record"] == today and "rephead" in new and "oldbar" not in new
    for k in ("spread_pick", "spread_line", "spread_verdict", "total_pick", "total_line"):
        assert nd["games"][1].get(k) == d["games"][1].get(k)
    assert report_html.refresh_past(scores, reports=str(tmp_path)) == []
    assert (tmp_path / "cbb_2026-11-02.html").read_text() == src
