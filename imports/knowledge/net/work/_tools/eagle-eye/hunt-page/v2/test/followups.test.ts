import { resetDb, pool, token, api, asOwner, item } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

const { planFollowups, planAll, stopReason, unscheduled, FOLLOWUPS } = await import("../src/followups.ts");

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

const DAY = 86_400_000;
const fund = (n: number) => item({ huntType: "funding", externalId: `fund:${n}`, target: `Co${n}`, signal: "seed", upwork: undefined,
  funding: { kind: "launch", round: "seed", announcedOn: "2026-11-20", sourceUrl: "https://x.test" } });

async function itemWithHead(n: number, sentAt: string) {
  const it = (await api(tok, "POST", "/rest/huntItems?upsert=true", fund(n))).body.data.createHuntItem;
  const h = await api(tok, "POST", "/rest/touches?upsert=true", { itemId: it.id, channel: "email", status: "sent", step: "offer", sentAt,
    providerId: `g-${n}`, threadId: `th-${n}`, details: { subject: "s" } });
  assert.equal(h.status, 201, JSON.stringify(h.body));
  return it.id as string;
}
const fuOf = (id: string) => asOwner(async tx => (await tx.query("select step, status, due_at, thread_id, details from touches where item_id = $1 and step like 'fu%' order by due_at", [id])).rows);

test("three follow-ups on days 3, 7 and 14 after the first send, each adding a different new thing", () => {
  assert.deepEqual(FOLLOWUPS.map(f => [f.step, f.day, f.adds]), [["fu_1", 3, "fix"], ["fu_2", 7, "clip"], ["fu_3", 14, "result"]]);
  const sent = new Date("2026-11-21T17:00:00Z");
  const p = planFollowups(sent, sent);
  assert.deepEqual(p.map(x => (x.dueAt.getTime() - sent.getTime()) / DAY), [3, 7, 14]);
  assert.ok(p.every(x => x.status === "queued"));
});

test("a backfill never fires two at once: only the latest overdue one runs now", () => {
  const sent = new Date("2026-11-01T00:00:00Z");
  const p = planFollowups(sent, new Date("2026-11-09T00:00:00Z"));
  assert.deepEqual(p.map(x => x.status), ["cancelled", "queued", "queued"]);
});

test("scan writes the touches in the head's thread once (idempotent) and lists them for pg-boss", async () => {
  const id = await itemWithHead(1, new Date().toISOString());
  assert.equal(await asOwner(tx => planAll(tx)), 1);
  assert.equal(await asOwner(tx => planAll(tx)), 0, "planned prospects are not planned again");
  const fu = await fuOf(id);
  assert.deepEqual(fu.map(t => [t.step, t.status, t.thread_id]), [["fu_1", "queued", "th-1"], ["fu_2", "queued", "th-1"], ["fu_3", "queued", "th-1"]]);
  const todo = await asOwner(tx => unscheduled(tx));
  assert.equal(todo.filter(t => t.slug === "tyler").length, 3);
});

test("stop rule: any reply, unsubscribe or bounce cancels; investors stay held", async () => {
  const id = await itemWithHead(2, new Date().toISOString());
  await asOwner(tx => planAll(tx));
  const [t1] = await fuOf(id);
  const tid = (await asOwner(async tx => (await tx.query("select id from touches where item_id = $1 and step = 'fu_1'", [id])).rows[0].id)) as string;
  assert.equal(await asOwner(tx => stopReason(tx, tid)), null, "no reply yet: go");
  await api(tok, "POST", "/rest/replies", { itemId: id, channel: "email", body: "please remove me", receivedAt: new Date().toISOString(), outcome: "unsubscribe", providerId: "r2" });
  assert.match(String(await asOwner(tx => stopReason(tx, tid))), /reply received \(unsubscribe\)/);
  assert.equal(t1.status, "queued");

  const b = await itemWithHead(3, new Date().toISOString());
  await asOwner(tx => planAll(tx));
  await asOwner(tx => tx.query("update touches set status = 'failed' where item_id = $1 and step = 'offer'", [b]));
  const bid = (await asOwner(async tx => (await tx.query("select id from touches where item_id = $1 and step = 'fu_1'", [b])).rows[0].id)) as string;
  assert.equal(await asOwner(tx => stopReason(tx, bid)), "bounce");
});

test("a prospect that already replied gets no follow-ups at all", async () => {
  const id = await itemWithHead(4, new Date().toISOString());
  await api(tok, "POST", "/rest/replies", { itemId: id, channel: "email", body: "yes send it", receivedAt: new Date().toISOString(), providerId: "r4" });
  await asOwner(tx => planAll(tx));
  assert.deepEqual(await fuOf(id), []);
});

test("replies accept outcome bounce", async () => {
  const id = await itemWithHead(5, new Date().toISOString());
  const r = await api(tok, "POST", "/rest/replies", { itemId: id, channel: "email", body: "Delivery failed", receivedAt: new Date().toISOString(), outcome: "bounce", providerId: "r5" });
  assert.equal(r.status, 201, JSON.stringify(r.body));
});
