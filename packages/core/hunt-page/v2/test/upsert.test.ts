import { resetDb, pool, token, api, item, asOwner } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

const count = async (sql: string, p: unknown[] = []) => asOwner(async tx => (await tx.query(sql, p)).rows[0].n as number);

test("re-finding the same source id upserts: one row, one item.found, found_at kept", async () => {
  const a = await api(tok, "POST", "/rest/huntItems?upsert=true", item());
  const b = await api(tok, "POST", "/rest/huntItems?upsert=true", item());
  assert.equal(a.status, 201); assert.equal(a.body.status, "created");
  assert.equal(b.status, 200); assert.equal(b.body.status, "unchanged");
  assert.equal(a.body.data.createHuntItem.id, b.body.data.createHuntItem.id);
  assert.equal(await count("select count(*)::int n from hunt_items"), 1);
  assert.equal(await count("select count(*)::int n from upwork_jobs"), 1);
  assert.equal(await count("select count(*)::int n from events where type = 'item.found'"), 1);
  assert.equal(await count("select count(*)::int n from events"), 1, "an unchanged re-find writes no event");

  const c = await api(tok, "POST", "/rest/huntItems?upsert=true", item({ signal: "Proposals 5 to 10", fit: 80 }));
  assert.equal(c.body.status, "updated");
  assert.equal(c.body.data.createHuntItem.foundAt, a.body.data.createHuntItem.foundAt, "found_at is the first find, never moved");
  const ev = await asOwner(async tx => (await tx.query("select type, data from events order by id")).rows);
  assert.deepEqual(ev.map(e => e.type), ["item.found", "item.updated"]);
  assert.deepEqual(ev[1].data.signal, { from: "Upwork job alert", to: "Proposals 5 to 10" });
});

test("plain POST of an existing source id is a 409; batch upsert counts created/unchanged", async () => {
  assert.equal((await api(tok, "POST", "/rest/huntItems", item())).status, 409);
  const batch = [item({ externalId: "b1" }), item({ externalId: "b2" }), item({ signal: "Proposals 5 to 10" })]; // the third is the item the previous test already moved
  const r1 = await api(tok, "POST", "/rest/batch/huntItems?upsert=true", batch);
  const r2 = await api(tok, "POST", "/rest/batch/huntItems?upsert=true", batch);
  assert.deepEqual(r1.body.counts, { created: 2, updated: 0, unchanged: 1 });
  assert.deepEqual(r2.body.counts, { created: 0, updated: 0, unchanged: 3 });
  assert.equal(await count("select count(*)::int n from hunt_items"), 3);
});

test("Idempotency-Key: same request replays the stored response, a different body is a 422", async () => {
  const body = { fullName: "Mohamed A.", email: "mohamed@example.com" };
  const h = { "idempotency-key": "k-1" };
  const a = await api(tok, "POST", "/rest/people", body, h);
  const b = await api(tok, "POST", "/rest/people", body, h);
  assert.equal(a.status, 201);
  assert.equal(b.status, 201);
  assert.equal(b.headers.get("idempotent-replayed"), "true");
  assert.deepEqual(b.body, a.body);
  assert.equal(await count("select count(*)::int n from people"), 1);
  assert.equal((await api(tok, "POST", "/rest/people", { ...body, title: "CTO" }, h)).status, 422);
});

test("touches upsert on (channel, provider_id); speed_to_lead_minutes = first sent_at - signal_at", async () => {
  const it = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "speed", signalAt: "2026-11-21T20:00:00Z" }))).body.data.createHuntItem;
  const t = { itemId: it.id, channel: "upwork", sentAt: "2026-11-21T20:42:30Z", providerId: "proposal-123" };
  assert.equal((await api(tok, "POST", "/rest/touches?upsert=true", t)).body.status, "created");
  assert.equal((await api(tok, "POST", "/rest/touches?upsert=true", t)).body.status, "unchanged");
  await api(tok, "POST", "/rest/touches?upsert=true", { ...t, sentAt: "2026-11-21T23:00:00Z", providerId: "followup-1", channel: "email" });
  assert.equal(await count("select count(*)::int n from touches"), 2);
  assert.equal(await count("select count(*)::int n from events where type = 'touch.sent'"), 2);
  const d = (await api(tok, "GET", `/rest/huntItems/${it.id}?depth=1`)).body.data.huntItem;
  assert.equal(Number(d.speedToLeadMinutes), 42.5);
  assert.equal(d.touches.length, 2);
  assert.equal(d.extension.title, "Shopify replatform");
  const feed = (await api(null, "GET", "/api/items?workspace=tyler")).body.data.items;
  assert.equal(Number(feed.find((r: any) => r.id === it.id).speedToLeadMinutes), 42.5);
});

test("list: Twenty filter/order_by/limit/starting_after pages newest signal first without gaps", async () => {
  for (let i = 0; i < 5; i++) await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: `page-${i}`, signalAt: `2026-11-2${i}T10:00:00Z` }));
  const seen: string[] = [];
  let cursor: string | null = null;
  do {
    const r: any = await api(tok, "GET", `/rest/huntItems?filter=externalId[startsWith]:page-&order_by=signalAt[DescNullsLast]&limit=2${cursor ? "&starting_after=" + cursor : ""}`);
    assert.equal(r.body.totalCount, 5);
    seen.push(...r.body.data.huntItems.map((x: any) => x.externalId));
    cursor = r.body.pageInfo.hasNextPage ? r.body.pageInfo.endCursor : null;
  } while (cursor);
  assert.deepEqual(seen, ["page-4", "page-3", "page-2", "page-1", "page-0"]);
  const g = await api(tok, "GET", "/rest/huntItems/groupBy?field=huntType");
  assert.equal(g.body.data.groupBy[0].huntType, "upwork");
});

test("roost: Mohamed's item converts, leaves the feed, keeps its history", async () => {
  const it = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "mohamed", target: "Mohamed A. · Polymarket bot", person: { fullName: "Mohamed A." } }))).body.data.createHuntItem;
  const before = (await api(null, "GET", "/api/items?workspace=tyler")).body.data.items.map((r: any) => r.id);
  assert.ok(before.includes(it.id));
  const r = await api(tok, "POST", `/rest/huntItems/${it.id}/roost`, { kind: "client" });
  assert.equal(r.status, 200);
  const after = (await api(null, "GET", "/api/items?workspace=tyler")).body.data.items.map((r: any) => r.id);
  assert.ok(!after.includes(it.id));
  const tl = (await api(tok, "GET", `/rest/roosts/${r.body.data.roostHuntItem.roostId}/timeline`)).body.data.timeline.map((e: any) => e.type);
  assert.deepEqual(tl, ["item.found", "item.roosted"]);
  const feed = (await api(null, "GET", "/api/feed?workspace=tyler")).body;
  assert.deepEqual(feed.roosts[0].rows.map((x: any) => [x.name, x.hunt]), [["Mohamed A.", "upwork"]]);
});

test("pipeline fields only move forward on an upsert (a re-find never undoes a recording); PATCH sets them freely", async () => {
  const it = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "fwd", stage: "one_shot", vslStage: "scripted" }))).body.data.createHuntItem;
  await api(tok, "PATCH", `/rest/huntItems/${it.id}`, { vslStage: "recorded" });
  const again = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "fwd", stage: "one_shot", vslStage: "scripted" }))).body;
  assert.equal(again.status, "unchanged");
  assert.equal(again.data.createHuntItem.vslStage, "recorded");
  const fwd = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "fwd", vslStage: "sent" }))).body;
  assert.equal(fwd.data.createHuntItem.vslStage, "sent");
});
