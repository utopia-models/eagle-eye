import { resetDb, pool, token, api, asOwner, item } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

const { deriveNext, short, sortRows } = await import("../src/roosts.ts");
const { nextSteps, stepLabel } = await import("../src/ingest.ts");

let tok: string;
before(async () => { await resetDb(); tok = await token(); });
after(() => pool.end());

test("empty: no replies, no bookings, no roosts -> zero rows (the UI shows its empty state, never mock rows)", async () => {
  const r = await api(null, "GET", "/api/roosts?workspace=tyler");
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.rows, []);
});

test("a row leads with next step + when + owner and the last thing they said; sorted by due soonest", async () => {
  // a replied hunt item: their message is newer than ours -> Reply within 5 min, owner = the hunt's backend agent
  const a = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "~021000000000000000000a", target: "Shopify replatform", backendAgent: "upwork" }))).body.data.createHuntItem;
  await api(tok, "PATCH", `/rest/huntItems/${a.id}`, { stage: "replied", replyStatus: "replied" });
  await api(tok, "POST", "/rest/replies", { itemId: a.id, channel: "upwork", body: "Hi Tyler,\n\nCan you start Monday? We need the cart fixed first.\n\nThanks", receivedAt: "2026-11-21T20:00:00Z", providerId: "r-a" });
  // a client roost with an explicit next step due earlier
  const p = (await api(tok, "POST", "/rest/people?upsert=true", { fullName: "Mohamed" })).body.data.createPerson;
  const ro = (await api(tok, "POST", "/rest/roosts?upsert=true", { personId: p.id, kind: "client", stage: "contract", origin: "upwork" })).body.data.createRoost;
  const s = await api(tok, "POST", "/rest/nextSteps?upsert=true", { roostId: ro.id, what: "M2 due", dueAt: "2026-11-21T17:00:00Z", owner: "tyler", sourceKey: "clients:mohamed:next:M2 due" });
  assert.equal(s.status, 201, JSON.stringify(s.body));
  assert.equal((await api(tok, "POST", "/rest/nextSteps?upsert=true", { roostId: ro.id, what: "M2 due", dueAt: "2026-11-21T17:00:00Z", owner: "tyler", sourceKey: "clients:mohamed:next:M2 due" })).body.status, "unchanged");
  await api(tok, "POST", "/rest/replies", { roostId: ro.id, channel: "upwork", body: "View your message and send a reply. ͏ ͏", receivedAt: "2026-11-21T19:00:00Z", providerId: "r-m" });

  const rows = (await api(null, "GET", "/api/roosts?workspace=tyler")).body.rows;
  assert.deepEqual(rows.map((r: any) => r.name), ["Mohamed", "Shopify replatform"]);
  assert.deepEqual(rows[0].next, { what: "M2 due", due: "2026-11-21T17:00:00Z", owner: "tyler", derived: false });
  assert.equal(rows[0].last.said, null, "an Upwork notification carries no text: a time, never 'what they said'");
  assert.deepEqual(rows[1].next, { what: "Reply", due: "2026-11-21T20:05:00Z", owner: "upwork", derived: true });
  assert.equal(rows[1].last.said, "Can you start Monday? We need the cart fixed first.");
});

test("a negative reply, an unsubscribe or a bounce is not a roost row", async () => {
  const b = (await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "~021000000000000000000b", target: "Nope Inc" }))).body.data.createHuntItem;
  await api(tok, "PATCH", `/rest/huntItems/${b.id}`, { stage: "replied", replyStatus: "replied" });
  await api(tok, "POST", "/rest/replies", { itemId: b.id, channel: "email", body: "not interested", receivedAt: "2026-11-21T21:00:00Z", outcome: "negative", providerId: "r-b" });
  const rows = (await api(null, "GET", "/api/roosts?workspace=tyler")).body.rows;
  assert.ok(!rows.some((r: any) => r.name === "Nope Inc"));
});

test("deriveNext / short / sort", () => {
  const t = (s: string) => new Date(s);
  assert.equal(deriveNext({ replyStatus: "booked", lastIn: null, lastOut: null, owner: "x" })?.what, "Call");
  assert.deepEqual(deriveNext({ replyStatus: "replied", lastIn: t("2026-11-20T00:00:00Z"), lastOut: t("2026-11-20T01:00:00Z"), owner: "eagle" }),
    { what: "Follow up", due: "2026-11-23T01:00:00Z", owner: "eagle", derived: true });
  assert.equal(deriveNext({ replyStatus: "replied", lastIn: null, lastOut: null, owner: "x" }), null);
  assert.equal(short("Hey Tyler, sounds good.\n\nOn Mon, Nov 20, 2026 Tyler wrote:\n> hi"), "sounds good.");
  const r = (id: string, due: string | null, has = true) => ({ id, next: has ? { what: "x", due, owner: "t", derived: false } : null, last: null } as any);
  assert.deepEqual(sortRows([r("none", null, false), r("undated", null), r("late", "2026-11-25T00:00:00Z"), r("soon", "2026-11-22T00:00:00Z")]).map((x: any) => x.id),
    ["soon", "late", "undated", "none"]);
});

test("ingest: a client's dated milestone + the CRM tasks WE own become next steps; a task the client owns does not", () => {
  const dir = mkdtempSync(`${tmpdir()}/crm-`);
  writeFileSync(`${dir}/mohamed.jsonl`, [
    { type: "task", id: "mohamed-cap-choice", text: "Mohamed chooses one of the two options", owner: "mohamed", due: null },
    { type: "task", id: "mohamed-12-round-count", text: "Send the 12-round count", owner: "tyler", due: "2026-11-19T02:30:00Z" },
    { type: "done", id: "mohamed-12-round-count" },
    { type: "task", id: "mohamed-bot-reply", text: "Answer his last message about the low number of trade entries once he picks the cap option; keep rule 34b", owner: "tyler", due: null },
  ].map(x => JSON.stringify(x)).join("\n"));
  const n = nextSteps({ slug: "mohamed", next: { kind: "milestone", label: "M2 due", date: "2026-11-22" } }, dir);
  assert.deepEqual(n, [
    { what: "M2 due", dueAt: "2026-11-22T17:00:00Z", owner: "tyler", sourceKey: "clients:mohamed:next:M2 due" },
    { what: "Answer his last message about the low number of trade entries", dueAt: null, owner: "tyler", sourceKey: "crm:mohamed-bot-reply" },
  ]);
  assert.equal(stepLabel("Write and send the detailed AI-automation proposal: live stock"), "Write and send the detailed AI-automation proposal");
});
