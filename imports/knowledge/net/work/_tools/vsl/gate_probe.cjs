// gate_probe.cjs MODE URL [ARGS...] -> one JSON line. Headless WebKit 1920x1080 over OUR OWN package pages (Ra or file://), never a third-party site.
//   diagram URL          caption on beat 0, caption title on beat 1 vs the page title, beat count, font px of a node title at beat 1, steps lit on every beat
//   clicks URL [MAX]     clicks up to MAX (default 12) visible buttons in turn; counts the ones that changed the page
//   targets URL SEL...   for each CSS selector, how many elements exist (an action script dry run)
const { webkit } = require(process.env.PLAYWRIGHT_DIR || '/srv/playwright-mcp/node_modules/playwright');
(async () => {
  const [mode, url, ...rest] = process.argv.slice(2);
  const b = await webkit.launch(), p = await b.newPage({ viewport: { width: 1920, height: 1080 } }); p.setDefaultTimeout(30000);
  await p.goto(url, { waitUntil: 'load', timeout: 60000 }); await p.waitForTimeout(2500);
  let out = {};
  if (mode === 'diagram') {
    const n = await p.evaluate(() => document.querySelectorAll('#nav button').length);   // beat buttons: 0..N plus prev/next
    const beats = n - 2, pageTitle = await p.evaluate(() => (document.querySelector('h1') || {}).childNodes ? document.querySelector('h1').childNodes[0].textContent.trim() : '');
    const go = async (i) => { await p.evaluate((i) => { location.hash = 'beat=' + i; }, i); await p.waitForTimeout(2600); };
    await go(0); out.cap0 = await p.evaluate(() => getComputedStyle(document.getElementById('cap')).display);
    out.beats = beats; out.pageTitle = pageTitle; out.lit = [];
    for (let i = 1; i < beats; i++) {
      await go(i);
      out.lit.push(await p.evaluate(() => document.querySelectorAll('.hot').length));
      if (i === 1) {
        out.capTitle1 = await p.evaluate(() => document.querySelector('#cap h2').textContent.trim());
        out.fontPx = await p.evaluate(() => { const t = [...document.querySelectorAll('.nw text')].filter((e) => e.getBoundingClientRect().height > 0).map((e) => e.getBoundingClientRect().height); return t.length ? Math.round(Math.max(...t)) : 0; });
      }
    }
  } else if (mode === 'clicks') {
    const max = +(rest[0] || 12); let changed = 0, tried = 0; const clog = []; const contact = new Set(); const EM = /[\w.+-]+@[\w-]+\.[A-Za-z]{2,}/g, PH = /\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}/g;
    const scan = async () => { const t = await p.evaluate(() => document.body.innerText); for (const m of [...(t.match(EM) || []), ...(t.match(PH) || [])]) contact.add(m); };
    await scan(); const sig = () => p.evaluate(() => document.body.innerText.length + ':' + document.body.innerText.slice(0, 400));
    for (let i = 0; i < max; i++) {
      const bt = p.locator('button:visible').nth(i); if (!(await bt.count())) break;
      const label = ((await bt.innerText().catch(() => '')) || (await bt.getAttribute('aria-label').catch(() => '')) || '(icon)').trim().replace(/\s+/g, ' ').slice(0, 40); const before = await sig(); try { await bt.click({ timeout: 3000 }); } catch (e) { await p.keyboard.press('Escape').catch(() => {}); continue; } await p.waitForTimeout(500); tried++;
      const did = (await sig()) !== before; if (did) changed++; clog.push({ n: tried, button: label, changed: did });
      await scan(); await p.keyboard.press('Escape').catch(() => {});   // close any menu or dialog the click opened
    }
    out = { tried, changed, contact: [...contact].slice(0, 5), log: clog };
  } else if (mode === 'shot') {   // shot URL OUT.png [BEAT]: a 1920x1080 screenshot (a diagram page can be put on a beat first)
    if (rest[1] !== undefined) { await p.evaluate((n) => { location.hash = 'beat=' + n; }, +rest[1]); await p.waitForTimeout(3500); }
    await p.screenshot({ path: rest[0] }); out = { shot: rest[0] };
  } else if (mode === 'walk') {   // the action script dry run: each selector in order must appear, be enabled, and be clickable
    for (const s of rest) {
      const el = p.locator(s).first(); let ok = false;
      for (let i = 0; i < 50 && !ok; i++) { ok = (await el.count()) > 0 && (await el.isEnabled().catch(() => false)); if (!ok) await p.waitForTimeout(500); }
      if (ok) { try { await el.click({ timeout: 10000 }); await p.waitForTimeout(500); } catch (e) { ok = false; } }
      out[s] = ok ? 1 : 0;
    }
  } else if (mode === 'targets') {
    for (const s of rest) out[s] = await p.locator(s).count();
  }
  console.log(JSON.stringify(out)); await b.close();
})().catch((e) => { console.error(String(e).slice(0, 300)); process.exit(1); });
