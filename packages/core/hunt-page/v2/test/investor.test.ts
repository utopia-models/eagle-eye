import { resetDb, pool, token, api, asOwner } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

const { buildFeed, pipelineStatus } = await import("../src/feed.ts");

let tok: string, ws: string;
before(async () => {
  await resetDb();
  tok = await token();
  ws = await asOwner(async tx => (await tx.query("select id from workspaces where slug = 'tyler'")).rows[0].id);
});
after(() => pool.end());

const inv = (o: Record<string, unknown> = {}) => ({
  huntType: "investor", externalId: "investor:oss-capital", target: "OSS Capital", subtype: "fund",
  signal: "Plane $4M seed, sole investor", signalAt: "2026-11-21T00:00:00Z", fit: 74, stage: "qualified",
  details: { rank: 1, status: "Ranked", trigger_fresh: false },
  investor: { investor: "OSS Capital", firm: "OSS Capital", investorKind: "fund", verified: true, dealCompany: "Plane", dealRound: "seed",
    dealAmount: "$4M", coldRoute: "https://oss.capital/contact-us/", thesisQuote: "exclusively dedicated to backing leading COSS startup founders",
    similarity: 85, score: 74, scoreParts: { similarity: 34, check_stage: 8, oss_history: 20, cold_route: 7, warm_path: 0 }, sourceUrl: "https://oss.capital" },
  ...o,
});

test("investor hunt type exists for tyler with the Investor label and its extension table", async () => {
  const r = await asOwner(async tx => (await tx.query("select label, extension_table from hunt_types t join workspaces w on w.id = t.workspace_id where w.slug = 'tyler' and key = 'investor'")).rows[0]);
  assert.deepEqual(r, { label: "Investor", extension_table: "investor_signals" });
});

test("investor upsert writes the 1:1 extension + subtype; a re-find is unchanged; a score change updates", async () => {
  const a = await api(tok, "POST", "/rest/huntItems?upsert=true", inv());
  assert.equal(a.status, 201, JSON.stringify(a.body));
  assert.equal(a.body.data.createHuntItem.subtype, "fund");
  const b = await api(tok, "POST", "/rest/huntItems?upsert=true", inv());
  assert.equal(b.body.status, "unchanged");
  const c = await api(tok, "POST", "/rest/huntItems?upsert=true", inv({ investor: { ...(inv().investor as any), score: 80 } }));
  assert.equal(c.body.status, "updated");
  const row = await asOwner(async tx => (await tx.query("select score, verified, score_parts from investor_signals")).rows[0]);
  assert.equal(row.score, 80);
  assert.equal(row.verified, true);
  assert.equal(row.score_parts.oss_history, 20);
  const bad = await api(tok, "POST", "/rest/huntItems?upsert=true", inv({ externalId: "x", investor: { investor: "X", investorKind: "vc", sourceUrl: "u" } }));
  assert.equal(bad.status, 400, "investorKind is fund | angel | program");
});

test("feed: investor lane rows carry the Investor badge, subtype, score and derived status; counts by type", async () => {
  await api(tok, "POST", "/rest/huntItems?upsert=true", inv({ externalId: "investor:runa", target: "Runa Capital", subtype: "fund",
    investor: { ...(inv().investor as any), investor: "Runa Capital", verified: false, score: 50 }, details: { rank: null } }));
  const f: any = await buildFeed(ws);
  const lane = f.hunts.find((h: any) => h.id === "investor");
  assert.ok(lane, "investor lane present");
  assert.equal(lane.name, "Investor");
  assert.equal(lane.feed.length, 2);
  assert.equal(lane.feed[0].investor, "OSS Capital", "ranked by score");
  assert.equal(lane.feed[0].badge, "Investor");
  assert.equal(lane.feed[0].subtype, "fund");
  assert.equal(lane.feed[0].status, "Held", "Tyler 11-21: investor sends hold");
  assert.equal(lane.feed[0].flag, null);
  assert.equal(lane.feed[1].status, "Held");
  assert.equal(lane.feed[1].flag, "unverified", "an [unverified] row stays flagged");
  assert.equal(f.counts.by_type.investor, 2);
  assert.equal(f.items[0].huntLabel ?? f.items.find((x: any) => x.huntType === "investor").huntLabel, "Investor");
});

test("sequence touches: step + due_at + queued/cancelled, channel ats; offer touch drives the funding status", async () => {
  const it = (await api(tok, "POST", "/rest/huntItems?upsert=true", { huntType: "funding", externalId: "https://example.com/raise", target: "Acme",
    signal: "Acme raises $2M seed", signalAt: "2026-11-21T10:00:00Z", stage: "one_shot", details: { status: "Offer queued" },
    funding: { kind: "news", round: "seed", announcedOn: "2026-11-21", sourceUrl: "https://example.com/raise" } })).body.data.createHuntItem;
  const offer = await api(tok, "POST", "/rest/touches?upsert=true", { itemId: it.id, channel: "email", status: "queued", step: "offer",
    sentAt: "2026-11-21T10:05:00Z", dueAt: "2026-11-21T10:05:00Z", providerId: `seq:${it.id}:offer` });
  assert.equal(offer.status, 201, JSON.stringify(offer.body));
  assert.equal(offer.body.data.createTouch.step, "offer");
  const ats = await api(tok, "POST", "/rest/touches?upsert=true", { itemId: it.id, channel: "ats", status: "queued", step: "ats",
    sentAt: "2026-11-21T10:05:00Z", dueAt: "2026-11-21T10:05:00Z", providerId: `seq:${it.id}:ats` });
  assert.equal(ats.status, 201, "channel ats is allowed");
  const cancel = await api(tok, "PATCH", `/rest/touches/${ats.body.data.createTouch.id}`, { status: "cancelled" });
  assert.equal(cancel.status, 200);
  let f: any = await buildFeed(ws);
  const row = () => f.hunts.find((h: any) => h.id === "funding").feed.find((r: any) => r.item_id === it.id);
  assert.equal(row().status, "Offer queued");
  assert.equal(row().queued_touches, 1);
  await api(tok, "PATCH", `/rest/touches/${offer.body.data.createTouch.id}`, { status: "sent", threadId: "t1" });
  f = await buildFeed(ws);
  assert.equal(row().status, "Offered");
  await api(tok, "POST", "/rest/replies?upsert=true", { itemId: it.id, channel: "email", body: "yes send it", receivedAt: "2026-11-21T12:00:00Z", providerId: "m1", outcome: "positive" });
  f = await buildFeed(ws);
  assert.equal(row().status, "Ready to record");
  assert.equal(f.counts.by_status["Ready to record"], 1);
});

test("pipelineStatus precedence", () => {
  assert.equal(pipelineStatus({ offer_status: "queued" }), "Offer queued");
  assert.equal(pipelineStatus({ offer_status: "sent" }), "Offered");
  assert.equal(pipelineStatus({ offer_status: "sent", pos_reply: true }), "Ready to record");
  assert.equal(pipelineStatus({ offer_status: "sent", pos_reply: true, vsl_stage: "recorded" }), "Recorded");
  assert.equal(pipelineStatus({ pos_reply: true, vsl_stage: "sent" }), "Sent");
  assert.equal(pipelineStatus({ neg_reply: true, offer_status: "sent" }), "Not interested");
  assert.equal(pipelineStatus({}), null);
});
