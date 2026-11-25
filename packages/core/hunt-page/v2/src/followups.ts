// Follow-ups (Tyler card 11-21 ~8:50 PM): 3 per prospect with no reply, days 3, 7 and 14 after the first send, each one
// adding something NEW, never "just bumping". Structure copied from lemlist's "added value" sequence
// (https://www.lemlist.com/blog/cold-email-follow-up: "Email 1: ...helped a competitor solve the same issue. Email 2: Include
// a quick video explaining how you'd deal with it. ... Email 4: Send a case study of how you solved it for a similar
// company.") with lemlist's rule "Add new value with each email" (https://www.lemlist.com/blog/how-many-cold-email-follow-ups)
// and the last step framed as the break-up (https://www.lemlist.com/blog/cold-email-sequence step 14).
//
// Here: pg-boss schedules them. `followup-scan` (every 5 min) finds each prospect's first sent email (the head of its thread),
// writes the three touches (step fu_1|fu_2|fu_3, status queued, due_at) and one `followup-send` job per touch with
// startAfter = due_at. The job re-checks the stop rule, then runs send/followups.py, which has the backend agent write the
// follow-up through the copy gate in Tyler's voice and sends it in-thread from tyler@ (dryrun workspace: agent@ only).
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import type { PgBoss } from "pg-boss";
import { asOwner, type Tx } from "./db.ts";

export const FOLLOWUPS = [
  { step: "fu_1", day: 3, adds: "fix" },     // another fix found on their product (lemlist email 1: the pain point you noticed)
  { step: "fu_2", day: 7, adds: "clip" },    // a new demo clip (lemlist email 2: "a quick video explaining how you'd deal with it")
  { step: "fu_3", day: 14, adds: "result" }, // a result for a similar company (lemlist email 4: the case study), framed as the last note
] as const;
export type FollowupStep = typeof FOLLOWUPS[number]["step"];

const DAY = 86_400_000;
const LIVE_REPLY = ["none", "opened", "watched"];   // reply_status values that still allow a follow-up

/** The three touches for a head email sent at `sentAt`. A step already overdue at `now` is cancelled when a LATER step is
 *  also overdue (a backfill never fires two follow-ups at once); the latest overdue one runs now. */
export function planFollowups(sentAt: Date, now: Date) {
  const plan = FOLLOWUPS.map(f => ({ ...f, dueAt: new Date(sentAt.getTime() + f.day * DAY), status: "queued" as "queued" | "cancelled", reason: null as string | null }));
  const overdue = plan.filter(p => p.dueAt <= now);
  for (const p of overdue.slice(0, -1)) { p.status = "cancelled"; p.reason = "overdue when scheduled; a later follow-up was also due"; }
  return plan;
}

/** Why a follow-up must not go (null = go). Any reply (incl. unsubscribe), a bounce, or a later stage stops it. */
export async function stopReason(tx: Tx, touchId: string): Promise<string | null> {
  const r = (await tx.query(`
    select t.status, t.item_id, i.reply_status, i.hunt_type, i.stage, i.deleted_at,
           (select count(*) from replies p where p.item_id = t.item_id)::int as replies,
           (select string_agg(distinct p.outcome, ',') from replies p where p.item_id = t.item_id) as outcomes,
           (select count(*) from touches x where x.item_id = t.item_id and x.channel = 'email' and x.status = 'failed')::int as failed
    from touches t join hunt_items i on i.id = t.item_id where t.id = $1`, [touchId])).rows[0];
  if (!r) return "touch not found";
  if (r.status !== "queued") return `touch is ${r.status}`;
  if (r.deleted_at) return "item deleted";
  if (r.hunt_type === "investor") return "investor sends are held (Tyler 11-21)";
  if (r.failed) return "bounce";
  if (r.replies) return `reply received (${r.outcomes || "unclassified"})`;
  if (!LIVE_REPLY.includes(r.reply_status)) return `reply status ${r.reply_status}`;
  if (["roosted", "passed"].includes(r.stage)) return `stage ${r.stage}`;
  return null;
}

/** Heads with no follow-ups yet -> three touches each. Returns how many prospects were planned. */
export async function planAll(tx: Tx, now = new Date()) {
  const heads = (await tx.query(`
    select distinct on (t.item_id) t.workspace_id, t.item_id, t.one_shot_id, t.sent_at, t.thread_id, t.id as head_id
    from touches t join hunt_items i on i.id = t.item_id
    where t.channel = 'email' and t.status = 'sent' and t.thread_id is not null and coalesce(t.step, '') not like 'fu\\_%'
      and i.deleted_at is null and i.hunt_type <> 'investor' and i.reply_status = any($1) and i.stage not in ('roosted','passed')
      and not exists (select 1 from touches f where f.item_id = t.item_id and f.step like 'fu\\_%')
      and not exists (select 1 from replies p where p.item_id = t.item_id)
    order by t.item_id, t.sent_at`, [LIVE_REPLY])).rows;
  for (const h of heads) {
    for (const p of planFollowups(new Date(h.sent_at), now)) {
      await tx.query(`insert into touches (workspace_id, item_id, one_shot_id, channel, status, step, sent_at, due_at, provider_id, thread_id, details)
        values ($1, $2, $3, 'email', $4, $5, now(), $6, $7, $8, $9) on conflict (workspace_id, channel, provider_id) do nothing`,
        [h.workspace_id, h.item_id, h.one_shot_id, p.status, p.step, p.dueAt, `fu:${h.item_id}:${p.step}`, h.thread_id,
         JSON.stringify({ runner: "boss", day: p.day, adds: p.adds, head: h.head_id, ...(p.reason ? { reason: p.reason } : {}) })]);
      await tx.query(`insert into events (workspace_id, item_id, type, actor, data) values ($1, $2, $3, $4, $5)`,
        [h.workspace_id, h.item_id, p.status === "queued" ? "touch.queued" : "touch.cancelled", JSON.stringify({ source: "SYSTEM", name: "followup-scan" }),
         JSON.stringify({ step: p.step, due_at: p.dueAt, adds: p.adds })]);
    }
  }
  return heads.length;
}

/** Queued fu touches with no job yet (details.job_id unset). */
export async function unscheduled(tx: Tx) {
  return (await tx.query(`select t.id, t.due_at, w.slug from touches t join workspaces w on w.id = t.workspace_id
    where t.status = 'queued' and t.step like 'fu\\_%' and not (t.details ? 'job_id') order by t.due_at`)).rows as { id: string; due_at: Date; slug: string }[];
}

const SENDER = fileURLToPath(new URL("../send/followups.py", import.meta.url));

/** Runs send/followups.py for one touch; resolves with its stdout, rejects on a non-zero exit. It runs in its own transient
 *  systemd unit (900M, like hunt-send.service): the model CLI it starts does not fit the server's 320M cgroup (the first live
 *  run was oom-killed together with the server, 2026-11-21 18:15). FOLLOWUP_SCOPE=0 (tests, no systemd) runs it directly. */
export function runSender(ws: string, touchId: string, bin = process.env.FOLLOWUP_SENDER || SENDER): Promise<string> {
  const argv = ["python3", bin, "send", "--ws", ws, "--touch", touchId];
  const [cmd, ...args] = process.env.FOLLOWUP_SCOPE === "0" ? argv
    : ["systemd-run", "--user", "--wait", "--pipe", "--collect", "--quiet", "-p", "MemoryMax=900M", `--unit=followup-${touchId.slice(-12)}-${Date.now() % 1e6}`, ...argv];
  return new Promise((res, rej) => {
    const p = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"], timeout: 15 * 60_000 });
    let out = "", err = "";
    p.stdout.on("data", d => out += d);
    p.stderr.on("data", d => err += d);
    p.on("close", code => code === 0 ? res(out) : rej(new Error(`followups.py exit ${code}: ${(err || out).slice(-400)}`)));
  });
}

type SendJob = { ws: string; touchId: string };
const RETRIES = 2;

export async function registerFollowups(boss: PgBoss) {
  await boss.createQueue("followup-scan");
  await boss.createQueue("followup-send", { policy: "exclusive", retryLimit: RETRIES, retryDelay: 600 } as any);
  await boss.schedule("followup-scan", "*/5 * * * *");
  await boss.work("followup-scan", async () => {
    const planned = await asOwner(tx => planAll(tx));
    const todo = await asOwner(tx => unscheduled(tx));
    for (const t of todo) {
      const id = await boss.send("followup-send", { ws: t.slug, touchId: t.id } satisfies SendJob, { startAfter: new Date(t.due_at), singletonKey: t.id });
      if (id) await asOwner(tx => tx.query(`update touches set details = details || jsonb_build_object('job_id', $2::text) where id = $1`, [t.id, id]));
    }
    if (planned || todo.length) console.log("followup-scan", JSON.stringify({ planned, scheduled: todo.length }));
  });
  await boss.work<SendJob>("followup-send", async jobs => {
    for (const j of jobs) {
      const { ws, touchId } = j.data;
      const why = await asOwner(tx => stopReason(tx, touchId));
      if (why) {
        await asOwner(tx => tx.query(`update touches set status = 'cancelled', details = details || jsonb_build_object('reason', $2::text)
          where id = $1 and status = 'queued'`, [touchId, why]));
        console.log("followup-send stop", touchId, why);
        continue;
      }
      try {
        console.log("followup-send", touchId, (await runSender(ws, touchId)).trim().split("\n").at(-1));
      } catch (e: any) {
        if ((j.retryCount ?? 0) >= RETRIES)
          await asOwner(tx => tx.query(`update touches set status = 'failed', details = details || jsonb_build_object('reason', $2::text)
            where id = $1 and status = 'queued'`, [touchId, String(e.message).slice(0, 400)]));
        throw e;
      }
    }
  });
}
