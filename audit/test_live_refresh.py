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


def test_a_card_run_keeps_the_game_clock(monkeypatch):
    """Chad, Nov 2 ("it's not showing half and time anymore"): each card run rebuilt the page without the clock until
    the next results refresh. The card build now reads the clock itself (ESPN's free scoreboard)."""
    card = pd.read_csv(os.path.join(REPORTS, "cbb_2026-11-02.csv"))
    card.loc[0, "state"] = "in"
    rt = pd.DataFrame({"net": [1.0], "adj_oe": [110.0], "adj_de": [100.0], "adj_tempo": [68.0], "team": ["X"]}, index=[1])
    monkeypatch.setattr(live_refresh, "clocks", lambda day: {str(card["game_id"].iloc[0]): "15:48 - 2nd"})
    page = report_html.build(card, rt, pd.Timestamp("2026-11-02"), 2027)
    assert json.loads(DATA.search(page).group(1))["games"][0]["clock"] == "15:48 - 2nd"
    monkeypatch.setattr(live_refresh, "clocks", lambda day: (_ for _ in ()).throw(OSError("down")))
    assert "clock" not in json.loads(DATA.search(report_html.build(card, rt, pd.Timestamp("2026-11-02"), 2027)).group(1))["games"][0]


TICK = r"""
const {chromium} = require('playwright');
(async () => {
  const [file, gid] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1300, height: 900}});
  const errors = []; p.on('pageerror', (e) => errors.push(String(e)));
  let n = 0;
  await p.route(/site\.api\.espn\.com/, (r) => { n++; const fin = n > 1; return r.fulfill({status: 200, contentType: 'application/json',
    headers: {'access-control-allow-origin': '*'}, body: JSON.stringify({events: [{id: gid, status: {type: {state: fin ? 'post' : 'in',
    shortDetail: fin ? 'Final' : '3:05 - 2nd'}}, competitions: [{competitors: [{homeAway: 'home', score: fin ? '200' : '61'},
    {homeAway: 'away', score: '55'}]}]}]})}); });
  await p.goto('file://' + file);
  const sel = "#t-plays .score[data-g='" + gid + "']";
  await p.waitForTimeout(2500);
  const one = await p.$eval(sel, (e) => e.textContent);
  const board = await p.$$eval(".sc[data-g='" + gid + "']", (es) => es.map((e) => e.textContent));
  await p.evaluate(() => window.otgLiveTick()); await p.waitForTimeout(500);
  const two = await p.$eval(sel, (e) => e.textContent);
  console.log(JSON.stringify({one, board, two, errors})); await b.close();
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_the_page_updates_its_own_scores_and_clock(tmp_path):
    """Chad, Nov 2 ("time not updating"): while a game is on, the page reads ESPN's scoreboard every 30 seconds and
    repaints scores, the clock and the final W/L in place, between site publishes."""
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    D = json.loads(DATA.search(src).group(1))
    g = next(x for x in D["games"] if x.get("spread_logged_pick") and x.get("spread_logged_side") == "home"
             and float(x["spread_logged_line"]) > -100)
    g.update(state="in", home_score=40, away_score=33, clock="8:41 - 2nd")
    f = tmp_path / "card.html"
    f.write_text(live_refresh._page(src, D))
    js = tmp_path / "t.js"
    js.write_text(TICK)
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(js), str(f), str(g["game_id"])], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["errors"] == []
    assert o["one"].startswith("2nd half · 3:05 left") and "55" in o["one"] and "61" in o["one"]
    assert o["board"] == ["55", "61"]
    assert o["two"].startswith("Final") and o["two"].endswith("W")      # home won by 145: covers any home line


def _hold_setup(tmp_path, games_state):
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    data = json.loads(DATA.search(src).group(1))
    data["games"] = [dict(data["games"][0], game_id=1, state=st, start=start) for st, start in games_state]
    (tmp_path / "cbb_2026-11-02.html").write_text(live_refresh._page(src, data))
    json.dump({"days": ["2026-11-02", "2026-11-03"], "current": "2026-11-03"}, open(tmp_path / "days.json", "w"))


def test_home_page_holds_tonight_until_the_last_game_is_final(tmp_path):
    """Chad, Nov 2: "keep home page on tonight until last game ends"."""
    now = pd.Timestamp("2026-11-03T02:00:00Z")                        # 9 pm ET Nov 2: the card run made Nov 3 current
    no_scores = lambda day: pd.DataFrame()
    _hold_setup(tmp_path, [("post", "2026-11-02T23:00Z"), ("in", "2026-11-03T01:00Z")])
    assert live_refresh.hold_tonight(str(tmp_path), no_scores, now, fresh_card=True) == "2026-11-02"
    dj = json.load(open(tmp_path / "days.json"))
    assert dj["current"] == "2026-11-02" and dj["held_from"] == "2026-11-03"
    # a game still to tip holds it too; a postponed one (tip long past, never started) does not
    _hold_setup(tmp_path, [("pre", "2026-11-03T04:59Z")])
    assert live_refresh.hold_tonight(str(tmp_path), no_scores, now, fresh_card=True) == "2026-11-02"
    _hold_setup(tmp_path, [("post", "2026-11-02T23:00Z"), ("pre", "2026-11-02T17:00Z")])
    assert live_refresh.hold_tonight(str(tmp_path), no_scores, now, fresh_card=True) == "2026-11-03"
    # the results refresh releases it once the scoreboard says the last game is final
    _hold_setup(tmp_path, [("in", "2026-11-03T01:00Z")])
    live_refresh.hold_tonight(str(tmp_path), no_scores, now, fresh_card=True)
    final = lambda day: pd.DataFrame([{"game_id": 1, "state": "post", "home_score": 70, "away_score": 60}])
    assert live_refresh.hold_tonight(str(tmp_path), final, now) == "2026-11-03"
    assert json.load(open(tmp_path / "days.json")) == {"days": ["2026-11-02", "2026-11-03"], "current": "2026-11-03"}


def test_card_run_applies_the_hold_after_its_own_build():
    src = open(os.path.join(ROOT, "cbb", "card_features.py")).read()
    main = src[src.index('if __name__ == "__main__":'):]
    assert main.index("run_day.main()") < main.index("refresh_past") < main.index("hold_tonight(fresh_card=True)")


RELIST = r"""
const {chromium} = require('playwright');
(async () => {
  const [file, gid, home, away] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 1300, height: 900}});
  await p.route(/site\.api\.espn\.com/, (r) => r.fulfill({status: 200, contentType: 'application/json',
    headers: {'access-control-allow-origin': '*'}, body: JSON.stringify({events: [{id: gid, status: {type: {state: 'in',
    shortDetail: '6:43 - 1st'}}, competitions: [{competitors: [{homeAway: 'home', team: {id: away}, score: '15'},
    {homeAway: 'away', team: {id: home}, score: '34'}]}]}]})}));
  await p.goto('file://' + file); await p.waitForTimeout(2500);
  console.log(JSON.stringify(await p.$$eval(".sc[data-g='" + gid + "']", (es) => es.map((e) => [e.dataset.sd, e.textContent]))));
  await b.close();
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_the_page_puts_live_scores_on_the_right_team_when_espn_relists_home(tmp_path):
    src = open(os.path.join(REPORTS, "cbb_2026-11-02.html")).read()
    D = json.loads(DATA.search(src).group(1))
    g = D["games"][0]
    g.update(state="in", home_score=0, away_score=0)
    f = tmp_path / "card.html"
    f.write_text(live_refresh._page(src, D))
    js = tmp_path / "t.js"
    js.write_text(RELIST)
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(js), str(f), str(g["game_id"]), str(g["home_id"]), str(g["away_id"])],
                       capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    assert dict(json.loads(r.stdout.strip().splitlines()[-1])) == {"home": "34", "away": "15"}   # ESPN's "home" is our away


def test_every_refresh_publishes_the_charts_page(tmp_path, monkeypatch):
    """Nov 3 ("charts page doesn't work"): record/charts.html is built on the runner, never saved in the repo; a refresh
    that graded nothing published the site without it, so the Charts tab returned 404 until the next card run."""
    from cbb import record_page, tracker
    monkeypatch.setattr(record_page, "CHARTS", str(tmp_path / "record" / "charts.html"))
    monkeypatch.setattr(tracker, "settle", lambda *a, **k: 0)
    monkeypatch.setattr(live_refresh, "hold_tonight", lambda *a, **k: json.load(open(os.path.join(REPORTS, "days.json")))["current"])
    monkeypatch.setattr(live_refresh, "refresh_cards", lambda *a, **k: [])
    monkeypatch.setattr(report_html, "refresh_past", lambda *a, **k: [])
    live_refresh.main()
    assert (tmp_path / "record" / "charts.html").read_text().startswith("<!doctype html>")


def test_logged_plays_show_the_model_from_when_they_were_logged():
    """Nov 3: an Over logged at +3 sat beside today's model total below the line. The Model column is the model when
    the play was logged (matching its edge); today's model and edge are on the line underneath."""
    t = report_html.TEMPLATE
    assert 'g[mk + "_logged_model"]' in t and "(edge now " in t
    src = open(os.path.join(REPORTS, "cbb_2026-11-03.html")).read()
    D = json.loads(DATA.search(src).group(1))
    for g in D["games"]:
        g.pop("total_logged_model", None)
        g.pop("spread_logged_model", None)
    live_refresh._fill_logged_models(D["games"], "2026-11-03")
    g = next(x for x in D["games"] if x["game_id"] == 401909796)
    assert abs(g["total_logged_model"] - 161.51) < 0.01
