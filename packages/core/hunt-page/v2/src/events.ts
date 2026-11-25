// POST /rest/events: the one ingest for outward-send FACTS (push at the source; Tyler 11-22 ~2 AM MT: "We don't want to
// have to rely on Agent Upwork to be able to update the backend for Eagle Eye. This should be automatic.").
//
// The tools that write a fact (ledger.append / store_home.ledger_append in the knowledge repo, the desk-upwork URL
// observer, takeflow's render, hunt_send) call this as a side effect of writing it. One transaction: resolve the item
// from whatever reference the fact carries, move stage / vslStage / replyStatus FORWARD only, record the upwork touch,
// fold a title-only alert duplicate into the job's card, and write a `fact.applied` event holding the proof (the
// card's timeline). The fact's key is unique at the database (0008_facts.sql): a replay is a no-op, never a move back.
// A fact that matches no card creates one flagged details.auto_created (nothing is ever dropped) and says so.
import { z } from "zod";
import { HttpError, type Tx } from "./db.ts";
import { emit } from "./rest.ts";
import { upsertHuntItem, assertOneShotSystem } from "./hunts.ts";
import type { Actor } from "./keys.ts";

export const KINDS = ["proposal_sent", "video_attached", "vsl_recorded", "render_done", "email_sent", "reply_received", "watched", "one_shot_built", "one_shot_blocked"] as const;

const ts = z.string().refine(s => !Number.isNaN(Date.parse(s)), "must be an ISO timestamp");
export const FactIn = z.object({
  kind: z.enum(KINDS),
  key: z.string().min(3).max(300).optional(),           // the fact's own id; default derived from kind + proof
  at: ts,
  itemRef: z.object({
    itemId: z.string().uuid().optional(),
    huntType: z.string().optional(),
    job: z.string().optional(),                          // Upwork job key ~02...
    url: z.string().optional(),
    slug: z.string().optional(),
    messageId: z.string().optional(),
    proposalId: z.string().optional(),
    title: z.string().optional(),
  }).refine(r => Object.values(r).some(Boolean), "itemRef needs at least one reference"),
  proof: z.record(z.string(), z.unknown()).default({}),
  source: z.string().max(80).optional(),                 // which writer pushed it (ledger.py, desk-observer, takeflow, ...)
  // the one-shot system the take was made with (takeflow vsl-make --take intro|entire -> upwork-intro-vsl | upwork-entire-vsl):
  // the maker's word wins over the lane default the database derives; niche = the "entire VSL for a specific niche" one
  oneShotSystem: z.string().max(64).optional(),
  niche: z.string().max(80).optional(),
});
export type Fact = z.infer<typeof FactIn>;

const ORDER = {
  stage: ["new", "qualified", "one_shot", "sent", "replied"],
  vsl_stage: ["none", "scripted", "recorded", "rendered", "sent", "watched"],
  reply_status: ["none", "opened", "watched", "replied", "booked", "won"],
} as const;

/** What a fact moves. Only forward: a later state already on the card wins. */
export function effect(f: Pick<Fact, "kind" | "proof">): Partial<Record<keyof typeof ORDER, string>> {
  const video = ["E", "F"].includes(String(f.proof?.arm ?? "")) || !!f.proof?.video;
  switch (f.kind) {
    case "proposal_sent": return video ? { stage: "sent", vsl_stage: "sent" } : { stage: "sent" };
    case "video_attached": return { stage: "sent", vsl_stage: "sent" };
    case "vsl_recorded": return { vsl_stage: "recorded" };
    case "render_done": return { vsl_stage: "rendered" };
    case "email_sent": return { stage: "sent" };
    case "reply_received": return { stage: "replied", reply_status: "replied" };
    case "watched": return { vsl_stage: "watched", reply_status: "watched" };
    case "one_shot_built": case "one_shot_blocked": return {};   // no stage move: built stamps details.ready_at (applyFact), blocked is recorded only
  }
}

export const jobKey = (s?: string | null) => {
  const m = String(s || "").match(/~?(0[12]\d{10,})/);
  return m ? "~" + m[1] : null;
};
export function factKey(f: Fact) {
  if (f.key) return f.key;
  const p = f.proof as any;
  const id = p.proposal_id || p.message_id || p.ledger_row || p.gmail_id || p.render || f.itemRef.proposalId || f.itemRef.messageId;
  if (!id) throw new HttpError(400, "a fact needs a key, or a proof id (proposal_id | message_id | ledger_row | gmail_id | render)");
  return `${f.kind}:${id}`;
}

const live = "deleted_at is null";
async function one(tx: Tx, sql: string, args: unknown[]): Promise<string | null> {
  return (await tx.query(sql, args)).rows[0]?.id ?? null;
}

/** The card a fact is about, from the strongest reference it carries. -> {id, via} or null. */
export async function resolveItem(tx: Tx, r: Fact["itemRef"]): Promise<{ id: string; via: string } | null> {
  if (r.itemId) { const id = await one(tx, `select id from hunt_items where id = $1 and ${live}`, [r.itemId]); if (id) return { id, via: "itemId" }; }
  const job = jobKey(r.job) || jobKey(r.url);
  if (job) {
    const id = await one(tx, `select id from hunt_items where hunt_type = 'upwork' and external_id in ($1, $2) and ${live} order by created_at limit 1`, [job, job.slice(1)]);
    if (id) return { id, via: "job" };
  }
  if (r.proposalId) {
    const id = await one(tx, `select i.id from touches t join hunt_items i on i.id = t.item_id where t.channel = 'upwork' and t.provider_id = $1 and i.${live} limit 1`, [r.proposalId]);
    if (id) return { id, via: "proposalId" };
  }
  if (r.messageId) {
    const id = await one(tx, `select i.id from touches t join hunt_items i on i.id = t.item_id where (t.provider_id = $1 or t.thread_id = $1) and i.${live} limit 1`, [r.messageId]);
    if (id) return { id, via: "messageId" };
  }
  if (r.url) {
    const id = await one(tx, `select i.id from hunt_items i left join upwork_jobs u on u.item_id = i.id left join job_posts j on j.item_id = i.id
        left join funding_signals f on f.item_id = i.id
      where i.${live} and $1 in (i.details->>'link', i.details->>'url', u.job_url, j.source_url, f.source_url) limit 1`, [r.url]);
    if (id) return { id, via: "url" };
  }
  if (r.slug) {
    const id = await one(tx, `select coalesce(
        (select v.item_id from viewers v join hunt_items i on i.id = v.item_id where v.slug = $1 and i.${live} limit 1),
        (select i.id from hunt_items i where i.${live} and (i.details->>'slug' = $1 or i.details->>'tabs' like '%/' || $1 || '/%') limit 1)) as id`, [r.slug]);
    if (id) return { id, via: "slug" };
  }
  if (r.title) {
    const id = await one(tx, `select i.id from hunt_items i join upwork_jobs u on u.item_id = i.id
      where i.${live} and lower(u.title) = lower($1) order by (i.external_id like 'alert:%'), i.created_at limit 1`, [r.title]);
    if (id) return { id, via: "title" };
  }
  return null;
}

/** A title-only Upwork alert row (external_id alert:<hash>) is the same job as the card with its job key: fold it in. */
export async function mergeAlertTwins(tx: Tx, ws: string, actor: Actor, itemId: string) {
  const it = (await tx.query(`select i.external_id, u.title from hunt_items i join upwork_jobs u on u.item_id = i.id where i.id = $1 and i.hunt_type = 'upwork'`, [itemId])).rows[0];
  if (!it || it.external_id.startsWith("alert:")) return [];
  const twins = (await tx.query(`update hunt_items i set deleted_at = now(), details = i.details || jsonb_build_object('merged_into', $1::text)
      from upwork_jobs u where u.item_id = i.id and i.hunt_type = 'upwork' and i.external_id like 'alert:%' and i.deleted_at is null
        and lower(u.title) = lower($2) and i.id <> $1 returning i.id, i.external_id`, [itemId, it.title])).rows;
  for (const t of twins)
    await emit(tx, { workspaceId: ws, actor, itemId: t.id, type: "item.merged", data: { into: itemId, external_id: t.external_id, why: "title-only alert row of the same Upwork job" } });
  return twins.map(t => t.id as string);
}

export async function applyFact(tx: Tx, ws: string, actor: Actor, raw: unknown) {
  const p = FactIn.safeParse(raw);
  if (!p.success) throw new HttpError(400, "invalid fact", { issues: p.error.issues });
  const f = p.data;
  const key = factKey(f);

  const dup = (await tx.query(`select item_id from events where type = 'fact.applied' and data->>'key' = $1 limit 1`, [key])).rows[0];
  if (dup) return { status: "unchanged" as const, key, itemId: dup.item_id as string, changed: {}, via: "replay" };

  let hit = await resolveItem(tx, f.itemRef);
  let autoCreated = false;
  if (!hit) {
    // nothing matched: make the card so the fact is never lost, flagged for the drift audit and the Architect
    const job = jobKey(f.itemRef.job) || jobKey(f.itemRef.url);
    const huntType = f.itemRef.huntType || (job ? "upwork" : null);
    if (!huntType) throw new HttpError(422, "no card matches this fact and it names no huntType/job to create one from", { key, itemRef: f.itemRef });
    const title = f.itemRef.title || (f.proof as any).title || job || f.itemRef.slug || key;
    const ext = job || `auto:${key}`;
    const r = await upsertHuntItem(tx, ws, actor, {
      huntType, externalId: ext, target: title, signal: `auto-created from ${f.kind}`, signalAt: f.at,
      details: { auto_created: true, auto_created_from: key, ...(f.itemRef.url ? { link: f.itemRef.url } : {}) },
      ...(huntType === "upwork" ? { upwork: { title, postedAt: f.at, jobUrl: f.itemRef.url ?? (job ? `https://www.upwork.com/jobs/${job}` : null) } } : {}),
    }, true);
    hit = { id: r.row.id, via: "auto_created" };
    autoCreated = true;
  }

  const before = (await tx.query(`select stage, vsl_stage, reply_status, one_shot_system, details->>'one_shot_niche' as niche from hunt_items where id = $1 for update`, [hit.id])).rows[0];
  const want = effect(f);
  const sets: string[] = [], args: unknown[] = [hit.id];
  if (f.oneShotSystem && f.oneShotSystem !== before.one_shot_system) {
    await assertOneShotSystem(tx, f.oneShotSystem);
    args.push(f.oneShotSystem); sets.push(`one_shot_system = $${args.length}`);
  }
  if (f.niche && f.niche !== before.niche) { args.push(f.niche); sets.push(`details = details || jsonb_build_object('one_shot_niche', $${args.length}::text)`); }
  for (const [col, to] of Object.entries(want) as [keyof typeof ORDER, string][]) {
    const order = ORDER[col] as readonly string[];
    const cur = order.indexOf(before[col]);
    if (cur >= 0 && order.indexOf(to) > cur) { args.push(to); sets.push(`${col} = $${args.length}`); }
  }
  // knowledge#17557: the builder says a package is ready -> the timeline "One-shot built" step reads details.ready_at (earliest wins)
  if (f.kind === "one_shot_built")
    await tx.query(`update hunt_items set details = details || jsonb_build_object('ready_at', $2::text)
      where id = $1 and (details->>'ready_at' is null or details->>'ready_at' > $2)`, [hit.id, new Date(f.at).toISOString()]);
  const changed: Record<string, { from: string; to: string }> = {};
  if (sets.length) {
    const after = (await tx.query(`update hunt_items set ${sets.join(", ")} where id = $1
      returning stage, vsl_stage, reply_status, one_shot_system, details->>'one_shot_niche' as niche`, args)).rows[0];
    for (const k of [...Object.keys(ORDER), "one_shot_system", "niche"]) if (before[k] !== after[k]) changed[k] = { from: before[k], to: after[k] };
    await emit(tx, { workspaceId: ws, actor, itemId: hit.id, type: "item.updated", data: { ...changed, fact: key } });
  }

  // the Upwork proposal is a touch (the send record speed-to-lead, the sent queue and hunt_send's double-send check read)
  const pid = (f.proof as any).proposal_id || f.itemRef.proposalId;
  if (f.kind === "proposal_sent" && pid)
    await tx.query(`insert into touches (workspace_id, item_id, channel, status, sent_at, provider_id, details)
        values ($1, $2, 'upwork', 'sent', $3, $4, $5) on conflict (workspace_id, channel, provider_id) do nothing`,
      [ws, hit.id, f.at, String(pid), JSON.stringify({ fact: key, ...f.proof })]);

  const merged = await mergeAlertTwins(tx, ws, actor, hit.id);
  await emit(tx, { workspaceId: ws, actor, itemId: hit.id, type: "fact.applied",
    data: { key, kind: f.kind, at: f.at, via: hit.via, source: f.source ?? actor.name, proof: f.proof, changed, auto_created: autoCreated, merged } });
  return { status: autoCreated ? "auto_created" as const : Object.keys(changed).length ? "updated" as const : "unchanged" as const,
    key, itemId: hit.id, changed, via: hit.via, merged };
}
