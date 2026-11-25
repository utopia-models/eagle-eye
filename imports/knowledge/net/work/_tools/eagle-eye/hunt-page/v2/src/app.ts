import { Hono, type Context } from "hono";
import { cors } from "hono/cors";
import { streamSSE } from "hono/streaming";
import { HttpError, withWorkspace, workspaceIdBySlug, camelRow, type Tx } from "./db.ts";
import { resolveKey, allowed, actorOf, sha256, type ApiKey, type Actor } from "./keys.ts";
import { RESOURCES, list, getOne, groupBy, write, patch, softDelete, type Resource } from "./rest.ts";
import { upsertHuntItem, huntItemDetail, assertOneShotSystem } from "./hunts.ts";
import { applyFact } from "./events.ts";
import { buildFeed } from "./feed.ts";
import { buildRoosts } from "./roosts.ts";
import { subscribe, replay, subscriberCount, type StreamMsg } from "./stream.ts";
import { viewerRoutes, serveFile } from "./viewer.ts";
import { sendFileUrl, SEND_DIR } from "./feed.ts";
import { join } from "node:path";

type Env = { Variables: { key: ApiKey } };

// Workspaces readable without a token (the feed, item detail, SSE). Ra binds the Tailscale IP only; in front of the public
// hostname this becomes Cloudflare Access + a member session. Comma list of slugs; empty = token required everywhere.
const OPEN_READ = new Set((process.env.EAGLE_OPEN_READ ?? "").split(",").map(s => s.trim()).filter(Boolean));

const bearer = (c: Context) => (c.req.header("authorization") || "").replace(/^Bearer\s+/i, "") || c.req.query("token") || "";

function resource(name: string): Resource {
  const r = RESOURCES[name];
  if (!r) throw new HttpError(404, `unknown object ${name}`);
  return r;
}
function need(k: ApiKey, res: string, mode: "read" | "write") {
  if (!allowed(k.scopes, res, mode)) throw new HttpError(403, `token ${k.name} lacks ${res}:${mode}`);
}

/** Stripe-style Idempotency-Key: same key + same body replays the stored response; same key + new body is a 422. */
async function idempotent(c: Context<Env>, tx: Tx, run: () => Promise<{ status: number; body: unknown }>) {
  const key = c.req.header("idempotency-key");
  if (!key) return run();
  const hash = sha256(c.req.method + " " + c.req.path + "?" + new URL(c.req.url).search + "\n" + (await c.req.text()));
  const ins = await tx.query("insert into idempotency_keys (workspace_id, key, request_sha256) values ($1, $2, $3) on conflict do nothing returning key",
    [c.get("key").workspaceId, key, hash]);
  if (!ins.rowCount) {
    const prev = (await tx.query("select request_sha256, status_code, response from idempotency_keys where key = $1", [key])).rows[0];
    if (!prev.request_sha256.equals(hash)) throw new HttpError(422, "Idempotency-Key reused with a different request");
    return { status: prev.status_code, body: prev.response, replayed: true };
  }
  const out = await run();
  await tx.query("update idempotency_keys set status_code = $2, response = $3 where key = $1", [key, out.status, JSON.stringify(out.body)]);
  return out;
}

async function readWorkspace(c: Context): Promise<{ ws: string; key: ApiKey | null }> {
  const tok = bearer(c);
  if (tok) {
    const k = await resolveKey(tok);
    if (!k) throw new HttpError(401, "invalid, expired or revoked token");
    need(k, "huntItems", "read");
    return { ws: k.workspaceId, key: k };
  }
  const slug = c.req.query("workspace") || (OPEN_READ.size === 1 ? [...OPEN_READ][0] : "");
  if (!slug || !OPEN_READ.has(slug)) throw new HttpError(401, "Authorization: Bearer <token> required");
  const ws = await workspaceIdBySlug(slug);
  if (!ws) throw new HttpError(404, `no workspace ${slug}`);
  return { ws, key: null };
}

export function buildApp() {
  const app = new Hono<Env>();

  app.onError((e, c) => {
    if (e instanceof HttpError) return c.json({ statusCode: e.status, error: e.message, ...e.extra }, e.status as any);
    const code = (e as any).cause?.code ?? (e as any).code;
    const msg = (e as any).cause?.message ?? e.message;
    if (code === "23505") return c.json({ statusCode: 409, error: msg }, 409);
    if (["23502", "23503", "23514", "22P02", "22007", "22008", "42703"].includes(code)) return c.json({ statusCode: 400, error: msg }, 400);
    console.error(e);
    return c.json({ statusCode: 500, error: "internal error" }, 500);
  });

  // ---------- public one-shot viewer + watch beacon (no token; see viewer.ts) ----------
  app.route("/", viewerRoutes());

  app.use("/api/*", cors({ origin: "*", allowMethods: ["GET"], exposeHeaders: ["Content-Type"] }));

  app.get("/healthz", async c => {
    const ws = await workspaceIdBySlug("tyler");
    return c.json({ ok: true, workspace: !!ws, sse_clients: subscriberCount(), at: new Date().toISOString() });
  });

  // ---------- read side for the UI ----------
  app.get("/api/feed", async c => { const { ws } = await readWorkspace(c); return c.json(await buildFeed(ws)); });
  // the sent VSL file itself (knowledge#18576): one data path for the hunt detail page; only a *.mp4 that sits in the sender's own folder
  app.get("/api/vsl/:file", async c => { const u = sendFileUrl(c.req.param("file")); if (!u) throw new HttpError(404, "not found"); return serveFile(c, join(SEND_DIR, u.slice("/api/vsl/".length))); });
  app.get("/api/roosts", async c => { const { ws } = await readWorkspace(c); return c.json(await buildRoosts(ws)); });
  app.get("/api/items", async c => {
    const { ws } = await readWorkspace(c);
    const limit = Math.min(Number(c.req.query("limit")) || 100, 500);
    const before = c.req.query("before");
    const rows = await withWorkspace(ws, async tx => (await tx.query(
      `select * from feed_rows ${before ? "where (signal_at, id) < (select signal_at, id from hunt_items where id = $2)" : ""} order by signal_at desc, id desc limit $1`,
      before ? [limit, before] : [limit])).rows);
    return c.json({ data: { items: rows.map(camelRow) } });
  });
  app.get("/api/items/:id", async c => {
    const { ws } = await readWorkspace(c);
    return c.json({ data: { item: await withWorkspace(ws, tx => huntItemDetail(tx, c.req.param("id"), 1)) } });
  });
  app.get("/api/stream", async c => {
    const { ws } = await readWorkspace(c);
    const last = c.req.header("last-event-id") || c.req.query("last_event_id") || null;
    return streamSSE(c, async s => {
      let sent = last || "";
      const queue: StreamMsg[] = [];
      let wake: (() => void) | null = null;
      const off = subscribe(ws, m => { queue.push(m); wake?.(); });
      s.onAbort(() => { off(); wake?.(); });
      const send = async (m: StreamMsg) => { if (m.id <= sent) return; sent = m.id; await s.writeSSE({ id: m.id, event: m.type, data: JSON.stringify(m.data) }); };
      await s.writeSSE({ event: "ready", data: JSON.stringify({ workspace: ws, replay_from: last }) });
      for (const m of await replay(ws, last)) await send(m);
      const hb = setInterval(() => { s.write(": hb\n\n").catch(() => {}); }, 25_000);
      try {
        while (!s.aborted) {
          while (queue.length) await send(queue.shift()!);
          let t: NodeJS.Timeout | undefined;
          await new Promise<void>(r => { wake = r; t = setTimeout(r, 30_000); });
          clearTimeout(t);
          wake = null;
        }
      } finally { clearInterval(hb); off(); }
    });
  });

  // ---------- REST (token required) ----------
  app.use("/rest/*", async (c, next) => {
    const tok = bearer(c);
    const k = tok ? await resolveKey(tok) : null;
    if (!k) throw new HttpError(401, tok ? "invalid, expired or revoked token" : "Authorization: Bearer <token> required");
    c.set("key", k);
    await next();
  });

  const ctx = (c: Context<Env>) => { const k = c.get("key"); return { k, ws: k.workspaceId, actor: actorOf(k) as Actor }; };
  const writeOne = (tx: Tx, name: string, ws: string, actor: Actor, body: any, upsert: boolean) =>
    name === "huntItems" ? upsertHuntItem(tx, ws, actor, body, upsert) : write(tx, resource(name), ws, actor, body, upsert);
  const respond = (c: Context, out: { status: number; body: unknown; replayed?: boolean }) => {
    if (out.replayed) c.header("Idempotent-Replayed", "true");
    return c.json(out.body as any, out.status as any);
  };

  // metadata (eagle hunt publish)
  app.get("/rest/metadata/huntTypes", async c => { const { k, ws } = ctx(c); need(k, "huntTypes", "read"); return c.json(await withWorkspace(ws, tx => list(tx, RESOURCES.huntTypes, c.req.query()))); });
  app.post("/rest/metadata/huntTypes", async c => {
    const { k, ws, actor } = ctx(c); need(k, "huntTypes", "write");
    const body = await c.req.json();
    return respond(c, await withWorkspace(ws, tx => idempotent(c, tx, async () => {
      const r = await write(tx, RESOURCES.huntTypes, ws, actor, body, true);
      return { status: r.status === "created" ? 201 : 200, body: { data: { createHuntType: camelRow(r.row) }, status: r.status } };
    })));
  });

  app.post("/rest/batch/:obj", async c => {
    const name = c.req.param("obj"); resource(name);
    const { k, ws, actor } = ctx(c); need(k, name, "write");
    const body = await c.req.json();
    if (!Array.isArray(body) || body.length > 200) throw new HttpError(400, "batch body is an array of at most 200 records");
    const upsert = c.req.query("upsert") === "true";
    const plural = resource(name).plural;
    return respond(c, await withWorkspace(ws, tx => idempotent(c, tx, async () => {
      const rows: any[] = [], counts = { created: 0, updated: 0, unchanged: 0 };
      for (const b of body) { const r = await writeOne(tx, name, ws, actor, b, upsert); counts[r.status]++; rows.push({ ...camelRow(r.row), _status: r.status }); }
      return { status: 201, body: { data: { ["create" + plural[0].toUpperCase() + plural.slice(1)]: rows }, counts } };
    })));
  });

  app.get("/rest/:obj", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws } = ctx(c); need(k, name, "read");
    if (name === "events" && c.req.query("starting_after") && !c.req.query("order_by")) {
      // replay: GET /rest/events?starting_after=<uuidv7> (the SSE cursor), oldest first
      const after = c.req.query("starting_after")!;
      const limit = Math.min(Number(c.req.query("limit")) || 200, 1000);
      const rows = await withWorkspace(ws, async tx => (await tx.query("select * from events where id > $1 order by id limit $2", [after, limit])).rows);
      return c.json({ data: { events: rows.map(camelRow) }, pageInfo: { hasNextPage: rows.length === limit, endCursor: rows.at(-1)?.id ?? null } });
    }
    return c.json(await withWorkspace(ws, tx => list(tx, r, c.req.query())));
  });
  app.get("/rest/:obj/groupBy", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws } = ctx(c); need(k, name, "read");
    return c.json(await withWorkspace(ws, tx => groupBy(tx, r, c.req.query("field"), c.req.query("filter"))));
  });
  app.get("/rest/roosts/:id/timeline", async c => {
    const { k, ws } = ctx(c); need(k, "roosts", "read");
    const rows = await withWorkspace(ws, async tx => (await tx.query("select * from roost_timeline where roost_id = $1 order by id", [c.req.param("id")])).rows);
    return c.json({ data: { timeline: rows.map(camelRow) } });
  });
  app.get("/rest/:obj/:id", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws } = ctx(c); need(k, name, "read");
    if (name === "huntItems") return c.json({ data: { huntItem: await withWorkspace(ws, tx => huntItemDetail(tx, c.req.param("id"), Number(c.req.query("depth") || 0))) } });
    return c.json({ data: { [r.singular]: camelRow(await withWorkspace(ws, tx => getOne(tx, r, c.req.param("id")))) } });
  });
  app.post("/rest/huntItems/:id/roost", async c => {
    const { k, ws, actor } = ctx(c); need(k, "huntItems", "write"); need(k, "roosts", "write");
    const body = await c.req.json().catch(() => ({}));
    const kind = body.kind || "client";
    return respond(c, await withWorkspace(ws, tx => idempotent(c, tx, async () => {
      const roostId = (await tx.query("select roost_item($1, $2, $3::jsonb) as id", [c.req.param("id"), kind, JSON.stringify(actor)])).rows[0].id;
      return { status: 200, body: { data: { roostHuntItem: { roostId, itemId: c.req.param("id"), kind } } } };
    })));
  });
  // outward-send facts (events.ts): one fact or an array of at most 200, each applied forward-only and idempotent by key
  app.post("/rest/events", async c => {
    const { k, ws, actor } = ctx(c); need(k, "events", "write");
    const body = await c.req.json();
    const facts = Array.isArray(body) ? body : [body];
    if (facts.length > 200) throw new HttpError(400, "at most 200 facts per call");
    const results = await withWorkspace(ws, async tx => { const out = []; for (const f of facts) out.push(await applyFact(tx, ws, actor, f)); return out; });
    return c.json({ data: { applyFacts: results } }, 200);
  });
  app.post("/rest/:obj", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws, actor } = ctx(c); need(k, name, "write");
    const body = await c.req.json();
    const upsert = c.req.query("upsert") === "true";
    return respond(c, await withWorkspace(ws, tx => idempotent(c, tx, async () => {
      const out = await writeOne(tx, name, ws, actor, body, upsert);
      return { status: out.status === "created" ? 201 : 200, body: { data: { ["create" + r.singular[0].toUpperCase() + r.singular.slice(1)]: camelRow(out.row) }, status: out.status } };
    })));
  });
  app.patch("/rest/:obj/:id/restore", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws, actor } = ctx(c); need(k, name, "write");
    return c.json({ data: { ["restore" + r.singular[0].toUpperCase() + r.singular.slice(1)]: camelRow(await withWorkspace(ws, tx => softDelete(tx, r, ws, actor, c.req.param("id"), true))) } });
  });
  app.patch("/rest/:obj/:id", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws, actor } = ctx(c); need(k, name, "write");
    if (name === "huntItems") {
      const body = await c.req.json();
      if ("stage" in body && body.stage === "roosted") throw new HttpError(400, "use POST /rest/huntItems/:id/roost");
    }
    const body = await c.req.json();
    return respond(c, await withWorkspace(ws, tx => idempotent(c, tx, async () => {
      if (name === "huntItems" && body.oneShotSystem) await assertOneShotSystem(tx, body.oneShotSystem);
      const out = await patch(tx, r, ws, actor, c.req.param("id"), body);
      return { status: 200, body: { data: { ["update" + r.singular[0].toUpperCase() + r.singular.slice(1)]: camelRow(out.row) }, status: out.status } };
    })));
  });
  app.delete("/rest/:obj/:id", async c => {
    const name = c.req.param("obj"), r = resource(name); const { k, ws, actor } = ctx(c); need(k, name, "write");
    const row = await withWorkspace(ws, tx => softDelete(tx, r, ws, actor, c.req.param("id")));
    return c.json({ data: { ["delete" + r.singular[0].toUpperCase() + r.singular.slice(1)]: { id: row.id } } });
  });

  return app;
}
