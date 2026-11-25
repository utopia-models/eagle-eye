#!/usr/bin/env node
// test_pwa_refresh.mjs: pwa.js reloads a page whose code changed on the server, and only then (WebKit).
//   PLAYWRIGHT_DIR=<dir with playwright> EAGLE_ACCESS_CLIENT_ID=.. EAGLE_ACCESS_CLIENT_SECRET=.. node test_pwa_refresh.mjs
// Runs against the live /icon page (static), with /pwa.js swapped for the local file and the page body switched mid-test.
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const here = path.dirname(fileURLToPath(import.meta.url));
const { webkit } = createRequire(path.join(process.env.PLAYWRIGHT_DIR, 'package.json'))('playwright');
const H = { 'CF-Access-Client-Id': process.env.EAGLE_ACCESS_CLIENT_ID, 'CF-Access-Client-Secret': process.env.EAGLE_ACCESS_CLIENT_SECRET };
const b = await webkit.launch(); const c = await b.newContext({ extraHTTPHeaders: H, serviceWorkers: 'block' }); const p = await c.newPage(); // real-browser-check: ok (webkit test of our own PWA, no login to any third party)
let version = 1, loads = 0;
await p.addInitScript(() => { window.EE_CHECK_MS = 400; window.EE_IDLE_MS = 0; });
await p.route('**/pwa.js', r => r.fulfill({ body: fs.readFileSync(path.join(here, 'pwa/pwa.js')), contentType: 'text/javascript' }));
await p.route('**/icon', async r => {
  const res = await r.fetch(); let body = await res.text();
  if (r.request().resourceType() === 'document') loads++;
  if (!body.includes('/pwa.js')) body = body.replace('</body>', '<script src="/pwa.js"></script></body>');
  r.fulfill({ response: res, body: body.replace('</title>', `</title><!-- v${version} -->`) });
});
await p.goto('https://eagle.utopiamodels.ai/icon'); await p.waitForTimeout(6000);
const stable = loads; if (stable !== 1) { console.log('FAIL: reloaded with no change, loads =', loads); process.exit(1); }
version = 2; await p.waitForTimeout(3000);
if (loads < 2) { console.log('FAIL: did not reload after a change, loads =', loads); process.exit(1); }
console.log('ok: 1 load while unchanged, reloaded after the change (loads =', loads + ')'); await b.close();
