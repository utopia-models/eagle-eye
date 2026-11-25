import { resetDb, pool, token, api, item, asOwner } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

const one = async (sql: string, p: unknown[] = []) => asOwner(async tx => (await tx.query(sql, p)).rows[0]);
const JOB = "~022124298273556552350";
const fact = (o: Record<string, unknown> = {}) => ({ kind: "proposal_sent", at: "2026-11-22T05:37:53Z",
  itemRef: { job: JOB, title: "AI Engineer for Workflow Solutions" },
  proof: { proposal_id: "2124376726426906625", arm: "F", bid_usd: 10, ledger_ts: "2026-11-22T05:37:53Z" }, source: "test", ...o });

test("a proposal_sent fact moves the card to sent (stage + VSL), records the touch and the proof, folds the alert twin", async () => {
  const card = await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: JOB, target: "Upwork client · USA",
    details: { vsl: "record", status: "Ready to record" }, upwork: { title: "AI Engineer for Workflow Solutions", postedAt: "2026-11-22T00:26:49Z" } }));
  const twin = await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "alert:0f6c300153b1d890e3a9",
    upwork: { title: "AI Engineer for Workflow Solutions", postedAt: "2026-11-22T00:27:07Z" } }));
  const id = card.body.data.createHuntItem.id;

  const r = await api(tok, "POST", "/rest/events", fact());
  assert.equal(r.status, 200, JSON.stringify(r.body));
  const out = r.body.data.applyFacts[0];
  assert.equal(out.status, "updated"); assert.equal(out.itemId, id); assert.equal(out.via, "job");
  // the card is Upwork Entire VSL from creation (0013), so the fact moves only the stages
  assert.deepEqual(out.changed, { stage: { from: "new", to: "sent" }, vsl_stage: { from: "none", to: "sent" } });
  assert.equal((await one("select one_shot_system from hunt_items where id = $1", [id])).one_shot_system, "upwork-entire-vsl");
  assert.deepEqual(out.merged, [twin.body.data.createHuntItem.id]);

  const row = await one("select stage, vsl_stage from hunt_items where id = $1", [id]);
  assert.deepEqual(row, { stage: "sent", vsl_stage: "sent" });
  assert.equal((await one("select count(*)::int n from touches where item_id = $1 and channel = 'upwork' and provider_id = '2124376726426906625' and status = 'sent'", [id])).n, 1);
  const ev = await one("select data from events where item_id = $1 and type = 'fact.applied'", [id]);
  assert.equal(ev.data.proof.proposal_id, "2124376726426906625"); assert.equal(ev.data.key, "proposal_sent:2124376726426906625");
  assert.ok((await one("select deleted_at from hunt_items where id = $1", [twin.body.data.createHuntItem.id])).deleted_at, "the alert twin is folded in");

  // the feed shows what happened, not the hunter's copied "record": the card is in the upwork lane's sent queue with vsl sent
  const feed = await api(null, "GET", "/api/feed?workspace=tyler");
  const up = feed.body.hunts.find((l: any) => l.id === "upwork");
  const sent = up.queue.sent.find((s: any) => s.item_id === id);
  assert.equal(sent.vsl, "sent"); assert.match(sent.note, /proposal 2124376726426906625 sent/);
  assert.ok(!up.feed.some((f: any) => f.item_id === twin.body.data.createHuntItem.id), "the folded twin is off the board");
});

test("replaying old facts changes nothing and never moves a stage backwards", async () => {
  const again = await api(tok, "POST", "/rest/events", fact());
  assert.equal(again.body.data.applyFacts[0].status, "unchanged"); assert.equal(again.body.data.applyFacts[0].via, "replay");
  // an older, weaker fact about the same card (a render that finished before the send) is applied but moves nothing back
  const older = await api(tok, "POST", "/rest/events", { kind: "render_done", at: "2026-11-22T04:31:33Z", itemRef: { job: JOB },
    proof: { render: "For-AI-Workflow-Automation.mp4" } });
  assert.equal(older.body.data.applyFacts[0].status, "unchanged");
  const row = await one("select stage, vsl_stage from hunt_items where external_id = $1", [JOB]);
  assert.deepEqual(row, { stage: "sent", vsl_stage: "sent" });
  assert.equal((await one("select count(*)::int n from touches where provider_id = '2124376726426906625'")).n, 1);
  assert.equal((await one("select count(*)::int n from events where type = 'fact.applied' and data->>'key' = 'proposal_sent:2124376726426906625'")).n, 1);
  // a later fact still moves it forward
  const w = await api(tok, "POST", "/rest/events", { kind: "watched", at: "2026-11-22T07:00:00Z", itemRef: { proposalId: "2124376726426906625" }, proof: { ledger_row: "w1" } });
  assert.equal(w.body.data.applyFacts[0].via, "proposalId");
  assert.deepEqual(w.body.data.applyFacts[0].changed.vsl_stage, { from: "sent", to: "watched" });
});

test("a fact with no matching card is reported and auto-creates a flagged card, never silently dropped", async () => {
  const r = await api(tok, "POST", "/rest/events", fact({ itemRef: { job: "~029999999999999999999", title: "Never seen job" },
    proof: { proposal_id: "1111", arm: "manual" } }));
  const out = r.body.data.applyFacts[0];
  assert.equal(out.status, "auto_created"); assert.equal(out.via, "auto_created");
  const row = await one("select stage, vsl_stage, details from hunt_items where id = $1", [out.itemId]);
  assert.equal(row.details.auto_created, true); assert.equal(row.stage, "sent"); assert.equal(row.vsl_stage, "none", "a text-only arm is not a video");
  // with nothing to build a card from, it is a 422 that names the fact: the caller keeps it in its outbox and the audit reports it
  const bad = await api(tok, "POST", "/rest/events", { kind: "video_attached", at: "2026-11-22T05:38:01Z", itemRef: { slug: "no-such-slug" }, proof: { ledger_row: "x" } });
  assert.equal(bad.status, 422); assert.match(bad.body.error, /no card matches/);
});

test("events:write is its own scope", async () => {
  const ro = await token(["huntItems:read"]);
  assert.equal((await api(ro, "POST", "/rest/events", fact({ key: "scope-check" }))).status, 403);
});
