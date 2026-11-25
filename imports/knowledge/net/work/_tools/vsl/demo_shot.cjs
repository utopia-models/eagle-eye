// demo_shot.cjs URL OUT.png -> one JSON line: {final, bytes, iframes, controls, dhash}
// Renders a package page (our own Ra pages or local files, never a third-party site) in WebKit at 1920x1080 and computes a 64-bit dHash in the page, so no image library is needed.
const { webkit } = require(process.env.PLAYWRIGHT_DIR || '/srv/playwright-mcp/node_modules/playwright');
(async () => {
  const b = await webkit.launch(), p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto(process.argv[2], { waitUntil: 'load', timeout: 60000 }); await p.waitForTimeout(3000);
  const info = await p.evaluate(() => ({ final: location.href, iframes: document.querySelectorAll('iframe').length,
    controls: document.querySelectorAll('button,input,select,textarea,[role=button]').length }));
  // the visible words of every frame: an iframe of the diagram shows the diagram's words even though the top page has none
  const texts = []; for (const f of p.frames()) { try { texts.push(await f.evaluate(() => document.body ? document.body.innerText : '')); } catch (e) { /* cross-origin frame */ } }
  info.words = [...new Set(texts.join(' ').toLowerCase().match(/[a-z]{3,}/g) || [])];
  const png = await p.screenshot({ path: process.argv[3] });
  const q = await b.newPage();
  info.dhash = await q.evaluate(async (b64) => {
    const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
    const W = 33, H = 18;   // 32 x 18 dHash = 576 bits: a 64-bit hash cannot tell two dark UI pages apart
    const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'); x.drawImage(img, 0, 0, W, H);
    const d = x.getImageData(0, 0, W, H).data, g = (i) => 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; let bits = '';
    for (let r = 0; r < H; r++) for (let k = 0; k < W - 1; k++) bits += g((r * W + k) * 4) > g((r * W + k + 1) * 4) + 3 ? '1' : '0';
    return bits;
  }, png.toString('base64'));
  info.bytes = png.length; console.log(JSON.stringify(info)); await b.close();
})().catch((e) => { console.error(String(e)); process.exit(1); });
