// ROOSTS view (Tyler card 11-21 ~8:50 PM): a row = someone who replied or booked. Each row leads with the next step + when,
// its owner (tyler or an agent name) and the last thing they said, sorted by due soonest. Real rows only: hunt items with a
// reply/booking that are not roosted yet, plus every roost (clients like Mohamed). The next step is the earliest open
// next_steps row; without one it is derived from the touch log (their message is newer than ours -> Reply within 5 min;
// we answered -> Follow up 3 days later; booked -> Call).
import { withWorkspace, type Tx } from "./db.ts";

const iso = (d: Date | string | null | undefined) => d ? new Date(d).toISOString().replace(/\.\d{3}Z$/, "Z") : null;
// Upwork notification mail carries no message text ("View your message and send a reply."): a time, never "what they said".
const NO_TEXT = /^\s*View your message and send a reply/i;
const STOP_OUTCOMES = ["negative", "unsubscribe", "bounce"];

export type NextStep = { what: string; due: string | null; owner: string; derived: boolean };
export type RoostRow = {
  id: string; kind: "item" | "roost"; name: string; company: string | null; type: string; origin: string | null;
  status: string; next: NextStep | null; last: { said: string | null; at: string | null; channel: string | null } | null;
  itemId: string | null; roostId: string | null;
};

export function short(s: string | null | undefined, n = 90) {
  if (!s) return null;
  const body = s.replace(/\r/g, "").split(/\n(?=On .{5,200}wrote:)/)[0].replace(/^\s*(hi|hey|hello|dear)\b(?:[ \t]+\w+)?[ \t]*(?:[,!]|(?=\n))[ \t]*/i, "");
  const line = (body.split(/\n\s*\n/).map(p => p.trim()).find(Boolean) || "").replace(/\s+/g, " ").trim();
  return line.length > n ? line.slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : line;
}

/** The next step when no open next_steps row exists, from the touch log. */
export function deriveNext(o: { replyStatus: string; lastIn: Date | null; lastOut: Date | null; owner: string }): NextStep | null {
  if (o.replyStatus === "booked") return { what: "Call", due: null, owner: "tyler", derived: true };
  if (o.lastIn && (!o.lastOut || o.lastIn > o.lastOut)) return { what: "Reply", due: iso(new Date(o.lastIn.getTime() + 5 * 60_000)), owner: o.owner, derived: true };
  if (o.lastOut && o.lastIn) return { what: "Follow up", due: iso(new Date(o.lastOut.getTime() + 3 * 86_400_000)), owner: o.owner, derived: true };
  return null;
}

export function sortRows(rows: RoostRow[]) {
  // due soonest first; a step with no date after dated ones; no step last; ties: most recent message first
  const rank = (r: RoostRow) => r.next ? (r.next.due ? 0 : 1) : 2;
  const due = (r: RoostRow) => r.next?.due ? Date.parse(r.next.due) : 0;
  const at = (r: RoostRow) => r.last?.at ? Date.parse(r.last.at) : 0;
  return rows.sort((a, b) => rank(a) - rank(b) || due(a) - due(b) || at(b) - at(a));
}

export async function roostRows(tx: Tx): Promise<RoostRow[]> {
  const steps = (await tx.query(`select distinct on (coalesce(item_id, roost_id)) coalesce(item_id, roost_id) as k, what, due_at, owner
      from next_steps where done_at is null order by coalesce(item_id, roost_id), due_at asc nulls last, created_at`)).rows;
  const stepOf = new Map(steps.map(s => [s.k, { what: s.what, due: iso(s.due_at), owner: s.owner, derived: false } as NextStep]));
  const lastSaid = async (col: "item_id" | "roost_id") => new Map((await tx.query(`select distinct on (${col}) ${col} as k, body, received_at, channel
      from replies where ${col} is not null and coalesce(outcome, '') <> 'bounce' and body !~* '^\\s*View your message and send a reply'
      order by ${col}, received_at desc`)).rows.map(r => [r.k, r]));
  const lastIn = async (col: "item_id" | "roost_id") => new Map((await tx.query(`select ${col} as k, max(received_at) as at, (array_agg(channel order by received_at desc))[1] as channel
      from replies where ${col} is not null and coalesce(outcome, '') <> 'bounce' group by ${col}`)).rows.map(r => [r.k, r]));
  const lastOut = async (col: "item_id" | "roost_id") => new Map((await tx.query(`select ${col} as k, max(sent_at) as at from touches
      where ${col} is not null and status = 'sent' group by ${col}`)).rows.map(r => [r.k, r.at as Date]));

  const out: RoostRow[] = [];
  const items = (await tx.query(`select i.id, i.target, i.hunt_type, i.reply_status, i.stage, i.backend_agent, p.full_name, c.name as company,
        (select outcome from replies r where r.item_id = i.id and r.outcome is not null order by received_at desc limit 1) as outcome
      from hunt_items i left join people p on p.id = i.person_id left join companies c on c.id = i.company_id
      where i.deleted_at is null and i.roost_id is null and i.reply_status in ('replied','booked','won')`)).rows
    .filter(i => !STOP_OUTCOMES.includes(i.outcome));
  const iSaid = await lastSaid("item_id"), iIn = await lastIn("item_id"), iOut = await lastOut("item_id");
  for (const i of items) {
    const said = iSaid.get(i.id), inn = iIn.get(i.id);
    out.push({ id: i.id, kind: "item", name: i.full_name || i.target, company: i.company || (i.full_name ? i.target : null), type: i.hunt_type, origin: i.hunt_type,
      status: i.reply_status, itemId: i.id, roostId: null,
      next: stepOf.get(i.id) ?? deriveNext({ replyStatus: i.reply_status, lastIn: inn?.at ?? null, lastOut: iOut.get(i.id) ?? null, owner: i.backend_agent || "eagle" }),
      last: { said: short(said?.body), at: iso(said?.received_at ?? inn?.at), channel: said?.channel ?? inn?.channel ?? null } });
  }
  const roosts = (await tx.query(`select r.id, r.kind, r.stage, r.origin, r.status, p.full_name, c.name as company
      from roosts r left join people p on p.id = r.person_id left join companies c on c.id = r.company_id where r.deleted_at is null`)).rows;
  const rSaid = await lastSaid("roost_id"), rIn = await lastIn("roost_id"), rOut = await lastOut("roost_id");
  for (const r of roosts) {
    const said = rSaid.get(r.id), inn = rIn.get(r.id);
    const owner = r.origin === "upwork" ? "upwork" : "tyler";
    out.push({ id: r.id, kind: "roost", name: r.full_name || r.company, company: r.full_name ? r.company : null, type: r.kind, origin: r.origin,
      status: String(r.stage || r.status).split(":")[0], itemId: null, roostId: r.id,
      next: stepOf.get(r.id) ?? deriveNext({ replyStatus: "replied", lastIn: inn?.at ?? null, lastOut: rOut.get(r.id) ?? null, owner }),
      last: said || inn ? { said: short(said?.body), at: iso(said?.received_at ?? inn?.at), channel: said?.channel ?? inn?.channel ?? null } : null });
  }
  return sortRows(out);
}

export async function buildRoosts(ws: string) {
  return withWorkspace(ws, async tx => ({ rows: await roostRows(tx), built: iso(new Date()) }));
}
