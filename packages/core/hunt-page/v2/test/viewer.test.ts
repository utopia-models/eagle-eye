import { resetDb, pool, token, api, item, asOwner, app } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { VIEWER_DIR } from "../src/viewer.ts";

let tok: string, itemId: string, touchId: string;
const slug = "river-test01";
before(async () => {
  await resetDb();
  tok = await token();
  itemId = (await api(tok, "POST", "/rest/huntItems?upsert=true", item())).body.data.createHuntItem.id;
  const v = await api(tok, "POST", "/rest/viewers?upsert=true", { slug, itemId, title: "River walkthrough", senderName: "Tyler Youk", pageUrl: `https://utopiamodels.ai/v/${slug}/` });
  assert.equal(v.status, 201, JSON.stringify(v.body));
  touchId = (await api(tok, "POST", "/rest/touches", { itemId, channel: "email", sentAt: new Date().toISOString(), providerId: "gm-1", threadId: "th-1" })).body.data.createTouch.id;
  await api(tok, "POST", "/rest/touches", { itemId, channel: "linkedin", status: "queued", sentAt: new Date().toISOString() });
  mkdirSync(join(VIEWER_DIR, slug), { recursive: true });
  writeFileSync(join(VIEWER_DIR, slug, "index.html"), "<h1>River</h1>");
  writeFileSync(join(VIEWER_DIR, slug, "video.mp4"), Buffer.alloc(1000, 7));
});
after(() => pool.end());

const beacon = (body: unknown, s = slug) => app.request(`/v/${s}/e`, { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify(body) });
const touch = async () => asOwner(async tx => (await tx.query("select * from touches where id = $1", [touchId])).rows[0]);
const itemRow = async () => asOwner(async tx => (await tx.query("select vsl_stage, reply_status from hunt_items where id = $1", [itemId])).rows[0]);

test("page and video serve without a token; video honours Range", async () => {
  const p = await app.request(`/v/${slug}/`);
  assert.equal(p.status, 200);
  assert.match(await p.text(), /River/);
  const r = await app.request(`/v/${slug}/video.mp4`, { headers: { range: "bytes=10-19" } });
  assert.equal(r.status, 206);
  assert.equal(r.headers.get("content-range"), "bytes 10-19/1000");
  assert.equal((await r.arrayBuffer()).byteLength, 10);
  assert.equal((await app.request(`/v/${slug}/..%2F..%2Fetc`)).status, 404);
  assert.equal((await app.request(`/v/nope-unknown/`)).status, 404);
});

test("a view opens the touch; milestones write watch_pct/watched_s once per session and move the item to watched", async () => {
  assert.equal((await beacon({ e: "view", sid: "s1", c: "email" })).status, 202);
  let t = await touch();
  assert.ok(t.opened_at, "view sets opened_at");
  assert.equal(t.watch_pct, null);
  assert.equal((await itemRow()).reply_status, "opened");

  for (const pct of [0, 25, 50]) assert.equal((await beacon({ e: pct ? "progress" : "play", pct, sid: "s1", c: "email", t: pct })).status, 202);
  const dup = await (await beacon({ e: "progress", pct: 25, sid: "s1", c: "email" })).json();
  assert.equal(dup.recorded, false, "same session + milestone is recorded once");
  t = await touch();
  assert.equal(t.watch_pct, 50);
  assert.equal(Number(t.watched_s), 50);
  assert.deepEqual(await itemRow(), { vsl_stage: "watched", reply_status: "watched" });

  const n = await asOwner(async tx => (await tx.query("select count(*)::int n from events where type = 'touch.watch'")).rows[0].n);
  assert.equal(n, 3);
});

test("a queued touch is never credited; bad input is refused", async () => {
  await beacon({ e: "progress", pct: 100, sid: "s2", c: "linkedin" });
  const q = await asOwner(async tx => (await tx.query("select watch_pct from touches where channel = 'linkedin'")).rows[0]);
  assert.equal(q.watch_pct, null, "the queued LinkedIn touch is not credited; the sent email touch is");
  const types = await asOwner(async tx => (await tx.query("select type from events where type like 'touch.%' and data->>'channel' = 'linkedin' and type <> 'touch.watch'")).rows.map((r: any) => r.type));
  assert.deepEqual(types, ["touch.queued"], "a queued touch is announced as queued, never as sent");
  assert.equal((await touch()).watch_pct, 100);
  assert.equal((await beacon({ e: "progress", pct: 33, sid: "s3" })).status, 400);
  assert.equal((await beacon({ e: "hack" })).status, 400);
  assert.equal((await beacon({ e: "view" }, "zzzz-none")).status, 404);
});

test("the dryrun workspace exists with the same hunt types and is isolated from tyler", async () => {
  const dtok = await token(["*"], "dryrun");
  const types = await api(dtok, "GET", "/rest/huntTypes");
  assert.deepEqual(types.body.data.huntTypes.map((t: any) => t.key).sort(), ["funding", "investor", "job_post", "upwork"]);
  const vs = await api(dtok, "GET", "/rest/viewers");
  assert.equal(vs.body.totalCount, 0, "tyler's viewer is invisible to the dryrun workspace");
});
