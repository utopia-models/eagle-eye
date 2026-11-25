import { resetDb, pool, app, asOwner } from "./helpers.ts";
import { serve } from "@hono/node-server";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { AddressInfo } from "node:net";

let srv: any, file: string, live: string, roster: string, ingest: typeof import("../src/ingest.ts");
before(async () => {
  await resetDb();
  await new Promise<void>(r => { srv = serve({ fetch: app.fetch, hostname: "127.0.0.1", port: 0 }, () => r()); });
  process.env.EAGLE_API = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
  ingest = await import("../src/ingest.ts");
  // The shape live_refresh.py writes (tyler.json): live rows carry live:true; 11-20 copy rows do not.
  const dir = mkdtempSync(join(process.env.TMPDIR || tmpdir(), "ee-ingest-"));
  file = join(dir, "tyler.json");
  live = join(dir, "hunts-live.json");
  roster = join(dir, "clients.json");
  writeFileSync(roster, JSON.stringify({ schema: "clients/1", clients: [
    { slug: "mohamed", name: "Mohamed", what: "Polymarket market-maker bot", kind: "contract", source: "upwork", money: { paidCents: 10000, pendingCents: 0, fundedCents: 10000 },
      items: [{ label: "M1", state: "paid", amountCents: 10000, paidAt: "2026-11-12T20:52:55Z" }] },
    { slug: "yusuf", name: "Yusuf", what: "AI consulting (hourly)", kind: "hourly", source: "consulting", money: { paidCents: 10000, pendingCents: 0, fundedCents: 0 } },
    { slug: "pat", name: "Pat", what: "job-search setup + equity", kind: "direct", source: "direct", money: { paidCents: 0, agreedCents: 15000 } }],
    prospects: [{ name: "Resul", what: "SameDay Pack proposal", amountCents: 15000, status: "draft, not sent" }] }));
  // the data agent's hunts-live.json: a flat array, live by definition; ts = ready time, signal_at = the source's time
  writeFileSync(live, JSON.stringify([{ ts: "2026-11-21T22:15:25Z", kind: "launch", co: "River", target: "River", what: "Launched on YC (Fall 2026): River",
    title: "River - AI that works everywhere you do", round: "YC Fall 2026", usd: 500000, link: "https://www.ycombinator.com/launches/Xon-river",
    url: "https://meetriver.com/", src: "Launch YC", signal_at: "2026-11-20T17:00:00Z", found_at: "2026-11-21T22:12:00Z", ready_at: "2026-11-21T22:15:25Z",
    status: "Ready to record", vsl: "record", oneshot: { kind: "vsl", label: "Vizier talk-script river · 6 takes · ~82 s", ok: true, file: "river" },
    contact: { name: "Chandler Supple", role: "Founder/CEO", email: "chandler@rivereditor.example", linkedin: "https://www.linkedin.com/in/chandlersupple/", ch: ["email", "linkedin"] },
    script: "/x/hunts/funding/river/script.md" }]));
  writeFileSync(file, JSON.stringify({
    hunts: [
      { id: "funding", feed: [
        { ts: "2026-11-20T21:03:40Z", kind: "form_d", co: "Luwian AI Inc", what: "Form D filed · Other Technology", round: "Form D", amount: "indefinite offering",
          link: "https://www.sec.gov/Archives/edgar/data/2160625/000216062526000001/", src: "SEC EDGAR Form D", usd: 693000, us: true, live: true },
        { ts: "2026-11-20T17:12:25Z", kind: "launch", co: "MouseCat", what: "Launched on YC (Winter 2026): Morphy", round: "YC Winter 2026",
          link: "https://www.ycombinator.com/launches/Xpo-morphy", site: "https://www.mousecat.ai", src: "Launch YC", usd: 500000, live: true },
      ] },
      { id: "upwork", feed: [
        { ts: "2026-11-21T21:24:06Z", kind: "job_read", co: "Upwork", what: "Senior Data Engineer & AI Systems Evaluator", src: "dev@ inbox (Upwork alert)", live: true },
        { ts: "2026-11-19T08:00:00Z", kind: "job_read", co: "Upwork", what: "stale snapshot row", src: "11-20 copy" },
      ], queue: { sent: [{ slug: "Adam Gromling", ts: "2026-11-19T08:01:26Z" }] } },
      { id: "jobs", feed: [{ ts: "2026-11-21T10:00:00Z", kind: "rejection", co: "Acme", what: "legacy letter", live: true },
        { post: true, src: "LinkedIn jobs (guest)", board: "LinkedIn", co: "Evlo AI", what: "Machine Learning Engineer", link: "https://www.linkedin.com/jobs/view/4493103349/",
          signal_at: "2026-11-21T18:28:19Z", ts: "2026-11-21T18:28:19Z", kind: "post", status: "Found", location: "Chicago, IL · remote", employment: "Full-time",
          fit_ok: true, live: true, found_at: "2026-11-21T22:30:15Z", agent: "sekhmet", front: "eagle", type: "job", subtype: "LinkedIn", oneshot_type: "video + demo" }] },
      { id: "upwork", feed: [{ post: true, src: "Upwork desk (most-recent)", board: "Upwork", co: "Upwork client · Costa Rica", what: "ML engineer for a real-time scoring engine",
          link: "https://www.upwork.com/jobs/~022124244189017107222", signal_at: "2026-11-21T21:28:19Z", ts: "2026-11-21T21:28:19Z", kind: "post", status: "Found",
          job: "~022124244189017107222", oneshot_type: "terminal run", chips: [["budget", "hourly $120-$180"], ["client spent", "$20K+"], ["proposals", "20 to 50"]],
          live: true, found_at: "2026-11-21T22:30:15Z", agent: "upwork", front: "eagle" }] },
    ],
    roosts: [{ id: "clients", rows: [{ name: "Mohamed" }], feed: [
      { ts: "2026-11-21T15:07:31Z", kind: "client_reply", co: "Mohamed", what: "how do I control the bot?", src: "dev@ inbox (Upwork message)", live: true },
      { ts: "2026-11-20T15:07:31Z", kind: "client_reply", co: "Mohamed", what: "old copy", src: "11-20 copy" },
    ] }],
  }));
});
after(async () => { srv.close(); await pool.end(); });

test("only live rows enter; snapshot rows and legacy letter mail never do", async () => {
  const live = ingest.liveRows([file]);
  assert.equal(live.length, 7);
  assert.ok(live.every(s => s.row.live === true));
});

test("ingest writes through the API and a second run is a no-op (idempotent source ids)", async () => {
  const a = (await ingest.runIngest({ files: [file], clientsFile: "/nonexistent" })).summary;
  assert.deepEqual(a.items, { created: 5, updated: 0, unchanged: 0 });
  assert.deepEqual(a.replies, { created: 1, updated: 0, unchanged: 0 });
  assert.equal(a.skipped, 1);
  const b = (await ingest.runIngest({ files: [file], clientsFile: "/nonexistent" })).summary;
  assert.deepEqual(b.items, { created: 0, updated: 0, unchanged: 5 });
  assert.deepEqual(b.replies, { created: 0, updated: 0, unchanged: 1 });
  const n = await asOwner(async tx => (await tx.query(`select (select count(*) from hunt_items)::int items, (select count(*) from funding_signals)::int f,
     (select count(*) from roosts)::int roosts, (select count(*) from replies)::int replies,
     (select count(*) from api_keys where revoked_at is null)::int live_keys, (select count(*) from hunt_items where external_id like '%stale%')::int stale`)).rows[0]);
  assert.deepEqual(n, { items: 5, f: 2, roosts: 1, replies: 1, live_keys: 0, stale: 0 });
});

test("/api/feed serves the spike shape the UI's EE.build() reads, from Postgres", async () => {
  const d = (await (await app.request("/api/feed?workspace=tyler")).json()) as any;
  assert.deepEqual(d.hunts.map((h: any) => h.id), ["funding", "jobs", "upwork", "investor"]);
  const f = d.hunts[0];
  assert.deepEqual(f.feed.map((r: any) => r.co), ["Luwian AI Inc", "MouseCat"], "newest signal first");
  assert.equal(f.feed[1].site, "https://www.mousecat.ai");
  const up = d.hunts[2].feed.find((r: any) => r.post);
  assert.deepEqual([up.job, up.oneshot_type, up.signal_at, up.found_at, up.agent], ["~022124244189017107222", "terminal run", "2026-11-21T21:28:19Z", "2026-11-21T22:30:15Z", "upwork"]);
  const jp = d.hunts[1].feed[0];
  assert.deepEqual([jp.co, jp.what, jp.board, jp.agent, jp.post], ["Evlo AI", "Machine Learning Engineer", "LinkedIn", "sekhmet", true]);
  const uj = await asOwner(async tx => (await tx.query("select budget_type, budget_min_usd, budget_max_usd, client_country, client_spend_usd, proposals_band from upwork_jobs where job_url like '%0222124244%' or job_url like '%022124244189017107222'")).rows[0]);
  assert.deepEqual(uj, { budget_type: "hourly", budget_min_usd: "120.00", budget_max_usd: "180.00", client_country: "Costa Rica", client_spend_usd: "20000.00", proposals_band: "20 to 50" });
  assert.deepEqual(d.hunts[2].queue, { ready: [], recorded: [], sent: [] });
  assert.deepEqual(d.roosts.map((r: any) => r.id), ["clients", "network"]);
  assert.equal(d.roosts[0].rows[0].name, "Mohamed");
  assert.equal(d.roosts[0].feed[0].kind, "client_reply");
  assert.ok(Array.isArray(d.enrich.jobs) && typeof d.enrich.upwork === "object");
  assert.equal(d.items[0].huntType, "upwork");
  assert.ok("speedToLeadMinutes" in d.items[0] && "foundAt" in d.items[0]);
});

test("hunts-live.json rows: signal_at (not the ready-time ts) is the signal; contact + one-shot land; re-run is a no-op", async () => {
  const a = (await ingest.runIngest({ files: [live], clientsFile: "/nonexistent" })).summary;
  assert.deepEqual([a.items.created, a.oneShots.created], [1, 1]);
  const b = (await ingest.runIngest({ files: [live], clientsFile: "/nonexistent" })).summary;
  assert.deepEqual([b.items.unchanged, b.oneShots.unchanged], [1, 1]);
  const r = await asOwner(async tx => (await tx.query(`select i.signal_at, i.found_at, i.stage, i.vsl_stage, p.full_name, p.email, o.kind, o.status
      from hunt_items i join people p on p.id = i.person_id join one_shots o on o.item_id = i.id where i.target = 'River'`)).rows[0]);
  assert.equal(r.signal_at.toISOString(), "2026-11-20T17:00:00.000Z");
  assert.equal(r.found_at.toISOString(), "2026-11-21T22:12:00.000Z");
  assert.deepEqual([r.stage, r.vsl_stage, r.full_name, r.email, r.kind, r.status], ["one_shot", "scripted", "Chandler Supple", "chandler@rivereditor.example", "vsl", "ready"]);
  const d = (await (await app.request("/api/feed?workspace=tyler")).json()) as any;
  const row = d.hunts[0].feed.find((x: any) => x.co === "River");
  assert.equal(row.ts, "2026-11-20T17:00:00Z");
  assert.equal(row.status, "Ready to record");
  assert.equal(row.vsl, "record");
  assert.equal(row.oneshot.label, "Vizier talk-script river · 6 takes · ~82 s");
  assert.equal(row.contact.name, "Chandler Supple");
});

test("client roster: the current clients load as client roosts (records only); Mohamed's live-reply roost is the same roost", async () => {
  const before = await asOwner(async tx => (await tx.query("select count(*)::int n from events where type not like 'roost.%' and type not like 'person.%' and type not like 'next_step.%'")).rows[0].n);
  const a = (await ingest.runIngest({ files: [], clientsFile: roster })).summary;
  assert.deepEqual(a.clients, { created: 3, updated: 1, unchanged: 0 }, "Mohamed's roost (from his live reply) is updated, not duplicated");
  const b = (await ingest.runIngest({ files: [], clientsFile: roster })).summary;
  assert.deepEqual(b.clients, { created: 0, updated: 0, unchanged: 4 });
  const after = await asOwner(async tx => (await tx.query("select count(*)::int n from events where type not like 'roost.%' and type not like 'person.%' and type not like 'next_step.%'")).rows[0].n);
  assert.equal(after, before, "no old client events are imported");
  const d = (await (await app.request("/api/feed?workspace=tyler")).json()) as any;
  const rows = d.roosts[0].rows.map((r: any) => [r.name, r.hunt, r.stage, r.what, r.paid]);
  assert.deepEqual(rows, [
    ["Mohamed", "upwork", "contract", "Polymarket market-maker bot", "$100 · $100 pending/funded"],
    ["Yusuf", "personal_network", "hourly", "AI consulting (hourly)", "$100"],
    ["Pat", "personal_network", "direct", "job-search setup + equity", "$0"],
    ["Resul", null, "prospect: draft, not sent", "SameDay Pack proposal", "$0"],
  ]);
  assert.deepEqual(d.roosts[1].rows, [], "network roster stays out");
});

test("toWrite: an 'Offer queued' funding row is a built one-shot (stage one_shot, no Vizier stage); a job row carries its HM", async () => {
  const { toWrite } = await import("../src/ingest.ts");
  const f: any = toWrite({ lane: "funding", group: "hunts", row: { ts: "2026-11-21T10:00:00Z", kind: "news", co: "Acme", what: "Acme raises $2M", link: "https://x/a",
    status: "Offer queued", oneshot: { kind: "walkthrough", ok: true, file: "acme" }, contact: { name: "Dana Lee", email: "dana@acme.example", phone: "+15555550100" } } });
  assert.equal(f.body.stage, "one_shot");
  assert.equal(f.body.vslStage, undefined, "not on the Vizier bar until a yes");
  assert.equal(f.body.person.handles.phone, "+15555550100", "the Form D phone reaches the dial steps");
  const j: any = toWrite({ lane: "jobs", group: "hunts", row: { ts: "2026-11-21T10:00:00Z", post: true, co: "Evlo AI", what: "ML Engineer", link: "https://x/j", board: "LinkedIn",
    contact: { name: "Sam Park", role: "CTO", email: "sam@evlo.example", email_confidence: "verified", linkedin: "https://linkedin.com/in/sam" } } });
  assert.deepEqual([j.body.person.fullName, j.body.person.email, j.body.person.handles.email_confidence], ["Sam Park", "sam@evlo.example", "verified"]);
});
