// Eagle Eye hunt DETAIL page (full page, Linear issue-view structure: main column + properties rail). Black/gold.
// Contract: the feed page calls window.EEDetail.render(row, {nav: {view, idx, n, prev, next}, EE}) and inserts the HTML.
// Rule (Tyler 11-21): no Ask bar, zero sentences. Components carry the data. A card renders only when it has real data.
//
// PKG = the real package files a hunt row points at, read on Ra 2026-11-21 (the snapshot has no per-hunt package data):
//   ai-automation: knowledge@horus/vsl-airport-queue net/work/vsl/ai-automation/{vsl-90s-context.md, stage.json, demo.md,
//     architecture.yaml, tyler-script.md (v15), runsheet.md, ai-automation-architecture.png}; Upwork ledger
//     /home/upwork/.claude/state/net/upwork/ledger.jsonl (job_read, demo_ready, vsl_pick, job_private); takes
//     /srv/vsl/2026-11-18/ai-automation-take*.{json,md,mp4} + frames; git log of the package folder; demo host probe 530 at 22:11Z.
//   ai-data: /home/eagle/dev/eagle-eye/studio.json (takes, scores, tasks); net/work/vsl/ai-data/{stage.json, vsl-90s-context.md, ai-data-vsl.png}.
(() => {
  const PKG = {
    "ai-automation": {
      client: "AI Automation Engineer",
      job: "~022122526809409647896",
      jobUrl: "https://www.upwork.com/jobs/~022122526809409647896",
      chips: [["budget", "$20–30/h"], ["bid", "$20/h"], ["client spent", "$928K"], ["hires", "86"], ["proposals", "50"], ["fit", "85"]],
      read: "2026-11-17T06:59:32Z",
      closedAt: "2026-11-18T02:32:48Z",
      issue: "upwork #7570",
      demo: {
        url: "https://ai-automation.utopiamodels.ai", img: "/assets/ai-automation-architecture.png", ready: "2026-11-17T08:35:00Z",
        http: 530, checked: "2026-11-21T22:11:57Z", host: "novaserver",
        facts: [["agents", "3"], ["approval queue", "1"], ["WebKit runs", "10/10"], ["invoice", "5.0–18.4 s"], ["model", "claude-sonnet-5-5"]],
        flow: ["Inbound email", "Public host", "Page", "Coordinator agent", ["Invoice agent", "Campaign drafter"], "Approval queue", ["Sample ledger · outbox", "Action log"]],
        stack: ["Next.js 16", "Cloudflare tunnel", "n8n export", "sample data"],
      },
      script: {
        v: "v15", secs: 60, file: "tyler-script.md",
        beats: [
          {name: "What you will see", secs: 10, lines: [
            ["0:00", "I'm going through your whole post right now."],
            [null, "You want AI assistants for invoicing and email, with a person approving every step."],
            [null, "Here is how I would build it, on one page."]]},
          {name: "How one email moves", secs: 40, lines: [
            ["0:10", "An email comes in through one public address."],
            ["0:16", "The page shows it in an inbox."],
            ["0:21", "A coordinator reads it and decides what it is: an invoice request, or nothing to do."],
            ["0:27", "For an invoice, Claude reads the email and pulls out the line items, and plain code adds up the totals, so the model never does the math."],
            ["0:37", "The result waits in an approval queue."],
            [null, "Nothing happens until a person approves it."],
            ["0:42", "Once approved, it goes to QuickBooks or Gmail, and every step is written to a log that cannot be edited."]]},
          {name: "Next step", secs: 10, lines: [
            ["0:50", "The next build is connecting your QuickBooks and your email, behind this same approval step, and I can start it the day you reply."]]},
        ],
      },
      takes: [
        {n: "take 7", f: "ai-automation-take7-take1", at: "2026-11-18T07:50:54Z", s: 104.92, words: 271, verdict: "url", img: "/assets/ai-automation-take7-take1.jpg"},
        {n: "take 6", f: "ai-automation-take6-take1", at: "2026-11-18T07:48:27Z", s: 17.72, words: 13, verdict: "url", img: "/assets/ai-automation-take6-take1.jpg"},
        {n: "take 5", f: "ai-automation-take5-take1", at: "2026-11-18T07:38:40Z", s: 41.65, words: 118, verdict: "url", img: "/assets/ai-automation-take5-take1.jpg"},
        {n: "take 4", f: "ai-automation-take3-take1", at: "2026-11-18T07:14:18Z", s: 97.82, words: 33, verdict: "url", img: "/assets/ai-automation-take3-take1.jpg"},
        {n: "take 3", f: "ai-automation-take3", at: "2026-11-18T07:08:14Z", s: 30.92, words: 48, verdict: null, img: "/assets/ai-automation-take3.jpg"},
        {n: "take 2", f: "ai-automation-take2", at: "2026-11-18T05:38:47Z", s: 10.6, words: null, verdict: "noreview", img: "/assets/ai-automation-take2.jpg"},
        {n: "take 1", f: "ai-automation-take1", at: "2026-11-18T05:32:49Z", s: 17.42, words: 22, verdict: null, img: "/assets/ai-automation-take1.jpg"},
      ],
      events: [
        {ts: "2026-11-21T09:34:27Z", who: "horus", what: "Script cues", tag: "v15"},
        {ts: "2026-11-18T11:02:35Z", who: "horus", what: "Script", tag: "v15 · 60 s"},
        {ts: "2026-11-18T09:22:13Z", who: "horus", what: "Driver check", tag: "12/12"},
        {ts: "2026-11-18T07:56:23Z", who: "dust", what: "Diagram title", tag: "architecture.png"},
        {ts: "2026-11-18T07:50:54Z", who: "horus", what: "Takes", tag: "7 · last 1:45"},
        {ts: "2026-11-18T02:32:48Z", who: "upwork", what: "Job private", tag: "closed", warn: true},
        {ts: "2026-11-18T01:10:11Z", who: "dust", what: "Demo run fixed", tag: "10/10 WebKit"},
        {ts: "2026-11-18T00:48:06Z", who: "horus", what: "Script", tag: "v7"},
        {ts: "2026-11-17T23:45:52Z", who: "dust", what: "VSL pick", tag: "fit 85"},
        {ts: "2026-11-17T08:35:00Z", who: "dust", what: "Demo ready", tag: "live"},
        {ts: "2026-11-17T06:59:32Z", who: "upwork", what: "Job read", tag: "fit 85"},
      ],
      agents: {backend: "upwork", demo: "dust", script: "horus", frontend: "eagle"},
      sources: [
        ["stage.json", "net/work/vsl/ai-automation/stage.json"], ["vsl-90s-context.md", "net/work/vsl/ai-automation/vsl-90s-context.md"],
        ["architecture.yaml", "net/work/vsl/ai-automation/architecture.yaml"], ["tyler-script.md", "net/work/vsl/ai-automation/tyler-script.md"],
        ["runsheet.md", "net/work/vsl/ai-automation/runsheet.md"], ["ledger.jsonl", "/home/upwork/.claude/state/net/upwork/ledger.jsonl"],
        ["takes", "/srv/vsl/2026-11-18/ai-automation-take*"],
      ],
    },
    "ai-data": {
      client: "AI Data Engineer client",
      job: "~022122386398617111601",
      jobUrl: "https://www.upwork.com/jobs/~022122386398617111601",
      chips: [["bid", "$50/h"], ["proposals", "4"], ["connects", "26"], ["fit", "35"], ["size", "10–99"], ["rating", "★ 5.0 · 7"]],
      place: "Chicago",
      read: "2026-11-16T20:15:00Z",
      demo: {img: "/assets/ai-data-vsl.png", facts: [["studio score", "88"]], stack: ["Azure Databricks", "Python", "MCP"]},
      takes: [
        {n: "take 4", at: "2026-11-17T07:24:20Z", s: 76.4, verdict: "ready"},
        {n: "take 3", at: "2026-11-17T07:22:23Z", s: 123.67, score: 88, verdict: "ready"},
        {n: "take 1", at: "2026-11-17T07:21:07Z", s: 78.4, score: 90, verdict: "ready"},
      ],
      tasks: [["Script", "wip"], ["Record", "wfa"], ["Review", "wfa"]],
      events: [
        {ts: "2026-11-17T07:24:20Z", who: "horus", what: "Take", tag: "4 · 1:16"},
        {ts: "2026-11-17T06:33:00Z", who: "tyler", what: "Take note", tag: "terminal cut off"},
        {ts: "2026-11-16T20:15:00Z", who: "upwork", what: "Post read", tag: "fleetmail #6612"},
      ],
      agents: {backend: "upwork", script: "horus", frontend: "eagle"},
      sources: [["studio.json", "/home/eagle/dev/eagle-eye/studio.json"], ["stage.json", "net/work/vsl/ai-data/stage.json"], ["vsl-90s-context.md", "net/work/vsl/ai-data/vsl-90s-context.md"]],
    },
  };

  let X = null; // shared.js helpers (EE is a global lexical const, not a window property): ctx.EE first
  const E = () => X || (X = (typeof EE !== "undefined" ? EE : window.EE));
  const esc = s => E().esc(s);
  const icon = (n, c) => E().icon(n, c);
  const ago = ts => E().ago(ts);
  const exact = ts => E().exact(ts);
  const mmss = s => s == null ? "–" : Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0");
  const host = u => { try { return new URL(u).host.replace(/^www\./, ""); } catch (e) { return u; } };
  const TYPE = {job: "Job post", upwork: "Upwork", funding: "Funding", client: "Client", network: "Network"};
  const ICON = {job: "job", upwork: "upwork", funding: "funding", client: "client", network: "net"};
  const STAGES = [["record", "Record"], ["recorded", "Recorded"], ["sent", "Sent"]];
  // agent avatars: shades of the one palette (/opt/tokens.css), never a new hue
  const AG = {upwork: "var(--gold-11)", dust: "var(--gold-10)", horus: "var(--ink-11)", eagle: "var(--gold-9)", sekhmet: "var(--gold-12)", tyler: "var(--ink-12)", funding: "var(--gold-11)"};

  const slugOf = r => {
    const m = String(r.source || "").match(/net\/work\/vsl\/([\w-]+)\//);
    if (m) return m[1];
    const j = r.contact?.job; if (j) for (const k in PKG) if (PKG[k].job === j) return k;
    const t = String(r.target || "").toLowerCase().trim().replace(/\s+/g, "-");
    return PKG[t] ? t : null;
  };

  // ---- atoms ----
  const badge = t => `<span class="ed-tb ${t}">${icon(ICON[t] || "job")}${esc(TYPE[t] || t)}</span>`;
  const sub = (s, cls = "") => `<span class="ed-sub ${cls}">${s}</span>`;
  const stc = s => "st s-" + String(s).toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");
  const num = (k, v) => `<span class="ed-num"><b>${esc(v)}</b>${esc(k)}</span>`;
  const av = (who, big) => `<span class="ed-av ${big ? "lg" : ""}" style="--c:${AG[who] || "var(--gold-9)"}" title="${esc(who)}">${esc(String(who || "·")[0].toUpperCase())}</span>`;
  const agent = (who, role) => who ? `<span class="ed-agent">${av(who)}<span>${esc(who)}</span>${role ? `<em>${esc(role)}</em>` : ""}</span>` : "";
  const time = ts => ts ? `<time class="ed-time" title="${esc(exact(ts))}">${esc(ago(ts))}</time>` : "";
  const mark = r => r.logo ? `<img class="ed-logo" src="${esc(r.logo)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ed-mono',textContent:'${esc(String(r.target || "·")[0])}'}))">`
    : `<span class="ed-mono">${badge(r.type).includes("upwork") ? icon("upwork") : esc(String(r.target || "·")[0])}</span>`;
  const card = (key, ic, title, count, body, extra = "") => `<section data-in class="ed-card" data-card="${key}">
      <header><span class="ed-ch">${icon(ic)}${esc(title)}</span>${count != null ? `<span class="ed-count">${esc(count)}</span>` : ""}<span class="ed-sp"></span>${extra}</header>
      <div class="ed-body">${body}</div></section>`;
  const prop = (k, v) => v ? `<div class="ed-prop"><span class="k">${esc(k)}</span><span class="v">${v}</span></div>` : "";
  const ext = (u, label) => u ? `<a class="ed-link" href="${esc(u)}" target="_blank" rel="noopener">${icon("link")}${esc(label || host(u))}</a>` : "";
  const chOf = c => /upwork/i.test(c) ? "upwork" : /mail|letter/i.test(c) ? "mail" : /linkedin/i.test(c) ? "user" : /call|phone/i.test(c) ? "reply" : "send";

  function stageBar(v) {
    const at = STAGES.findIndex(s => s[0] === v);
    return `<div class="ed-stage" title="VSL stage">${STAGES.map(([k, l], i) => `<span class="st ${i < at ? "done" : i === at ? "now" : ""}">
      <i>${i < at ? icon("check") : ""}</i>${l}</span>${i < STAGES.length - 1 ? `<span class="bar ${i < at ? "done" : ""}"></span>` : ""}`).join("")}</div>`;
  }

  // ---- funding hunt package, served static at /hunts/<slug>/{script.md, tabs.txt, evidence/} (funding agent writes them) ----
  const HA = {};
  const huntSlug = r => { const m = String(r.oneshot?.label || "").match(/talk-script\s+([\w-]+)/i); if (m) return m[1]; if (r.type === "funding" && r.oneshot?.file) return r.oneshot.file;
    // Upwork rows: the built VSL lives at /hunts/<package>/take.mp4 (r.oss.package; R2 store path vsl/dust, knowledge#18689)
    const pk = r.type === "upwork" && String(r.oss?.package || "").split("/").filter(Boolean).pop(); return pk && /^[\w-]+$/.test(pk) ? pk : null; };
  const txt = u => fetch(u, {cache: "no-store"}).then(x => x.ok ? x.text() : "").catch(() => "");
  function loadHunt(slug) {
    if (HA[slug]) return HA[slug].p;
    const base = "/hunts/" + encodeURIComponent(slug) + "/";
    // read the folder listing first and request only files it lists: a take not recorded yet is never a 404 in the console
    const p = txt(base).then(ls => { const has = f => ls.includes(`href="${f}"`);
      return Promise.all([has("script.md") ? txt(base + "script.md") : "", has("tabs.txt") ? txt(base + "tabs.txt") : "", has("evidence/") ? txt(base + "evidence/") : "",
        has("take.mp4") ? fetch(base + "take.mp4", {method: "HEAD", cache: "no-store"}).then(x => x.ok ? x.headers.get("Last-Modified") || "yes" : "").catch(() => "") : ""]); }).then(([md, tabs, idx, take]) => {
      const takes = [];
      md.replace(/<!--[\s\S]*?-->/g, "").split("\n").forEach(l => {
        l = l.trim(); if (!l || /^# /.test(l)) return;
        const h = l.match(/^##\s*(\d+)\s*[·.\-:]?\s*(.*?)\s*(?:\((\d+)\s*s\))?$/);
        if (h) takes.push({n: +h[1], name: h[2], secs: h[3] ? +h[3] : null, lines: []});
        else if (takes.length && !/^#/.test(l)) takes[takes.length - 1].lines.push(l.replace(/^[-*]\s+/, ""));
      });
      const ev = [...idx.matchAll(/href="([^"?#\/]+\.(?:png|jpe?g|webp))"/gi)].map(m => base + "evidence/" + m[1]);
      return HA[slug].d = {takes, tabs: tabs.split("\n").map(x => x.trim()).filter(x => /^https?:/.test(x)), ev, base, take: take ? base + "take.mp4" : null, takeAt: take && take !== "yes" ? take : null};
    });
    HA[slug] = {p, d: null};
    return p;
  }
  function huntCards(slug, d) {
    if (!d) return `<div data-ha="${esc(slug)}"></div>`;
    const C = [];
    // the finished take (silent take + Tyler's cloned voice, voice/voiceover.sh) to rewatch here
    if (d.take) C.push(card("take", "video", "Take", null, `<video class="ed-take" src="${esc(d.take)}" controls playsinline preload="metadata" style="width:100%;max-height:70vh;border-radius:8px;background:#000"></video>`, d.takeAt ? sub(esc(new Date(d.takeAt).toLocaleString())) : ""));
    const nl = d.takes.reduce((n, t) => n + t.lines.length, 0);
    if (d.takes.length) {
      let k = 0;
      const body = `<div class="ed-script">${d.takes.map(t => `<div class="ed-beat"><div class="ed-beat-h"><span class="ed-tk">${t.n}</span><span>${esc(t.name)}</span>${t.secs ? `<span class="ed-sub">${t.secs} s</span>` : ""}<span class="ed-sub">${t.lines.length}</span>${d.tabs[t.n - 1] ? `<a class="ed-link ed-tabref" href="${esc(d.tabs[t.n - 1])}" target="_blank" rel="noopener">${icon("link")}${esc(host(d.tabs[t.n - 1]))}</a>` : ""}</div>
        <ol>${t.lines.map(l => `<li class="nt"><span class="n">${++k}</span><span class="l">${esc(l)}</span></li>`).join("")}</ol></div>`).join("")}</div>`;
      const secs = d.takes.reduce((n, t) => n + (t.secs || 0), 0);
      C.push(card("script", "script", "Script", `${nl} lines`, body, `${sub(d.takes.length + " takes")}${secs ? sub("~" + secs + " s") : ""}${sub(esc(slug), "mono")}`));
    }
    if (d.tabs.length) {
      const body = `<ol class="ed-tabs">${d.tabs.map((u, i) => `<li><span class="ed-tk">${i + 1}</span><a class="ed-tabchip" href="${esc(u)}" target="_blank" rel="noopener" title="${esc(u)}">${icon("link")}<b>${esc(host(u))}</b><span>${esc((() => { try { const x = new URL(u); return (x.pathname + x.search).replace(/\/$/, ""); } catch (e) { return ""; } })())}</span></a></li>`).join("")}</ol>`;
      C.push(card("tabs", "net", "Tabs", d.tabs.length, body, sub("take order")));
    }
    if (d.ev.length) {
      const body = `<div class="ed-ev">${d.ev.map(u => { const f = u.split("/").pop(); const ph = /phone/i.test(f); return `<a class="ed-evi ${ph ? "ph" : ""}" href="${esc(u)}" target="_blank" rel="noopener" title="${esc(f)}"><img src="${esc(u)}" alt="" loading="lazy"><span class="ed-shot-tag">${icon(ph ? "user" : "film")}${esc(f.replace(/\.\w+$/, ""))}</span></a>`; }).join("")}</div>`;
      C.push(card("evidence", "search", "Evidence", d.ev.length, body));
    }
    return C.join("");
  }

  // ---- stage track (knowledge#18540): Posted -> Built -> Recorded -> Sent. Each stage = a check + its time; a stage's clock stops when the
  // next stage happens, and every clock stops at Sent (no ticking clock after Sent).
  const dur = (a, b) => { const m = Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 60000)); if (m < 60) return m + " min";
    const h = Math.floor(m / 60), x = m % 60; return h < 24 ? h + " h" + (x ? " " + x + " min" : "") : Math.floor(h / 24) + " d" + (h % 24 ? " " + (h % 24) + " h" : ""); };
  const secs = s => s < 60 ? Math.round(s) + " s" : Math.floor(s / 60) + " min " + String(Math.round(s % 60)).padStart(2, "0") + " s";
  // the proposal on Upwork (Tyler 11-24): its id comes from upwork's send ledger, carried by /api/feed timelines
  const propLink = id => id ? `<a class="ed-prop" href="https://www.upwork.com/nx/proposals/${encodeURIComponent(id)}" target="_blank" rel="noopener">Proposal ↗</a>` : "";
  function track(r) {
    const st = r.tl?.steps; if (!st || r.type === "investor") return "";
    const by = k => st.find(s => s.key === k) || {};
    const sent = by("vsl").state === "done" ? by("vsl") : by("text").state === "done" ? by("text") : by("vsl");
    const rec = by("recorded"), auto = !!(rec.auto_intro || r.tl.vsl?.auto_intro);
    const S = [{k: "posted", l: "Posted", s: by("posted")}, {k: "built", l: "Built", s: by("built")}, {k: "recorded", l: "Recorded", s: rec}, {k: "sent", l: "Sent", s: sent}]
      .filter(x => x.k !== "posted" || x.s.state === "done");
    const reached = x => x.s.state === "done" || x.s.state === "done_no_time";
    const done = reached(S[S.length - 1]);
    const now = new Date().toISOString();
    return `<ol class="ed-track" data-track data-sent="${done ? 1 : 0}" aria-label="Stages">${S.map((x, i) => {
      const nx = S.slice(i + 1).find(y => y.s.state === "done"), at = x.s.at;
      // clock: this stage's time until the next one happened; only the stage in progress runs, and nothing runs once Sent
      const clock = !at ? "" : nx ? dur(at, nx.s.at) : x.k === "sent" || done ? "" : dur(at, now);
      const run = !!at && !nx && !done && x.k !== "sent";
      const note = x.k === "recorded" && auto ? `<span class="ed-sub gold">Auto intro${rec.render_s ? " · " + esc(secs(rec.render_s)) + " render" : ""}</span>` : "";
      return `<li class="ed-ts ${reached(x) ? "on" : ""}" data-stage="${x.k}"><span class="dot">${reached(x) ? icon("check") : ""}</span>
        <div><b>${x.l}</b>${note}${x.k === "sent" ? propLink(x.s.proposal_id || r.tl.vsl?.proposal_id) : ""}<span class="when">${at ? esc(exact(at)) : reached(x) ? "time not recorded" : "pending"}</span>
        ${clock ? `<span class="clk ${run ? "run" : ""}" title="${run ? "running: this stage has not ended" : "time in this stage"}">${esc(clock)}</span>` : ""}</div></li>`; }).join("")}</ol>`;
  }

  // ---- foldable sections: the VSL that was sent, and its analysis (what vsls.utopiamodels.ai showed per job)
  const fold = (key, ic, title, extra, body) => `<details class="ed-card ed-fold" data-card="${key}" data-in><summary><span class="ed-ch">${icon(ic)}${esc(title)}</span><span class="ed-sp"></span>${extra || ""}<span class="chev"></span></summary><div class="ed-body">${body}</div></details>`;
  function vslCards(r) {
    const v = r.tl?.vsl; if (!v) return [];
    const C = [];
    if (v.url) C.push(fold("vsl", "video", "VSL", v.sent_at ? sub("sent " + esc(exact(v.sent_at))) : "",
      `<video class="ed-take" src="${esc(/^\/api\//.test(v.url) ? EE_API + v.url : v.url)}" controls playsinline preload="metadata" style="width:100%;max-height:70vh;border-radius:8px;background:#000"></video>
       <div class="ed-row" style="margin-top:10px">${v.sent_at ? `<span class="ed-kv">${icon("send")}sent ${esc(exact(v.sent_at))}</span>` : ""}${v.proposal_id ? `<span class="ed-kv mono">proposal ${esc(v.proposal_id)}</span>` : ""}</div>`));
    const kv = [["Status", r.status], ["Proposal", v.proposal_id], ["Sent", v.sent_at && exact(v.sent_at)], ["Bid", v.bid_usd != null ? "$" + v.bid_usd : null],
      ["Connects", v.connects], ["Video", v.file], ["Kind", v.file ? (v.auto_intro ? "Auto intro" : "Recorded by hand") : null],
      ["Length", v.length_s && secs(v.length_s)], ["Intro", v.intro_s && secs(v.intro_s)], ["Size", v.size_mb && v.size_mb + " MB"], ["Voice", v.voice],
      ["Rendered", v.rendered_at && exact(v.rendered_at)], ["Render time", v.render_s && secs(v.render_s)], ["Checksum", v.sha], ["Note", v.note]].filter(([, x]) => x != null && x !== "");
    C.push(fold("analysis", "log", "Analysis", sub(esc(kv.length + " facts")), `<dl class="ed-an">${kv.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${esc(x)}</dd>`).join("")}</dl>`));
    return C;
  }
  // the cover letter that was sent (Tyler 11-24: he has never seen one): the exact text, collapsed, next to the VSL
  function letterCard(r) {
    const L = r.tl?.letter; if (!L) return [];
    return [fold("letter", "mail", "Cover letter", L.sent_at ? sub("sent " + esc(exact(L.sent_at))) : "",
      `<pre class="ed-letter" style="white-space:pre-wrap;word-break:break-word;font:inherit;margin:0">${esc(L.text)}</pre>
       <div class="ed-row" style="margin-top:10px">${L.proposal_id ? `<span class="ed-kv mono">proposal ${esc(L.proposal_id)}</span>` : ""}</div>`)];
  }
  document.addEventListener("click", e => {
    const l = e.target.closest("[data-letter-open]");
    if (l) { const d = document.querySelector('details[data-card="letter"]'); if (d) { d.open = true; d.scrollIntoView({behavior: "smooth", block: "center"}); } return; }
    const b = e.target.closest("[data-vsl-open]"); if (!b) return;
    const d = document.querySelector('details[data-card="vsl"]'); if (!d) return;
    d.open = true; d.scrollIntoView({behavior: "smooth", block: "center"});
    const v = d.querySelector("video"); if (v) v.play().catch(() => {});
  });

  // ---- take-over (knowledge#18939): FULL VSL / INTRO VSL on a hunt. FULL stops the intro countdown, claims the job and loads its script into Vizier
  // (POST /api/take -> take_api.py on Ra). The state line polls GET /api/take every 3 s and counts the intro timer down every second.
  const takeLabel = s => !s || !s.found ? "no package yet" : s.take === "full" && s.state !== "sent" && s.state !== "recording" && s.state !== "claimed" ? "Full VSL picked: waiting for Tyler"
    : s.state === "waiting" || s.state === "due" ? (s.remaining_s > 0 ? "Intro sends in " : "Intro sends now") : s.label || s.state;
  function takeBody(job, s) {
    const on = k => s && s.take === k ? " on" : "";
    const chip = s && s.found ? `<span class="ed-sub ${s.state === "claimed" || s.take === "full" ? "gold" : ""}" data-take-label data-send-at="${esc(s.send_at || "")}">${esc(takeLabel(s))}</span>` : sub("not ready: pick now, it builds first");
    const voice = s && s.found && (s.by === "voice" || s.claim_by === "voice") ? sub("by voice") : "";
    const sc = s && s.script_loaded_at ? sub(`script in Vizier ${time(s.script_loaded_at)}`, "ok") : "";
    return `<div class="ed-row" data-take-job="${esc(job)}"><button type="button" class="ed-sub ed-vslchip${on("full")}" data-take="full">FULL VSL</button>
      <button type="button" class="ed-sub ed-vslchip${on("intro")}" data-take="intro">INTRO VSL</button>${chip}${voice}${sc}</div>`;
  }
  const takeFetch = (job, init) => fetch("/api/take" + (init ? "" : "?job=" + encodeURIComponent(job)), init).then(x => x.json()).catch(() => null);
  function takeRefresh() {
    const el = document.querySelector("[data-take-job]"); if (!el) return;
    takeFetch(el.dataset.takeJob).then(s => { const cur = document.querySelector("[data-take-job]"); if (s && cur && cur.dataset.takeJob === el.dataset.takeJob) cur.outerHTML = takeBody(el.dataset.takeJob, s); });
  }
  setInterval(takeRefresh, 3000);
  setInterval(() => document.querySelectorAll("[data-take-label][data-send-at]").forEach(l => {
    if (!l.dataset.sendAt || !/^Intro sends in/.test(l.textContent)) return;
    const s = Math.max(0, Math.round((Date.parse(l.dataset.sendAt) - Date.now()) / 1000));
    l.textContent = s ? "Intro sends in " + String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0") : "Intro sends now";
  }), 1000);
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-take]"); if (!b) return;
    const el = b.closest("[data-take-job]"); if (!el) return;
    const job = el.dataset.takeJob; b.disabled = true;
    takeFetch(job, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({job, take: b.dataset.take})})
      .then(s => { const cur = document.querySelector("[data-take-job]"); if (cur && cur.dataset.takeJob === job) cur.outerHTML = s && s.found ? takeBody(job, s) : takeBody(job, null).replace("not ready: pick now, it builds first", esc((s && s.error) || "not saved, try again")); });
  });

  function render(r, ctx = {}) {
    if (ctx.EE) X = ctx.EE;
    const nav = ctx.nav || ctx || {};
    const P = PKG[slugOf(r)] || null;
    // funding hunt rows: the raw feed entry (hunts-live.json via tyler.json) carries contact, fit checks and timestamps the row drops
    const raw = r.type === "funding" ? ((E().data?.funding?.feed) || []).find(e => e.co === r.target && (e.ts === r.ts || e.signal_at === r.ts)) || {} : {};
    const contact = Object.assign({}, r.contact || {}, raw.contact || {});
    const checks = raw.fit && typeof raw.fit === "object" ? Object.entries(raw.fit) : (r.fitChecks ? Object.entries(r.fitChecks) : []);
    const fitN = checks.filter(([, v]) => v).length;
    const hunt = !!r.vsl || r.type === "upwork" || (r.type === "job" && r.oneshot && r.oneshot.kind !== "letter");
    const lab = String(r.oneshot?.label || "");
    const oTakes = +((lab.match(/(\d+) takes/) || [])[1] || 0), oSecs = +((lab.match(/~?(\d+) s\b/) || [])[1] || 0);
    const takes = P?.takes || [];
    const sends = r.sends || [];
    const repl = (r.repl || []).filter(x => x.ts);
    const subs = (r.subs || []).slice();
    const closed = r.closed || !!P?.closedAt;
    const best = takes.reduce((m, t) => Math.max(m, t.s || 0), 0);
    const scriptLines = P?.script ? P.script.beats.reduce((n, b) => n + b.lines.length, 0) : 0;
    const title = P?.client || r.target;

    // ---- top bar: breadcrumb + prev/next (Linear) ----
    const top = `<div class="ed-top">
      <button data-close class="ed-back" title="Esc">${icon("left")}<span>${esc(nav.view === "roosts" ? "Roosts" : "Hunts")}</span></button>
      <span class="ed-crumb">›</span>${badge(r.type)}<span class="ed-crumb-t">${esc(title)}</span>
      <span class="ed-sp"></span>
      <kbd>esc</kbd>
      ${nav.n ? `<span class="ed-pos">${esc(nav.idx)} / ${esc(nav.n)}</span>` : ""}
      <button ${nav.prev ? `data-go="${esc(nav.prev)}"` : "disabled"} data-dir="prev" class="ed-nav" title="Previous (k)">${icon("up")}</button>
      <button ${nav.next ? `data-go="${esc(nav.next)}"` : "disabled"} data-dir="next" class="ed-nav" title="Next (j)">${icon("down")}</button>
    </div>`;

    // ---- header ----
    const kpis = [
      r.fit != null && num("fit", r.fit),
      checks.length && num("fit", fitN + "/" + checks.length),
      raw.usd && num("raised", "$" + (raw.usd >= 1e6 ? +(raw.usd / 1e6).toFixed(1) + "M" : Math.round(raw.usd / 1e3) + "K")),
      takes.length && num("takes", takes.length),
      !takes.length && oTakes && num("takes", oTakes),
      !takes.length && oSecs && num("length", "~" + oSecs + " s"),
      best && num("longest", mmss(best)),
      scriptLines && num("script lines", scriptLines),
      hunt && num("sends", sends.length),
      (hunt || r.replyCount != null) && num("replies", repl.length || r.replyCount || 0),
      r.type === "job" && (r.nums || []).length && (r.nums || []).map(([k, v]) => num(k, v)).join(""),
      r.type === "funding" && !raw.usd && (r.nums || []).map(([k, v]) => num(k, v)).join(""),
    ].filter(Boolean).join("");
    // Tyler 11-22 ~5:00 AM MT: the page leads with the one-shot SYSTEM, then the niche, then the demo and its link (never the URL first)
    const vslChip = r => (r.tl?.vsl?.url ? `<button type="button" class="ed-sub gold ed-vslchip" data-vsl-open title="Open the sent VSL">VSL ▶</button>` : "")
      + (r.tl?.letter ? `<button type="button" class="ed-sub gold ed-vslchip" data-letter-open title="Open the cover letter that was sent">Cover letter</button>` : "");
    const ossHead = r => !r.oss ? "" : `<div class="ed-row ed-oss">${r.oss.key
      ? `<a class="ed-sub gold wrap" href="#" data-oss-system="${esc(r.oss.system)}" data-oss-row="${esc(JSON.stringify({...r.oss, target: r.target}))}" title="Open the one-shot pipeline">${icon("video")}<span class="ed-k">One-shot system:</span>${esc(((s=>String(s||'').replace(/\s+(entire|intro)\s+vsl\b.*$/i,'').replace(/\s+one-shot$/i,'').trim()||String(s||'')))(r.oss.system))}</a>${vslChip(r)}`
        + (r.oss.niche ? sub(`<span class="ed-k">Niche:</span>${esc(r.oss.niche)}`, "wrap") : "")
        + (d => `<span class="ed-sub wrap ${d.ok ? "ok" : d.ok === false ? "warn" : ""}" title="${esc(d.about)}"><span class="ed-k">Demo:</span>${esc(d.say)}</span>`)(E().demoOf(r))
        + (r.oss.url ? ext(r.oss.url, r.oss.state === "MVP live" ? "Open working app" : r.oss.state === "Working demo" ? "Open working version" : "Open diagram") : "")
      : sub(`${esc(r.oss.hunt)} · No one-shot yet`, "warn") + vslChip(r)}</div>`;
    const head = `<div data-in class="ed-head">
      <div class="ed-tags">${badge(r.type)}${subs.map(s => sub(esc(s))).join("")}${r.roleClass ? sub(esc(r.roleClass)) : ""}${closed ? sub(`${icon("x")}Job closed${P?.closedAt ? " · " + esc(ago(P.closedAt)) : ""}`, "warn") : ""}${r.status ? sub(esc(r.status), stc(r.status)) : ""}</div>
      <div class="ed-title">${mark(r)}<h1>${esc(title)}</h1></div>
      ${ossHead(r)}
      ${track(r)}
      ${kpis ? `<div class="ed-kpis">${kpis}</div>` : ""}
    </div>`;

    // ---- cards ----
    const C = [];

    // Take over (knowledge#18939): only a job post that is not sent yet
    if (r.type === "job" && (P?.job || r.contact?.job) && !r.tl?.vsl?.sent_at) {
      const tj = String(P?.job || r.contact.job);
      C.push(card("take", "video", "Take over", null, takeBody(tj, null), sub("full VSL stops the intro")));
      setTimeout(takeRefresh, 0);
    }

    // Timeline (Tyler 11-22 ~5:10 AM MT): Posted -> One-shot built -> Recorded -> Text proposal -> VSL proposal, each labelled, MT
    if (r.tl?.steps) {
      const st = {done: "", done_no_time: "", skipped: "warn", pending: "warn"};
      const gaps = new Map(); let prev = null;
      r.tl.steps.forEach(s => { if (s.state === "done") { if (prev) gaps.set(s.key, dur(prev, s.at)); prev = s.at; } });
      const gapOf = s => gaps.get(s.key);
      const p0 = r.tl.steps[0], v = r.tl.steps[4], total = p0?.state === "done" && v?.state === "done" ? dur(p0.at, v.at) : null;
      const say = s => s.state === "done" ? `${s.auto_intro ? "Auto intro · " : ""}${esc(exact(s.at))}` : s.state === "done_no_time" ? "done, time not recorded" : s.state === "skipped" ? (s.key === "text" ? "not sent" : "none") : "pending";
      const body = `<ol class="ed-tl act">${r.tl.steps.map(s => `<li><span class="dot ch">${icon(s.state === "done" || s.state === "done_no_time" ? "check" : s.state === "skipped" ? "x" : "rec")}</span>
          <span class="what">${esc(s.label)}</span>${gapOf(s) ? `<span class="ed-dim" title="time from the previous step">+${esc(gapOf(s))}</span>` : ""}<span class="ed-sp"></span>${s.state === "done" ? `<span class="ed-dim">${esc(ago(s.at))}</span>` : ""}${sub(say(s), st[s.state])}</li>`).join("")}</ol>
        ${r.tl.stuck ? `<div class="ed-kv" style="margin-top:10px;color:var(--warn,#d97706)" data-stuck="1">Stuck: ${esc(r.tl.stuck.hours)} h at "${esc(r.tl.stuck.stage)}", budget ${esc(r.tl.stuck.budget_h)} h, waiting for "${esc(r.tl.stuck.waiting_for)}"</div>` : ""}
        ${total ? `<div class="ed-kv" style="margin-top:10px">${esc(r.tl.steps[0].label)} to ${esc(r.tl.steps[4].label.replace(/ sent$/, ""))} sent: <b style="margin-left:4px">${esc(total)}</b></div>` : ""}`;
      C.push(card("timeline", "log", "Timeline", null, body));
      C.push(...vslCards(r), ...letterCard(r));
    }

    // Signal
    {
      const fchips = r.type === "funding" ? [raw.round && ["round", raw.round], raw.usd && ["amount", "$" + (raw.usd >= 1e6 ? +(raw.usd / 1e6).toFixed(1) + "M" : Math.round(raw.usd / 1e3) + "K")], raw.us && ["", "US"], raw.src && ["", raw.src]].filter(Boolean) : null;
      const chips = (P?.chips || fchips || r.nums || []).filter(([k]) => !(P && k === "fit")).map(([k, v]) => num(k, v)).join("");
      const ck = checks.length ? `<div class="ed-row ed-checks">${checks.map(([k, v]) => `<span class="ed-ck ${v ? "on" : ""}">${icon(v ? "check" : "x")}${esc(k.replace(/_/g, " "))}</span>`).join("")}</div>` : "";
      const meta = [r.location || P?.place, r.kind, r.type === "job" && r.subs?.[0]].filter(Boolean);
      const link = P?.jobUrl || raw.link || r.url;
      const posted = P?.read || raw.signal_at || r.ts;
      const body = `<div class="ed-sig">
          <div class="ed-sig-t">${esc(r.title || r.signal || title)}</div>
          <div class="ed-row">${chips}</div>
          <div class="ed-row ed-meta">${posted ? `<span class="ed-kv">${icon("log")}${r.type === "funding" ? (raw.kind === "launch" ? "launched" : "filed") : r.type === "job" ? "posted" : "read"} ${time(posted)}</span>` : ""}
            ${meta.map(m => `<span class="ed-kv">${esc(m)}</span>`).join("")}
            ${P?.job || r.contact?.job ? `<span class="ed-kv mono">${esc(P?.job || r.contact.job)}</span>` : ""}
            ${P?.issue ? `<span class="ed-kv mono">${esc(P.issue)}</span>` : ""}
            ${r.proposal ? `<span class="ed-kv mono">${esc(r.proposal)}</span>` : ""}
            <span class="ed-sp"></span>${raw.url && raw.url !== link ? ext(raw.url) : ""}${ext(link)}</div>${ck}</div>`;
      C.push(card("signal", r.type === "funding" ? "funding" : "log", "Signal", null, body));
    }

    // One-shot
    const o = r.oneshot;
    if (P?.demo || (o && o.kind !== "letter")) {
      const d = P?.demo || {};
      const url = d.url || o?.url;
      const up = d.http ? (d.http < 400) : null;
      const body = `<div class="ed-one">
          ${d.img ? `<a class="ed-shot" href="${esc(d.img)}" target="_blank"><img src="${esc(d.img)}" alt="" loading="lazy"><span class="ed-shot-tag">${icon("film")}architecture.png</span></a>` : ""}
          <div class="ed-one-side">
            ${r.oss?.key ? `<div class="ed-row">${sub(`<span class="ed-k">One-shot system:</span>${esc(r.oss.system)}`, "gold wrap")}${r.oss.niche ? sub(`<span class="ed-k">Niche:</span>${esc(r.oss.niche)}`, "wrap") : ""}</div>` : ""}
            <div class="ed-row">${o ? lab.split(" · ").map((x, i) => sub(i === 0 && o.ok ? `${icon("check")}${esc(x)}` : esc(x), i === 0 ? (o.ok ? "ok" : o.ok === false ? "warn" : "") : "")).join("") : ""}</div>
            ${url ? `<div class="ed-demo">${ext(url, r.oss?.key ? (r.oss.state === "MVP live" ? "Open working app" : r.oss.state === "Working demo" ? "Open working version" : "Open diagram") : undefined)}${up != null ? `<span class="ed-http ${up ? "ok" : "warn"}" title="probed ${esc(exact(d.checked))}"><i></i>${esc(d.http)}${d.host && !up ? " · " + esc(d.host) + " off" : ""}</span>` : ""}</div>` : ""}
            ${o?.file ? `<div class="ed-kv mono">${icon("film")}${esc(o.file)}</div>` : ""}
            ${d.ready ? `<div class="ed-kv">${icon("check")}demo ready ${time(d.ready)}</div>` : ""}
            ${(d.facts || []).length ? `<div class="ed-row">${d.facts.map(([k, v]) => num(k, v)).join("")}</div>` : ""}
            ${(d.stack || []).length ? `<div class="ed-row">${d.stack.map(s => sub(esc(s))).join("")}</div>` : ""}
          </div></div>
          ${d.flow && !d.img ? `<div class="ed-flow">${d.flow.map(n => Array.isArray(n) ? `<span class="fork">${n.map(x => `<span class="node ${/agent|drafter/i.test(x) ? "ai" : ""}">${esc(x)}</span>`).join("")}</span>` : `<span class="node ${/agent/i.test(n) ? "ai" : /queue/i.test(n) ? "gate" : ""}">${esc(n)}</span>`).join(`<span class="arr">${icon("right")}</span>`)}</div>` : ""}`;
      C.push(card("oneshot", "video", "One-shot", null, body, r.oss?.key ? sub(esc(r.oss.system)) : o?.kind ? sub(esc(o.kind)) : ""));
    }

    // funding hunt: script / tabs / evidence from /hunts/<slug>/ (async: placeholder swaps in when loaded)
    const hs = !P && huntSlug(r);
    if (hs) {
      const h = HA[hs];
      C.push(huntCards(hs, h && h.d));
      if (!h || !h.d) loadHunt(hs).then(d => document.querySelectorAll(`[data-ha="${CSS.escape(hs)}"]`).forEach(el => {
        const t = document.createElement("template"); t.innerHTML = huntCards(hs, d); el.replaceWith(t.content);
      }));
    }

    // Script: the lines are the data
    if (P?.script) {
      const s = P.script;
      let k = 0;
      const body = s.beats.map(b => `<div class="ed-beat"><div class="ed-beat-h"><span>${esc(b.name)}</span><span class="ed-sub">${b.secs} s</span><span class="ed-sub">${b.lines.length}</span></div>
        <ol>${b.lines.map(([t, l]) => `<li><span class="n">${++k}</span><span class="t">${t ? esc(t) : ""}</span><span class="l">${esc(l)}</span></li>`).join("")}</ol></div>`).join("");
      C.push(card("script", "script", "Script", `${scriptLines} lines`, `<div class="ed-script">${body}</div>`, `${sub(esc(s.v))}${sub("~" + s.secs + " s")}${sub(esc(s.file), "mono")}`));
    }

    // Recordings
    if (takes.length) {
      const V = {url: ["URL seen", "warn"], short: ["short", ""], noreview: ["no review", ""], ready: ["ready", "ok"]};
      const body = `<div class="ed-takes">${takes.map(t => `<div class="ed-take" title="${esc(t.f || t.n)}">
          <div class="thumb">${t.img ? `<img src="${esc(t.img)}" alt="" loading="lazy">` : icon("film")}<span class="dur">${mmss(t.s)}</span></div>
          <div class="ed-take-m"><b>${esc(t.n)}</b>${t.verdict ? sub(esc(V[t.verdict][0]), V[t.verdict][1]) : ""}</div>
          <div class="ed-take-m dim">${time(t.at)}${t.words != null ? `<span>${t.words} w</span>` : ""}${t.score != null ? `<span>score ${t.score}</span>` : ""}</div>
        </div>`).join("")}</div>
        ${P.tasks ? `<div class="ed-row" style="margin-top:12px">${P.tasks.map(([k, v]) => sub(`${esc(k)} · ${esc(v)}`, v === "wip" ? "warn" : "")).join("")}</div>` : ""}`;
      C.push(card("takes", "film", "Recordings", takes.length, body, sub(`longest ${mmss(best)}`)));
    }

    // Sends
    if (sends.length) {
      const body = `<ol class="ed-tl">${sends.map(s => `<li><span class="dot ch">${icon(chOf(s.ch || ""))}</span>
          <span class="ed-sub">${esc(s.ch || "send")}</span><span class="ed-kv mono">${esc(s.what)}</span><span class="ed-sp"></span>${time(s.ts)}</li>`).join("")}</ol>`;
      C.push(card("sends", "send", "Sends", sends.length, body));
    }

    // Replies
    if (repl.length) {
      const who = r.contact?.name || r.target;
      const body = `<ol class="ed-tl">${repl.map(x => `<li>${av(who)}<span class="ed-sub ok">${icon("reply")}reply</span>
          ${x.what ? `<span class="ed-quote" title="${esc(x.what)}">${esc(x.what)}</span>` : ""}<span class="ed-sp"></span>${time(x.ts)}</li>`).join("")}</ol>`;
      C.push(card("replies", "reply", "Replies", repl.length, body));
    }

    // Agent activity
    {
      const ev = (P?.events || []).slice();
      const fa = r.agent || "funding";
      if (raw.ready_at) ev.push({ts: raw.ready_at, who: r.front || "eagle", what: "Ready to record", tag: lab.split(" · ").slice(1).join(" · ") || null});
      if (raw.found_at) ev.push({ts: raw.found_at, who: fa, what: "Found", tag: checks.length ? "fit " + fitN + "/" + checks.length : null});
      if (raw.signal_at) ev.push({ts: raw.signal_at, who: fa, what: raw.kind === "launch" ? "Launch" : "Signal", tag: raw.src || null});
      (r.log || []).forEach(l => { if (l.ts && !ev.some(e => e.ts === l.ts)) ev.push({ts: l.ts, who: l.who, what: String(l.what || "").replace(/_/g, " ")}); });
      ev.sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts));
      if (ev.length) {
        const body = `<ol class="ed-tl act">${ev.map(e => `<li>${av(e.who)}<span class="who">${esc(e.who || "–")}</span><span class="what">${esc(e.what)}</span>
            ${e.tag ? sub(esc(e.tag), e.warn ? "warn" : "") : ""}<span class="ed-sp"></span>${time(e.ts)}</li>`).join("")}</ol>`;
        C.push(card("activity", "bot", "Activity", ev.length, body));
      }
    }

    // ---- right rail: properties ----
    const A = P?.agents || {backend: r.agent, frontend: r.front};
    const evs = (P?.events || []).map(e => e.ts).concat((r.log || []).map(l => l.ts), sends.map(s => s.ts), repl.map(x => x.ts)).filter(Boolean).sort();
    const created = P?.read || evs[0] || r.ts;
    const updated = evs[evs.length - 1] || r.ts;
    const rail = `<aside class="ed-rail">
      <div data-in class="ed-group"><div class="ed-gh">Properties</div>
        ${prop("Status", r.status ? sub(esc(r.status), stc(r.status)) : "")}
        ${prop("Job", r.job_tag ? `<b data-jobtag style="font-family:ui-monospace,monospace">Job ${esc(r.job_tag)}</b> <span class="ed-dim">say &quot;job ${esc(r.job_tag)}&quot;</span>` : "")}
        ${prop("Hunt", badge(r.type))}
        ${prop("One-shot system", !r.oss ? "" : r.oss.key ? sub(icon(r.oss.take === "entire" ? "film" : r.oss.take === "none" ? "link" : "video") + esc(r.oss.system), "gold wrap") : sub(`${esc(r.oss.hunt)} · No one-shot yet`, "warn"))}
        ${prop("Niche", r.oss?.niche ? sub(esc(r.oss.niche), "wrap") : "")}
        ${prop("Demo", r.oss?.key ? (d => `<span class="ed-sub wrap ${d.ok ? "ok" : d.ok === false ? "warn" : ""}" title="${esc(d.about)}">${esc(d.say)}</span>`)(E().demoOf(r)) : "")}
        ${prop("Demo page", r.oss?.url ? ext(r.oss.url, r.oss.state === "MVP live" ? "Working app" : r.oss.state === "Working demo" ? "Working version" : "Diagram") : "")}
        ${prop("Subtype", subs.length ? subs.map(s => sub(esc(s))).join("") : (r.kind ? sub(esc(r.kind)) : ""))}
        ${prop("Fit", checks.length && r.fit == null ? `<span class="ed-fit"><i style="--p:${Math.round(fitN / checks.length * 100)}%"></i><b>${fitN}/${checks.length}</b></span>` : "")}
        ${prop("Fit", r.fit != null ? `<span class="ed-fit"><i style="--p:${Math.min(100, +r.fit || 0)}%"></i><b>${esc(r.fit)}</b></span>` : "")}
        ${prop("Location", r.location || P?.place ? esc(r.location || P.place) : "")}
      </div>
      ${contact.email || contact.linkedin || contact.role ? `<div data-in class="ed-group"><div class="ed-gh">Contact</div>
        <div class="ed-person">${av(contact.name || r.target, true)}<div><b>${esc(contact.name || r.target)}</b>${contact.role ? `<span>${esc(contact.role)}</span>` : ""}</div></div>
        <div class="ed-chans">${contact.email ? `<a class="ed-chan" href="mailto:${esc(contact.email)}">${icon("mail")}${esc(contact.email)}</a>` : ""}
          ${contact.linkedin ? `<a class="ed-chan" href="${esc(contact.linkedin)}" target="_blank" rel="noopener">${icon("user")}${esc(contact.linkedin.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>` : ""}
          ${contact.x ? `<a class="ed-chan" href="${esc(contact.x)}" target="_blank" rel="noopener">${icon("x")}${esc(contact.x.replace(/^https?:\/\//, ""))}</a>` : ""}
          ${contact.github ? `<a class="ed-chan" href="${esc(contact.github)}" target="_blank" rel="noopener">${icon("cmd")}${esc(contact.github.replace(/^https?:\/\//, ""))}</a>` : ""}</div>
      </div>` : ""}
      <div data-in class="ed-group"><div class="ed-gh">Agents</div>
        ${prop("Backend", agent(A.backend))}
        ${prop("Demo", agent(A.demo))}
        ${prop("Script", agent(A.script))}
        ${prop("Frontend", agent(A.frontend))}
      </div>
      <div data-in class="ed-group"><div class="ed-gh">Dates</div>
        ${prop(r.tl?.primary?.kind || "Posted", r.tl?.primary?.at ? `${time(r.tl.primary.at)}<span class="ed-dim">${esc(exact(r.tl.primary.at))}</span>` : created ? `${time(created)}<span class="ed-dim">${esc(exact(created))}</span>` : "")}
        ${prop("Found", raw.found_at ? `${time(raw.found_at)}<span class="ed-dim">${esc(exact(raw.found_at))}</span>` : "")}
        ${prop("One-shot built", raw.ready_at ? `${time(raw.ready_at)}<span class="ed-dim">${esc(exact(raw.ready_at))}</span>` : "")}
        ${prop("Demo ready", P?.demo?.ready ? `${time(P.demo.ready)}<span class="ed-dim">${esc(exact(P.demo.ready))}</span>` : "")}
        ${prop("Closed", P?.closedAt ? `${time(P.closedAt)}<span class="ed-dim">${esc(exact(P.closedAt))}</span>` : "")}
        ${(r.tl?.steps || []).filter(s => ["recorded", "text", "vsl"].includes(s.key) && s.at).map(s => prop(s.label, `${time(s.at)}<span class="ed-dim">${esc(exact(s.at))}</span>${propLink(s.proposal_id)}`)).join("")}
      </div>
      <div data-in class="ed-group"><div class="ed-gh">Links</div>
        ${prop(r.type === "funding" ? "Signal" : "Post", ext(P?.jobUrl || raw.link || r.url))}
        ${prop("Demo", ext(P?.demo?.url || r.oneshot?.url))}
        ${prop("Website", ext(r.website || raw.url))}
      </div>
      <div data-in class="ed-group"><div class="ed-gh">Sources</div>
        <div class="ed-srcs">${(P?.sources || (r.source ? [[String(r.source).split("/").pop(), r.source]] : [])).map(([l, p]) => `<span class="ed-src" title="${esc(p)}">${icon("script")}${esc(l)}</span>`).join("")}</div>
      </div>
    </aside>`;

    return `<div class="ed">${top}<div class="ed-grid"><main class="ed-main"><div class="ed-col">${head}${C.join("")}</div></main>${rail}</div></div>`;
  }

  // j/k and Left/Right walk the feed while the page is open (Esc/back is handled by the app).
  // Up/Down are NOT taken: they scroll the page (chief 11-22: the laptop could not scroll a hunt page by keys).
  document.addEventListener("keydown", e => {
    const pg = document.querySelector("#page");
    if (!pg || pg.hidden || e.target.closest("input,textarea")) return;
    const dir = e.key === "j" || e.key === "ArrowRight" ? "next" : e.key === "k" || e.key === "ArrowLeft" ? "prev" : null;
    if (!dir) return;
    const b = pg.querySelector(`.ed-nav[data-dir="${dir}"][data-go]`);
    if (b) { e.preventDefault(); b.click(); }
  });

  window.EEDetail = {render, PKG};
})();
