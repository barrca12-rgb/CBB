"""Record page layout and controls (display only), on the real record page in Chromium:
no sideways scrolling from phone to wide desktop; the result and market filters; sorting by a column header, kept
after a reload; the running total follows the filter.

    python -m pytest -q audit/test_record_page.py
"""
import json
import os
import shutil
import subprocess

import pytest

from cbb import record_page

JS = r"""
const {chromium} = require('playwright');
(async () => {
  const f = process.argv[2], out = {overflow: {}, errors: []};
  const b = await chromium.launch();
  for (const w of [390, 900, 1100, 1280, 1440, 1920]) {
    const p = await b.newPage({viewport: {width: w, height: 900}});
    p.on('pageerror', (e) => out.errors.push(String(e)));
    await p.goto('file://' + f);
    out.overflow[w] = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth ||
      [...document.querySelectorAll('.scroll')].some((s) => s.scrollWidth > s.clientWidth + 1));
    await p.close();
  }
  const p = await b.newPage({viewport: {width: 1440, height: 900}});
  await p.goto('file://' + f);
  const vis = () => p.evaluate(() => [...document.getElementById('rec-v1').tBodies[0].rows].filter((r) => !r.hidden)
    .map((r) => ({res: r.dataset.res, mk: r.dataset.mk, edge: Number(r.dataset.edge)})));
  out.all = (await vis()).length;
  await p.click(".recctl[data-for='rec-v1'] .fchip[data-v='O']");
  out.open = await vis();
  await p.click(".recctl[data-for='rec-v1'] .fchip[data-grp='res'][data-v='']");
  await p.click(".recctl[data-for='rec-v1'] .fchip[data-v='spread']");
  out.spread = await vis();
  await p.click(".recctl[data-for='rec-v1'] .fchip[data-grp='mk'][data-v='']");
  await p.click("#rec-v1 th[data-k='edge']");
  out.by_edge = await vis();
  await p.reload();
  out.after_reload = await vis();
  out.sort_mark = await p.$eval("#rec-v1 th[data-k='edge']", (h) => h.getAttribute('aria-sort'));
  out.total = await p.$eval(".recctl[data-for='rec-v1'] .rectot", (e) => e.textContent);
  console.log(JSON.stringify(out));
  await b.close();
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_record_page_fits_and_sorts(tmp_path):
    f = tmp_path / "record.html"
    f.write_text(record_page.build())
    js = tmp_path / "t.js"
    js.write_text(JS)
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(js), str(f)], capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["errors"] == []
    assert not any(o["overflow"].values()), o["overflow"]
    if not o["all"]:
        pytest.skip("no plays in the log")
    assert o["open"] and all(x["res"] == "O" for x in o["open"])
    assert all(x["mk"] == "spread" for x in o["spread"])
    e = [x["edge"] for x in o["by_edge"]]
    assert e == sorted(e, reverse=True) and len(e) == o["all"]
    assert o["after_reload"] == o["by_edge"] and o["sort_mark"] == "descending"
    assert o["total"].startswith(f"Showing {o['all']} of {o['all']}")
