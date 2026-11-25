// The row/detail timeline reads from the facts (Eagle 11-23, fleetmail 18021: 'Recorded' read pending on jobs with a vsl_recorded
// fact): Recorded = min(at) of vsl_recorded; a VSL proposal that went out implies Recorded.
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
const fact = async (o: Record<string, unknown>) => {
  const r = await api(tok, "POST", "/rest/events", { source: "test", proof: {}, ...o });
  assert.equal(r.status, 200, JSON.stringify(r.body));
};
const steps = async (id: string) => Object.fromEntries(
  (await api(null, "GET", "/api/feed?workspace=tyler")).body.timelines[id].steps.map((s: any) => [s.key, { state: s.state, at: s.at }]));

test("Recorded is the earliest vsl_recorded fact", async () => {
  const c = await create({ externalId: "~022100000000000003710" });
  await fact({ kind: "vsl_recorded", at: "2026-11-23T13:28:44Z", key: "vsl_recorded:t1:b", itemRef: { itemId: c.id } });
  await fact({ kind: "vsl_recorded", at: "2026-11-23T13:20:00Z", key: "vsl_recorded:t1:a", itemRef: { itemId: c.id } });
  assert.deepEqual((await steps(c.id)).recorded, { state: "done", at: "2026-11-23T13:20:00Z" });
});

test("a VSL proposal that went out implies Recorded, even with no vsl_recorded fact", async () => {
  const c = await create({ externalId: "~022100000000000009263" });
  await fact({ kind: "proposal_sent", at: "2026-11-23T13:03:55Z", key: "proposal_sent:2124000000000009263", itemRef: { itemId: c.id },
    proof: { proposal_id: "2124000000000009263", arm: "F" } });
  const s = await steps(c.id);
  assert.equal(s.vsl.state, "done");
  assert.notEqual(s.recorded.state, "pending");
});


test("a recorded hunt with no one-shot and no touches appears ONCE, in the recorded queue (3710 showed twice, 11-23)", async () => {
  const c = await create({ externalId: "~022100000000000013710" });
  await fact({ kind: "vsl_recorded", at: "2026-11-23T13:28:44Z", key: "vsl_recorded:once:1", itemRef: { itemId: c.id } });
  const up = (await api(null, "GET", "/api/feed?workspace=tyler")).body.hunts.find((l: any) => l.id === "upwork");
  const where = [["feed", up.feed], ...Object.entries(up.queue)].flatMap(([k, rows]: any) => rows.filter((x: any) => x.item_id === c.id).map(() => k));
  assert.deepEqual(where, ["recorded"]);
});
