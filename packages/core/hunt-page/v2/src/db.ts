import pg from "pg";

// Ra: unix-socket peer auth as the OS user (no password exists to leak). Elsewhere: PG_DATABASE_URL.
export const PG_CONFIG: pg.ClientConfig = process.env.PG_DATABASE_URL
  ? { connectionString: process.env.PG_DATABASE_URL }
  : { host: "/var/run/postgresql", database: process.env.PG_DATABASE || "eagleeye", user: process.env.PG_USER || process.env.USER, ssl: false };

// Keep RAM low (Ra has ~1-2 GB free): a handful of connections is plenty for a few agents + one UI.
export const pool = new pg.Pool({ ...PG_CONFIG, max: Number(process.env.PG_POOL_MAX || 5), idleTimeoutMillis: 30_000 });

export type Tx = pg.PoolClient;

export class HttpError extends Error {
  constructor(public status: number, message: string, public extra: Record<string, unknown> = {}) { super(message); }
}

/** One request = one transaction as role eagle_app, scoped to one workspace by RLS. */
export async function withWorkspace<T>(workspaceId: string, fn: (tx: Tx) => Promise<T>): Promise<T> {
  const c = await pool.connect();
  try {
    await c.query("begin");
    await c.query("set local role eagle_app");
    await c.query("select set_config('app.workspace_id', $1, true)", [workspaceId]);
    const out = await fn(c);
    await c.query("commit");
    return out;
  } catch (e) {
    await c.query("rollback").catch(() => {});
    throw e;
  } finally {
    c.release();
  }
}

/** Admin path (key minting, resolution, purge): the owner role, which has the owner_all policy. */
export async function asOwner<T>(fn: (tx: Tx) => Promise<T>): Promise<T> {
  const c = await pool.connect();
  try {
    await c.query("begin");
    await c.query("set local role eagleeye_owner");
    const out = await fn(c);
    await c.query("commit");
    return out;
  } catch (e) {
    await c.query("rollback").catch(() => {});
    throw e;
  } finally {
    c.release();
  }
}

export async function workspaceIdBySlug(slug: string): Promise<string | null> {
  return asOwner(async tx => (await tx.query("select id from workspaces where slug = $1 and deleted_at is null", [slug])).rows[0]?.id ?? null);
}

export const snake = (s: string) => s.replace(/[A-Z]/g, c => "_" + c.toLowerCase());
export const camel = (s: string) => s.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase());
export function camelRow(r: Record<string, unknown>) {
  const o: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r)) o[camel(k)] = v;
  return o;
}
