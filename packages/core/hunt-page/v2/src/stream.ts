// Realtime: INSERT events -> trigger pg_notify('eagle_events', {w, id}) -> ONE LISTEN connection here ->
// fan-out to the SSE clients of that workspace. NOTIFY carries only the cursor (8,000-byte cap); the row is read here.
// Reconnects send Last-Event-ID (= events.id, uuidv7, time-ordered) and get a replay of everything after it.
import pg from "pg";
import { PG_CONFIG, withWorkspace, camelRow } from "./db.ts";

export type StreamMsg = { id: string; type: string; data: unknown };
type Sub = (m: StreamMsg) => void;
const subs = new Map<string, Set<Sub>>();
let listener: pg.Client | null = null;
let stopping = false;

async function hydrate(ws: string, ids: string[]): Promise<StreamMsg[]> {
  return withWorkspace(ws, async tx => {
    const ev = (await tx.query("select * from events where id = any($1::uuid[]) order by id", [ids])).rows;
    const itemIds = [...new Set(ev.map(e => e.item_id).filter(Boolean))];
    const rows = itemIds.length ? (await tx.query("select * from feed_rows where id = any($1::uuid[])", [itemIds])).rows : [];
    const byId = new Map(rows.map(r => [r.id, camelRow(r)]));
    return ev.map(e => ({ id: e.id, type: e.type, data: { ...camelRow(e), item: e.item_id ? byId.get(e.item_id) ?? null : null } }));
  });
}

export async function replay(ws: string, after: string | null, limit = 500): Promise<StreamMsg[]> {
  if (!after) return [];
  const ids = await withWorkspace(ws, async tx => (await tx.query("select id from events where id > $1 order by id limit $2", [after, limit])).rows.map(r => r.id));
  return ids.length ? hydrate(ws, ids) : [];
}

// One drain loop per workspace: a burst of NOTIFYs (one transaction can write dozens of events) is hydrated in a single
// query and dispatched in id order. Hydrating each notification concurrently let a later id overtake an earlier one,
// and clients (which skip ids <= the last one sent) dropped the earlier event.
const pending = new Map<string, string[]>();
const draining = new Set<string>();
async function drain(w: string) {
  if (draining.has(w)) return;
  draining.add(w);
  try {
    for (let ids = pending.get(w) ?? []; ids.length; ids = pending.get(w) ?? []) {
      pending.set(w, []);
      const msgs = await hydrate(w, ids.sort());
      const set = subs.get(w);
      if (set) for (const m of msgs) for (const s of set) s(m);
    }
  } catch (e) { console.error("stream drain", e); }
  finally { draining.delete(w); }
}

export async function startListener() {
  stopping = false;
  const c = new pg.Client(PG_CONFIG);
  await c.connect();
  await c.query("listen eagle_events");
  c.on("notification", n => {
    try {
      const { w, id } = JSON.parse(n.payload || "{}");
      if (!subs.get(w)?.size) return;
      (pending.get(w) ?? pending.set(w, []).get(w)!).push(id);
      void drain(w);
    } catch (e) { console.error("stream notify", e); }
  });
  c.on("error", e => { console.error("listener error", e.message); });
  c.on("end", () => { listener = null; if (!stopping) setTimeout(() => startListener().catch(err => console.error("relisten", err.message)), 1000); });
  listener = c;
}

export async function stopListener() { stopping = true; await listener?.end().catch(() => {}); listener = null; }

export function subscribe(ws: string, fn: Sub) {
  let set = subs.get(ws);
  if (!set) subs.set(ws, (set = new Set()));
  set.add(fn);
  return () => { set!.delete(fn); };
}

export const subscriberCount = () => [...subs.values()].reduce((n, s) => n + s.size, 0);
