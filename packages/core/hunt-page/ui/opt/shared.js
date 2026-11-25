// Eagle Eye v2: shared data, brand and icons for the hunts feed.
// Data rule (Tyler 11-21): Mohamed is a client now, so his Upwork thread lives in ROOSTS > Clients, never in the hunt feed.
// API origin: same-origin behind eagle.utopiamodels.ai (the tunnel routes /api/* to eagle-server); the tailnet API on ra.*.ts.net
const EE_API = location.hostname.endsWith(".ts.net") ? "https://ra.tail4016d7.ts.net:8451" : "";
const EE = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const ago = ts => {
    if (!ts) return "–";
    const s = (Date.now() - Date.parse(ts)) / 1000;
    if (isNaN(s)) return "–";
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + "m";
    if (s < 86400 * 2) return Math.round(s / 3600) + "h";
    return Math.round(s / 86400) + "d";
  };
  // every time Eagle Eye shows is in the VIEWER'S browser zone, always labelled (Tyler 11-22 6:47 AM ET: "not a fixed ET value ...
  // so it follows him as he travels"). Feeds carry UTC (ISO, Z); the browser's Intl zone does the rest. The label is the short
  // generic name when it is a code (ET, MT, PT), else the offset (GMT+2 in Cairo); per date, so a DST change is right.
  const zone = ts => { const d = ts == null ? new Date() : new Date(ts); if (isNaN(d)) return "";
    const p = f => (new Intl.DateTimeFormat("en-US", {timeZoneName: f}).formatToParts(d).find(x => x.type === "timeZoneName") || {}).value || "";
    const g = p("shortGeneric"); return /^[A-Z]{1,4}$/.test(g) ? g : p("short"); };
  const day = ts => ts ? new Date(ts).toLocaleDateString("en-US", {month: "short", day: "numeric"}) : "–";
  const exact = ts => ts ? new Date(ts).toLocaleString("en-US", {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}) + " " + zone(ts) : "–";
  const tsIn = s => { const m = String(s || "").match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z/); return m ? m[0] : null; };
  const isMohamed = s => /mohamed/i.test(String(s || ""));
  const jobId = s => /^~\d{10,}/.test(s) ? "job " + s.slice(1, 7) + "…" + s.slice(-4) : s;
  const nice = slug => /^~\d/.test(slug) ? jobId(slug) : slug.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase()).replace(/\bAi\b/g, "AI");

  // lucide icon paths (shadcn/ui's icon set)
  const P = {
    job: '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
    upwork: '<circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/>',
    funding: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    investor: '<path d="M10 18v-7"/><path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949z"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M3 22h18"/><path d="M6 18v-7"/>',
    video: '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    reply: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    filter: '<path d="M3 6h18"/><path d="M7 12h10"/><path d="M10 18h4"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>', down: '<path d="m6 9 6 6 6-6"/>', up: '<path d="m18 15-6-6-6 6"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    link: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3"/>',
    inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    rec: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="currentColor"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    ask: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
    film: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    log: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    script: '<path d="M15 12h-5"/><path d="M15 8h-5"/><path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
    client: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    net: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    cmd: '<path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3"/>',
  };
  const icon = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ""}</svg>`;

  const TYPE = {job: "Job post", upwork: "Upwork", funding: "Funding", investor: "Investor"};
  // what is BUILT in the one-shot's package (API one_shot_system.state), in plain words + the tap/hover explanation
  const DEMO = {
    "MVP live": {say: "working app live", ok: true, about: "A working app built for this job is published; open it from the hunt page."},
    "Working demo": {say: "working version", ok: true, about: "A working version runs on sample data (a recorded terminal run), plus the architecture diagram."},
    "Diagram only": {say: "diagram only", ok: null, about: "Only the architecture diagram is built; no working app yet."},
    "Script only": {say: "script only", ok: null, about: "Only the walkthrough script is written; nothing on screen is built yet."},
    "Not built": {say: "not built", ok: false, about: "The one-shot is chosen but nothing is built yet."},
  };
  // a hunt whose VSL went out never needed a demo: "Not built" is wrong there (knowledge#18540)
  const demoOf = r => (r.oss.state === "Not built" && (r.vsl === "sent" || r.tl?.vsl?.sent_at))
    ? {say: "none needed, VSL sent", ok: true, about: "This hunt went out as a VSL; no demo app was part of it."} : DEMO[r.oss.state] || DEMO["Not built"];
  const VSL = ["record", "recorded", "sent"];
  const VSL_L = {record: "Record", recorded: "Recorded", sent: "Sent"};

  function build(d) {
    const lane = id => d.hunts.find(l => l.id === id) || {};
    const jobs = lane("jobs"), up = lane("upwork"), fund = lane("funding"), inv = lane("investor");
    const rows = [];
    const E = d.enrich || {}, UM = E.upwork || {};
    const hid = (...a) => "h" + Array.from(a.join("|")).reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7).toString(36);
    const upRow = (r, base) => {
      const m = UM[r.slug] || {};
      const bid = m.bid != null ? "$" + Math.round(m.bid).toLocaleString() + (m.bid_unit === "/h" ? "/h" : "") : null;
      return Object.assign({
        type: "upwork", lane: "upwork", agent: up.backend?.agent, front: up.frontend?.agent, checked: up.checked,
        subs: (m.formats || []).slice(), closed: !!m.closed, title: m.title || null, kind: m.kind || null,
        nums: [m.budget && ["budget", m.budget], bid && [m.bid_unit === "fixed" ? "fixed bid" : "bid", bid], m.fit != null && ["fit", m.fit], m.proposals != null && ["proposals", m.proposals],
               m.connects != null && ["connects", m.connects], m.spent && ["client spent", m.spent], m.rating && ["rating", "★ " + m.rating]].filter(Boolean),
        fit: m.fit ?? null, repl: (m.replies || []).map(x => ({ts: x.ts, what: x.what})), logo: null, oss: r.one_shot_system || null, item: r.item_id || null,
        job_tag: r.job_tag ?? m.job_tag ?? null,   // API field (feed.ts jobTag): last 4 digits of the Upwork job id
      }, base);
    };
    // Tyler 11-21: legacy plain-letter cold applications are not hunts; job posts return when the AI/ML video+demo hunt runs (rows with oneshot set).
    (E.jobs || []).filter(e => e.oneshot).forEach(e => rows.push({
      id: hid("job", e.ts, e.co), type: "job", lane: "jobs", target: e.co, signal: e.role, title: e.role, ts: e.ts,
      subs: [e.level, e.board].filter(Boolean), location: lane === "jobs" ? e.location || null : null, roleClass: e.role_class || null, logo: e.logo || null, url: e.url || null,
      nums: [], oneshot: e.oneshot, vsl: e.vsl || null, fit: null, status: e.status || "Staged", replyCount: e.replies ?? null,
      agent: jobs.backend?.agent, front: jobs.frontend?.agent, source: e.source || jobs.source, checked: jobs.checked,
      sends: [], log: [], contact: {name: e.co, ch: []}, repl: [], oss: e.one_shot_system || null, item: e.item_id || null,
    }));
    // Live post rows (live_refresh.py, last 48 h only): JOB POSTS = AI/ML engineer roles (backend sekhmet), UPWORK = AI/agent/automation/data jobs (backend upwork).
    // Legacy letter-application mail never lands here (Tyler 11-21); interview invites go to the Network roost below.
    const postRow = (e, lane, L) => ({
      id: hid(lane, e.link || e.what, e.co), found: e.found_at || null, type: lane === "jobs" ? "job" : "upwork", lane, target: e.co, signal: e.what, title: e.what,
      ts: e.signal_at || e.ts, subs: lane === "jobs" ? [e.board, e.level].filter(Boolean) : [e.oneshot_type, e.level].filter(Boolean),
      location: lane === "jobs" ? e.location || null : null, roleClass: e.employment || null, logo: e.board === "LinkedIn" ? null : e.logo || null, url: e.link || null,  // LinkedIn card logos are signed media URLs that 403 off-site
      nums: (e.chips && e.chips.length ? e.chips : [e.comp && ["comp", e.comp]].filter(Boolean)),
      // a built one-shot (hunts/oneshots/agent -> hunts-live.json) carries its own oneshot + vsl stage
      oneshot: e.oneshot || {kind: lane === "jobs" ? "video + demo" : e.oneshot_type, label: (lane === "jobs" ? "Video + demo" : e.oneshot_type[0].toUpperCase() + e.oneshot_type.slice(1)) + " · not built", ok: null},
      vsl: e.vsl || null, fit: null, status: e.status || "Found", agent: e.agent || L.backend?.agent, front: e.front || L.frontend?.agent || "eagle",
      source: e.src, checked: L.checked, closed: false, kind: null, sends: [], log: [{ts: e.found_at || e.ts, who: e.agent || L.backend?.agent, what: "found · " + e.src}],
      contact: {name: e.co, ch: lane === "jobs" ? [] : ["upwork"], job: e.job || null}, repl: [], raw: e, oss: e.one_shot_system || null, item: e.item_id || null,
      job_tag: e.job_tag ?? null,
    });
    (jobs.feed || []).filter(e => e.post).forEach(e => rows.push(postRow(e, "jobs", jobs)));
    (up.feed || []).filter(e => e.post).forEach(e => rows.push(postRow(e, "upwork", up)));
    (fund.feed || []).forEach(e => {
      const am = String(e.amount || "").match(/^(\$[\d.]+[KMB]?|indefinite)\s*(.*)$/i);
      const src = String(e.src || "").replace(/^SEC EDGAR /, "").replace(/ RSS$/, "");
      rows.push({
        id: hid("fund", e.ts, e.co), found: e.found_at || e.found || null, type: "funding", lane: "funding", target: e.co, signal: e.what === e.co ? null : e.what, title: e.what, ts: e.ts,
        subs: [e.round, src && src !== e.round ? src : null].filter(Boolean), url: e.link || null,
        nums: e.kind !== "news" && am ? [[am[2] || "raised", am[1]]] : [], logo: e.logo || null,
        oneshot: e.oneshot || null, vsl: e.vsl || null, fit: null, status: e.status || "Found", agent: fund.backend?.agent, front: fund.frontend?.agent, source: e.src || "funding feed",
        sends: [], log: [{ts: e.ts, who: fund.backend?.agent, what: (e.kind || "found").replace(/_/g, " ")}], contact: {name: e.co, ch: []}, repl: [],
        oss: e.one_shot_system || null, item: e.item_id || null,
      });
    });
    // INVESTOR hunt (investor_hunt.md): one row per ranked investor; the trigger = their latest similar bet. Sends HELD (Tyler 11-21).
    (inv.feed || []).forEach(e => {
      const money = n => n == null ? null : n >= 1e6 ? "$" + +(n / 1e6).toFixed(1) + "M" : "$" + Math.round(n / 1e3) + "K";
      // one number when both ends match ("$500K", never "$500K–$500K")
      const chk = e.check && (e.check.min || e.check.max) ? [...new Set([e.check.min && money(e.check.min), e.check.max && money(e.check.max)].filter(Boolean))].join("–") : null;
      rows.push({
        id: hid("inv", e.item_id), found: e.found_at || null, type: "investor", lane: "investor", target: e.investor, signal: e.what, title: e.what, ts: e.ts,
        subs: [...new Set([e.subtype, e.flag, e.lane && e.lane !== "cold" ? e.lane : null].filter(Boolean))], url: e.deal?.url || e.link || null,
        nums: [e.score != null && ["score", e.score], e.rank && ["rank", "#" + e.rank], chk && ["check", chk], e.similarity != null && ["similar", e.similarity]].filter(Boolean),
        logo: null, oneshot: e.oneshot || null, vsl: e.vsl || null, fit: e.score ?? null, status: e.status || "Held", agent: inv.backend?.agent, front: inv.frontend?.agent,
        source: e.link, sends: [], log: [{ts: e.found_at, who: inv.backend?.agent, what: e.trigger_fresh ? "fresh trigger" : "ranked"}],
        contact: {name: e.investor, ch: [e.email && "email", e.x && "x"].filter(Boolean)}, repl: [], raw: e, oss: e.one_shot_system || null, item: e.item_id || null,
      });
    });
    const q = up.queue || {};
    (q.ready || []).forEach(r => {
      const ts = tsIn(r.note);
      rows.push(upRow(r, {
        id: hid("up", r.slug), target: nice(r.slug), signal: (UM[r.slug] || {}).title || jobId(r.job), ts,
        oneshot: {kind: "demo", label: r.demo_ok ? "Demo ready" : "Demo gated", ok: !!r.demo_ok, url: r.demo}, vsl: "record",
        status: r.demo_ok ? "Staged" : "Blocked", source: r.source,
        sends: [], log: [{ts, who: up.backend?.agent, what: r.demo_ok ? "demo ready" : "show-gate 6/6/6"}],
        contact: {name: nice(r.slug), ch: ["upwork"], job: r.job},
      }));
    });
    (q.recorded || []).forEach(r => {
      const ts = tsIn(r.note), tk = String(r.note).match(/(\d+) takes ready/), du = String(r.note).match(/(\d+) s \(/);
      rows.push(upRow(r, {
        id: hid("up", r.slug), target: nice(r.slug), signal: (UM[r.slug] || {}).title || nice(r.slug), ts,
        oneshot: {kind: "vsl", label: [tk && tk[1] + " takes", du && du[1] + " s"].filter(Boolean).join(" · ") || "VSL", ok: true}, vsl: "recorded", status: "Recorded",
        source: r.source, sends: [], log: [{ts, who: up.frontend?.agent, what: r.note.split(" (")[0]}], contact: {name: nice(r.slug), ch: ["upwork"]},
      }));
    });
    (q.sent || []).filter(r => !isMohamed(r.slug)).forEach(r => {
      const m = UM[r.slug] || {};
      rows.push(upRow(r, {
        id: hid("up", r.slug, r.ts), target: /^~\d/.test(r.slug) ? (m.client || (m.title ? m.title.split(" | ")[0] : jobId(r.slug))) : r.slug, signal: m.title || r.file, ts: r.ts,
        oneshot: {kind: "vsl", label: "VSL", ok: true, file: r.file}, vsl: "sent", status: "Sent", source: r.source,
        sends: [{ts: r.ts, what: r.file, ch: "upwork"}], log: [{ts: r.ts, who: up.backend?.agent, what: "vsl_sent"}],
        contact: {name: r.slug, ch: ["upwork"]}, proposal: (String(r.note).match(/proposal (\d+)[^,]*/) || [])[0] || null,
      }));
    });
    // per-item timeline from the API (Posted -> One-shot built -> Recorded -> Text proposal -> VSL proposal); data only here
    // the row's primary time is when the job was POSTED (signal_at; investors: Found), never the send time (Tyler 11-22 ~5:08 AM)
    rows.forEach(r => { r.tl = (r.item && (d.timelines || {})[r.item]) || null; const p = r.tl?.primary; if (p?.at) { if (p.kind === "Posted") r.ts = p.at; r.shown = p.at; r.tsKind = p.kind; } });
    rows.forEach(r => { if (r.subs) r.subs = [...new Set(r.subs)]; });   // a chip appears once ("program program" was subtype + lane)
    rows.sort((a, b) => (b.ts ? Date.parse(b.ts) : -1) - (a.ts ? Date.parse(a.ts) : -1));
    // Tyler 11-22 ~3:59 AM MT: the old one-word "VSL" / talk-script pill "doesn't make sense". The one-shot is named by its label
    // (<hunt type> · <one-shot system> · <niche>, shown next to the title) and this pill carries what is BUILT in its package
    // (MVP live / Working demo / Diagram only / Script only / Not built), from the API's package read. No one-shot = no pill.
    // Tyler 11-22 ~4:55 AM MT: "MVP live" read as "IVP"; every piece says what it is, no acronyms ("working app", never "MVP")
    rows.forEach(r => {
      if (!r.oss) return;
      const d = demoOf(r);
      r.oneshot = r.oss.key ? {kind: d.ok ? "demo" : "video", label: "Demo: " + d.say, about: d.about, ok: d.ok, url: r.oss.url, file: r.oss.package} : null;
    });

    // ROOSTS: Clients (Mohamed's thread lives here) + Network
    const cl = d.roosts.find(r => r.id === "clients") || {rows: [], feed: []};
    const nw = d.roosts.find(r => r.id === "network") || {rows: [], feed: []};
    const roosts = [];
    cl.rows.forEach((c, i) => {
      const thread = (cl.feed || []).filter(e => (e.co || "").toLowerCase() === c.name.toLowerCase());
      roosts.push({
        id: "CL-" + (i + 1), type: "client", lane: "clients", target: c.name, signal: c.what, ts: thread[0]?.ts || null,
        stage: String(c.stage).split(":")[0], status: String(c.stage).split(":")[0], paid: c.paid, from: c.hunt, agent: cl.agent,
        sends: thread.filter(e => e.kind !== "client_reply").map(e => ({ts: e.ts, what: e.what, ch: c.hunt || "direct"})),
        repl: thread.filter(e => e.kind === "client_reply").map(e => ({ts: e.ts, what: e.what})),
        log: [{ts: cl.checked, who: cl.agent, what: "crm sync"}], contact: {name: c.name, ch: [c.hunt || "direct"]},
        source: cl.source, checked: cl.checked, vsl: null, oneshot: null, fit: null,
      });
    });
    nw.rows.forEach((p, i) => roosts.push({
      id: "NW-" + (i + 1), type: "network", lane: "network", target: p.name, signal: p.what, ts: p.at || null,
      stage: (p.channels || []).length + " ch", status: "Network", channels: p.channels || [], agent: nw.agent,
      sends: [], repl: [], log: [{ts: nw.checked, who: nw.agent, what: "roster sync"}], contact: {name: p.name, ch: p.channels || []},
      source: nw.source, checked: nw.checked, vsl: null, oneshot: null, fit: null,
    }));
    (nw.feed || []).filter(e => e.kind === "interview invite").forEach((e, i) => roosts.push({
      id: "IV-" + hid(e.ts, e.co), type: "network", lane: "network", target: e.co, signal: e.what, ts: e.ts,
      stage: "interview invite", status: "Interview", channels: ["email"], agent: "sekhmet",
      sends: [], repl: [{ts: e.ts, what: e.what}], log: [{ts: e.ts, who: "sekhmet", what: "interview invite · dev@"}], contact: {name: e.co, ch: ["email"]},
      source: e.src, checked: nw.checked, vsl: null, oneshot: null, fit: null,
    }));
    return {rows, roosts, funding: fund, funnels: {jobs: jobs.funnel, upwork: up.funnel}, copy_at: d.copy_at, built: d.built};
  }

  let DATA = null;
  // ROOSTS = replied/booked people from /api/roosts (opt/roosts.js), sorted by due soonest; never the feed's roster rows
  async function roostsInto(D) {
    if (!window.EERoosts) return;
    try { const r = await window.EERoosts.load(); D.roosts = r.rows; D.roostsBuilt = r.built; } catch (e) { D.roosts = []; }
  }
  async function load() {
    const d = await fetch(EE_API + "/api/feed").then(r => r.json());
    DATA = build(d);
    await roostsInto(DATA);
    return DATA;
  }

  // brand top bar (kept from the spike) + eye intro
  function brand() {
    return `<div class="brand"><img id="mark" src="/eye.png" alt="Eagle Eye"><div class="word"><b>EAGLE EYE</b><span>the networking machine</span></div></div>`;
  }
  function intro() {
    const root = document.documentElement;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || /nointro/.test(location.search)) { root.classList.add("intro-done"); return Promise.resolve(); }
    root.classList.add("intro-on");
    return new Promise(res => setTimeout(() => {
      const dock = () => { root.classList.remove("intro-on"); root.classList.add("intro-done"); res(); };
      if (document.startViewTransition) document.startViewTransition(dock); else dock();
    }, 430));
  }

  async function ask(lane, q) {
    try {
      const r = await fetch("/api/ask", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({q, lane, person: "tyler"})});
      const j = await r.json();
      return j.answer ? j.answer.replace(/\*\*/g, "") : "–";
    } catch (e) { return "–"; }
  }

  // filters (same four facets everywhere)
  const F = {type: null, status: null, vsl: null};
  const match = r => (!F.type || r.type === F.type) && (!F.status || r.status === F.status) && (!F.vsl || (F.vsl === "none" ? !r.vsl : r.vsl === F.vsl));
  const STATUS = ["Applied", "Found", "Staged", "Blocked", "Offer queued", "Offered", "Ready to record", "Recorded", "Sent", "Replied", "Held"];

  // full-page open: the row's box grows to the page (Motion), Esc / back reverses
  function openFrom(rowEl, page) {
    const M = window.Motion;
    const r = rowEl ? rowEl.getBoundingClientRect() : {top: innerHeight / 2, bottom: innerHeight / 2};
    page.hidden = false;
    page.scrollTop = 0;
    document.documentElement.classList.add("ee-open");          // lock the list behind; keys + wheel go to the page
    page.tabIndex = -1; page.focus({preventScroll: true});
    const from = `inset(${Math.max(0, r.top)}px 0px ${Math.max(0, innerHeight - r.bottom)}px 0px)`;
    if (!M || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    M.animate(page, {clipPath: [from, "inset(0px 0px 0px 0px)"]}, {duration: .42, easing: [.65, 0, .2, 1]});
    M.animate(page.querySelectorAll("[data-in]"), {opacity: [0, 1], y: [10, 0]}, {delay: M.stagger(.035, {startDelay: .18}), duration: .3});
  }
  function close(page, rowEl) {
    const M = window.Motion;
    document.documentElement.classList.remove("ee-open");
    if (document.activeElement === page) page.blur();
    if (!M || !rowEl || matchMedia("(prefers-reduced-motion: reduce)").matches) { page.hidden = true; return; }
    const r = rowEl.getBoundingClientRect();
    M.animate(page, {clipPath: ["inset(0px 0px 0px 0px)", `inset(${r.top}px 0px ${innerHeight - r.bottom}px 0px)`]}, {duration: .32, easing: [.65, 0, .2, 1]})
      .then(() => { page.hidden = true; page.style.clipPath = ""; });
  }
  function streamIn(els) {
    const M = window.Motion;
    if (!M || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    M.animate(els, {opacity: [0, 1], y: [-14, 0]}, {delay: M.stagger(.045), duration: .35, easing: [.2, .8, .2, 1]});
  }

  const ICON = {job: "job", upwork: "upwork", funding: "funding", investor: "investor", client: "client", network: "net"};
  const TYPE_ALL = {job: "Job post", upwork: "Upwork", funding: "Funding", investor: "Investor", client: "Client", network: "Network"};

  // one controller for all three options: tabs, filters, popovers, open/close, ask
  function app(o) {
    let view = location.hash.includes("roosts") ? "roosts" : "hunts", rowEl = null;
    const rowsFor = () => view === "hunts" ? DATA.rows.filter(match) : DATA.roosts;
    const find = id => DATA.rows.concat(DATA.roosts).find(r => r.id === id);
    function paint(anim) {
      document.querySelectorAll("[data-tab]").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === view));
      o.list.innerHTML = o.renderList(view, rowsFor());
      if (o.bar) o.bar.innerHTML = o.renderBar(view);
      if (anim) streamIn(o.list.querySelectorAll("[data-row]"));
    }
    function open(id, el) {
      const r = find(id); if (!r) return;
      rowEl = el || o.list.querySelector(`[data-row="${id}"]`);
      const list = view === "hunts" ? DATA.rows.filter(match) : DATA.roosts;
      o.page.innerHTML = o.renderDetail(r, {view, idx: list.findIndex(x => x.id === id) + 1, n: list.length, prev: list[list.findIndex(x => x.id === id) - 1]?.id, next: list[list.findIndex(x => x.id === id) + 1]?.id});
      openFrom(rowEl, o.page);
      history.replaceState(null, "", "#" + view + "/" + id);
    }
    function shut() { if (o.page.hidden) return; close(o.page, rowEl); history.replaceState(null, "", "#" + view); }
    document.addEventListener("click", e => {
      const t = e.target.closest("[data-tab]");
      if (t) { view = t.dataset.tab; close(o.page, null); history.replaceState(null, "", "#" + view); paint(true); return; }
      const pop = e.target.closest("[data-pop]");
      document.querySelectorAll("[data-popbody]").forEach(b => { if (!pop || b.dataset.popbody !== pop.dataset.pop) b.hidden = true; });
      if (pop) { const b = document.querySelector(`[data-popbody="${pop.dataset.pop}"]`); if (b) b.hidden = !b.hidden; return; }
      const f = e.target.closest("[data-f]");
      if (f) { const k = f.dataset.f, v = f.dataset.v || null; F[k] = F[k] === v ? null : v; paint(true); return; }
      const go = e.target.closest("[data-go]");
      if (go) { open(go.dataset.go); return; }
      const c = e.target.closest("[data-close]");
      if (c) { shut(); return; }
      const r = e.target.closest("[data-row]");
      if (r) open(r.dataset.row, r);
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") shut(); });
    document.addEventListener("submit", async e => {
      const f = e.target.closest("form[data-ask]"); if (!f) return;
      e.preventDefault();
      const q = f.q.value.trim(), out = f.querySelector("[data-ans]") || f.parentElement.querySelector("[data-ans]");
      if (!q || !out) return;
      out.hidden = false; out.textContent = "…";
      out.textContent = await ask(f.dataset.ask, q);
    });
    (async () => {
      await load();
      paint(true);
      const m = location.hash.match(/#(?:hunts|roosts)\/([\w-]+)/);
      if (m) setTimeout(() => open(m[1]), 500);
    })();
    // LIVE, NO POLLING (chief 11-22; Tyler: live updates, no polling, no manual refresh). The server pushes every write
    // over SSE (/api/stream: INSERT events -> pg_notify -> one LISTEN -> this socket). Any event (a burst = one refresh)
    // re-reads the feed: new rows stream in on top, changed rows repaint in place. Each (re)connect resyncs once, so a
    // dropped link never leaves the page stale; EventSource reconnects by itself.
    const sig = r => JSON.stringify(r);
    const live = window.__eeLive = {events: 0, refreshes: 0, at: 0, last: "", state: "connecting"};
    async function refresh() {
      try {
        const d = await fetch(EE_API + "/api/feed?" + Date.now(), {cache: "no-store"}).then(r => r.json());
        const next = build(d), old = new Map(DATA.rows.concat(DATA.roosts).map(r => [r.id, sig(r)]));
        await roostsInto(next);
        DATA = next;
        live.refreshes++; live.at = Date.now();
        if (o.page && !o.page.hidden) return;
        const list = view === "hunts" ? next.rows.filter(match) : next.roosts;
        const fresh = list.filter(r => !old.has(r.id)), changed = list.some(r => old.has(r.id) && old.get(r.id) !== sig(r));
        if (view === "roosts" || changed || !o.addRows) { if (fresh.length || changed) paint(false); return; }   // in place
        if (fresh.length) o.addRows(view, fresh);
      } catch (e) {}
    }
    let soon = null;
    const kick = ev => { live.events++; live.last = ev && ev.type || ""; clearTimeout(soon); soon = setTimeout(refresh, 250); };
    if (window.EventSource) {
      const es = new EventSource(EE_API + "/api/stream");
      let first = true;
      es.addEventListener("ready", () => { live.state = "live"; if (!first) { clearTimeout(soon); soon = setTimeout(refresh, 250); } first = false; });
      es.onerror = () => { live.state = "reconnecting"; };
      es.onmessage = kick;
      // SSE named events reach only a listener of that exact name: every type the server writes (rest.ts `${noun}.${verb}`
      // and the custom ones) is registered here
      const NOUNS = ["item", "company", "person", "roost", "touch", "reply", "recording", "one_shot", "one_shot_system", "next_step", "hunt_type", "viewer", "event"];
      const VERBS = ["created", "updated", "deleted", "restored"];
      const EXTRA = ["item.found", "item.qualified", "item.merged", "fact.applied", "touch.queued", "touch.sent", "touch.opened", "touch.watched",
                     "touch.cancelled", "reply.received", "recording.final", "one_shot.ready"];
      for (const t of new Set([...NOUNS.flatMap(n => VERBS.map(v => n + "." + v)), ...EXTRA])) es.addEventListener(t, kick);
    }
    return {open, shut, paint};
  }

  return {DEMO, demoOf, app, ICON, TYPE_ALL, $, esc, ago, day, exact, zone, icon, TYPE, VSL, VSL_L, STATUS, F, match, load, brand, intro, ask, openFrom, close, streamIn, get data() { return DATA; }};
})();
