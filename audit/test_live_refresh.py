"""Results-only refresh (cbb/live_refresh.py, .github/workflows/live_refresh.yml; Chad, Nov 2): live scores, results
and the record between card runs, with no odds pull, no model run, nothing committed and no way to post or alert.

    python -m pytest -q audit/test_live_refresh.py
"""
import json
import os
import re
import shutil
import subprocess

import pandas as pd
import pytest

from cbb import live_refresh, report_html

ROOT = os.path.join(os.path.dirname(__file__), "..")
WF = os.path.join(ROOT, ".github", "workflows")
REPORTS = os.path.join(ROOT, "reports")
DATA = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


def _step(path: str, name: str) -> str:
    src = open(path).read()
    i = src.index(f"- name: {name}")
    j = src.index("\n\n", i)
    return "\n".join(l for l in src[i:j].splitlines() if not l.strip().startswith("if:"))


def test_publishes_the_same_site_as_the_card_run():
    assert _step(os.path.join(WF, "live_refresh.yml"), "Build site") == _step(os.path.join(WF, "update.yml"), "Build site")


def test_workflow_cannot_spend_credits_commit_post_or_alert():
    wf = open(os.path.join(WF, "live_refresh.yml")).read()
    assert "secrets." not in wf                         # no odds, KenPom, Discord or phone key reaches it
    assert "git push" not in wf and "git commit" not in wf and "contents: read" in wf
    src = open(live_refresh.__file__).read()
    imports = " ".join(re.findall(r"^\s*(?:from \S+ )?import (.+)$", src, re.M))
    for mod in ("odds", "odds_api", "kenpom", "barttorvik", "notify", "record", "public_record"):
        assert not re.search(rf"\b{mod}\b", imports), mod      # record_page is the record page, not Discord


def _days(tmp_path, cur: str, days: list[str]):
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    for d in days:
        data = json.loads(DATA.search(src).group(1))
        data["date"] = d
        for g in data["games"]:
            g.update(state="pre", home_score=0, away_score=0)
            g.pop("clock", None)
        data["record"] = {"status": "old"}
        (tmp_path / f"cbb_{d}.html").write_text(live_refresh._page(src, data))
    json.dump({"days": days, "current": cur}, open(tmp_path / "days.json", "w"))
    return json.loads(DATA.search(src).group(1))["games"]


def _load(tmp_path, d):
    return json.loads(DATA.search((tmp_path / f"cbb_{d}.html").read_text()).group(1))


def test_scores_clock_and_record_land_where_they_belong(tmp_path, monkeypatch):
    games = _days(tmp_path, "2026-11-03", ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"])
    gid = games[0]["game_id"]
    scores = lambda day: pd.DataFrame([{"game_id": gid, "state": "in", "home_score": 40, "away_score": 33}])
    monkeypatch.setattr(live_refresh, "clocks", lambda day: {str(gid): "8:41 - 2nd"})
    done = live_refresh.refresh_cards(scores, reports=str(tmp_path), rec={"status": "new"})
    assert done == ["2026-11-02", "2026-11-03", "2026-11-04"]          # two days before the current one: untouched
    for d in ("2026-11-02", "2026-11-03"):                              # last night's games and today's: live scores
        g = _load(tmp_path, d)["games"][0]
        assert (g["state"], g["home_score"], g["away_score"], g["clock"]) == ("in", 40, 33, "8:41 - 2nd")
    assert _load(tmp_path, "2026-11-04")["games"][0]["state"] == "pre"  # tomorrow: no live scores
    assert _load(tmp_path, "2026-11-02")["record"] == {"status": "old"}  # past days: refresh_past's job
    assert _load(tmp_path, "2026-11-03")["record"] == _load(tmp_path, "2026-11-04")["record"] == {"status": "new"}
    for k in ("spread_pick", "spread_line", "spread_logged_pick", "total_pick", "total_logged_line"):
        assert _load(tmp_path, "2026-11-03")["games"][1].get(k) == games[1].get(k)
    assert live_refresh.refresh_cards(scores, reports=str(tmp_path), rec={"status": "new"}) == []   # nothing new


def test_the_card_keeps_its_own_updated_time(tmp_path, monkeypatch):
    games = _days(tmp_path, "2026-11-03", ["2026-11-03"])
    before = _load(tmp_path, "2026-11-03")["generated_at"]
    monkeypatch.setattr(live_refresh, "clocks", lambda day: {})
    scores = lambda day: pd.DataFrame([{"game_id": games[0]["game_id"], "state": "post", "home_score": 70, "away_score": 60}])
    live_refresh.refresh_cards(scores, reports=str(tmp_path))
    page = (tmp_path / "cbb_2026-11-03.html").read_text()
    assert _load(tmp_path, "2026-11-03")["generated_at"] == before                      # lines' time, unchanged
    assert re.search(r'otg-built" content="([^"]+)"', page).group(1) > before         # open pages still reload


JS = r"""
const {chromium} = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1300, height: 900}});
  const errors = []; p.on('pageerror', (e) => errors.push(String(e)));
  await p.goto('file://' + process.argv[2]);
  const rows = await p.$$eval("#t-plays tbody tr[data-gid]", (r) => r.map((x) => ({gid: x.dataset.gid, mk: x.dataset.mk,
    score: (x.querySelector('.score') || {}).textContent || ""})));
  console.log(JSON.stringify({rows, errors})); await b.close();
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_play_rows_show_the_score_and_grade_like_the_bet_log(tmp_path):
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    D = json.loads(DATA.search(src).group(1))
    lg = [g for g in D["games"] if g.get("spread_logged_pick") and g.get("spread_logged_side") == "home"
          and not g.get("total_logged_pick")][:3]
    assert len(lg) == 3
    # a final that covers by 3 grades W, one that misses by 3 grades L, a live game shows the clock and no grade
    a, b, c = lg
    line = lambda g: float(g["spread_logged_line"])
    a.update(state="post", home_score=100, away_score=int(100 + line(a) - 3), clock="Final")      # covers by 3
    b.update(state="post", home_score=100, away_score=int(100 + line(b) + 3), clock="Final/OT")   # misses by 3
    c.update(state="in", home_score=40, away_score=33, clock="8:41 - 2nd")
    f = tmp_path / "card.html"
    f.write_text(live_refresh._page(src, D))
    js = tmp_path / "t.js"
    js.write_text(JS)
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(js), str(f)], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["errors"] == []
    by = {(x["gid"], x["mk"]): x["score"] for x in o["rows"]}
    assert by[(str(a["game_id"]), "spread")].startswith("Final ·") and by[(str(a["game_id"]), "spread")].endswith("W")
    assert by[(str(b["game_id"]), "spread")].startswith("Final/OT ·") and by[(str(b["game_id"]), "spread")].endswith("L")
    assert by[(str(c["game_id"]), "spread")].startswith("2nd half · 8:41 left ·") and "40" in by[(str(c["game_id"]), "spread")]
    assert not by[(str(c["game_id"]), "spread")].endswith(("W", "L", "P"))


def test_no_line_time_label_once_a_game_starts():
    """Chad, Nov 2: the card's line-freshness note is about the current line; started games have none (books take
    lines down at tip), and a pregame game with no line says so plainly."""
    t = report_html.TEMPLATE
    i = t.index("const freshTag")
    body = t[i:t.index("};", i)]
    assert 'if (g.state === "in" || g.state === "post") return "";' in body
    assert "no book has a line up right now" in body and "no current line at " in body
