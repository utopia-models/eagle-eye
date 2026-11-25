// THROWAWAY SPIKE verifier: node shoot.mjs <chromium|webkit> [out dir]
import { createRequire } from "module";
const require = createRequire(import.meta.url);
let pw;
for (const p of ["/srv/playwright-mcp/node_modules/playwright", "playwright", "/usr/lib/node_modules/playwright", "/usr/local/lib/node_modules/playwright", process.env.HOME + "/.npm-global/lib/node_modules/playwright"]) {
  try { pw = require(p); break; } catch (e) {}
}
const engine = process.argv[2] || "chromium";
const OUT = process.argv[3] || "shots";
const BASE = "http://100.127.249.81:8797";
const sizes = [["1920x1080", 1920, 1080], ["1366x768", 1366, 768], ["1440x900", 1440, 900], ["412x915", 412, 915], ["390x844", 390, 844]];
const browser = await pw[engine].launch();
const report = [];
for (const [name, w, h] of sizes) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", e => errs.push(String(e)));
  page.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
  await page.goto(BASE + "/tyler#hunts");
  await page.waitForTimeout(220);
  await page.screenshot({ path: `${OUT}/${engine}-${name}-0-intro-open.png` });
  await page.waitForTimeout(330);
  await page.screenshot({ path: `${OUT}/${engine}-${name}-1-intro-dock.png` });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/${engine}-${name}-2-hunts.png` });
  await page.screenshot({ path: `${OUT}/${engine}-${name}-2b-hunts-full.png`, fullPage: true });
  const hs = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  await page.click('.tabs button[data-view="roosts"]');
  await page.waitForTimeout(600);
  const tabOk = await page.evaluate(() => !document.querySelector("#v-roosts").hidden && document.querySelector("#v-hunts").hidden);
  await page.screenshot({ path: `${OUT}/${engine}-${name}-3-roosts.png` });
  const hs2 = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  await page.click('.tabs button[data-view="hunts"]');
  await page.waitForTimeout(500);
  await page.click('[data-open="upwork"]');
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${engine}-${name}-4-upwork-expanded.png`, fullPage: true });
  const hs3 = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  if (name === "1366x768") {
    await page.goto(BASE + "/claire#hunts"); await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/${engine}-${name}-5-claire.png` });
    await page.goto(BASE + "/yusuf#hunts"); await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/${engine}-${name}-6-yusuf.png` });
  }
  report.push({ engine, name, hscroll: [hs, hs2, hs3], tabOk, errs });
  await ctx.close();
}
// reduced motion: intro skipped
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: "reduce" });
const p = await ctx.newPage(); await p.goto(BASE + "/tyler"); await p.waitForTimeout(150);
const introHidden = await p.evaluate(() => getComputedStyle(document.querySelector("#intro")).display === "none");
await p.screenshot({ path: `${OUT}/${engine}-1366x768-reduced-motion-150ms.png` });
report.push({ engine, reducedMotionIntroSkipped: introHidden });
await browser.close();
console.log(JSON.stringify(report, null, 1));
