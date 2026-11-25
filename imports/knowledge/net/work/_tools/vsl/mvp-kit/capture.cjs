// Capture an MVP at 60 fps, DPR 2: node capture.cjs <url> <out-dir> [seconds]
const { chromium } = require('playwright');
(async () => {
  const [url, out, secs = '12'] = process.argv.slice(2);
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2,
    recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
  const p = await ctx.newPage(); await p.goto(url); await p.waitForTimeout(+secs * 1000);
  await ctx.close(); await b.close();
})();
