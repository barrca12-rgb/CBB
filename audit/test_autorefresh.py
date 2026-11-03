"""Auto refresh (cbb/autorefresh.py) in a real browser, on a real card served over HTTP.

  1. same build on the server: no reload
  2. newer build published: the page reloads itself, the URL is clean, and the odds-board tab, "Plays only" and the
     scroll position are kept; no JavaScript error
  3. a reload that lands on an older copy (cache behind): no second reload for 10 minutes
  4. a replay card has no auto refresh; the record page has it

    python -m audit.test_autorefresh
"""
from __future__ import annotations

import functools
import html as H
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import threading

import pytest

from cbb import autorefresh, report_html

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORTS = os.path.join(ROOT, "reports")
DAY = "2026-11-02"


def page(built: str, title: str) -> str:
    src = open(os.path.join(REPORTS, f"cbb_{DAY}.html")).read()
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1)
    return (report_html.TEMPLATE.replace("__HEAD__", report_html.HEAD).replace("__BRAND__", report_html.BRAND)
            .replace("__X__", report_html.X_HANDLE).replace("__TITLE__", H.escape(title)).replace("__DATA__", data)
            .replace("__BUILT__", autorefresh.meta(built)).replace("__AUTOREFRESH__", autorefresh.SCRIPT))


JS = r"""
const {chromium} = require('playwright');
const fs = require('fs');
(async () => {
  const [base, file, newer] = process.argv.slice(2);
  const out = {errors: []};
  const b = await chromium.launch();
  const p = await b.newPage({viewport: {width: 1200, height: 900}});
  p.on('pageerror', (e) => out.errors.push(String(e)));
  let navs = 0;
  p.on('load', () => navs++);
  await p.goto(base + '/card.html');
  await p.click(".seg button[data-m='total']");
  await p.check('#only-plays');
  await p.evaluate(() => window.scrollTo(0, 1500));
  await p.waitForTimeout(4500);                           // first check (3 s) sees the same build
  out.same_build_navs = navs - 1;
  fs.writeFileSync(file, fs.readFileSync(newer));         // publish a newer build
  await Promise.all([p.waitForEvent('framenavigated', {timeout: 15000}),
                     p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))]);
  await p.waitForLoadState('load');
  await p.waitForTimeout(1200);
  out.title = await p.title();
  out.url = p.url();
  out.market = await p.$eval(".seg button[aria-pressed='true']", (e) => e.dataset.m);
  out.only = await p.$eval('#only-plays', (e) => e.checked);
  out.scroll = await p.evaluate(() => window.scrollY);
  out.keep_left = await p.evaluate(() => Object.keys(sessionStorage).length);

  // 3: the check sees a newer build but the reload gets an older copy
  const q = await b.newPage();
  q.on('pageerror', (e) => out.errors.push(String(e)));
  const old = fs.readFileSync(file, 'utf8').replace(/otg-built" content="[^"]+"/, 'otg-built" content="2026-01-01T00:00:00+00:00"');
  await q.route('**/card.html?fresh=*', (r) => r.fulfill({body: old.replace('2026-01-01T00:00:00', '2099-01-01T00:00:00'), contentType: 'text/html'}));
  await q.route(/card\.html(\?t=\d+)?$/, (r) => r.fulfill({body: old, contentType: 'text/html'}));
  let qn = 0;
  q.on('load', () => qn++);                               // page loads only (the URL clean-up is not a load)
  await q.goto(base + '/card.html');
  await q.waitForTimeout(5000);                           // first check: newer -> one reload, lands on the old copy
  await q.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await q.waitForTimeout(3000);
  out.backoff_reloads = qn - 1;
  console.log(JSON.stringify(out));
  await b.close();
})();
"""


def main() -> int:
    fails = []
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "card.html")
        open(f, "w").write(page("2026-11-01T10:00:00+00:00", "Old build"))
        open(os.path.join(d, "newer.html"), "w").write(page("2026-11-01T10:10:00+00:00", "New build"))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
            type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=d))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        js = os.path.join(d, "t.js")
        open(js, "w").write(JS)
        r = subprocess.run(["node", js, f"http://127.0.0.1:{srv.server_address[1]}", f, os.path.join(d, "newer.html")],
                           capture_output=True, text=True, timeout=180, cwd=d,
                           env=dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True,
                                                                         text=True).stdout.strip()))
        srv.shutdown()
    if r.returncode:
        print(r.stderr)
        return 1
    o = json.loads(r.stdout.strip().splitlines()[-1])
    print(o)
    checks = {"no reload on the same build": o["same_build_navs"] == 0,
              "reloaded to the newer build": o["title"] == "New build",
              "URL clean after reload": o["url"].endswith("/card.html"),
              "odds-board tab kept": o["market"] == "total",
              "Plays only kept": o["only"] is True,
              "scroll kept": abs(o["scroll"] - 1500) < 5,
              "nothing left in sessionStorage": o["keep_left"] == 0,
              "one reload, then back off on an older copy": o["backoff_reloads"] == 1,
              "no JavaScript error": not o["errors"]}
    # 4: replay cards carry none of it; the record page does
    import pandas as pd
    from cbb import record_page
    card = pd.read_csv(os.path.join(REPORTS, f"cbb_{DAY}.csv"))
    rt = pd.DataFrame({"team": ["A"], "net": [1.0], "adj_oe": [1.0], "adj_de": [1.0], "adj_tempo": [1.0]}, index=[1])
    live = report_html.build(card, rt, pd.Timestamp(DAY), 2027)
    rep = report_html.build(card, rt, pd.Timestamp(DAY), 2027, replay=True)
    stamp = re.search(r'<meta name="otg-built" content="([^"]+)">', live)
    checks["live card: build time matches generated_at"] = bool(stamp) and f'"generated_at": "{stamp.group(1)}"' in live
    checks["replay card: no auto refresh"] = "otg-built" not in rep and "otg-keep" not in rep and "__" + "AUTOREFRESH" not in rep
    rec = record_page.build()
    checks["record page: auto refresh"] = "otg-built" in rec and "otg-keep" in rec
    for k, ok in checks.items():
        print(("ok    " if ok else "FAIL  ") + k)
        if not ok:
            fails.append(k)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())


NAV = r"""
const {chromium} = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage(); const reqs = [];
  p.on('request', (r) => { if (r.resourceType() === 'document') reqs.push(r.url()); });
  await p.goto(process.argv[2] + '/a.html'); await p.click('#l'); await p.waitForLoadState('load'); await p.waitForTimeout(300);
  console.log(JSON.stringify({requested: reqs, final: p.url()})); await b.close(); })();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_links_between_pages_open_the_newest_copy(tmp_path):
    """Chad, Nov 2 ("records aren't matching on all tabs"): a tab opened from the browser's cache showed an older
    record. Links between the site's pages now request a fresh copy and drop the query on arrival."""
    import functools
    import http.server
    import threading
    for name, other in (("a.html", "b.html"), ("b.html", "a.html")):
        (tmp_path / name).write_text("<!doctype html><html><head>" + autorefresh.meta("2026-11-03T02:00:00+00:00") +
                                     f"</head><body><a id=l href='{other}'>go</a>" + autorefresh.SCRIPT + "</body></html>")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler,
                                                                            directory=str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        js = tmp_path / "nav.js"
        js.write_text(NAV)
        env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
        r = subprocess.run(["node", str(js), f"http://127.0.0.1:{srv.server_address[1]}"], capture_output=True, text=True,
                           timeout=120, env=env)
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert re.search(r"/b\.html\?t=\d+$", o["requested"][-1]) and o["final"].endswith("/b.html")
