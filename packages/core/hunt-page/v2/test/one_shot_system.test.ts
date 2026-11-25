// The one-shot SYSTEM on every hunt item (Tyler 11-22 ~2:50 AM MT: "it is not clear which one-shot system we are using, it just
// says Upwork"): the channel (hunt type) and the system inside it (Intro VSL, Entire VSL for a niche, Founder walkthrough, ...)
// are separate fields; the maker of the take names it, the database derives the lane default once a one-shot exists.
import { resetDb, pool, token, api, item, asOwner } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

const one = async (sql: string, p: unknown[] = []) => asOwner(async tx => (await tx.query(sql, p)).rows[0]);
const create = async (o: Record<string, unknown>) => {
  const r = await api(tok, "POST", "/rest/huntItems?upsert=true", item(o));
  assert.ok(r.status < 300, JSON.stringify(r.body));
  return r.body.data.createHuntItem;
};
const feedRow = async (lane: string, id: string) => {
  const f = await api(null, "GET", "/api/feed?workspace=tyler");
  const L = f.body.hunts.find((l: any) => l.id === lane);
  return [...L.feed, ...Object.values(L.queue || {}).flat()].find((x: any) => x.item_id === id);
};

test("the catalog is seeded per workspace and readable over REST", async () => {
  const r = await api(tok, "GET", "/rest/oneShotSystems");
  assert.equal(r.status, 200);
  const got = r.body.data.oneShotSystems.map((s: any) => [s.key, s.label, s.huntType, s.take, s.isDefault]);
  assert.deepEqual(got, [
    ["upwork-intro-vsl", "Upwork Intro VSL", "upwork", "intro", false],
    ["upwork-entire-vsl", "Upwork Entire VSL", "upwork", "entire", true],   // 0013: the Upwork default is Entire VSL
    ["funding-walkthrough", "Funding Founder Walkthrough", "funding", "intro", true],
    ["jobs-video-demo", "Job Post Video + Demo", "job_post", "intro", true],
    ["investor-fleet-demo", "Investor Fleet Demo", "investor", "intro", true],
  ]);
});

test("a new Upwork hunt is Upwork Entire VSL from creation (0013); other lanes get their default the moment a one-shot exists", async () => {
  const card = await create({ externalId: "~022100000000000000101" });
  assert.equal(card.oneShotSystem, "upwork-entire-vsl");
  assert.equal((await feedRow("upwork", card.id)).one_shot_system.key, "upwork-entire-vsl");

  // a one-shots row (the builder's package) keeps the system the row already has
  const os = await api(tok, "POST", "/rest/oneShots", { itemId: card.id, kind: "demo", status: "ready", demoUrl: "https://example.test/d" });
  assert.equal(os.status, 201, JSON.stringify(os.body));
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [card.id])).one_shot_system, "upwork-entire-vsl");

  // a writer that names a system at creation wins over the default
  const named = await create({ externalId: "~022100000000000000104", oneShotSystem: "upwork-intro-vsl" });
  assert.equal(named.oneShotSystem, "upwork-intro-vsl");

  // a found funding row (not Upwork) still has no system until a one-shot exists
  const found = await create({ huntType: "funding", externalId: "https://launch.example/found-only", target: "Found Only",
    upwork: undefined, funding: { kind: "launch", round: "Seed", announcedOn: "2026-11-21", sourceUrl: "https://launch.example/found-only" } });
  assert.equal(found.oneShotSystem, null);

  // a funding offer (stage one_shot) -> the funding walkthrough
  const fund = await create({ huntType: "funding", externalId: "https://launch.example/river", target: "River", stage: "one_shot", vslStage: "scripted",
    upwork: undefined, funding: { kind: "launch", round: "Seed", announcedOn: "2026-11-21", sourceUrl: "https://launch.example/river" } });
  assert.equal(fund.oneShotSystem, "funding-walkthrough");
  assert.deepEqual(
    (({ key, label, take }) => ({ key, label, take }))((await feedRow("funding", fund.id)).one_shot_system),
    { key: "funding-walkthrough", label: "Funding Founder Walkthrough", take: "intro" });

  // a package the builder already made (details.oneshot ready, the hunter's "Record" copy) is a one-shot too
  const built = await create({ externalId: "~022100000000000000103", details: { vsl: "record", oneshot: { status: "ready", kind: "architecture page" } } });
  assert.equal(built.oneShotSystem, "upwork-entire-vsl");

  // a text-only Upwork proposal is still an Upwork hunt: it carries the lane default from creation
  const text = await create({ externalId: "~022100000000000000102", stage: "sent" });
  assert.equal(text.oneShotSystem, "upwork-entire-vsl");
});

test("0013's backfill gives every live Upwork item with no system the default, and leaves a set one alone", async () => {
  const { readFileSync } = await import("node:fs");
  const a = await create({ externalId: "~022100000000000000111" }), b = await create({ externalId: "~022100000000000000112", oneShotSystem: "upwork-intro-vsl" });
  await asOwner(tx => tx.query("update hunt_items set one_shot_system = null where id = $1", [a.id]));   // a row from before 0013
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [a.id])).one_shot_system, null);
  await asOwner(tx => tx.query(readFileSync(new URL("../migrations/0013_upwork_entire_vsl_default.sql", import.meta.url), "utf8")));
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [a.id])).one_shot_system, "upwork-entire-vsl");
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [b.id])).one_shot_system, "upwork-intro-vsl");
});

test("the take's maker names the system on POST /rest/events (vsl-make --take entire --niche) and the row shows it", async () => {
  const card = await create({ externalId: "~022100000000000000201" });
  await one("update hunt_items set one_shot_system = null where id = $1 returning id", [card.id]);   // a row with no system yet
  const r = await api(tok, "POST", "/rest/events", { kind: "render_done", at: "2026-11-22T09:00:00Z", key: "render_done:t-entire:vsl:1",
    itemRef: { job: "~022100000000000000201" }, proof: { render: ["vsl.mp4"] }, source: "takeflow vsl-make",
    oneShotSystem: "upwork-entire-vsl", niche: "dental clinics" });
  assert.equal(r.status, 200, JSON.stringify(r.body));
  const out = r.body.data.applyFacts[0];
  assert.deepEqual(out.changed.one_shot_system, { from: null, to: "upwork-entire-vsl" });
  assert.deepEqual(out.changed.vsl_stage, { from: "none", to: "rendered" });
  const row = await feedRow("upwork", card.id);
  assert.equal(row.one_shot_system.key, "upwork-entire-vsl");
  assert.equal(row.one_shot_system.label, "Upwork Entire VSL · dental clinics");
  assert.equal(row.one_shot_system.take, "entire");

  // a hunter re-finding the row (no system in its body) never clears it
  await create({ externalId: "~022100000000000000201", signal: "re-found" });
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [card.id])).one_shot_system, "upwork-entire-vsl");

  // the maker's word wins over a derived default: an intro take on a defaulted row moves it
  const c2 = await create({ externalId: "~022100000000000000202", vslStage: "scripted" });
  assert.equal(c2.oneShotSystem, "upwork-entire-vsl");
  const e2 = await api(tok, "POST", "/rest/events", { kind: "render_done", at: "2026-11-22T09:05:00Z", key: "render_done:t2:vsl:1",
    itemRef: { itemId: c2.id }, proof: { render: ["vsl.mp4"] }, oneShotSystem: "upwork-intro-vsl" });
  assert.deepEqual(e2.body.data.applyFacts[0].changed.one_shot_system, { from: "upwork-entire-vsl", to: "upwork-intro-vsl" });
});

test("an unknown system is a 400 that lists the known ones (upsert, fact, PATCH); a new one is a catalog row, not code", async () => {
  const bad = await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "~022100000000000000301", oneShotSystem: "upwork-nope" }));
  assert.equal(bad.status, 400); assert.match(bad.body.error, /unknown oneShotSystem upwork-nope/);
  assert.ok(bad.body.known.includes("upwork-intro-vsl"));

  const card = await create({ externalId: "~022100000000000000302" });
  const f = await api(tok, "POST", "/rest/events", { kind: "render_done", at: "2026-11-22T09:10:00Z", key: "render_done:bad:1",
    itemRef: { itemId: card.id }, proof: {}, oneShotSystem: "upwork-nope" });
  assert.equal(f.status, 400);
  const p = await api(tok, "PATCH", `/rest/huntItems/${card.id}`, { oneShotSystem: "upwork-nope" });
  assert.equal(p.status, 400);

  // forward-compatible: register a new Upwork one-shot, then use it
  const n = await api(tok, "POST", "/rest/oneShotSystems?upsert=true", { key: "upwork-mvp-only", label: "MVP only", huntType: "upwork", take: "none",
    template: null, description: "the MVP link in the proposal, no video", sort: 25 });
  assert.ok(n.status < 300, JSON.stringify(n.body));
  const ok = await api(tok, "PATCH", `/rest/huntItems/${card.id}`, { oneShotSystem: "upwork-mvp-only" });
  assert.equal(ok.status, 200, JSON.stringify(ok.body));
  assert.equal((await feedRow("upwork", card.id)).one_shot_system.label, "MVP only");
});

test("the niche is the job's subject in a few words, from the package's architecture title or the post title", async () => {
  const { nicheOf } = await import("../src/packages.ts");
  assert.equal(nicheOf("AI chief of staff: system architecture", ""), "AI chief of staff");
  assert.equal(nicheOf("Hardware workflow automation: Eagle to bench test", ""), "Hardware workflow automation");
  assert.equal(nicheOf("Python + SQL ETL pipeline with a machine learning step", ""), "Python + SQL ETL pipeline");
  assert.equal(nicheOf("Real-time scoring and detection engine", ""), "Real-time scoring and detection engine");
  assert.equal(nicheOf("One request, end to end: multi-agent automation architecture", "AI Automation Specialist / AI Agent Developer (Python)"), "AI Automation Specialist");
  assert.equal(nicheOf("Tallis: agent tracking architecture", ""), "agent tracking");
  assert.equal(nicheOf("Your custom AI agent: system architecture", "AI Agent Developer Needed for Custom AI Project"), "AI Agent Developer");
  assert.equal(nicheOf("", "AI Automation Architect | Build My Personal & Business AI Operating System"), "AI Automation Architect");
});

test("titles are decoded once at ingest (Upwork mail sends 'AI &amp; Business')", async () => {
  const { decodeEntities } = await import("../src/hunts.ts");
  assert.equal(decodeEntities("Software, AI &amp; Business"), "Software, AI & Business");
  assert.equal(decodeEntities("R&amp;amp;D &#39;x&#39; &lt;b&gt;"), "R&D 'x' <b>");
  assert.equal(decodeEntities("AT&T"), "AT&T");
  const r = await create({ externalId: "~022100000000000000901", signal: "B2B Sales Closer — Software, AI &amp; Business",
    upwork: { title: "B2B Sales Closer — Software, AI &amp; Business", postedAt: "2026-11-21T20:00:00Z" } });
  assert.equal(r.signal, "B2B Sales Closer — Software, AI & Business");
});
