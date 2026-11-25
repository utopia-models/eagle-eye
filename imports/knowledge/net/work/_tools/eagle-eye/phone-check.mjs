#!/usr/bin/env node
// phone-check.mjs: the gate for any change to Eagle Eye's home page (knowledge#14223). Two checks, exit 1 on either:
//
// 1. PHONE: at 360, 390 and 412 px wide (several heights, Chromium mobile + WebKit), no two visible components overlap
//    (the HUNTS/ROOSTS headings, every lane row, the person switcher, the eye's drawn box, the mark; and inside each
//    row its name, agent, count, latest line and the Upwork badge), nothing leaves the page, nothing scrolls sideways, and
//    the canvas keeps its aspect (its CSS box is the size of its bitmap: Tyler 2026-11-16, "the eye is too large").
//    The eye is the desktop eye (round 3, Tyler 2026-11-16: "doesn't look the same as the desktop view eye"): lids
//    1.75 R wide as on desktop, spanning 85-92% of the width; the page scrolls down to it rather than shrinking it.
// 2. DESKTOP LOCK (Tyler 2026-11-16: "the desktop view is perfect, the half desktop view is perfect as well"): at
//    1440x900 and 960x1080 the candidate's layout (the box of every element) is identical to the live page's.
//
// The candidate is the live page with named assets swapped for local files, so it runs before a deploy:
//   eval "$(bash _infra/scripts/occ-access.sh --env)"
//   node net/work/_tools/eagle-eye/phone-check.mjs --asset /home-v2.js=out/home-v2.js --asset /who.js=net/work/_tools/eagle-eye/who.js ...
// With no --asset it checks the live page as it is (the desktop lock is then trivially equal).
// Playwright: the site-audit install (_infra/scripts/site-audit, `npm ci`) or PLAYWRIGHT_DIR.
import { createRequire } from 'module';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const pwDir = process.env.PLAYWRIGHT_DIR || path.resolve(here, '../../../../_infra/scripts/site-audit');
const { chromium, webkit } = createRequire(path.join(pwDir, 'package.json'))('playwright');

const args = process.argv.slice(2);
let url = 'https://eagle.utopiamodels.ai/', shots = null, deskAllow = null; const assets = {};
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--asset') { const [k, v] = args[++i].split('='); assets[k] = path.resolve(v); }
  else if (args[i] === '--shots') shots = args[++i];
  else if (args[i] === '--desk-allow') deskAllow = new RegExp(args[++i]);
  else url = args[i];
}
if (shots) fs.mkdirSync(shots, { recursive: true });
const headers = process.env.CF_ACCESS_CLIENT_ID
  ? { 'CF-Access-Client-Id': process.env.CF_ACCESS_CLIENT_ID, 'CF-Access-Client-Secret': process.env.CF_ACCESS_CLIENT_SECRET } : {};
const SETTLE = +(process.env.SETTLE || 6000);

// the live bytes of every swapped asset: the desktop lock routes BOTH sides the same way, so routing itself is no diff
const liveAssets = {};
for (const k of Object.keys(assets)) {
  const r = await fetch(new URL(k, url), { headers }); if (!r.ok) throw new Error(`live ${k}: HTTP ${r.status}`);
  liveAssets[k] = Buffer.from(await r.arrayBuffer());
}
const mine = Object.fromEntries(Object.entries(assets).map(([k, f]) => [k, fs.readFileSync(f)]));

async function open(engine, w, h, mobile, swap) {
  if (swap === true) swap = mine;
  const b = await engine.launch();
  const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, hasTouch: mobile,
    isMobile: engine === chromium && mobile ? true : undefined, extraHTTPHeaders: headers });
  const p = await ctx.newPage();
  if (swap) for (const [k, body] of Object.entries(swap))
    await p.route(u => new URL(u).pathname === k, r => r.fulfill({ body, contentType: 'text/javascript; charset=utf-8' }));
  await p.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(SETTLE);
  return { b, p };
}

// every component's box, plus the facts the checks need
const MEASURE = () => {
  const R = e => { const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
  const vis = e => { const c = getComputedStyle(e), r = e.getBoundingClientRect(); return c.display !== 'none' && c.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const out = { W: innerWidth, H: innerHeight, sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, top: [], rows: [] };
  const add = (name, e) => { if (e && vis(e)) out.top.push({ name, ...R(e) }); };
  document.querySelectorAll('#e2 .grp h3').forEach((e, i) => add('heading ' + e.textContent.trim(), e));
  document.querySelectorAll('#e2 .gly').forEach(e => add('row ' + (e.getAttribute('aria-label') || e.dataset.i), e));
  add('switcher', document.getElementById('ee-who'));
  add('mark', document.querySelector('#e2 #mark'));
  const eye = document.querySelector('#e2 #eyebox'); if (eye) { const r = R(eye); if (r.w) out.top.push({ name: 'eye', ...r }); out.eye = { r: +eye.dataset.r, lid: +eye.dataset.lid }; }
  document.querySelectorAll('#e2 .gly').forEach(g => {
    const parts = [], gt = g.querySelector('.gt'), nm = gt && gt.firstChild;
    if (nm && nm.nodeType === 3) { const rg = document.createRange(); rg.selectNodeContents(nm); const r = rg.getBoundingClientRect();
      parts.push({ name: 'name', x: r.left, y: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }); }
    for (const [n, s] of [['glyph', '.gs svg'], ['agent', 'i.ag'], ['count', 'small.num'], ['latest', 'small.why'], ['badge', '.upb']]) {
      const e = g.querySelector(s); if (!e || !vis(e)) continue;
      // the agent's box after the room kept for the badge (its text ellipsizes inside it)
      if (n === 'agent') { const r = R(e), pl = parseFloat(getComputedStyle(e).paddingLeft) || 0; parts.push({ ...r, name: n, x: r.x + pl, w: r.w - pl }); continue; }
      parts.push({ name: n, ...R(e) });
    }
    out.rows.push({ row: g.getAttribute('aria-label') || '', parts });
  });
  const cv = document.querySelector('#e2 canvas.main');
  if (cv) { const r = cv.getBoundingClientRect(); out.canvas = { cssW: r.width, cssH: r.height, bw: cv.width, bh: cv.height };
    // an emulator's 100vh IS innerHeight, but Chrome on Android's 100vh is the viewport with its toolbar hidden (taller),
    // which stretched the eye on the RAW Pixel: so read which height rule wins and fail a plain vh one
    const spec = sel => (sel.match(/#/g) || []).length * 100 + (sel.match(/[.:\[]/g) || []).length * 10 + (sel.match(/(^|[\s>+~])[a-z]/gi) || []).length;
    let best = null;
    for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch (e) { continue; }
      for (const ru of rules) { if (!ru.selectorText || !ru.style.height) continue;
        for (const sel of ru.selectorText.split(',')) { try { if (!cv.matches(sel)) continue; } catch (e) { continue; }
          const sp = spec(sel) + (ru.style.getPropertyPriority('height') ? 1e6 : 0);
          if (!best || sp >= best.sp) best = { sp, h: ru.style.height, sel }; } } }
    if (best) out.canvas.rule = best.sel.trim() + ' { height: ' + best.h + ' }'; }
  return out;
};
// the eye as drawn (Tyler 12:22 MT: "make sure the circle of the eye is a circle ... wider as in the eyelid"): read the
// canvas's own pixels, mapped to CSS px by the canvas's CSS box, so a stretched canvas shows as an ellipse here.
// iris = the outer edge of the gold rim on the four axes (inside the lids, which sit at 1.16 R); lids = the box of
// the lash dust. Returns CSS px.
const EYE_SCAN = () => {
  const cv = document.querySelector('#e2 canvas.main'), eb = document.querySelector('#e2 #eyebox');
  if (!cv || !eb || !eb.dataset.r) return null;
  const R = +eb.dataset.r, b = eb.getBoundingClientRect(), cr = cv.getBoundingClientRect();
  const sx = cv.width / cr.width, sy = cv.height / cr.height;
  const ccx = b.left + b.width / 2 - cr.left, ccy = b.top + b.height / 2 - cr.top;
  const x0 = Math.max(0, Math.floor((b.left - cr.left) * sx)), y0 = Math.max(0, Math.floor((b.top - cr.top) * sy));
  const w = Math.min(cv.width - x0, Math.ceil(b.width * sx)), h = Math.min(cv.height - y0, Math.ceil(b.height * sy));
  const img = cv.getContext('2d').getImageData(x0, y0, w, h).data;
  const L = (X, Y) => { X = Math.round(X); Y = Math.round(Y); if (X < 0 || Y < 0 || X >= w || Y >= h) return 0; const i = (Y * w + X) * 4; return .3 * img[i] + .59 * img[i + 1] + .11 * img[i + 2]; };
  const bx = x => (x + cr.left - b.left) * sx, by = y => (y + cr.top - b.top) * sy;   // CSS (canvas-relative) -> image px
  // the brightest of a 5-px strip across the scan line
  const at = (x, y, horiz) => { let m = 0; for (let k = -2; k <= 2; k++) m = Math.max(m, horiz ? L(bx(x), by(y) + k) : L(bx(x) + k, by(y))); return m; };
  const rim = (dx, dy) => {   // outermost pixel above half the peak between 0.9 R and 1.06 R
    let peak = 0, prof = [];
    for (let d = .9 * R; d <= 1.06 * R; d += .25) { const v = at(ccx + dx * d, ccy + dy * d, dy === 0); prof.push([d, v]); peak = Math.max(peak, v); }
    let edge = null; for (const [d, v] of prof) if (v >= peak * .5) edge = d; return edge;
  };
  const iris = { w: rim(-1, 0) + rim(1, 0), h: rim(0, -1) + rim(0, 1) };
  // the lids: the box of every column and row holding 6+ pixels brighter than any star (a stray grain is one pixel or two)
  const T = 130, cols = new Array(w).fill(0), rows = new Array(h).fill(0);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (L(x, y) > T) { cols[x]++; rows[y]++; }
  const first = a => a.findIndex(v => v >= 6), last = a => a.length - 1 - [...a].reverse().findIndex(v => v >= 6);
  const lids = { w: (last(cols) - first(cols) + 1) / sx, h: (last(rows) - first(rows) + 1) / sy };
  return { R, iris: { ...iris, ratio: iris.w / iris.h }, lids: { ...lids, ratio: lids.w / lids.h }, W: innerWidth };
};
// every box keyed by what it is (tag, id, class, its lane row, its label text, nth such), so a removed element is reported
// as removed and does not shift every box after it
const LAYOUT = () => { const seen = {};
  return [...document.querySelectorAll('#e2 *, #ee-who, #ee-who *')]
  .filter(e => !(e instanceof SVGElement) || e.tagName === 'svg')
  .map(e => { const r = e.getBoundingClientRect(), g = e.closest('.gly, .grp');
    // labels (headings, units, agent names) are part of the key; live data (a latest line, a count) is not, so a feed
    // update between the two loads is no diff
    const own = /^(H3|EM|I)$/.test(e.tagName) ? [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ').slice(0, 24) : '';
    let k = e.tagName + (e.id ? '#' + e.id : '') + '.' + (typeof e.className === 'string' ? e.className : '') + ' @' + (g ? (g.getAttribute('aria-label') || g.id || '') : '') + ' "' + own + '"';
    seen[k] = (seen[k] || 0) + 1; k += ' #' + seen[k];
    return [k, Math.round(r.left * 2) / 2, Math.round(r.top * 2) / 2, Math.round(r.width * 2) / 2, Math.round(r.height * 2) / 2]; }); };

// the eye is alive (dust drifts, particles flow), so one frame is noisy by ~2%: read nine frames 250 ms apart and take
// the median of each ratio
async function eyeScan(p) {
  const r = [];
  for (let i = 0; i < 9; i++) { r.push(await p.evaluate(EYE_SCAN)); await p.waitForTimeout(250); }
  if (r.some(x => !x)) return null;
  const med = f => r.map(f).sort((a, b) => a - b)[4];
  return { R: r[0].R, iris: { ratio: med(x => x.iris.ratio) }, lids: { ratio: med(x => x.lids.ratio), w: med(x => x.lids.w) } };
}
// the desktop eye is the reference the phone eye must match
let deskEye = null;
{ const { b, p } = await open(chromium, 1440, 900, false, true); deskEye = await eyeScan(p); await b.close();
  console.log(`desktop 1440x900 eye: iris ${deskEye.iris.ratio.toFixed(3)} (w/h), lids ${deskEye.lids.ratio.toFixed(3)} (w/h), R ${deskEye.R.toFixed(1)}`); }
const hit = (a, b, pad = 0.5) => a.x < b.r - pad && b.x < a.r - pad && a.y < b.b - pad && b.y < a.b - pad;
const fails = [];

for (const [engine, ename] of [[chromium, 'chromium'], [webkit, 'webkit']]) {
  for (const [w, h] of (process.env.SKIP_PHONE ? [] : [[360, 740], [390, 664], [390, 844], [411, 777], [412, 915]])) {
    const { b, p } = await open(engine, w, h, true, true);
    const m = await p.evaluate(MEASURE);
    const ey = await eyeScan(p);
    if (shots) await p.screenshot({ path: path.join(shots, `phone-${w}x${h}-${ename}.png`), fullPage: true });
    await b.close();
    const tag = `${ename} ${w}x${h}`;
    if (m.sw > m.W) fails.push(`${tag}: page scrolls sideways (${m.sw} in ${m.W})`);
    for (const c of m.top) if (c.x < -0.5 || c.r > m.W + 0.5 || c.y < -0.5 || c.b > m.sh + 0.5) fails.push(`${tag}: ${c.name} leaves the page`);
    if (m.eye) { const span = (2 * m.eye.lid) / m.W, ratio = m.eye.lid / m.eye.r;
      if (span < 0.85 || span > 0.92) fails.push(`${tag}: the eye spans ${(span * 100).toFixed(1)}% of the width (want 85-92%)`);
      if (Math.abs(ratio - 1.75) > 0.01) fails.push(`${tag}: the eye's lids are ${ratio.toFixed(3)} R wide (the desktop eye: 1.75)`); }
    for (let i = 0; i < m.top.length; i++) for (let j = i + 1; j < m.top.length; j++)
      if (hit(m.top[i], m.top[j])) fails.push(`${tag}: ${m.top[i].name} overlaps ${m.top[j].name}`);
    for (const r of m.rows) for (let i = 0; i < r.parts.length; i++) for (let j = i + 1; j < r.parts.length; j++)
      if (hit(r.parts[i], r.parts[j])) fails.push(`${tag}: in ${r.row}, ${r.parts[i].name} overlaps ${r.parts[j].name}`);
    if (m.canvas && Math.abs(m.canvas.cssW / m.canvas.cssH - m.canvas.bw / m.canvas.bh) > 0.01)
      fails.push(`${tag}: the eye canvas is stretched (box ${m.canvas.cssW}x${m.canvas.cssH}, bitmap ${m.canvas.bw}x${m.canvas.bh})`);
    if (m.canvas && m.canvas.rule && /\d(vh|lvh)\b/.test(m.canvas.rule))
      fails.push(`${tag}: the eye canvas is sized in vh (${m.canvas.rule}); on Android Chrome that is taller than the screen and stretches the eye`);
    if (ey) {
      if (ey.iris.ratio < 0.98 || ey.iris.ratio > 1.02) fails.push(`${tag}: the iris is not a circle (w/h ${ey.iris.ratio.toFixed(3)})`);
      const dl = Math.abs(ey.lids.ratio / deskEye.lids.ratio - 1);
      if (dl > 0.03) fails.push(`${tag}: the lids are ${ey.lids.ratio.toFixed(3)} w/h, the desktop eye's ${deskEye.lids.ratio.toFixed(3)} (${(dl * 100).toFixed(1)}% off)`);
    } else fails.push(`${tag}: the eye could not be read`);
    console.log(`${tag}: ${m.top.length} components, ${m.rows.length} rows checked; eye: iris ${ey && ey.iris.ratio.toFixed(3)}, lids ${ey && ey.lids.ratio.toFixed(3)} spanning ${ey && (ey.lids.w / m.W * 100).toFixed(1)}% of the width`);
  }
}

if (Object.keys(assets).length) {
  for (const [w, h] of [[1440, 900], [960, 1080]]) {
    const live = await open(chromium, w, h, false, liveAssets), cand = await open(chromium, w, h, false, true);
    const [a, c] = [await live.p.evaluate(LAYOUT), await cand.p.evaluate(LAYOUT)];
    if (shots) { await live.p.screenshot({ path: path.join(shots, `desk-${w}-live.png`) }); await cand.p.screenshot({ path: path.join(shots, `desk-${w}-candidate.png`) }); }
    await live.b.close(); await cand.b.close();
    const A = new Map(a.map(x => [x[0], x.slice(1)])), C = new Map(c.map(x => [x[0], x.slice(1)]));
    const gone = [...A.keys()].filter(k => !C.has(k)), added = [...C.keys()].filter(k => !A.has(k));
    const moved = [...A.keys()].filter(k => C.has(k) && JSON.stringify(A.get(k)) !== JSON.stringify(C.get(k)))
      .map(k => `${k} ${JSON.stringify(A.get(k))} -> ${JSON.stringify(C.get(k))}`);
    // --desk-allow <regex>: boxes a change was asked to move (named in the PR); every other box must not move
    const bad = [...added.map(k => 'added ' + k), ...moved].filter(x => !(deskAllow && deskAllow.test(x)));
    if (bad.length) fails.push(`desktop ${w}x${h} changed (${bad.length} boxes), first: ${bad.slice(0, 3).join(' | ')}`);
    console.log(`desktop ${w}x${h}: ${a.length} boxes; removed ${gone.length}, added ${added.length}, moved ${moved.length} (${bad.length} not allowed)`);
    if (process.env.DESK_DETAIL) { for (const k of gone) console.log('  removed ' + k); for (const k of added) console.log('  added ' + k); for (const m of moved) console.log('  moved ' + m); }
  }
}

if (fails.length) { console.log('FAIL\n' + fails.map(f => '  ' + f).join('\n')); process.exit(1); }
console.log('PASS');
