"""Card logic check: render real cards with the current template and test every display rule in a browser.

Each card's data (the JSON inside reports/cbb_<date>.html) is rendered with today's cbb/report_html.TEMPLATE, opened in
headless Chromium, and checked against the rules below for both markets. Read only; nothing is written to reports/.

  board     a logged side shows "Logged <pick>" and never BET or Watch; an unlogged pick side shows BET for a BET
            verdict and Watch for a WATCH verdict; every other side shows nothing
  watch     no row for a logged side; one row for each unlogged WATCH
  plays     each logged bet listed once; each unlogged BET listed once (none when the market is already logged)
  filter    "Plays only" keeps every game with a BET or a logged bet, and only those
  data      no game has more than one logged (non-void) bet in a market (the card can show only one)
  errors    no JavaScript error

    python -m audit.card_logic                  # every card in reports/days.json
    python -m audit.card_logic 2026-11-02       # one day
"""
from __future__ import annotations

import html as H
import json
import os
import re
import subprocess
import sys
import tempfile

import pandas as pd

from cbb import report_html

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORTS = os.path.join(ROOT, "reports")

JS = r"""
const {chromium} = require('playwright');
(async () => {
  const files = JSON.parse(process.argv[1]);
  const b = await chromium.launch();
  const out = {};
  for (const f of files) {
    const p = await b.newPage({viewport: {width: 1400, height: 900}});
    const errs = [];
    p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('file://' + f);
    await p.waitForTimeout(300);
    const res = {errors: errs, problems: []};
    const D = await p.evaluate(() => JSON.parse(document.getElementById('data').textContent));
    const side = (g, mk) => g[mk + '_logged_pick'] ? String(g[mk + '_logged_side'] || '').toLowerCase() : null;
    const pickSide = (g, mk) => mk === 'spread' ? g.spread_side : String(g.total_pick || '').toLowerCase();
    for (const mk of ['spread', 'total']) {
      await p.click(".seg button[data-m='" + mk + "']");
      await p.waitForTimeout(50);
      const cells = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('#t-board tbody.g')]
        .map((t) => [t.dataset.gid, [...t.querySelectorAll('td.edge')].map((c) => c.textContent.trim())])));
      for (const g of D.games) {
        const c = cells[String(g.game_id)];
        if (!c) { res.problems.push(`${g.away} at ${g.home}: not on the board`); continue; }
        const sides = mk === 'spread' ? ['away', 'home'] : ['over', 'under'];
        sides.forEach((sd, i) => {
          const ls = side(g, mk), v = g[mk + '_verdict'], ps = pickSide(g, mk);
          const want = ls === sd ? 'Logged' : (ps === sd && v === 'BET') ? 'BET' : (ps === sd && v === 'WATCH') ? 'Watch' : '';
          const got = c[i] || '';
          if (want ? !got.startsWith(want) : got !== '') res.problems.push(`${g.away} at ${g.home} ${mk} ${sd}: board shows "${got}", expected ${want || 'nothing'}`);
        });
      }
    }
    const watch = await p.evaluate(() => [...document.querySelectorAll('#t-watch tbody tr')].map((r) => r.dataset.gid + '|' + r.dataset.mk));
    const plays = await p.evaluate(() => [...document.querySelectorAll('#t-plays tbody tr[data-gid]')].map((r) => r.dataset.gid + '|' + r.dataset.mk));
    const count = (a, k) => a.filter((x) => x === k).length;
    for (const g of D.games) for (const mk of ['spread', 'total']) {
      const k = g.game_id + '|' + mk, ls = side(g, mk), v = g[mk + '_verdict'], ps = pickSide(g, mk);
      const wantW = v === 'WATCH' && ls !== ps ? 1 : 0;
      if (count(watch, k) !== wantW) res.problems.push(`${g.away} at ${g.home} ${mk}: ${count(watch, k)} watch row(s), expected ${wantW}`);
      const wantP = (ls ? 1 : 0) + (!ls && v === 'BET' ? 1 : 0);
      if (count(plays, k) !== wantP) res.problems.push(`${g.away} at ${g.home} ${mk}: ${count(plays, k)} play row(s), expected ${wantP}`);
      if (ls && v === 'BET' && ps !== ls) res.problems.push(`${g.away} at ${g.home} ${mk}: logged ${ls}, model now a BET on ${ps} (not listed under Plays)`);
    }
    await p.click("#only-plays");
    await p.waitForTimeout(50);
    const shown = await p.evaluate(() => [...document.querySelectorAll('#t-board tbody.g')].map((t) => t.dataset.gid));
    const want = D.games.filter((g) => g.spread_verdict === 'BET' || g.total_verdict === 'BET' || side(g, 'spread') || side(g, 'total')).map((g) => String(g.game_id));
    for (const w of want) if (!shown.includes(w)) res.problems.push(`Plays only: game ${w} missing`);
    for (const s of shown) if (!want.includes(s)) res.problems.push(`Plays only: game ${s} shown without a play`);
    res.games = D.games.length; res.watch = watch.length; res.plays = plays.length;
    out[f] = res;
    await p.close();
  }
  await b.close();
  console.log(JSON.stringify(out));
})();
"""


def render(day: str, folder: str) -> str:
    """The day's card data rendered with the current template."""
    src = open(os.path.join(REPORTS, f"cbb_{day}.html")).read()
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1)
    title = H.unescape(re.search(r"<title>(.*?)</title>", src, re.S).group(1))
    page = (report_html.TEMPLATE.replace("__HEAD__", report_html.HEAD).replace("__BRAND__", report_html.BRAND)
            .replace("__X__", report_html.X_HANDLE).replace("__TITLE__", H.escape(title)).replace("__DATA__", data))
    path = os.path.join(folder, f"cbb_{day}.html")
    open(path, "w").write(page)
    return path


def data_check() -> list[str]:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[b["status"] != "void"]
    d = b.groupby(["date", "game_id", "market"]).size()
    return [f"{k[0]} game {k[1]} {k[2]}: {n} logged bets; the card shows only the last" for k, n in d[d > 1].items()]


def main() -> int:
    days = sys.argv[1:] or json.load(open(os.path.join(REPORTS, "days.json")))["days"]
    with tempfile.TemporaryDirectory() as tmp:
        files = [render(d, tmp) for d in days if os.path.exists(os.path.join(REPORTS, f"cbb_{d}.html"))]
        r = subprocess.run(["node", "-e", JS, json.dumps(files)], capture_output=True, text=True, cwd=tmp, timeout=600)
        if r.returncode:
            print(r.stderr)
            return 2
        res = json.loads(r.stdout)
    bad = 0
    for f, x in res.items():
        p = x["problems"] + [f"JS error: {e}" for e in x["errors"]]
        bad += len(p)
        print(f"{os.path.basename(f)}: {x['games']} games, {x['plays']} plays, {x['watch']} watch rows, "
              f"{'OK' if not p else str(len(p)) + ' problem(s)'}")
        for q in p:
            print("   - " + q)
    for q in data_check():
        bad += 1
        print("data: " + q)
    print("ALL OK" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
