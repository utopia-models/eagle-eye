// node test_arch.mjs: the pure render of opt/arch.js against the real pipelines + offer feeds.
import path from "node:path"; import fs from "node:fs"; import assert from "node:assert";
await import("./arch.js");
const { archFlow, stageDetail, offerPanel, currentStage, sysName } = globalThis.EagleArch;
assert.equal(sysName("Upwork Entire VSL"), "Upwork"); assert.equal(sysName("Upwork Intro VSL"), "Upwork"); assert.equal(sysName("Upwork"), "Upwork");
const feed = f => JSON.parse(fs.readFileSync(path.join(process.env.EAGLE_KB || path.join(process.env.HOME, "dev/utopia-models/knowledge"), "_infra/occ-feeds", f)));
const P = feed("pipelines.json"), O = feed("offer.json");
const up = P.pipelines.find(p => p.id === "upwork"), fo = P.pipelines.find(p => p.id === "founder");
const h = archFlow(P, "Upwork Entire VSL");
assert.equal((h.match(/class="arch-box/g) || []).length, up.stages.length);
for (const s of up.stages) assert.ok(h.includes(`data-stage="${s.stage}"`));
// founder: hunt, job post, component, diagram, VSL, email, THE OFFER (last)
const f = archFlow(P, "Founder 14-Day Build", { state: "Working demo", target: "Acme" });
assert.equal(fo.stages.length, 7); assert.ok(/offer/i.test(fo.stages.at(-1).stage));
assert.ok(f.includes('class="arch-box hl"') && f.includes("at <b>Diagram</b>"));
// provenance: recorded fields render, missing ones say so
const d = stageDetail(P, "Founder 14-Day Build", "Component built", { target: "Acme", state: "Working demo" });
assert.ok(d.includes("FOUNDER-COPY-PACK.md") && d.includes("Acme"));
assert.ok(stageDetail(P, "Upwork", "Hunt", null).includes("source not recorded"));
// the offer panel reads offer.json, not page text
assert.ok(offerPanel(O).includes("they pay nothing") && offerPanel(O).includes("$9,000/month"));
assert.ok(offerPanel({ ...O, headline: "CHANGED" }).includes("CHANGED"));
assert.ok(offerPanel(null).includes("No offer feed"));
assert.ok(archFlow(null, "Upwork").includes("No architecture feed"));
console.log("ok", up.stages.length, fo.stages.length);
