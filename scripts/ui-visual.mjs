// ui-visual.mjs — automated visual regression against the LAST PASSING BUILD (utopia-models/knowledge#14826).
// Canonical copy: utopia-models/knowledge _infra/ci/ui-gate/ui-visual.mjs — a site repo carries a byte-identical copy.
//
//   node ui-visual.mjs check  <base-url> [route ...]   compare every route to design/baseline/ ; exit 1 on a diff
//   node ui-visual.mjs record <base-url> [route ...]   overwrite design/baseline/ with this build (run on main, after
//                                                      the gate passed — the new "last passing build")
//
// No human approves a baseline (Tyler, 2026-11-17: "I don't even need to approve it"). The baseline is simply the
// previous build that passed the gate; `record` is run by CI on merge to main, never by hand to quiet a red check.
// Viewports: phone 390x844 (WebKit) and desktop 1440x900 (Chromium), full page, animations off, reduced motion.
// A route passes when differing pixels <= MAX_DIFF_RATIO (default 0.002) of the page. A route with no baseline yet
// passes with a notice (first build) and is written by `record`. Exit 2 = could not check.
// Diff images are written to design/baseline/_diff/ (gitignore it) and the failing names are printed.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, webkit } from 'playwright';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';

const [mode, base, ...argRoutes] = process.argv.slice(2);
if (!['check', 'record'].includes(mode) || !base) { console.error('usage: ui-visual.mjs check|record <base-url> [route ...]'); process.exit(2); }
const cfg = existsSync('design/ui-gate.json') ? JSON.parse(readFileSync('design/ui-gate.json', 'utf8')) : {};
const routes = argRoutes.length ? argRoutes : (cfg.routes || ['/']);
const dir = process.env.BASELINE_DIR || 'design/baseline';
const maxRatio = Number(process.env.MAX_DIFF_RATIO || 0.002);
const runs = [
  { name: 'desktop', type: chromium, ctx: { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' } },
  { name: 'phone', type: webkit, ctx: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, reducedMotion: 'reduce' } },
];
const slug = r => (r.replace(/^\/+|\/+$/g, '').replace(/[^a-z0-9]+/gi, '-') || 'home').toLowerCase();
mkdirSync(join(dir, '_diff'), { recursive: true });
let failed = 0, shot = 0;
for (const run of runs) {
  const browser = await run.type.launch(run.type === chromium ? { args: ['--no-sandbox'] } : {});
  const ctx = await browser.newContext(run.ctx);
  for (const r of routes) {
    const page = await ctx.newPage();
    const name = `${slug(r)}-${run.name}.png`, file = join(dir, name);
    try {
      const resp = await page.goto(new URL(r, base).toString(), { waitUntil: 'load', timeout: 30000 });
      if (!resp || resp.status() >= 400) { console.log(`::error::${name}: HTTP ${resp ? resp.status() : 'none'}`); failed = 1; continue; }
      await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
      await page.waitForTimeout(400);
      const buf = await page.screenshot({ fullPage: true });
      shot++;
      if (mode === 'record') { mkdirSync(dir, { recursive: true }); writeFileSync(file, buf); console.log(`recorded ${file}`); continue; }
      if (!existsSync(file)) { console.log(`::notice::${name}: no baseline yet (first build) — passes; CI records it on merge`); continue; }
      const a = PNG.sync.read(readFileSync(file)), b = PNG.sync.read(buf);
      if (a.width !== b.width || a.height !== b.height) {
        console.log(`::error::${name}: size changed ${a.width}x${a.height} -> ${b.width}x${b.height}`); failed = 1;
        writeFileSync(join(dir, '_diff', name), buf); continue;
      }
      const diff = new PNG({ width: a.width, height: a.height });
      const n = pixelmatch(a.data, b.data, diff.data, a.width, a.height, { threshold: 0.1 });
      const ratio = n / (a.width * a.height);
      if (ratio > maxRatio) { console.log(`::error::${name}: ${n} px differ (${(ratio * 100).toFixed(3)}% > ${(maxRatio * 100).toFixed(3)}%)`); failed = 1; writeFileSync(join(dir, '_diff', name), PNG.sync.write(diff)); }
      else console.log(`ok ${name} (${n} px)`);
    } catch (e) { console.log(`::error::${name}: ${e.message}`); failed = 1; }
    finally { await page.close(); }
  }
  await browser.close();
}
process.exit(shot === 0 ? 2 : failed);
