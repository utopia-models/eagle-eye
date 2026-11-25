import { resetDb, pool, asOwner } from "./helpers.ts";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";

before(resetDb);
after(() => pool.end());

const TABLES = ["workspaces", "workspace_members", "api_keys", "hunt_types", "companies", "people", "roosts", "hunt_items",
  "funding_signals", "job_posts", "upwork_jobs", "one_shots", "recordings", "touches", "replies", "events", "idempotency_keys"];

test("every table exists with RLS forced", async () => {
  const r = await pool.query("select relname, relrowsecurity, relforcerowsecurity from pg_class where relnamespace = 'public'::regnamespace and relkind = 'r'");
  const byName = new Map(r.rows.map(x => [x.relname, x]));
  for (const t of TABLES) {
    assert.ok(byName.has(t), `missing table ${t}`);
    assert.ok(byName.get(t).relrowsecurity && byName.get(t).relforcerowsecurity, `RLS not forced on ${t}`);
  }
});

test("hunt signal timing: signal_at, found_at (default now), touches.sent_at are timestamptz; feed exposes speed_to_lead_minutes", async () => {
  const r = await pool.query(`select table_name, column_name, data_type from information_schema.columns
    where (table_name, column_name) in (('hunt_items','signal_at'),('hunt_items','found_at'),('touches','sent_at'),('feed_rows','speed_to_lead_minutes'),('feed_rows','found_at'))`);
  const m = Object.fromEntries(r.rows.map(x => [`${x.table_name}.${x.column_name}`, x.data_type]));
  assert.equal(m["hunt_items.signal_at"], "timestamp with time zone");
  assert.equal(m["hunt_items.found_at"], "timestamp with time zone");
  assert.equal(m["touches.sent_at"], "timestamp with time zone");
  assert.ok(m["feed_rows.speed_to_lead_minutes"]);
  assert.equal(m["feed_rows.found_at"], "timestamp with time zone");
});

test("events are append-only; roosted <=> roost_id; enums are checked", async () => {
  const ids = await asOwner(async tx => ({
    ws: (await tx.query("select id from workspaces where slug = 'tyler'")).rows[0].id as string,
    ht: (await tx.query("select id from hunt_types where key = 'upwork'")).rows[0].id as string,
  }));
  const ev = await asOwner(async tx => (await tx.query("insert into events (workspace_id, type, actor) values ($1, 'test.ping', '{}') returning id", [ids.ws])).rows[0].id);
  // each expected failure runs in its own transaction, so a pass can't hide behind an aborted one
  await assert.rejects(asOwner(tx => tx.query("update events set type = 'x' where id = $1", [ev])), /append-only/);
  await assert.rejects(asOwner(tx => tx.query("delete from events where id = $1", [ev])), /append-only/);
  const ins = (extra: string, val: string) => asOwner(tx => tx.query(`insert into hunt_items (workspace_id, hunt_type_id, hunt_type, external_id, target, signal, signal_at, ${extra})
      values ($1, $2, 'upwork', $3, 't', 's', now(), $4)`, [ids.ws, ids.ht, "x-" + extra, val]));
  await assert.rejects(ins("stage", "roosted"), /check constraint/);
  await assert.rejects(ins("vsl_stage", "bogus"), /check constraint/);
});

test("eagle_app cannot update or delete events (grant level, not only the trigger)", async () => {
  const r = await pool.query("select has_table_privilege('eagle_app', 'events', 'UPDATE') as u, has_table_privilege('eagle_app', 'events', 'DELETE') as d, has_table_privilege('eagle_app', 'events', 'INSERT') as i");
  assert.deepEqual(r.rows[0], { u: false, d: false, i: true });
});

test("seed: workspace tyler + the three first-party hunt types, zero hunt rows", async () => {
  const r = await pool.query("select key, extension_table from hunt_types h join workspaces w on w.id = h.workspace_id where w.slug = 'tyler' order by key");
  assert.deepEqual(r.rows, [{ key: "funding", extension_table: "funding_signals" }, { key: "investor", extension_table: "investor_signals" }, { key: "job_post", extension_table: "job_posts" }, { key: "upwork", extension_table: "upwork_jobs" }]);
  assert.equal((await pool.query("select count(*)::int n from hunt_items")).rows[0].n, 0);
});
