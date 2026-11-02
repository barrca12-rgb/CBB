"""The other side of a held game and market is never logged (cbb/tracker.log; Chad, Nov 1, after Over 146 was logged
against a standing Under 149.5 on Notre Dame-Villanova: "we didn't play both spots"), and the card never shows it as
a play or a watch.

    python -m pytest -q audit/test_opposite_side.py
"""
import html as H
import json
import os
import re
import shutil
import subprocess

import pandas as pd
import pytest

from cbb import report_html, run_day, tracker

DAY = pd.Timestamp("2026-11-04")
ST = {"spread": 1.0, "total": 1.0}


def _card(margin: float, total: float = 140.0) -> pd.DataFrame:
    """One game against one book at -110 both ways: home -10, total 140."""
    f = pd.DataFrame([{"game_id": 1, "start": "2026-11-05T00:00:00Z", "home": "Home", "away": "Away", "home_id": 10,
                       "away_id": 20, "neutral": False, "state": "pre", "final_margin": margin, "final_total": total}])
    lines = pd.DataFrame([{"home_id": 10, "away_id": 20, "book": "DraftKings", "home_spread": -10.0,
                           "home_spread_odds": -110, "away_spread_odds": -110, "total": 140.0, "over_odds": -110,
                           "under_odds": -110}])
    return run_day.plays(f, lines)


@pytest.fixture
def log(monkeypatch, tmp_path):
    monkeypatch.setattr(tracker, "BETS", str(tmp_path / "bets.csv"))
    return tmp_path


def _sides(mk: str) -> list[str]:
    b = tracker.load("all")
    return sorted(b.loc[b["market"] == mk, "side"].astype(str))


def test_a_held_under_blocks_a_later_over(log):
    assert [x["side"] for x in tracker.log(_card(10.0, 136.0), DAY, ST)] == ["under"]    # under 140, edge 4
    assert tracker.log(_card(10.0, 144.0), DAY, ST) == []                                # model moved: over, edge 4
    assert _sides("total") == ["under"]


def test_a_held_spread_side_blocks_the_other_side(log):
    tracker.log(_card(12.5), DAY, ST)                                                    # home -10, edge 2.5
    assert tracker.log(_card(7.0), DAY, ST) == []                                        # away +10, edge 3
    assert _sides("spread") == ["home"]


def test_a_band_b_play_blocks_the_other_side_for_v1(log):
    tracker.log_band_b(_card(12.2), DAY)                                                 # band B home, edge 2.2
    assert tracker.log(_card(7.0), DAY, ST) == []
    assert _sides("spread") == ["home"]


def test_the_same_side_still_joins_band_b(log):
    tracker.log_band_b(_card(12.2), DAY)
    assert [x["side"] for x in tracker.log(_card(12.6), DAY, ST)] == ["home"]           # the approved overlap
    assert _sides("spread") == ["home", "home"]


def test_a_void_bet_does_not_hold_the_game(log):
    tracker.log(_card(12.5), DAY, ST)
    b = tracker.load("all")
    b.loc[b["side"] == "home", "status"] = "void"
    tracker.save(b)
    assert [x["side"] for x in tracker.log(_card(7.0), DAY, ST)] == ["away"]


def test_the_other_market_is_not_blocked(log):
    tracker.log(_card(12.5), DAY, ST)                                                    # spread home
    assert [x["market"] for x in tracker.log(_card(12.5, 144.0), DAY, ST)] == ["total"]


def test_the_notre_dame_case_is_blocked_on_the_real_log(log):
    """The real bet log: Under 149.5 settled, Over 146 void. A fresh Over BET on that game is not logged."""
    real = os.path.join(os.path.dirname(__file__), "..", "bets", "bets.csv")
    shutil.copy(real, tracker.BETS)
    n0 = len(tracker.load("all"))
    c = pd.DataFrame([{"game_id": 401920982, "home_id": 222, "away_id": 87, "home": "Villanova", "away": "Notre Dame",
                       "spread_verdict": "PASS", "total_verdict": "BET", "total_pick": "Over", "total_line": 146.0,
                       "total_odds": -110.0, "total_book": "Fanatics", "total_edge": 3.38, "model_margin": 1.0,
                       "model_total": 149.38}])
    assert tracker.log(c, pd.Timestamp("2026-11-01"), ST) == []
    assert len(tracker.load("all")) == n0


JS = r"""
const {chromium} = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({viewport: {width: 1400, height: 900}});
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));
  await p.goto('file://' + process.argv[2]);
  const gid = process.argv[3];
  await p.click(".seg button[data-m='total']");
  const edge = await p.$$eval("#t-board tbody.g[data-gid='" + gid + "'] td.edge", (c) => c.map((x) => x.textContent.trim()));
  const plays = await p.$$eval("#t-plays tbody tr[data-gid='" + gid + "']", (r) => r.map((x) => x.dataset.mk));
  const watch = await p.$$eval("#t-watch tbody.g[data-gid='" + gid + "']", (r) => r.length);
  console.log(JSON.stringify({edge, plays, watch, errors}));
  await b.close();
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_the_card_never_shows_the_other_side_as_a_play(tmp_path):
    """A real card game set to: Under logged, model now a BET on the Over. The board shows Logged on the under row
    and nothing on the over row; Plays lists the logged Under only; no watch row."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "reports", "cbb_2026-11-02.html")).read()
    D = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1))
    # a game with a total and no spread play, so only the total can show (the live card's games change every run)
    g = next(x for x in D["games"] if x.get("total_line") is not None and not x.get("spread_logged_pick")
             and x.get("spread_verdict") != "BET" and not x.get("spread_bandb_pick"))
    g.update(total_verdict="BET", total_pick="Over", total_edge=3.5, total_logged_pick="Under 150", total_logged_side="under",
             total_logged_line=150.0, total_logged_book="DraftKings", total_logged_odds=-110.0, total_logged_edge=4.0)
    page = (report_html.TEMPLATE.replace("__HEAD__", report_html.HEAD).replace("__BRAND__", report_html.BRAND)
            .replace("__X__", report_html.X_HANDLE).replace("__TITLE__", H.escape("t"))
            .replace("__DATA__", json.dumps(D).replace("</", "<\\/")).replace("__BUILT__", "").replace("__AUTOREFRESH__", ""))
    f = tmp_path / "card.html"
    f.write_text(page)
    js = tmp_path / "t.js"
    js.write_text(JS)
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(js), str(f), str(g["game_id"])], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["errors"] == []
    assert o["edge"][0] == "" and o["edge"][1].startswith("Logged Under")     # over row: no BET tag
    assert o["plays"] == ["total"]                                           # the logged Under only
    assert o["watch"] == 0
