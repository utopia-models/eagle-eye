// The Eagle Eye pace chip counts VSLs SENT (timeline step "vsl") in the last 4 h, not hand-recorded takes. Run: node test_pace_chip.mjs
import fs from "node:fs"; import assert from "node:assert/strict"; import vm from "node:vm"; import {fileURLToPath} from "node:url"; import path from "node:path";
const html = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "hunt-page/ui/index.html"), "utf8");
const src = html.slice(html.indexOf("const PACE_N"), html.indexOf("function renderBar"));
const ago = h => new Date(Date.now() - h * 3600e3).toISOString();
const row = (vsl, rec, built, status) => ({status, tl: {steps: [{key: "built", at: built}, {key: "recorded", at: rec}, {key: "vsl", at: vsl}]}});
function chip(rows) {
  const ctx = {EE: {data: {rows}}, F: {}, icon: () => ""}; vm.createContext(ctx); vm.runInContext(src + ";this.vslPace=vslPace;this.paceChip=paceChip;", ctx);
  return {p: ctx.vslPace(), html: ctx.paceChip()};
}
let c = chip([row(ago(1), ago(30), ago(30)), row(ago(2), ago(2), ago(2)), row(ago(3), null, null, "Ready to record"), row(ago(5), ago(1), ago(1)), row(null, ago(1), null)]);
assert.equal(c.p.rec, 3);                       // sent in 4 h: three; the 5 h send and the recorded-only row do not count
assert.equal(c.p.ready, 1); assert.equal(c.p.built24, 2);
assert.match(c.html, /VSLs sent last 4 h: <b>3 of 4<\/b>/); assert.match(c.html, /border-\[#b4533c\]/);
c = chip([1, 2, 3, 3.5].map(h => row(ago(h), null, null)));
assert.match(c.html, /4 of 4/); assert.match(c.html, /border-gold/);
console.log("PASS");
