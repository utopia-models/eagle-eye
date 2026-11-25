// Hunt items: the typed write path. POST /rest/huntItems[?upsert=true] and POST /rest/batch/huntItems.
// Natural key (workspace_id, hunt_type, external_id): an agent re-finding the same job/raise upserts, never duplicates.
import { z } from "zod";
import { drizzle } from "drizzle-orm/node-postgres";
import { sql, getTableName } from "drizzle-orm";
import { huntItems, fundingSignals, jobPosts, upworkJobs, investorSignals } from "./schema.ts";
import { HttpError, camelRow, type Tx } from "./db.ts";
import { emit, write, RESOURCES } from "./rest.ts";
import type { Actor } from "./keys.ts";

const ts = z.string().refine(s => !Number.isNaN(Date.parse(s)), "must be an ISO timestamp");
const PersonIn = z.object({ fullName: z.string().min(1), email: z.string().email().optional(), title: z.string().optional(),
  linkedinUrl: z.string().optional(), handles: z.record(z.string(), z.unknown()).optional() });
const CompanyIn = z.object({ name: z.string().min(1), domain: z.string().optional(), linkedinUrl: z.string().optional() });

export const HuntItemIn = z.object({
  huntType: z.string().min(1),
  externalId: z.string().min(1).max(500),
  target: z.string().min(1),
  signal: z.string().min(1),
  signalAt: ts,
  foundAt: ts.optional(), // when the hunter first saw it; insert only, clamped to now; default = ingest time
  fit: z.number().int().min(0).max(100).nullish(),
  stage: z.enum(["new", "qualified", "one_shot", "sent", "replied", "passed"]).optional(),
  vslStage: z.enum(["none", "scripted", "recorded", "rendered", "sent", "watched"]).optional(),
  replyStatus: z.enum(["none", "opened", "watched", "replied", "booked", "won", "lost"]).optional(),
  subtype: z.string().max(40).nullish(),
  // the one-shot SYSTEM inside the channel (upwork-intro-vsl, upwork-entire-vsl, funding-walkthrough, ...): a key of
  // one_shot_systems. Omitted = keep what the card has; the database derives the lane's default once a one-shot exists.
  oneShotSystem: z.string().max(64).nullish(),
  backendAgent: z.string().optional(),
  frontendAgent: z.string().optional(),
  personId: z.string().uuid().optional(),
  companyId: z.string().uuid().optional(),
  person: PersonIn.optional(),
  company: CompanyIn.optional(),
  details: z.record(z.string(), z.unknown()).optional(),
  funding: z.object({ kind: z.enum(["launch", "form_d", "news"]), round: z.string().min(1), amountUsd: z.number().nullish(),
    announcedOn: z.string(), leadInvestor: z.string().nullish(), sourceUrl: z.string().min(1) }).optional(),
  jobPost: z.object({ title: z.string().min(1), board: z.string().min(1), postedAt: ts, location: z.string().nullish(),
    salaryRange: z.string().nullish(), sourceUrl: z.string().min(1) }).optional(),
  upwork: z.object({ title: z.string().min(1), budgetType: z.enum(["fixed", "hourly"]).nullish(), budgetMinUsd: z.number().nullish(),
    budgetMaxUsd: z.number().nullish(), clientCountry: z.string().nullish(), clientSpendUsd: z.number().nullish(),
    clientHireRate: z.number().nullish(), proposalsBand: z.string().nullish(), postedAt: ts, jobUrl: z.string().nullish() }).optional(),
  investor: z.object({ investor: z.string().min(1), firm: z.string().nullish(), investorKind: z.enum(["fund", "angel", "program"]),
    lane: z.enum(["cold", "warm", "program", "mena", "skip"]).optional(), verified: z.boolean().optional(),
    dealCompany: z.string().nullish(), dealRound: z.string().nullish(), dealAmount: z.string().nullish(), dealDate: z.string().nullish(),
    dealUrl: z.string().nullish(), similarity: z.number().int().min(0).max(100).nullish(), checkMin: z.number().nullish(),
    checkMax: z.number().nullish(), coldRoute: z.string().nullish(), thesisQuote: z.string().nullish(), xHandle: z.string().nullish(),
    portfolioUrl: z.string().nullish(), score: z.number().int().min(0).max(100).nullish(),
    scoreParts: z.record(z.string(), z.number()).optional(), sourceUrl: z.string().min(1) }).optional(),
});
export type HuntItemInput = z.infer<typeof HuntItemIn>;

const EXT = { funding: "funding", job_post: "jobPost", upwork: "upwork", investor: "investor" } as const;

/** Decode HTML entities ONCE at ingest: Upwork alert mail and RSS titles arrive escaped ("AI &amp; Business") and the UI
 *  escapes on render, so a stored entity shows literally. Repeats while "&amp;amp;" nests. */
export function decodeEntities(s: string): string {
  let prev = "", out = s;
  while (out !== prev && /&(amp|lt|gt|quot|#\d+|#x[0-9a-f]+);/i.test(out)) {
    prev = out;
    out = out.replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
  }
  return out;
}

export async function upsertHuntItem(tx: Tx, ws: string, actor: Actor, raw: unknown, upsert: boolean) {
  const p = HuntItemIn.safeParse(raw);
  if (!p.success) throw new HttpError(400, "invalid huntItem", { issues: p.error.issues });
  const b = p.data;
  b.target = decodeEntities(b.target); b.signal = decodeEntities(b.signal);
  if (b.upwork) b.upwork.title = decodeEntities(b.upwork.title);
  if (b.jobPost) b.jobPost.title = decodeEntities(b.jobPost.title);
  const db = drizzle(tx);

  const ht = (await tx.query("select id, key, extension_table from hunt_types where key = $1 and deleted_at is null", [b.huntType])).rows[0];
  if (!ht) throw new HttpError(400, `unknown huntType ${b.huntType} (POST /rest/metadata/huntTypes first)`);

  if (b.oneShotSystem) await assertOneShotSystem(tx, b.oneShotSystem);

  let companyId = b.companyId ?? null, personId = b.personId ?? null;
  if (!companyId && b.company) companyId = (await write(tx, RESOURCES.companies, ws, actor, b.company, true)).row.id;
  if (!personId && b.person) personId = (await write(tx, RESOURCES.people, ws, actor, { ...b.person, companyId: companyId ?? undefined }, true)).row.id;

  const values = {
    workspaceId: ws, huntTypeId: ht.id, huntType: b.huntType, externalId: b.externalId, personId, companyId,
    target: b.target, signal: b.signal, signalAt: new Date(b.signalAt).toISOString(), fit: b.fit ?? null,
    ...(b.foundAt ? { foundAt: new Date(Math.min(Date.parse(b.foundAt), Date.now())).toISOString() } : {}),
    stage: b.stage ?? "new", vslStage: b.vslStage ?? "none", replyStatus: b.replyStatus ?? "none",
    backendAgent: b.backendAgent ?? actor.name, frontendAgent: b.frontendAgent ?? null, details: b.details ?? {}, createdBy: actor,
    subtype: b.subtype ?? null,
    oneShotSystem: b.oneShotSystem ?? null,
  };
  const ins = db.insert(huntItems).values(values as any);
  const returning = { id: huntItems.id, inserted: sql<boolean>`(xmax = 0)` };
  // On a re-find: refresh what the source says; pipeline fields (stage, VSL, reply) only ever move FORWARD on an upsert,
  // so a hunter re-sending "ready to record" never undoes what Eagle recorded or sent. PATCH sets them freely.
  const fwd = (col: string, order: string[], named: boolean) => named
    ? sql.raw(`case when array_position(array[${order.map(o => `'${o}'`).join(",")}]::text[], excluded.${col}) > array_position(array[${order.map(o => `'${o}'`).join(",")}]::text[], hunt_items.${col}) then excluded.${col} else hunt_items.${col} end`)
    : sql.raw(`hunt_items.${col}`);
  const E = {
    target: sql`excluded.target`, signal: sql`excluded.signal`, signalAt: sql`excluded.signal_at`,
    fit: sql`coalesce(excluded.fit, hunt_items.fit)`,
    personId: sql`coalesce(excluded.person_id, hunt_items.person_id)`, companyId: sql`coalesce(excluded.company_id, hunt_items.company_id)`,
    details: sql`hunt_items.details || excluded.details`,
    stage: fwd("stage", ["new", "qualified", "one_shot", "sent", "replied"], !!b.stage),
    vslStage: fwd("vsl_stage", ["none", "scripted", "recorded", "rendered", "sent", "watched"], !!b.vslStage),
    replyStatus: fwd("reply_status", ["none", "opened", "watched", "replied", "booked", "won"], !!b.replyStatus),
    frontendAgent: b.frontendAgent ? sql`excluded.frontend_agent` : sql`hunt_items.frontend_agent`,
    subtype: sql`coalesce(excluded.subtype, hunt_items.subtype)`,
    oneShotSystem: sql`coalesce(excluded.one_shot_system, hunt_items.one_shot_system)`,
  };
  const set = E;
  const changedWhere = sql`(hunt_items.target, hunt_items.signal, hunt_items.signal_at, hunt_items.fit, hunt_items.person_id, hunt_items.company_id, hunt_items.details, hunt_items.stage, hunt_items.vsl_stage, hunt_items.reply_status, hunt_items.frontend_agent, hunt_items.subtype, hunt_items.one_shot_system)
    is distinct from (${E.target}, ${E.signal}, ${E.signalAt}, ${E.fit}, ${E.personId}, ${E.companyId}, ${E.details}, ${E.stage}, ${E.vslStage}, ${E.replyStatus}, ${E.frontendAgent}, ${E.subtype}, ${E.oneShotSystem})`;

  let id: string, status: "created" | "updated" | "unchanged";
  let before: any = null;
  if (upsert) {
    before = (await tx.query("select * from hunt_items where hunt_type = $1 and external_id = $2", [b.huntType, b.externalId])).rows[0] ?? null;
    const r = await ins.onConflictDoUpdate({ target: [huntItems.workspaceId, huntItems.huntType, huntItems.externalId], set: set as any, setWhere: changedWhere }).returning(returning);
    if (r[0]) { id = r[0].id; status = r[0].inserted ? "created" : "updated"; }
    else { id = before.id; status = "unchanged"; }
  } else {
    try {
      const r = await ins.returning(returning);
      id = r[0].id; status = "created";
    } catch (e: any) {
      if ((e.cause?.code ?? e.code) === "23505") throw new HttpError(409, `huntItem ${b.huntType}/${b.externalId} exists (use ?upsert=true)`);
      throw e;
    }
  }

  // extension row for first-party types (class-table inheritance, 1:1 on item_id)
  const extKey = EXT[b.huntType as keyof typeof EXT];
  const ext = extKey ? (b as any)[extKey] : undefined;
  let extChanged = false;
  if (ext) {
    const table = b.huntType === "funding" ? fundingSignals : b.huntType === "job_post" ? jobPosts : b.huntType === "investor" ? investorSignals : upworkJobs;
    const row: any = { itemId: id, workspaceId: ws, ...ext };
    for (const k of ["postedAt"]) if (row[k]) row[k] = new Date(row[k]).toISOString();
    for (const k of ["budgetMinUsd", "budgetMaxUsd", "clientSpendUsd", "clientHireRate"]) if (row[k] != null) row[k] = String(row[k]);
    if (row.amountUsd != null) row.amountUsd = Math.round(row.amountUsd);
    for (const k of ["checkMin", "checkMax"]) if (row[k] != null) row[k] = Math.round(row[k]);
    const cols = Object.keys(ext).map(k => (table as any)[k]).filter(Boolean);
    const setExt = Object.fromEntries(Object.keys(ext).filter(k => (table as any)[k]).map(k => [k, sql.raw(`excluded."${(table as any)[k].name}"`)]));
    const distinct = sql.raw(`(${cols.map((c: any) => `${getTableName(table)}."${c.name}"`).join(", ")}) is distinct from (${cols.map((c: any) => `excluded."${c.name}"`).join(", ")})`);
    const r = await db.insert(table).values(row).onConflictDoUpdate({ target: (table as any).itemId, set: setExt, setWhere: distinct }).returning({ itemId: (table as any).itemId });
    extChanged = r.length > 0;
  }
  if (status === "unchanged" && extChanged) status = "updated";

  const after = (await tx.query("select * from hunt_items where id = $1", [id])).rows[0];
  if (status === "created") {
    await emit(tx, { workspaceId: ws, actor, itemId: id, type: "item.found",
      data: { hunt_type: b.huntType, target: after.target, signal: after.signal, signal_at: after.signal_at, found_at: after.found_at } });
  } else if (status === "updated") {
    const keys = ["target", "signal", "signal_at", "fit", "stage", "vsl_stage", "reply_status", "person_id", "company_id", "one_shot_system"];
    const diff = before ? Object.fromEntries(keys.filter(k => JSON.stringify(before[k]) !== JSON.stringify(after[k])).map(k => [k, { from: before[k], to: after[k] }])) : {};
    const type = diff.stage && after.stage === "qualified" ? "item.qualified" : "item.updated";
    await emit(tx, { workspaceId: ws, actor, itemId: id, type, data: { ...diff, ...(extChanged ? { extension: extKey } : {}) } });
  }
  return { row: after, status };
}

/** A one-shot system key the workspace's catalog holds (one_shot_systems), else a 400 that lists the known ones. */
export async function assertOneShotSystem(tx: Tx, key: string) {
  const all = (await tx.query("select key from one_shot_systems where deleted_at is null order by sort, key")).rows.map(r => r.key as string);
  if (!all.includes(key)) throw new HttpError(400, `unknown oneShotSystem ${key} (POST /rest/oneShotSystems first)`, { known: all });
}

/** GET /rest/huntItems/:id?depth=1 -> item + extension row + one-shots (+ recordings) + touches + replies + events + speed. */
export async function huntItemDetail(tx: Tx, id: string, depth: number) {
  const item = (await tx.query("select * from hunt_items where id = $1", [id])).rows[0];
  if (!item) throw new HttpError(404, `huntItem ${id} not found`);
  const out: any = camelRow(item);
  const speed = (await tx.query(`select min(sent_at) as first_sent_at,
      round(extract(epoch from (min(sent_at) - $2::timestamptz)) / 60.0, 1) as speed_to_lead_minutes,
      round(extract(epoch from ($3::timestamptz - $2::timestamptz)) / 60.0, 1) as find_lag_minutes
    from touches where item_id = $1 and status = 'sent'`, [id, item.signal_at, item.found_at])).rows[0];
  Object.assign(out, camelRow(speed));
  if (depth < 1) return out;
  const ext = (await tx.query("select extension_table from hunt_types where id = $1", [item.hunt_type_id])).rows[0]?.extension_table;
  if (ext) out.extension = camelRow((await tx.query(`select * from ${ext} where item_id = $1`, [id])).rows[0] || {});
  const many = async (s: string) => (await tx.query(s, [id])).rows.map(camelRow);
  out.person = item.person_id ? camelRow((await tx.query("select * from people where id = $1", [item.person_id])).rows[0] || {}) : null;
  out.company = item.company_id ? camelRow((await tx.query("select * from companies where id = $1", [item.company_id])).rows[0] || {}) : null;
  out.oneShots = await many(`select o.*, coalesce((select json_agg(r order by r.recorded_at) from recordings r where r.one_shot_id = o.id and r.deleted_at is null), '[]') as recordings
                             from one_shots o where o.item_id = $1 and o.deleted_at is null order by o.id`);
  out.touches = await many("select * from touches where item_id = $1 order by sent_at");
  out.replies = await many("select * from replies where item_id = $1 order by received_at");
  out.events = await many("select * from events where item_id = $1 order by id");
  return out;
}
