// Render an HTML file to a 1600x900 PNG (social/graphics.py).
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
  await p.goto('file://' + process.argv[2]);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0));
  await p.evaluate(() => Promise.all([...document.images].map((i) => i.decode())));
  await p.waitForTimeout(1500);
  await p.screenshot({ path: process.argv[3] });
  await b.close();
})();
