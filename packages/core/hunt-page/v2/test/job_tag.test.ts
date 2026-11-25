// The Upwork job tag (Tyler 11-23, via Eagle: "put it on ALL upwork jobs"): every Upwork row the feed serializes carries job_tag =
// the last 4 digits of its Upwork job id, in every state (found, one-shot built, sent); non-Upwork rows carry null. The UI renders
// the field and never derives it.
import { resetDb, pool, token, api, item } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

const create = async (o: Record<string, unknown>) => {
  const r = await api(tok, "POST", "/rest/huntItems?upsert=true", item(o));
  assert.ok(r.status < 300, JSON.stringify(r.body));
  return r.body.data.createHuntItem;
};
const feed = async () => (await api(null, "GET", "/api/feed?workspace=tyler")).body;
const rowsFor = (f: any, lane: string, id: string) => {
  const L = f.hunts.find((l: any) => l.id === lane);
  return [...L.feed, ...Object.values(L.queue || {}).flat()].filter((x: any) => x.item_id === id);
};

test("jobTag: last 4 digits of the Upwork job id; null for non-Upwork and for an Upwork row with no job id", async () => {
  const { jobTag } = await import("../src/feed.ts");
  assert.equal(jobTag({ hunt_type: "upwork", external_id: "~022124848662075810005" }), "0005");
  assert.equal(jobTag({ hunt_type: "upwork", external_id: "alert:ea328997ae3f8e1dfb79", job_url: "https://www.upwork.com/jobs/~021999000000000009263?ref=x" }), "9263");
  assert.equal(jobTag({ hunt_type: "upwork", external_id: "alert:ea328997ae3f8e1dfb79", job_url: null }), null);
  assert.equal(jobTag({ hunt_type: "job_post", external_id: "https://www.linkedin.com/jobs/view/4239984019/" }), null);
  assert.equal(jobTag({ hunt_type: "investor", external_id: "investor:1517-fund" }), null);
});

test("a found Upwork row (no one-shot) and a row with a one-shot both carry a 4-digit job_tag", async () => {
  const found = await create({ externalId: "~022100000000000004321" });
  const built = await create({ externalId: "~022100000000000008765" });
  const os = await api(tok, "POST", "/rest/oneShots", { itemId: built.id, kind: "demo", status: "ready", demoUrl: "https://example.test/d" });
  assert.equal(os.status, 201, JSON.stringify(os.body));
  const f = await feed();

  const a = rowsFor(f, "upwork", found.id);
  assert.equal(a.length, 1);   // the feed row (no one-shot yet)
  assert.equal(a[0].job_tag, "4321");
  assert.match(a[0].job_tag, /^\d{4}$/);

  const b = rowsFor(f, "upwork", built.id);
  assert.ok(b.length >= 1, "the one-shot row is in the upwork queue");
  for (const r of b) { assert.equal(r.job_tag, "8765"); assert.match(r.job_tag, /^\d{4}$/); }
  assert.equal(f.enrich.upwork["~022100000000000008765"].job_tag, "8765");
});

test("non-Upwork rows carry job_tag null", async () => {
  const fund = await create({ huntType: "funding", externalId: "https://launch.example/river", target: "River", upwork: undefined,
    funding: { kind: "launch", round: "Seed", announcedOn: "2026-11-21", sourceUrl: "https://launch.example/river" } });
  const f = await feed();
  const r = rowsFor(f, "funding", fund.id);
  assert.equal(r.length, 1);
  assert.equal(r[0].job_tag, null);
});
