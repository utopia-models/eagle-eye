// Live ingest: the spike's LIVE rows -> Eagle Eye API, idempotent by source id.
//   tsx src/ingest.ts [file.json ...]   (default: eagle-eye-spike/public/people/hunts-live.json if present, then tyler.json)
// Only rows with live === true are read (Tyler 11-21: no mock or stale data); the 11-20 snapshot rows never enter.
// Writes go through the REST API with a per-run key (scopes listed below, 10 min TTL) that is revoked when the run ends,
// so no long-lived token exists anywhere.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { mintKey, revokeKey } from "./keys.ts";

const SPIKE = process.env.EAGLE_SPIKE_DIR || "/home/architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/public/people";
export const API = process.env.EAGLE_API || `http://${process.env.EAGLE_HOST || "100.127.249.81"}:${process.env.EAGLE_PORT || 8798}`;
// The current client roster: CRM Deals as published to the OCC feed (clients + prospects). Records only, never their events.
const CLIENTS = process.env.EAGLE_CLIENTS_FILE || "/home/architect/.claude/knowledge/_infra/occ-feeds/clients.json";
// Each client's open tasks (CRM: net/work/upwork/crm/<slug>.jsonl) become the roost's next steps (card 11-21 ~8:50 PM).
const CRM_DIR = process.env.EAGLE_CRM_DIR || "/home/architect/.claude/knowledge/net/work/upwork/crm";
const SCOPES = ["huntItems:write", "companies:write", "people:write", "roosts:write", "replies:write", "oneShots:write", "nextSteps:write"];
const h = (...a: unknown[]) => createHash("sha1").update(a.map(x => String(x ?? "")).join("|")).digest("hex").slice(0, 20);

type Row = Record<string, any>;
type Source = { lane: string; group: "hunts" | "roosts"; row: Row };

/** Reads the tyler.json shape ({hunts:[{id, feed}], roosts:[{id, feed}]}: rows with live === true) or a flat array.
 *  A flat hunts-live.json is the data agent's live output by definition (every row is a real, current hunt). */
const laneOf = (r: Row) => r.lane || r.hunt || (["launch", "form_d", "news"].includes(r.kind) ? "funding" : r.kind === "job_read" || r.kind === "upwork_job" ? "upwork" : r.kind === "job_post" ? "jobs" : r.type);
export function liveRows(files: string[]): Source[] {
  const out: Source[] = [];
  for (const f of files) {
    if (!existsSync(f)) continue;
    const d = JSON.parse(readFileSync(f, "utf8"));
    const flat = Array.isArray(d) ? d : Array.isArray(d.rows) ? d.rows : null;
    const allLive = /hunts-live\.json$/.test(f);
    if (flat) { for (const r of flat) if (allLive || r.live === true) out.push({ lane: laneOf(r), group: r.group === "roosts" ? "roosts" : "hunts", row: r }); continue; }
    for (const g of ["hunts", "roosts"] as const)
      for (const lane of d[g] || []) for (const r of lane.feed || []) if (r.live === true) out.push({ lane: lane.id, group: g, row: r });
  }
  return out;
}

const domainOf = (u?: string | null) => { try { return u ? new URL(u).hostname.replace(/^www\./, "") : undefined; } catch { return undefined; } };
const day = (t: string) => new Date(t).toISOString().slice(0, 10);

/** One live row -> the API call that records it. Returns null for rows that are not hunts (e.g. legacy letter mail). */
export function toWrite(s: Source): { path: string; body: Row; key: string; oneShot?: Row | null } | { roostReply: Row; key: string } | null {
  const r = s.row;
  if (!r.ts) return null;
  if (s.group === "hunts" && s.lane === "funding") {
    const kind = r.kind === "launch" || r.kind === "form_d" ? r.kind : "news";
    const ext = r.link || `${r.src}:${h(r.signal_at || r.ts, r.co, r.what)}`;
    const signalAt = r.signal_at || r.ts;
    const ready = /ready to record/i.test(r.status || "") || r.vsl === "record";
    // card 11-21: a built package now waits as "Offer queued" (touch 1 offers the walkthrough; Vizier gets it on "yes")
    const offerQueued = /offer queued/i.test(r.status || "");
    const ct = r.contact && r.contact.name && r.contact.name !== r.co ? r.contact : null;
    const site = r.url || r.site;
    return { key: `funding:${ext}`, path: "/rest/batch/huntItems?upsert=true", oneShot: r.oneshot ? {
        kind: ["demo", "vsl", "loom", "mockup", "audit"].includes(r.oneshot.kind) ? r.oneshot.kind : "vsl", status: r.oneshot.ok ? "ready" : "building",
        script: r.script ?? null, assets: [{ label: r.oneshot.label ?? null, file: r.oneshot.file ?? null, tabs: r.tabs ?? null }] } : null,
      body: {
      huntType: "funding", externalId: ext, target: r.target || r.co || r.what, signal: r.what || r.co, signalAt,
      ...(r.found_at ? { foundAt: r.found_at } : {}),
      ...(ready ? { stage: "one_shot", vslStage: "scripted" } : offerQueued ? { stage: "one_shot" } : {}),
      company: r.co ? { name: r.co, ...(domainOf(site) ? { domain: domainOf(site) } : {}) } : undefined,
      person: ct ? { fullName: ct.name, ...(ct.email ? { email: ct.email } : {}), ...(ct.role ? { title: ct.role } : {}), ...(ct.linkedin ? { linkedinUrl: ct.linkedin } : {}),
        handles: Object.fromEntries(Object.entries({ x: ct.x, github: ct.github, email_source: ct.email_source, phone: ct.phone }).filter(([, v]) => v)) } : undefined,
      funding: { kind, round: r.round || kind, amountUsd: typeof r.usd === "number" ? r.usd : null, announcedOn: day(signalAt), sourceUrl: r.link || r.src },
      details: { src: r.src, kind, title: r.title ?? null, amount_text: r.amount ?? null, fit: r.fit ?? null, fit_ok: r.fit_ok ?? null, tags: r.tags ?? [], site: site ?? null,
        us: r.us ?? null, stage_ok: r.stage_ok ?? null, status: r.status ?? null, ready_at: r.ready_at ?? null, logo: r.logo ?? null, channels: r.contact?.ch ?? [] },
    } };
  }
  if (s.group === "hunts" && (s.lane === "upwork" || s.lane === "jobs") && r.post) {
    // live post rows (live_refresh.py): Upwork desk/alert jobs (backend upwork) and LinkedIn AI/ML roles (backend sekhmet)
    const up = s.lane === "upwork";
    const signalAt = r.signal_at || r.ts;
    const ext = up ? (r.job || r.link || `alert:${h(signalAt, r.what)}`) : (r.link || `${r.src}:${h(signalAt, r.co, r.what)}`);
    const { live: _l, ts: _t, signal_at: _s, found_at: _f, co: _c, what: _w, ...extra } = r;
    const chip = (k: string) => (r.chips || []).find((c: any) => c[0] === k)?.[1] as string | undefined;
    const budget = chip("budget")?.match(/(hourly|fixed)?\s*\$([\d,.]+)(?:\s*-\s*\$([\d,.]+))?/i);
    const num = (x?: string) => x ? Number(x.replace(/,/g, "")) : null;
    const spent = chip("client spent")?.match(/\$([\d.]+)([KM])?/i);
    const base = { externalId: ext, target: r.co || r.what, signal: r.what, signalAt, ...(r.found_at ? { foundAt: r.found_at } : {}),
      ...(r.agent ? { backendAgent: r.agent } : {}), ...(r.front ? { frontendAgent: r.front } : {}), details: extra };
    return { key: `${s.lane}:${ext}`, path: "/rest/batch/huntItems?upsert=true", body: up ? {
      ...base, huntType: "upwork",
      upwork: { title: r.what, postedAt: signalAt, jobUrl: r.link ?? null,
        budgetType: budget?.[1] ? budget[1].toLowerCase() : null, budgetMinUsd: num(budget?.[2]), budgetMaxUsd: num(budget?.[3]),
        clientCountry: (r.co || "").split(" · ")[1] ?? null, proposalsBand: chip("proposals") ?? null,
        clientSpendUsd: spent ? Number(spent[1]) * (spent[2]?.toUpperCase() === "M" ? 1e6 : spent[2] ? 1e3 : 1) : null },
    } : {
      ...base, huntType: "job_post", company: r.co ? { name: r.co } : undefined,
      // the hiring manager / founder the one-shot builder found (careers page, LinkedIn guest search, team page)
      person: r.contact?.name && r.contact.name !== r.co ? { fullName: r.contact.name, ...(r.contact.email ? { email: r.contact.email } : {}),
        ...(r.contact.role ? { title: r.contact.role } : {}), ...(r.contact.linkedin ? { linkedinUrl: r.contact.linkedin } : {}),
        handles: Object.fromEntries(Object.entries({ email_source: r.contact.email_source, email_confidence: r.contact.email_confidence }).filter(([, v]) => v)) } : undefined,
      jobPost: { title: r.what, board: r.board || r.src || "unknown", postedAt: signalAt, location: r.location ?? null, salaryRange: r.comp ?? null, sourceUrl: r.link || r.src },
    } };
  }
  if (s.group === "hunts" && s.lane === "upwork" && r.kind === "job_read") {
    // Upwork alert mail (older live_refresh.py output) carries the title only: the source id is the alert itself (time + title).
    const ext = r.job || r.url || `alert:${h(r.signal_at || r.ts, r.what)}`;
    return { key: `upwork:${ext}`, path: "/rest/batch/huntItems?upsert=true", body: {
      huntType: "upwork", externalId: ext, target: r.what, signal: "Upwork job alert", signalAt: r.signal_at || r.ts,
      ...(r.found_at ? { foundAt: r.found_at } : {}),
      upwork: { title: r.what, postedAt: r.signal_at || r.ts, jobUrl: r.url ?? null }, details: { src: r.src, kind: r.kind },
    } };
  }
  if (s.group === "roosts" && s.lane === "clients" && r.kind === "client_reply") {
    // Tyler 11-21: "for Upwork, Mohamed is now a roost". A live client message lands on that client's roost.
    return { key: `reply:${h(r.ts, r.co, r.what)}`, roostReply: { person: r.co, channel: /upwork/i.test(r.src || "") ? "upwork" : "email",
      body: r.what, receivedAt: r.ts, providerId: `alert:${h(r.ts, r.co, r.what)}` } };
  }
  return null; // jobs lane: plain-letter ATS mail is legacy (Tyler 11-21); job-post hunts arrive once the video+demo builder runs
}

/** clients.json (schema clients/1) -> one client roost per client and prospect. */
export function rosterRows(file: string): Row[] {
  if (!existsSync(file)) return [];
  const d = JSON.parse(readFileSync(file, "utf8"));
  if (d.schema !== "clients/1") throw new Error(`${file}: expected schema clients/1, got ${d.schema}`);
  const clients = (d.clients || []).map((c: Row) => ({ fullName: c.name, next: nextSteps(c), roost: {
    kind: "client", status: "active", stage: c.kind, origin: c.source ?? null, notes: c.what ?? null,
    paidCents: c.money?.paidCents ?? 0, pendingCents: (c.money?.pendingCents ?? 0) + (c.money?.fundedCents ?? 0),
    valueCents: c.money?.agreedCents ?? null } }));
  const prospects = (d.prospects || []).map((p: Row) => ({ fullName: p.name, next: nextSteps({ slug: String(p.name || "").toLowerCase(), name: p.name }), roost: {
    kind: "client", status: "active", stage: `prospect: ${p.status}`, origin: null, notes: p.what ?? null,
    paidCents: 0, pendingCents: 0, valueCents: p.amountCents ?? null } }));
  return [...clients, ...prospects];
}

/** A short step label: the task's first clause ("Write and send the detailed AI-automation proposal: ..." -> before the colon). */
export function stepLabel(text: string) {
  const t = String(text || "").split(/[:;(]| once | then /)[0].trim();
  return t.length > 72 ? t.slice(0, 71).replace(/\s+\S*$/, "") + "…" : t;
}

/** Open next steps for one client: clients.json `next` (a dated milestone/step) + the CRM's open tasks owned by us (tyler or an
 *  agent; a task the client owns is waiting on them, not a step of ours). */
export function nextSteps(c: Row, dir = CRM_DIR): Row[] {
  const out: Row[] = [];
  if (c.next?.label && c.next?.kind === "milestone")
    out.push({ what: c.next.label, dueAt: c.next.date ? `${c.next.date}T17:00:00Z` : null, owner: "tyler", sourceKey: `clients:${c.slug}:next:${c.next.label}` });
  const f = `${dir}/${c.slug}.jsonl`;
  if (!c.slug || !existsSync(f)) return out;
  const rows = readFileSync(f, "utf8").split("\n").filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const done = new Set(rows.filter(r => r.type === "done").map(r => r.id));
  for (const t of rows) {
    if (t.type !== "task" || done.has(t.id) || !t.owner || t.owner.toLowerCase() === c.slug) continue;
    out.push({ what: stepLabel(t.text), dueAt: t.due ?? null, owner: t.owner, sourceKey: `crm:${t.id}` });
  }
  return out;
}

async function call(token: string, method: string, path: string, body?: unknown) {
  const res = await fetch(API + path, { method, headers: { authorization: `Bearer ${token}`, "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const j: any = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${j.error || ""} ${j.issues ? JSON.stringify(j.issues).slice(0, 300) : ""}`);
  return j;
}

export async function runIngest(o: { files?: string[]; workspace?: string; clientsFile?: string }) {
  const files = o.files ?? [`${SPIKE}/hunts-live.json`, `${SPIKE}/tyler.json`];
  const rows = liveRows(files);
  const seen = new Set<string>();
  const items: Row[] = [], replies: Row[] = [], oneShots = new Map<string, Row>();
  let skipped = 0;
  for (const s of rows) {
    const w = toWrite(s);
    if (!w) { skipped++; continue; }
    if (seen.has(w.key)) continue;
    seen.add(w.key);
    if ("roostReply" in w) replies.push(w.roostReply);
    else { items.push(w.body); if (w.oneShot) oneShots.set(`${w.body.huntType}:${w.body.externalId}`, w.oneShot); }
  }
  const key = await mintKey({ workspace: o.workspace || "tyler", name: "ingest-live@ra", actorKind: "agent_backend", scopes: SCOPES, ttlSeconds: 600 });
  const summary = { files: files.filter(existsSync), live_rows: rows.length, skipped, items: { created: 0, updated: 0, unchanged: 0 },
    oneShots: { created: 0, updated: 0, unchanged: 0 }, replies: { created: 0, updated: 0, unchanged: 0 },
    clients: { created: 0, updated: 0, unchanged: 0 } };
  const roster = rosterRows(o.clientsFile ?? CLIENTS);
  try {
    for (const c of roster) {
      const person = (await call(key.token, "POST", "/rest/people?upsert=true", { fullName: c.fullName })).data.createPerson;
      const r = await call(key.token, "POST", "/rest/roosts?upsert=true", { personId: person.id, ...c.roost });
      summary.clients[r.status as "created" | "updated" | "unchanged"]++;
      const roostId = r.data.createRoost.id, open = new Set<string>();
      for (const n of c.next || []) { await call(key.token, "POST", "/rest/nextSteps?upsert=true", { roostId, ...n }); open.add(n.sourceKey); }
      // an imported step that left the source (task done, milestone paid) is closed, never left dangling
      const have = (await call(key.token, "GET", `/rest/nextSteps?filter=roostId[eq]:${roostId}&limit=200`)).data.nextSteps;
      for (const s of have) if (!s.doneAt && /^(crm|clients):/.test(s.sourceKey || "") && !open.has(s.sourceKey))
        await call(key.token, "PATCH", `/rest/nextSteps/${s.id}`, { doneAt: new Date().toISOString() });
    }
    for (let i = 0; i < items.length; i += 100) {
      const j = await call(key.token, "POST", "/rest/batch/huntItems?upsert=true", items.slice(i, i + 100));
      for (const k of ["created", "updated", "unchanged"] as const) summary.items[k] += j.counts[k];
      for (const it of j.data.createHuntItems) {
        const os = oneShots.get(`${it.huntType}:${it.externalId}`);
        if (!os) continue;
        const r = await call(key.token, "POST", "/rest/oneShots?upsert=true", { itemId: it.id, ...os });
        summary.oneShots[r.status as "created" | "updated" | "unchanged"]++;
      }
    }
    for (const rp of replies) {
      const person = (await call(key.token, "POST", "/rest/people?upsert=true", { fullName: rp.person })).data.createPerson;
      const roost = (await call(key.token, "POST", "/rest/roosts?upsert=true", { personId: person.id, kind: "client" })).data.createRoost;
      const j = await call(key.token, "POST", "/rest/replies?upsert=true", { roostId: roost.id, channel: rp.channel, body: rp.body, receivedAt: rp.receivedAt, providerId: rp.providerId });
      summary.replies[j.status as "created" | "updated" | "unchanged"]++;
    }
  } finally {
    await revokeKey(key.id);
  }
  return { summary };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const { pool } = await import("./db.ts");
  try { console.log(JSON.stringify((await runIngest({ files: process.argv.length > 2 ? process.argv.slice(2) : undefined })).summary, null, 1)); }
  catch (e: any) { console.error(e.message); process.exitCode = 1; }
  finally { await pool.end(); }
}
