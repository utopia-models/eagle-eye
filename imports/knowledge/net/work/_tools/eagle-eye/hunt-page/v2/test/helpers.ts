// Imported FIRST by every test file: points the pool at the throwaway eagleeye_test database before db.ts loads.
process.env.PG_DATABASE = process.env.PG_TEST_DATABASE || "eagleeye_test";
process.env.EAGLE_OPEN_READ = "tyler";
process.env.EAGLE_INGEST = "0";
process.env.VSL_SHOTS = process.env.VSL_TEST_SHOTS || "/nonexistent/eagle-test-shots"; // feed labels never read the real hunts/ folder

const { pool, asOwner } = await import("../src/db.ts");
const { runMigrations } = await import("../src/migrate.ts");
const { loadColumns } = await import("../src/rest.ts");
const { mintKey } = await import("../src/keys.ts");
const { buildApp } = await import("../src/app.ts");

/** Fresh schema per test file: drop everything, re-run the real migrations (0001 core + 0002 workspace/hunt types). */
export async function resetDb() {
  const c = await pool.connect();
  try {
    await c.query("set role eagleeye_owner");
    await c.query("drop schema if exists drizzle cascade; drop schema if exists pgboss cascade; drop schema public cascade; create schema public");
  } finally { c.release(); }
  await runMigrations({ host: "/var/run/postgresql", database: process.env.PG_DATABASE, user: process.env.USER, ssl: false });
  await loadColumns();
  await asOwner(tx => tx.query("insert into workspaces (slug, name) values ('osman', 'Osman') on conflict do nothing"));
}

export async function token(scopes: string[] = ["*"], workspace = "tyler") {
  return (await mintKey({ workspace, name: `test-${workspace}`, scopes, ttlSeconds: 600 })).token;
}

export const app = buildApp();
export async function api(tok: string | null, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
  const res = await app.request(path, { method, headers: { ...(tok ? { authorization: `Bearer ${tok}` } : {}), "content-type": "application/json", ...headers }, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, body: await res.json().catch(() => null) as any, headers: res.headers };
}

export const item = (o: Record<string, unknown> = {}) => ({
  huntType: "upwork", externalId: "~0221000000000000000001", target: "Shopify replatform", signal: "Upwork job alert",
  signalAt: "2026-11-21T20:00:00Z", upwork: { title: "Shopify replatform", postedAt: "2026-11-21T20:00:00Z" }, ...o,
});

export { pool, asOwner };
