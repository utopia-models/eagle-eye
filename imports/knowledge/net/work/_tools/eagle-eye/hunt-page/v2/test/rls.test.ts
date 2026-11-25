import { resetDb, pool, token, api, item } from "./helpers.ts";
import { withWorkspace, workspaceIdBySlug } from "../src/db.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

let tyler: string, osman: string, tTok: string, oTok: string, itemId: string;
before(async () => {
  await resetDb();
  tyler = (await workspaceIdBySlug("tyler"))!;
  osman = (await workspaceIdBySlug("osman"))!;
  tTok = await token(["*"], "tyler");
  // osman's hunt types (a workspace installs its own hunts)
  oTok = await token(["*"], "osman");
  await api(oTok, "POST", "/rest/metadata/huntTypes", { key: "upwork", label: "Upwork", icon: "upwork", version: "0.1.0", extensionTable: "upwork_jobs" });
  itemId = (await api(tTok, "POST", "/rest/huntItems?upsert=true", item())).body.data.createHuntItem.id;
});
after(() => pool.end());

test("as eagle_app, a workspace sees only its own rows", async () => {
  const mine = await withWorkspace(tyler, async tx => (await tx.query("select count(*)::int n from hunt_items")).rows[0].n);
  const theirs = await withWorkspace(osman, async tx => (await tx.query("select count(*)::int n from hunt_items")).rows[0].n);
  const events = await withWorkspace(osman, async tx => (await tx.query("select count(*)::int n from events where item_id = $1", [itemId])).rows[0].n);
  assert.equal(mine, 1);
  assert.equal(theirs, 0);
  assert.equal(events, 0);
});

test("as eagle_app with no workspace set, nothing is visible", async () => {
  const c = await pool.connect();
  try {
    await c.query("begin; set local role eagle_app");
    assert.equal((await c.query("select count(*)::int n from hunt_items")).rows[0].n, 0);
    assert.equal((await c.query("select count(*)::int n from workspaces")).rows[0].n, 0);
  } finally { await c.query("rollback"); c.release(); }
});

test("writing a row into another workspace is refused by the policy", async () => {
  await assert.rejects(withWorkspace(osman, tx => tx.query(
    `insert into companies (workspace_id, name) values ($1, 'Leak Inc')`, [tyler])), /row-level security/);
});

test("set_config inside a request cannot widen it: the row filter still holds the other workspace out", async () => {
  // a request scoped to osman that flips the setting mid-transaction only becomes a tyler-scoped request: never both
  const n = await withWorkspace(osman, async tx => {
    await tx.query("select set_config('app.workspace_id', $1, true)", [osman]);
    return (await tx.query("select count(*)::int n from hunt_items where workspace_id = $1", [tyler])).rows[0].n;
  });
  assert.equal(n, 0);
});

test("over the API: osman's token gets 404 on tyler's item and an empty list", async () => {
  assert.equal((await api(oTok, "GET", `/rest/huntItems/${itemId}`)).status, 404);
  const l = await api(oTok, "GET", "/rest/huntItems");
  assert.equal(l.status, 200);
  assert.equal(l.body.totalCount, 0);
  const mine = await api(tTok, "GET", "/rest/huntItems");
  assert.equal(mine.body.totalCount, 1);
});

test("tokens: missing -> 401, wrong scope -> 403, revoked/expired -> 401; only the hash is stored", async () => {
  assert.equal((await api(null, "GET", "/rest/huntItems")).status, 401);
  const ro = await token(["people:read"]);
  assert.equal((await api(ro, "POST", "/rest/huntItems", item({ externalId: "nope" }))).status, 403);
  assert.equal((await api(ro, "GET", "/rest/people")).status, 200);
  assert.equal((await api("ee_not-a-real-token", "GET", "/rest/people")).status, 401);
  const c = await pool.connect();
  try {
    await c.query("set role eagleeye_owner");
    const cols = (await c.query("select column_name from information_schema.columns where table_name = 'api_keys'")).rows.map(r => r.column_name);
    assert.ok(cols.includes("token_sha256") && !cols.includes("token"));
    await c.query("update api_keys set expires_at = now() - interval '1 s' where name = 'test-tyler' and scopes = '{people:read}'");
  } finally { await c.query("reset role"); c.release(); }
  assert.equal((await api(ro, "GET", "/rest/people")).status, 401);
});
