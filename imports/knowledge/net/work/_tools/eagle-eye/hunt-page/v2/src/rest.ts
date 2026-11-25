// REST in Twenty's shape (twenty-server engine/api/rest/core/controllers/rest-api-core.controller.ts):
//   GET /rest/:obj?filter=a[eq]:x,b[gte]:y&order_by=f[DescNullsLast]&limit=50&starting_after=<cursor>
//   GET /rest/:obj/:id   POST /rest/:obj[?upsert=true]   PATCH /rest/:obj/:id   DELETE /rest/:obj/:id (soft)
//   PATCH /rest/:obj/:id/restore   POST /rest/batch/:obj   GET /rest/:obj/groupBy?field=f
// Response envelopes copy Twenty: {data:{<plural>:[...]}, pageInfo:{hasNextPage,startCursor,endCursor}, totalCount}.
import { pool, HttpError, snake, camelRow, type Tx } from "./db.ts";
import type { Actor } from "./keys.ts";

type Natural = { conflict?: (b: Record<string, unknown>) => string | null; lookup?: (b: Record<string, unknown>) => string[] | null };
export type Resource = {
  table: string; singular: string; plural: string; noun: string; softDelete: boolean; readOnly?: boolean;
  natural?: Natural; defaultOrder?: { col: string; dir: "asc" | "desc" }[]; eventFor?: (verb: string, row: any, before?: any) => string;
};

export const RESOURCES: Record<string, Resource> = {
  people: { table: "people", singular: "person", plural: "people", noun: "person", softDelete: true,
    natural: { conflict: b => b.email ? "(workspace_id, lower(email)) where email is not null and deleted_at is null" : null,
               lookup: b => b.email ? null : ["full_name", ...(b.company_id ? ["company_id"] : [])] } },
  companies: { table: "companies", singular: "company", plural: "companies", noun: "company", softDelete: true,
    natural: { conflict: b => b.domain ? "(workspace_id, lower(domain)) where domain is not null and deleted_at is null" : null,
               lookup: b => b.domain ? null : ["name"] } },
  roosts: { table: "roosts", singular: "roost", plural: "roosts", noun: "roost", softDelete: true,
    natural: { conflict: b => b.person_id ? "(workspace_id, person_id) where person_id is not null and deleted_at is null" : null } },
  oneShots: { table: "one_shots", singular: "oneShot", plural: "oneShots", noun: "one_shot", softDelete: true,
    natural: { lookup: b => b.item_id && b.kind ? ["item_id", "kind"] : null },
    eventFor: (v, r, b) => (r.status === "ready" && b?.status !== "ready") ? "one_shot.ready" : `one_shot.${v}` },
  recordings: { table: "recordings", singular: "recording", plural: "recordings", noun: "recording", softDelete: true,
    eventFor: (v, r, b) => (r.is_final && !b?.is_final) ? "recording.final" : `recording.${v}` },
  touches: { table: "touches", singular: "touch", plural: "touches", noun: "touch", softDelete: false,
    natural: { conflict: b => b.provider_id ? "(workspace_id, channel, provider_id)" : null },
    eventFor: (v, r, b) => v === "created" ? (r.status === "queued" ? "touch.queued" : "touch.sent") : (r.status === "sent" && b?.status === "queued") ? "touch.sent" : (r.opened_at && !b?.opened_at) ? "touch.opened" : (r.watched_s && !b?.watched_s) ? "touch.watched" : `touch.${v}` },
  replies: { table: "replies", singular: "reply", plural: "replies", noun: "reply", softDelete: false,
    natural: { conflict: b => b.provider_id ? "(workspace_id, channel, provider_id)" : null },
    eventFor: v => v === "created" ? "reply.received" : `reply.${v}` },
  nextSteps: { table: "next_steps", singular: "nextStep", plural: "nextSteps", noun: "next_step", softDelete: false,
    natural: { conflict: b => b.source_key ? "(workspace_id, source_key)" : null },
    eventFor: (v, r, b) => (r.done_at && !b?.done_at) ? "next_step.done" : `next_step.${v}` },
  viewers: { table: "viewers", singular: "viewer", plural: "viewers", noun: "viewer", softDelete: true,
    natural: { conflict: () => "(slug)" } },
  oneShotSystems: { table: "one_shot_systems", singular: "oneShotSystem", plural: "oneShotSystems", noun: "one_shot_system", softDelete: true,
    natural: { conflict: () => "(workspace_id, key)" }, defaultOrder: [{ col: "sort", dir: "asc" }] },
  huntTypes: { table: "hunt_types", singular: "huntType", plural: "huntTypes", noun: "hunt_type", softDelete: true,
    natural: { conflict: () => "(workspace_id, key)" } },
  events: { table: "events", singular: "event", plural: "events", noun: "event", softDelete: false, readOnly: true },
  // huntItems reads go through this generic path; its writes go through hunts.ts (typed upsert + extension rows).
  huntItems: { table: "hunt_items", singular: "huntItem", plural: "huntItems", noun: "item", softDelete: true,
    defaultOrder: [{ col: "signal_at", dir: "desc" }, { col: "id", dir: "desc" }] },
};

// ---------- column metadata (read from the catalog at boot, so the API follows the migrations) ----------
type Col = { name: string; type: string; nullable: boolean };
const COLS: Record<string, Map<string, Col>> = {};
export async function loadColumns() {
  const r = await pool.query(`select table_name, column_name, data_type, is_nullable from information_schema.columns where table_schema = 'public'`);
  for (const row of r.rows) (COLS[row.table_name] ||= new Map()).set(row.column_name, { name: row.column_name, type: row.data_type, nullable: row.is_nullable === "YES" });
}
export const cols = (t: string) => { const m = COLS[t]; if (!m) throw new Error(`columns not loaded for ${t}`); return m; };
const SERVER_OWNED = new Set(["id", "workspace_id", "created_at", "updated_at", "deleted_at", "found_at", "created_by"]);
const q = (s: string) => '"' + s.replace(/"/g, '""') + '"';

/** camelCase body -> snake_case, only real writable columns, json/array values encoded for pg. */
export function writable(table: string, body: Record<string, unknown>) {
  const m = cols(table), out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(body || {})) {
    const c = m.get(snake(k));
    if (!c || SERVER_OWNED.has(c.name)) continue;
    out[c.name] = c.type === "jsonb" && v !== null ? JSON.stringify(v) : v;
  }
  return out;
}

// ---------- filter / order / cursor ----------
const OPS: Record<string, string> = { eq: "=", neq: "<>", gt: ">", gte: ">=", lt: "<", lte: "<=", like: "like", ilike: "ilike" };
export function parseFilter(table: string, s: string | undefined, params: unknown[]) {
  const where: string[] = [], m = cols(table);
  let touchedDeleted = false;
  if (!s) return { where, touchedDeleted };
  const re = /([A-Za-z_][A-Za-z0-9_]*)\[([A-Za-z]+)\]:(\[[^\]]*\]|"(?:[^"\\]|\\.)*"|[^,]*)/g;
  let hit: RegExpExecArray | null, consumed = 0;
  while ((hit = re.exec(s))) {
    consumed += hit[0].length;
    const [, f, op, raw] = hit;
    const c = m.get(snake(f));
    if (!c) throw new HttpError(400, `unknown filter field ${f}`);
    if (c.name === "deleted_at") touchedDeleted = true;
    const unq = (v: string) => v.startsWith('"') ? JSON.parse(v) : v;
    if (op === "is") {
      const v = raw.toUpperCase();
      if (v !== "NULL" && v !== "NOT_NULL") throw new HttpError(400, "is takes NULL or NOT_NULL");
      where.push(`${q(c.name)} is ${v === "NULL" ? "null" : "not null"}`);
    } else if (op === "in") {
      const list = raw.replace(/^\[|\]$/g, "").split(",").map(x => unq(x.trim())).filter(x => x !== "");
      params.push(list);
      where.push(`${q(c.name)}::text = any($${params.length}::text[])`);
    } else if (op === "startsWith") {
      params.push(unq(raw) + "%");
      where.push(`${q(c.name)}::text like $${params.length}`);
    } else if (OPS[op]) {
      params.push(unq(raw));
      where.push(`${q(c.name)} ${OPS[op]} $${params.length}`);
    } else throw new HttpError(400, `unknown filter op ${op}`);
  }
  const commas = (s.match(/,/g) || []).length;
  if (consumed + commas < s.length - 1 && where.length === 0) throw new HttpError(400, `cannot parse filter ${s}`);
  return { where, touchedDeleted };
}

type Order = { col: string; dir: "asc" | "desc"; nulls: "first" | "last" };
export function parseOrder(r: Resource, s: string | undefined): Order[] {
  const m = cols(r.table);
  const base: Order[] = s
    ? s.split(",").map(part => {
        const hit = part.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)(?:\[(Asc|Desc)(NullsFirst|NullsLast)?\])?$/);
        if (!hit) throw new HttpError(400, `cannot parse order_by ${part}`);
        const c = m.get(snake(hit[1]));
        if (!c) throw new HttpError(400, `unknown order_by field ${hit[1]}`);
        const dir = (hit[2] || "Asc").toLowerCase() as "asc" | "desc";
        return { col: c.name, dir, nulls: (hit[3] === "NullsFirst" ? "first" : hit[3] === "NullsLast" ? "last" : dir === "desc" ? "first" : "last") as Order["nulls"] };
      })
    : (r.defaultOrder || [{ col: "id", dir: "desc" as const }]).map(o => ({ ...o, nulls: "last" as const }));
  if (!base.some(o => o.col === "id")) base.push({ col: "id", dir: base[0]?.dir || "desc", nulls: "last" });
  return base;
}

const enc = (o: unknown) => Buffer.from(JSON.stringify(o)).toString("base64url");
const dec = (s: string) => { try { return JSON.parse(Buffer.from(s, "base64url").toString()); } catch { throw new HttpError(400, "bad cursor"); } };

/** Keyset when every order column is NOT NULL and shares one direction (the common case); offset otherwise. */
function cursorClause(table: string, order: Order[], cursor: string | undefined, params: unknown[]) {
  const m = cols(table);
  const keyset = order.every(o => !m.get(o.col)!.nullable) && order.every(o => o.dir === order[0].dir);
  if (!cursor) return { keyset, clause: null as string | null, offset: 0 };
  const c = dec(cursor);
  if (keyset && Array.isArray(c.k)) {
    const ph = c.k.map((v: unknown) => { params.push(v); return `$${params.length}`; });
    return { keyset, clause: `(${order.map(o => q(o.col)).join(", ")}) ${order[0].dir === "desc" ? "<" : ">"} (${ph.join(", ")})`, offset: 0 };
  }
  return { keyset, clause: null, offset: Number(c.o) || 0 };
}

export async function list(tx: Tx, r: Resource, qs: Record<string, string | undefined>) {
  const params: unknown[] = [];
  const { where, touchedDeleted } = parseFilter(r.table, qs.filter, params);
  if (r.softDelete && !touchedDeleted) where.push("deleted_at is null");
  const order = parseOrder(r, qs.order_by);
  const limit = Math.min(Math.max(Number(qs.limit) || 60, 1), 200);
  const countSql = `select count(*)::int as n from ${q(r.table)}${where.length ? " where " + where.join(" and ") : ""}`;
  const total = (await tx.query(countSql, params.slice())).rows[0].n;
  const cur = cursorClause(r.table, order, qs.starting_after, params);
  const w = cur.clause ? [...where, cur.clause] : where;
  const sql = `select * from ${q(r.table)}${w.length ? " where " + w.join(" and ") : ""}
    order by ${order.map(o => `${q(o.col)} ${o.dir} nulls ${o.nulls}`).join(", ")} limit ${limit + 1} offset ${cur.offset}`;
  const rows = (await tx.query(sql, params)).rows;
  const more = rows.length > limit;
  const page = rows.slice(0, limit);
  const cursorOf = (row: any, i: number) => cur.keyset ? enc({ k: order.map(o => row[o.col]) }) : enc({ o: cur.offset + i + 1 });
  return {
    data: { [r.plural]: page.map(camelRow) },
    pageInfo: { hasNextPage: more, startCursor: page.length ? cursorOf(page[0], 0) : null, endCursor: page.length ? cursorOf(page[page.length - 1], page.length - 1) : null },
    totalCount: total,
  };
}

export async function getOne(tx: Tx, r: Resource, id: string) {
  const row = (await tx.query(`select * from ${q(r.table)} where id = $1`, [id])).rows[0];
  if (!row) throw new HttpError(404, `${r.singular} ${id} not found`);
  return row;
}

export async function groupBy(tx: Tx, r: Resource, field: string | undefined, filter?: string) {
  const c = field && cols(r.table).get(snake(field));
  if (!c) throw new HttpError(400, "groupBy needs ?field=<column>");
  const params: unknown[] = [];
  const { where, touchedDeleted } = parseFilter(r.table, filter, params);
  if (r.softDelete && !touchedDeleted) where.push("deleted_at is null");
  const rows = (await tx.query(`select ${q(c.name)} as value, count(*)::int as count from ${q(r.table)}${where.length ? " where " + where.join(" and ") : ""} group by 1 order by 2 desc`, params)).rows;
  return { data: { groupBy: rows.map(x => ({ [field!]: x.value, count: x.count })) } };
}

// ---------- events: every write inserts its event in the same transaction ----------
export async function emit(tx: Tx, e: { workspaceId: string; type: string; actor: Actor; itemId?: string | null; roostId?: string | null; data?: unknown }) {
  await tx.query(`insert into events (workspace_id, item_id, roost_id, type, actor, data) values ($1, $2, $3, $4, $5, $6)`,
    [e.workspaceId, e.itemId ?? null, e.roostId ?? null, e.type, JSON.stringify(e.actor), JSON.stringify(e.data ?? {})]);
}
function eventRefs(r: Resource, row: any) {
  return { itemId: r.table === "hunt_items" ? row.id : row.item_id ?? null, roostId: r.table === "roosts" ? row.id : row.roost_id ?? null };
}
const brief = (row: any) => Object.fromEntries(Object.entries(row).filter(([k, v]) => !["workspace_id", "created_at", "updated_at"].includes(k) && (typeof v !== "string" || v.length < 280)));

/** Create, or with upsert=true create-or-update on the resource's natural key. Returns {row, status}. */
export async function write(tx: Tx, r: Resource, ws: string, actor: Actor, body: Record<string, unknown>, upsert: boolean) {
  if (r.readOnly) throw new HttpError(405, `${r.plural} is read-only`);
  const v = writable(r.table, body);
  const keys = Object.keys(v);
  const insertCols = ["workspace_id", ...keys];
  const params: unknown[] = [ws, ...keys.map(k => v[k])];
  const ph = insertCols.map((_, i) => `$${i + 1}`);
  const conflict = upsert ? r.natural?.conflict?.(v) : null;
  const lookup = upsert && !conflict ? r.natural?.lookup?.(v) : null;

  if (lookup) {
    const lp = lookup.map(c => v[c]);
    const found = (await tx.query(`select * from ${q(r.table)} where ${lookup.map((c, i) => `${q(c)} = $${i + 1}`).join(" and ")}${r.softDelete ? " and deleted_at is null" : ""} limit 1 for update`, lp)).rows[0];
    if (found) return patch(tx, r, ws, actor, found.id, body, found);
  }
  let sql = `insert into ${q(r.table)} (${insertCols.map(q).join(", ")}) values (${ph.join(", ")})`;
  if (conflict) {
    const upd = keys;
    sql += upd.length
      ? ` on conflict ${conflict} do update set ${upd.map(k => `${q(k)} = excluded.${q(k)}`).join(", ")}
          where (${upd.map(k => `${q(r.table)}.${q(k)}`).join(", ")}) is distinct from (${upd.map(k => `excluded.${q(k)}`).join(", ")})`
      : ` on conflict ${conflict} do nothing`;
  }
  sql += " returning *, (xmax = 0) as _inserted";
  const res = (await tx.query(sql, params)).rows[0];
  if (!res) {
    // natural key matched and nothing changed: idempotent no-op, no event
    const nk = conflict!.replace(/\s+where\s.*$/s, "").trim().slice(1, -1).split(",").map(s => s.trim()).filter(s => s !== "workspace_id");
    const p2: unknown[] = [];
    const w = nk.map(expr => { const col = expr.replace(/^lower\((.*)\)$/, "$1"); p2.push(v[col]); return `${expr} = ${expr.startsWith("lower(") ? `lower($${p2.length})` : `$${p2.length}`}`; });
    const row = (await tx.query(`select * from ${q(r.table)} where ${w.join(" and ")} limit 1`, p2)).rows[0];
    return { row, status: "unchanged" as const };
  }
  const inserted = res._inserted; delete res._inserted;
  const verb = inserted ? "created" : "updated";
  await emit(tx, { workspaceId: ws, actor, type: r.eventFor?.(verb, res) || `${r.noun}.${verb}`, ...eventRefs(r, res), data: brief(res) });
  return { row: res, status: verb as "created" | "updated" };
}

export async function patch(tx: Tx, r: Resource, ws: string, actor: Actor, id: string, body: Record<string, unknown>, before?: any) {
  if (r.readOnly) throw new HttpError(405, `${r.plural} is read-only`);
  const v = writable(r.table, body);
  const keys = Object.keys(v);
  before ||= (await tx.query(`select * from ${q(r.table)} where id = $1 for update`, [id])).rows[0];
  if (!before) throw new HttpError(404, `${r.singular} ${id} not found`);
  if (!keys.length) return { row: before, status: "unchanged" as const };
  const params: unknown[] = [id, ...keys.map(k => v[k])];
  const res = (await tx.query(`update ${q(r.table)} set ${keys.map((k, i) => `${q(k)} = $${i + 2}`).join(", ")}
     where id = $1 and (${keys.map(k => q(k)).join(", ")}) is distinct from (${keys.map((_, i) => `$${i + 2}`).join(", ")}) returning *`, params)).rows[0];
  if (!res) return { row: before, status: "unchanged" as const };
  const changed = keys.filter(k => JSON.stringify(before[k]) !== JSON.stringify(res[k]));
  await emit(tx, { workspaceId: ws, actor, type: r.eventFor?.("updated", res, before) || `${r.noun}.updated`, ...eventRefs(r, res),
    data: Object.fromEntries(changed.map(k => [k, { from: before[k], to: res[k] }])) });
  return { row: res, status: "updated" as const };
}

export async function softDelete(tx: Tx, r: Resource, ws: string, actor: Actor, id: string, restore = false) {
  if (!r.softDelete) throw new HttpError(405, `${r.plural} cannot be deleted`);
  const res = (await tx.query(`update ${q(r.table)} set deleted_at = ${restore ? "null" : "now()"} where id = $1 returning *`, [id])).rows[0];
  if (!res) throw new HttpError(404, `${r.singular} ${id} not found`);
  await emit(tx, { workspaceId: ws, actor, type: `${r.noun}.${restore ? "restored" : "deleted"}`, ...eventRefs(r, res) });
  return res;
}
