// GET /api/feed: the exact JSON shape the spike UI's EE.build(d) reads from /people/tyler.json
// (eagle-eye-spike/public/opt/shared.js: d.hunts[{id, backend, frontend, checked, feed, queue, funnel}], d.enrich{jobs, upwork},
//  d.roosts[{id:'clients'|'network', rows, feed}], d.copy_at, d.built), rebuilt from Postgres, newest signal first.
// Plus `items`: the API-native feed rows (feed_rows view, incl. found_at + speed_to_lead_minutes) for the next UI.
import { withWorkspace, camelRow, type Tx } from "./db.ts";
import { packageFor, oneShotPage } from "./packages.ts";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";

// The sent VSL for the hunt page (knowledge#18540). An "automatic intro" is the renderer's own file (<tag>-intro[-vN].mp4, written by
// the vsl builder to /var/tmp/eagle-send with a -qa.json beside it): its mtime is when it finished rendering, qa.timings_s.mux the render
// seconds. The playable copy is Ra's public/hunts/up-*-<tag>/take.mp4 (generated media, never in git).
export const SEND_DIR = process.env.EAGLE_SEND_DIR || "/var/tmp/eagle-send";
const HUNTS_PUB = process.env.EAGLE_HUNTS_PUBLIC || "/home/architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/public/hunts";
const AUTO_INTRO = /^(\d{4})-intro(-v\d+)?\.mp4$/;
function takeUrl(tag: string | null): string | null {
  if (!tag) return null;
  try {
    const d = readdirSync(HUNTS_PUB).filter(n => n.startsWith("up-") && n.endsWith("-" + tag) && existsSync(join(HUNTS_PUB, n, "take.mp4"))).sort()[0];
    return d ? `/hunts/${d}/take.mp4` : null;
  } catch { return null; }
}
/** The VSL file the sender produced (SEND_DIR/<name>.mp4), served by GET /api/vsl/:file: the one data path, no second copy needed (knowledge#18576). */
const SEND_FILE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.mp4$/;
export function sendFileUrl(file: string | null, dir = SEND_DIR): string | null {
  const name = file ? basename(file) : "";
  return SEND_FILE.test(name) && existsSync(join(dir, name)) ? `/api/vsl/${name}` : null;
}
/** The cover letter that went out: the proposal_sent fact's letter_file (an Upwork drafts/final/<tag>.txt). Only files under the upwork drafts folder are ever read. */
const LETTER_DIR = process.env.EAGLE_LETTER_DIR || "/home/upwork/.claude/state/net/upwork/drafts/";
export function letterFor(proof: any, at: string | null, dir = LETTER_DIR) {
  const f = proof?.letter_file;
  if (typeof f !== "string" || !f.startsWith(dir) || f.includes("..")) return null;
  try { const text = readFileSync(f, "utf8").trim(); return text ? { text, file: basename(f), sent_at: at, proposal_id: proof.proposal_id ?? null } : null; } catch { return null; }
}
function introInfo(file: string | null) {
  const m = file && AUTO_INTRO.exec(file);
  if (!m) return null;
  try {
    const mp4 = join(SEND_DIR, file!), qa = JSON.parse(readFileSync(mp4.replace(/\.mp4$/, "-qa.json"), "utf8"));
    return { rendered_at: iso(statSync(mp4).mtime), render_s: qa.timings_s?.mux ?? null, length_s: qa.duration_s ?? null, intro_s: qa.intro_s ?? null,
      voice: qa.voice ?? null, sha: String(qa.sha256 ?? "").slice(0, 8) || null, size_mb: +(statSync(mp4).size / 1e6).toFixed(1) };
  } catch { return null; }
}
import { stuckFor } from "./stuck.ts";

// pipeline columns -> the spike's pill words
const VSL: Record<string, string | null> = { none: null, scripted: "record", recorded: "recorded", rendered: "recorded", sent: "sent", watched: "sent" };
const STATUS: Record<string, string> = { new: "Found", qualified: "Found", one_shot: "Staged", sent: "Sent", replied: "Replied" };
/** The Upwork job's tag (Tyler 11-23, via Eagle: "put it on ALL upwork jobs"): the last 4 digits of the Upwork job id (~02...9263),
 *  the way agents name a job ("job 9263"). Read from the item's external_id, else its job_url; null for a non-Upwork row and for an
 *  Upwork row whose source never carried a job id (a mail alert with no link). Set here for every Upwork row in every state; the UI
 *  only renders it, never derives it. */
export function jobTag(r: { hunt_type?: string | null; external_id?: string | null; job_url?: string | null }): string | null {
  if (r.hunt_type !== "upwork") return null;
  const id = [r.external_id, r.job_url].map(s => String(s ?? "").match(/~0\d{8,}/)?.[0]).find(Boolean);
  return id ? id.slice(-4) : null;
}
/** A hunt item back in live_refresh.py's post-row shape: the source's own fields (details) under the canonical columns. */
function postOut(r: any, title: string, link: string | null, co?: string) {
  // details.vsl / details.status are the hunter's copy from when it found the row ("record", "Ready to record"). Once the
  // card's own columns are past that (a fact moved vsl_stage to recorded/rendered/sent/watched, or stage to sent/replied),
  // the columns win: the pill shows what happened, never the stale copy.
  const vslPast = !["none", "scripted"].includes(r.vsl_stage), stagePast = ["sent", "replied"].includes(r.stage);
  return { ...(r.details || {}), post: r.details?.post === true, item_id: r.id, co: co ?? r.target, what: title ?? r.signal, link,
    ts: iso(r.signal_at), signal_at: iso(r.signal_at), found_at: iso(r.found_at), kind: r.details?.kind ?? "post",
    ...(vslPast ? { vsl: VSL[r.vsl_stage] } : {}),
    status: (vslPast || stagePast ? pipelineStatus(r) ?? STATUS[r.stage] : null) ?? r.details?.status ?? STATUS[r.stage] ?? "Found",
    vsl_stage: r.vsl_stage, agent: r.backend_agent, front: r.frontend_agent ?? "eagle", live: true, job_tag: jobTag(r) };
}
// Status is derived from what happened (touches + replies + VSL stage), never stored (cards 11-21: funding touch 1 offers the
// walkthrough with no link; a "yes" moves the row to Ready to record; the take goes out in-thread).
const PIPE = `(select t.status from touches t where t.item_id = i.id and t.step = 'offer' order by t.id desc limit 1) as offer_status,
  exists (select 1 from replies p where p.item_id = i.id and p.outcome in ('positive','booked','hired')) as pos_reply,
  exists (select 1 from replies p where p.item_id = i.id and p.outcome in ('negative','unsubscribe')) as neg_reply,
  (select count(*)::int from touches t where t.item_id = i.id and t.status = 'queued') as queued_touches,
  (select min(t.due_at) from touches t where t.item_id = i.id and t.status = 'queued') as next_due_at`;
export function pipelineStatus(r: { reply_status?: string; vsl_stage?: string; offer_status?: string | null; pos_reply?: boolean; neg_reply?: boolean }): string | null {
  if (r.reply_status === "won") return "Won";
  if (r.reply_status === "booked") return "Booked";
  if (r.neg_reply) return "Not interested";
  if (r.vsl_stage === "watched") return "Watched";
  if (r.vsl_stage === "sent") return "Sent";
  if (r.vsl_stage === "recorded" || r.vsl_stage === "rendered") return "Recorded";
  if (r.pos_reply) return "Ready to record";
  if (r.offer_status === "sent") return r.reply_status === "replied" ? "Replied" : "Offered";
  if (r.offer_status === "queued") return "Offer queued";
  return null;
}
const iso = (d: Date | string | null | undefined) => d ? new Date(d).toISOString().replace(/\.\d{3}Z$/, "Z") : null;
const money = (n: number | null) => n == null ? null : n === 0 ? "$0" : n >= 1e9 ? `$${+(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `$${+(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}K` : `$${n}`;

/** The row's one-shot for the UI (Tyler 11-22 ~5:00 AM MT: "One-shot system: Upwork Intro VSL", then "Niche: ...", then the demo;
 *  the hunt type stays its own field). system = the catalog name; label = "<system> · <niche>"; none = "No one-shot yet". The system is the item's column (one system
 *  per take type, not per job); the niche, build state and page come from the job's own package folder (packages.ts). */
type Oss = { key: string; label: string; hunt_type: string; take: string; template: string | null; status: string; description: string | null; is_default: boolean };
async function systems(tx: Tx) {
  const m = new Map<string, Oss>(), def = new Map<string, string>();
  for (const s of (await tx.query("select key, label, hunt_type, take, template, status, description, is_default from one_shot_systems where deleted_at is null")).rows) {
    m.set(s.key, s); if (s.is_default) def.set(s.hunt_type, s.key);
  }
  const hunts = new Map<string, string>((await tx.query("select key, label from hunt_types where deleted_at is null")).rows.map(h => [h.key, h.label]));
  return (r: { one_shot_system?: string | null; details?: any; external_id?: string }, huntType: string) => {
    const hunt = hunts.get(huntType) ?? huntType;
    const pkg = packageFor(r);
    // a package on disk is a one-shot even before a stage moved: it gets the lane's one system
    const key = r.one_shot_system ?? (pkg ? def.get(huntType) ?? null : null);
    const s = key ? m.get(key) : null;
    if (!s) return { key: null, hunt, system: null, niche: null, label: "No one-shot yet", take: null, state: null, url: null };
    const niche = r.details?.one_shot_niche ?? pkg?.niche ?? null;
    return { key: s.key, hunt, system: s.label, niche, label: [s.label, niche].filter(Boolean).join(" · "), take: s.take,
      template: s.template, status: s.status, about: s.description, state: pkg?.state ?? "Not built", url: pkg?.url ?? null,
      package: pkg?.slug ?? null, parts: pkg?.parts ?? null, page: oneShotPage(s.key) };
  };
}

/** Every hunt's TIMELINE (Tyler 11-22 ~5:08/5:10 AM MT: "It should show when the job was POSTED"; then One-shot built ->
 *  Recorded -> Text proposal sent -> VSL proposal sent). Only recorded facts, never an invented time:
 *    posted   = signal_at: the post's own time (upwork/job_post: equals the extension's posted_at; funding: the launch post /
 *               news story / Form D filing time). Investor rows have no posting: their primary time is found_at.
 *    built    = details.ready_at (the one-shot builder stamps it when the package is ready)
 *    recorded = the vsl_recorded fact's own time (events fact.applied data.at)
 *    text     = a proposal_sent / email_sent fact without video (a re-sighting of a video proposal's id is not a text one), or a
 *               sent 'offer' touch (funding offer-first)
 *    vsl      = video_attached, or proposal_sent on a video arm (E/F), else the first sent touch once the VSL stage is sent
 *  Step state: done (with its time) | done_no_time (the stage moved but no fact carries a time) | skipped | pending. */
async function timelines(tx: Tx) {
  const rows = (await tx.query(`with f as (
      select e.item_id, e.data->>'kind' as kind, (e.data->>'at')::timestamptz as at,
             (e.data->'proof'->>'arm' in ('E','F') or e.data->'proof' ? 'video') as video,
             e.data->'proof' as proof,
             coalesce(e.data->'proof'->>'proposal_id', substring(e.data->>'key' from '([0-9]{15,})')) as pid
      from events e where e.type = 'fact.applied' and e.item_id is not null)
    select i.id, i.hunt_type, i.external_id, i.signal_at, i.found_at, i.details->>'ready_at' as ready_at, i.stage, i.vsl_stage,
      (select min(at) from f where f.item_id = i.id and kind = 'vsl_recorded') as recorded_at,
      (select min(at) from f where f.item_id = i.id and kind = 'one_shot_built') as built_fact_at,
      (select proof from f where f.item_id = i.id and kind = 'video_attached' order by at limit 1) as video_proof,
      (select proof from f where f.item_id = i.id and kind = 'proposal_sent' and not video order by at limit 1) as text_proof,
      (select proof from f where f.item_id = i.id and kind = 'proposal_sent' and proof ? 'letter_file' order by at limit 1) as letter_proof,
      (select min(at) from f where f.item_id = i.id and kind = 'proposal_sent' and proof ? 'letter_file') as letter_at,
      (select min(at) from f where f.item_id = i.id and (kind = 'video_attached' or (kind = 'proposal_sent' and video))) as vsl_at,
      (select min(at) from f where f.item_id = i.id and kind in ('proposal_sent','email_sent') and not video
         and (pid is null or pid not in (select v.pid from f v where v.item_id = i.id and v.video and v.pid is not null))) as text_fact_at,
      (select min(t.sent_at) from touches t where t.item_id = i.id and t.status = 'sent' and t.step = 'offer') as offer_at,
      (select min(t.sent_at) from touches t where t.item_id = i.id and t.status = 'sent') as first_sent_at
    from hunt_items i where i.deleted_at is null`)).rows;
  const out: Record<string, any> = {};
  const past = (v: string, k: string[]) => k.indexOf(v) >= 0;
  for (const r of rows) {
    const posted = r.hunt_type === "investor" ? null : iso(r.signal_at);
    const vslSent = past(r.vsl_stage, ["sent", "watched"]);
    const vslAt = iso(r.vsl_at) ?? (vslSent ? iso(r.first_sent_at) : null);
    const textAt = iso(r.text_fact_at) ?? iso(r.offer_at) ?? (!vslSent && past(r.stage, ["sent", "replied"]) ? iso(r.first_sent_at) : null);
    const step = (at: string | null, reached: boolean, skipped = false) =>
      ({ at, state: at ? "done" : reached ? "done_no_time" : skipped ? "skipped" : "pending" });
    // Eagle 11-23 (fleetmail 18021): the steps read from the facts. Recorded = min(at) of vsl_recorded; a VSL proposal that went
    // out (vsl_stage sent/watched, or a video_attached / video proposal_sent fact) was recorded first, so it is never "pending"
    const recorded = past(r.vsl_stage, ["recorded", "rendered", "sent", "watched"]) || !!vslAt;
    // the sent VSL: its file, playable URL and analysis (what vsls.utopiamodels.ai showed per job). Auto intro = the renderer's own file.
    const tag = jobTag(r), file: string | null = r.video_proof?.file ?? null, intro = introInfo(file), pp = r.text_proof ?? r.video_proof ?? {};
    const note: string = String(r.video_proof?.note ?? "");
    const vsl = vslSent || file ? { file, url: sendFileUrl(file) ?? takeUrl(tag), auto_intro: !!intro, sent_at: vslAt, tag, proposal_id: pp.proposal_id ?? note.match(/proposal (\d{15,})/)?.[1] ?? null,
      bid_usd: pp.bid_usd ?? null, connects: pp.connects ?? note.match(/(\d+) Connects/)?.[1] ?? null, arm: pp.arm ?? null, note: note || null, ...(intro ?? {}) } : null;
    // an auto intro IS the recording: Recorded carries its render time, Built (no one-shot package for it) starts when the render started
    const recAt = iso(r.recorded_at) ?? intro?.rendered_at ?? null;
    const builtAt = iso(r.ready_at) ?? iso(r.built_fact_at) ?? (intro?.rendered_at && intro.render_s ? iso(new Date(Date.parse(intro.rendered_at) - intro.render_s * 1000)) : null);
    const up = r.hunt_type === "upwork";
    const tl: any = {
      primary: posted ? { kind: "Posted", at: posted } : { kind: "Found", at: iso(r.found_at) },
      found_at: iso(r.found_at),
      steps: [
        { key: "posted", label: "Posted", ...(posted ? step(posted, true) : { at: null, state: "skipped" }) },
        { key: "built", label: "One-shot built", ...step(builtAt, recorded || r.stage === "one_shot") },
        { key: "recorded", label: "Recorded", ...step(recAt, recorded), ...(intro ? { auto_intro: true, render_s: intro.render_s } : {}) },
        { key: "text", label: up ? "Text proposal sent" : "Text offer sent", ...step(textAt, false, vslSent), proposal_id: r.text_proof?.proposal_id ?? null },
        { key: "vsl", label: up ? "VSL proposal sent" : "VSL sent", ...step(vslAt, vslSent), proposal_id: vsl?.proposal_id ?? null },
      ],
      vsl,
      letter: letterFor(r.letter_proof, iso(r.letter_at)),
    };
    tl.stuck = r.stage === "passed" || r.stage === "roosted" ? null : stuckFor(tl.steps);
    out[r.id] = tl;
  }
  return out;
}

async function laneMeta(tx: Tx, key: string) {
  const t = (await tx.query("select label from hunt_types where key = $1", [key])).rows[0];
  const s = (await tx.query(`select count(*)::int as found, max(found_at) as checked,
      count(*) filter (where exists (select 1 from touches x where x.item_id = i.id and x.status = 'sent'))::int as sent,
      count(*) filter (where reply_status in ('replied','booked','won'))::int as replied
    from hunt_items i where hunt_type = $1 and deleted_at is null`, [key])).rows[0];
  return { name: t?.label ?? key, checked: iso(s.checked), funnel: [{ k: "found", v: s.found, note: null }, { k: "sent", v: s.sent, note: null }, { k: "replied", v: s.replied, note: null }] };
}

export async function buildFeed(ws: string) {
  return withWorkspace(ws, async tx => {
    const person = (await tx.query("select slug, name from workspaces where id = $1", [ws])).rows[0];
    const items = (await tx.query("select * from feed_rows order by signal_at desc, id desc limit 500")).rows;
    const sys = await systems(tx);

    // ---- funding lane: feed rows in live_refresh.py's row shape
    const fundRows = (await tx.query(`select i.id, i.target, i.signal, i.signal_at, i.found_at, i.details, i.backend_agent, i.stage, i.vsl_stage, i.reply_status, i.one_shot_system, i.external_id,
          f.kind, f.round, f.amount_usd, f.source_url, c.domain, c.name as company,
          p.full_name, p.title as person_title, p.email, p.linkedin_url, p.handles,
          (select row_to_json(o) from one_shots o where o.item_id = i.id and o.deleted_at is null order by o.id desc limit 1) as one_shot,
          (select min(t.sent_at) from touches t where t.item_id = i.id and t.status = 'sent') as first_sent_at, ${PIPE}
        from hunt_items i join funding_signals f on f.item_id = i.id left join companies c on c.id = i.company_id left join people p on p.id = i.person_id
        where i.deleted_at is null and i.stage not in ('roosted','passed') order by i.signal_at desc, i.id desc`)).rows;
    const fm = await laneMeta(tx, "funding");
    const funding = {
      id: "funding", name: fm.name, state: "running", checked: fm.checked, funnel: fm.funnel, queue: null,
      backend: { agent: fundRows[0]?.backend_agent ?? null }, frontend: { agent: "eagle" },
      feed: fundRows.map(r => ({
        // ts = signal_at: the UI sorts rows by ts, and the feed is ordered by when the signal happened (Tyler: hit signals ASAP)
        item_id: r.id, ts: iso(r.signal_at), signal_at: iso(r.signal_at), found_at: iso(r.found_at), ready_at: r.details?.ready_at ?? null,
        first_sent_at: iso(r.first_sent_at), kind: r.kind, co: r.company ?? r.target, target: r.target, what: r.signal, title: r.details?.title ?? null, round: r.round,
        url: r.details?.site ?? null, status: pipelineStatus(r) ?? r.details?.status ?? STATUS[r.stage] ?? "Found", stage: pipelineStatus(r) ?? r.details?.status ?? STATUS[r.stage] ?? "Found",
        queued_touches: r.queued_touches, next_due_at: iso(r.next_due_at),
        vsl: VSL[r.vsl_stage] ?? null, fit_ok: r.details?.fit_ok ?? null,
        oneshot: r.one_shot ? { kind: r.one_shot.kind, label: r.one_shot.assets?.[0]?.label ?? r.one_shot.status, ok: r.one_shot.status === "ready", file: r.one_shot.assets?.[0]?.file ?? null } : null,
        script: r.one_shot?.script ?? null, tabs: r.one_shot?.assets?.[0]?.tabs ?? null,
        contact: r.full_name ? { name: r.full_name, role: r.person_title, email: r.email, email_source: r.handles?.email_source ?? null, linkedin: r.linkedin_url,
          x: r.handles?.x ?? null, github: r.handles?.github ?? null, ch: r.details?.channels ?? [] } : null,
        amount: r.details?.amount_text ?? money(r.amount_usd), usd: r.amount_usd, link: r.source_url, src: r.details?.src ?? null,
        site: r.details?.site ?? (r.domain ? "https://" + r.domain : null), tags: r.details?.tags ?? [], fit: r.details?.fit ?? null,
        us: r.details?.us ?? null, stage_ok: r.details?.stage_ok ?? null, logo: r.details?.logo ?? null, live: true,
        one_shot_system: sys(r, "funding"), job_tag: null,
      })),
    };

    // ---- upwork lane: alerts as feed rows; queue buckets derived from one-shots / VSL stage / touches
    const upRows = (await tx.query(`select i.*, u.title, u.job_url, u.posted_at, u.budget_type, u.budget_min_usd, u.budget_max_usd, u.client_spend_usd, u.proposals_band,
          (select json_agg(o order by o.id desc) from one_shots o where o.item_id = i.id and o.deleted_at is null) as one_shots,
          (select json_agg(t order by t.sent_at) from touches t where t.item_id = i.id) as touches
        from hunt_items i join upwork_jobs u on u.item_id = i.id
        where i.deleted_at is null and i.stage not in ('roosted','passed') order by i.signal_at desc, i.id desc`)).rows;
    const um = await laneMeta(tx, "upwork");
    const slug = (r: any) => r.external_id;
    const queue = { ready: [] as any[], recorded: [] as any[], sent: [] as any[] };
    const enrichUp: Record<string, any> = {};
    const queued = new Set<string>();   // a hunt shows ONCE: in the queue of its furthest stage, else in the feed (3710 showed twice, 11-23)
    for (const r of upRows) {
      const os = (r.one_shots || [])[0], sent = (r.touches || [])[0];
      enrichUp[slug(r)] = { jobs: [r.external_id], job_tag: jobTag(r), formats: (r.one_shots || []).map((o: any) => o.kind), replies: [], fit: r.fit, proposals: r.proposals_band,
        title: r.title, bid: null, connects: null, kind: null, closed: false,
        budget: r.budget_min_usd ? `$${r.budget_min_usd}${r.budget_max_usd ? "–" + r.budget_max_usd : ""}${r.budget_type === "hourly" ? "/h" : ""}` : null,
        spent: r.client_spend_usd ? money(Number(r.client_spend_usd)) : null, rating: null, client: r.target };
      const note = (s: string, t: any) => `${s} ${iso(t)}`;
      const job_tag = jobTag(r);
      if (sent || ["recorded", "rendered"].includes(r.vsl_stage) || os) queued.add(r.id);
      if (sent) queue.sent.push({ slug: slug(r), job_tag, ts: iso(sent.sent_at), note: sent.channel === "upwork" && sent.provider_id ? `proposal ${sent.provider_id} sent` : "sent",
        file: os?.demo_url ?? sent.details?.file ?? takeUrl(job_tag), source: "eagleeye-api", item_id: r.id, title: r.title,
        vsl: VSL[r.vsl_stage] ?? null, vsl_stage: r.vsl_stage, stage: r.stage, one_shot_system: sys(r, "upwork") });
      else if (["recorded", "rendered"].includes(r.vsl_stage)) queue.recorded.push({ slug: slug(r), job_tag, note: note("recorded", r.updated_at), source: "eagleeye-api", item_id: r.id, one_shot_system: sys(r, "upwork") });
      else if (os) queue.ready.push({ slug: slug(r), job: r.external_id, job_tag, demo: os.demo_url, demo_ok: os.status === "ready", note: note(os.status === "ready" ? "demo ready" : os.status, os.updated_at), source: "eagleeye-api", item_id: r.id, one_shot_system: sys(r, "upwork") });
    }
    const upwork = {
      id: "upwork", name: um.name, state: "running", checked: um.checked, funnel: um.funnel, queue,
      backend: { agent: upRows[0]?.backend_agent ?? null }, frontend: { agent: "eagle" },
      feed: upRows.filter(r => !queued.has(r.id)).map(r => ({ ...postOut(r, r.title, r.job_url), one_shot_system: sys(r, "upwork") })),
    };

    // ---- job posts lane: only rows answered with a one-shot reach the UI (shared.js filters e.oneshot)
    const jobRows = (await tx.query(`select i.*, j.title, j.board, j.location, j.source_url, c.name as company,
          (select row_to_json(o) from one_shots o where o.item_id = i.id and o.deleted_at is null order by o.id desc limit 1) as one_shot,
          (select count(*)::int from replies r where r.item_id = i.id) as reply_count, ${PIPE}
        from hunt_items i join job_posts j on j.item_id = i.id left join companies c on c.id = i.company_id
        where i.deleted_at is null and i.stage not in ('roosted','passed') order by i.signal_at desc`)).rows;
    const jm = await laneMeta(tx, "job_post");
    const jobs = { id: "jobs", name: jm.name, state: "running", checked: jm.checked, funnel: jm.funnel, queue: {},
      feed: jobRows.filter(r => !r.one_shot).map(r => ({ ...postOut(r, r.title, r.source_url, r.company ?? r.target),
        ...(pipelineStatus(r) ? { status: pipelineStatus(r) } : {}), queued_touches: r.queued_touches, next_due_at: iso(r.next_due_at), one_shot_system: sys(r, "job_post") })),
      backend: { agent: jobRows[0]?.backend_agent ?? null }, frontend: { agent: "eagle" } };
    const enrichJobs = jobRows.map(r => ({
      item_id: r.id, ts: iso(r.signal_at), co: r.company ?? r.target, role: r.title, board: r.board, level: r.details?.level ?? null,
      role_class: r.details?.role_class ?? null, location: r.location, url: r.source_url, logo: r.details?.logo ?? null,
      oneshot: r.one_shot ? { kind: r.one_shot.kind, label: r.one_shot.status, ok: r.one_shot.status === "ready", url: r.one_shot.demo_url } : null,
      vsl: r.vsl_stage === "none" ? null : r.vsl_stage, status: r.stage, replies: r.reply_count, one_shot_system: sys(r, "job_post"),
    }));

    // ---- investor lane (investor_hunt.md: ranked investors, a row per investor, the trigger = their latest similar bet)
    const invRows = (await tx.query(`select i.id, i.target, i.signal, i.signal_at, i.found_at, i.details, i.backend_agent, i.stage, i.vsl_stage, i.reply_status,
          i.subtype, i.fit, i.one_shot_system, s.*, p.email, p.linkedin_url, p.handles,
          (select row_to_json(o) from one_shots o where o.item_id = i.id and o.deleted_at is null order by o.id desc limit 1) as one_shot, ${PIPE}
        from hunt_items i join investor_signals s on s.item_id = i.id left join people p on p.id = i.person_id
        where i.deleted_at is null and i.stage not in ('roosted','passed') order by s.score desc nulls last, i.signal_at desc`)).rows;
    const im = await laneMeta(tx, "investor");
    const investor = { id: "investor", name: im.name, state: "running", checked: im.checked, funnel: im.funnel, queue: null,
      backend: { agent: invRows[0]?.backend_agent ?? null }, frontend: { agent: "eagle" },
      feed: invRows.map(r => ({
        item_id: r.id, type: "investor", badge: im.name, subtype: r.subtype, ts: iso(r.signal_at), signal_at: iso(r.signal_at), found_at: iso(r.found_at),
        co: r.investor, investor: r.investor, firm: r.firm, what: r.signal, lane: r.lane, verified: r.verified,
        score: r.score, score_parts: r.score_parts, rank: r.details?.rank ?? null, similarity: r.similarity,
        deal: r.deal_company ? { company: r.deal_company, round: r.deal_round, amount: r.deal_amount, date: r.deal_date ? String(r.deal_date instanceof Date ? r.deal_date.toISOString() : r.deal_date).slice(0, 10) : null, url: r.deal_url } : null,
        trigger_fresh: r.details?.trigger_fresh ?? false, thesis: r.thesis_quote, check: { min: r.check_min, max: r.check_max }, route: r.cold_route,
        x: r.x_handle, portfolio: r.portfolio_url, link: r.source_url, email: r.email,
        // Tyler 11-21: "hold off on investors until this is clearer" -> every investor row reads Held; no send fires (hunt_send INVESTOR_SENDS_HELD)
        status: pipelineStatus(r) ?? "Held", flag: r.verified ? null : "unverified", ready: r.details?.status ?? null,
        vsl: VSL[r.vsl_stage] ?? null, queued_touches: r.queued_touches, next_due_at: iso(r.next_due_at),
        oneshot: r.one_shot ? { kind: r.one_shot.kind, label: r.one_shot.assets?.[0]?.label ?? r.one_shot.status, ok: r.one_shot.status === "ready", file: r.one_shot.assets?.[0]?.file ?? null } : null,
        script: r.one_shot?.script ?? null, live: true, one_shot_system: sys(r, "investor"), job_tag: null,
      })),
    };

    // ---- roosts: clients (+ their reply/touch thread) and network
    const roosts = (await tx.query(`select rr.*, r.notes, r.person_id from roost_rows rr join roosts r on r.id = rr.id order by rr.roosted_at, rr.id`)).rows;
    const thread = (await tx.query(`select r.id as roost_id, x.ts, x.kind, x.what, x.ch from roosts r cross join lateral (
          select received_at as ts, 'client_reply' as kind, body as what, channel as ch from replies p where p.roost_id = r.id
          union all select sent_at, 'message_sent', coalesce(provider_id, channel), channel from touches t where t.roost_id = r.id) x
        order by x.ts desc`)).rows;
    const clients = roosts.filter(r => r.kind === "client"), network = roosts.filter(r => r.kind === "network");
    const name = (r: any) => r.full_name ?? r.company;
    const roostOut = [
      { id: "clients", name: "Clients", agent: null, checked: iso(new Date()), source: "eagleeye-api",
        rows: clients.map(r => {
          const paid = Number(r.paid_cents ?? 0), pend = Number(r.pending_cents ?? 0);
          return { roost_id: r.id, name: name(r),
            // the spike's words: upwork stays upwork; consulting/direct relationships are personal_network; a prospect has none yet
            hunt: r.came_from?.[0] ?? (r.origin === "upwork" ? "upwork" : r.origin ? "personal_network" : null) ?? thread.find(t => t.roost_id === r.id)?.ch ?? null,
            stage: r.stage ?? r.status, what: r.notes, contracts: null,
            paid: (r.paid_cents == null ? null : money(paid / 100) ?? "$0") + (pend ? ` · ${money(pend / 100)} pending/funded` : ""),
            paid_cents: r.paid_cents, pending_cents: r.pending_cents, value_cents: r.value_cents };
        }),
        feed: thread.filter(t => clients.some(c => c.id === t.roost_id)).map(t => ({ ts: iso(t.ts), kind: t.kind, what: t.what, co: name(clients.find(c => c.id === t.roost_id)), src: "eagleeye-api" })) },
      { id: "network", name: "Network", agent: null, checked: iso(new Date()), source: "eagleeye-api",
        rows: network.map(r => ({ roost_id: r.id, name: name(r), hunt: r.came_from?.[0] ?? null, stage: r.status, channels: [], what: r.notes, at: iso(r.last_activity) })),
        feed: [] },
    ];

    const lastFound = items.reduce((m: string | null, r: any) => { const t = iso(r.found_at); return !m || (t && t > m) ? t : m; }, null);
    return {
      person: person.slug, display: person.name, source: "eagleeye-api",
      built: iso(new Date()), live_at: lastFound, copy_at: null,
      hunts: [funding, jobs, upwork, investor],
      counts: {
        by_type: Object.fromEntries([...new Set(items.map((r: any) => r.hunt_type))].map(t => [t, items.filter((r: any) => r.hunt_type === t).length])),
        by_status: [funding.feed, jobs.feed, investor.feed].flat().reduce((m: Record<string, number>, r: any) => (m[r.status] = (m[r.status] ?? 0) + 1, m), {}),
      },
      enrich: { jobs: enrichJobs, upwork: enrichUp },
      timelines: await timelines(tx),
      roosts: roostOut,
      items: items.map(camelRow),
    };
  });
}
