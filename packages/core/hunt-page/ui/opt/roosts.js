// ROOSTS view (Tyler card 11-21 ~8:50 PM): a row = someone who replied or booked. Columns lead with the next step + when,
// then the owner (Tyler or an agent), who it is, and the last thing they said; sorted by due soonest (the API sorts).
// Data: GET /api/roosts on the Eagle Eye v2 server (replies, bookings, next_steps). No rows -> the empty-state component.
const EERoosts = (() => {
  const API = (location.hostname.endsWith(".ts.net") ? "https://ra.tail4016d7.ts.net:8451" : "") + "/api/roosts";
  const css = `
.rrow{position:relative;display:grid;grid-template-columns:236px 104px minmax(0,1fr) minmax(0,1.25fr) 112px;align-items:center;column-gap:16px;min-height:72px;
  padding:10px 24px;border-bottom:1px solid var(--ink-5);cursor:pointer;transition:background .14s ease,box-shadow .18s ease}
.rrow:hover{background:var(--gold-2);box-shadow:inset 2px 0 0 var(--gold-9)}
.rhead{display:grid;grid-template-columns:236px 104px minmax(0,1fr) minmax(0,1.25fr) 112px;column-gap:16px;align-items:center;height:32px;padding:0 24px;
  border-bottom:1px solid var(--ink-5);background:var(--ink-2);font:600 11px/1 Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-10)}
.rhead span:last-child{text-align:right}
.nx{display:flex;min-width:0;flex-direction:column;align-items:flex-start;gap:5px}
.nx .what{display:inline-flex;max-width:100%;align-items:center;gap:6px;height:26px;padding:0 10px 0 8px;border-radius:7px;border:1px solid var(--gold-7);
  background:var(--gold-3);color:var(--gold-12);font:600 13px/1 Inter,sans-serif;letter-spacing:-.005em}
.nx .what .i{flex:none;width:15px;height:15px;color:var(--gold-10)}
.nx .what b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.nx .what.none{border-style:dashed;border-color:var(--ink-8);background:transparent;color:var(--ink-10)}
.due{display:inline-flex;align-items:center;gap:6px;font:500 12px/1 Inter,sans-serif;color:var(--ink-11);font-variant-numeric:tabular-nums;white-space:nowrap}
.due::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--ink-8)}
.due.soon{color:var(--gold-11)}.due.soon::before{background:var(--gold-9)}
.due.over{color:var(--gold-12)}.due.over::before{background:var(--gold-10);animation:ping 1.6s infinite}
.due.open{color:var(--ink-10)}
.own{display:inline-flex;max-width:100%;align-items:center;gap:5px;height:24px;padding:0 8px;border-radius:999px;border:1px solid var(--ink-7);background:var(--ink-3);
  font:500 12px/1 Inter,sans-serif;color:var(--ink-12);text-transform:capitalize;white-space:nowrap;justify-self:start}
.own .i{flex:none;width:13px;height:13px;color:var(--ink-10)}
.own.tyler{border-color:var(--gold-8);color:var(--gold-12)}.own.tyler .i{color:var(--gold-10)}
.who{display:flex;min-width:0;flex-direction:column;gap:6px}
.who .tgt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.who .chips{display:flex;min-width:0;gap:5px;flex-wrap:nowrap;overflow:hidden}
.said{display:flex;min-width:0;align-items:center;gap:8px}
.said q{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:400 13px/1.35 Inter,sans-serif;color:var(--ink-12);quotes:"\\201C" "\\201D"}
.said .ch{flex:none}
.rrow .age{min-width:0}
@media (max-width:1100px){.rrow,.rhead{grid-template-columns:200px 96px minmax(0,1fr) minmax(0,1fr) 80px;column-gap:12px;padding-left:16px;padding-right:16px}}
@media (max-width:760px){.rhead{display:none}.rrow{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"nx age" "who own" "said said";row-gap:8px;padding:12px 16px}
  .rrow .nx{grid-area:nx}.rrow .own{grid-area:own;justify-self:end}.rrow .who{grid-area:who}.rrow .said{grid-area:said}.rrow .age{grid-area:age}}`;
  if (!document.getElementById("ee-roosts-css")) { const s = document.createElement("style"); s.id = "ee-roosts-css"; s.textContent = css; document.head.appendChild(s); }

  const AGENT_TYPES = {client: "client", investor: "investor", funding: "funding", job_post: "job", upwork: "upwork", partner: "client", network: "network"};
  // API row -> the feed's row shape (detail.js renders it); keeps the roost fields for the list
  function map(r) {
    const type = AGENT_TYPES[r.type] || "client";
    return {
      id: "R-" + r.id, roost: r, type, lane: "roosts", target: r.name, signal: r.last?.said || null, ts: r.last?.at || null,
      status: r.status, stage: r.status, subs: [r.origin && r.origin !== type ? r.origin : null].filter(Boolean),
      agent: r.next && r.next.owner !== "tyler" ? r.next.owner : null, front: null, vsl: null, oneshot: null, fit: null,
      sends: [], repl: r.last?.at ? [{ts: r.last.at, what: r.last.said || (r.last.channel || "") + " message"}] : [],
      log: r.next ? [{ts: r.next.due, who: r.next.owner, what: r.next.what}] : [], contact: {name: r.name, ch: r.last?.channel ? [r.last.channel] : []},
    };
  }
  async function load() {
    const d = await fetch(API + "?" + Date.now(), {cache: "no-store"}).then(x => x.json());
    return {rows: (d.rows || []).map(map), built: d.built};
  }

  const day = 86400e3;
  function dueLabel(ts) {
    const d = new Date(ts), now = Date.now(), dt = d - now;
    const sameDay = new Date().toDateString() === d.toDateString();
    const t = d.toLocaleTimeString([], {hour: "numeric", minute: d.getMinutes() ? "2-digit" : undefined}) + " " + EE.zone(ts);   // viewer's zone, labelled
    if (sameDay) return "Today " + t;
    if (dt > 0 && dt < 6 * day) return d.toLocaleDateString([], {weekday: "short"}) + " " + t;
    return d.toLocaleDateString([], {month: "short", day: "numeric"}) + (Math.abs(dt) < 6 * day ? " " + t : "");
  }
  const dueClass = ts => { const dt = Date.parse(ts) - Date.now(); return dt < 0 ? "over" : dt < day ? "soon" : ""; };
  const STEP_ICON = w => /call|meet/i.test(w) ? "rec" : /reply|answer/i.test(w) ? "reply" : /proposal|send|write/i.test(w) ? "send" : "check";

  function row(x) {
    const {esc, icon, TYPE_ALL, ICON} = EE, r = x.roost, n = r.next;
    const next = n ? `<span class="what" title="${esc(n.what)}">${icon(STEP_ICON(n.what))}<b>${esc(n.what)}</b></span>
        ${n.due ? `<span class="due ${dueClass(n.due)}" data-due="${esc(n.due)}" title="${esc(new Date(n.due).toLocaleString())}">${esc(dueLabel(n.due))}</span>` : `<span class="due open">—</span>`}`
      : `<span class="what none">${icon("check")}<b>—</b></span>`;
    const owner = n ? `<span class="own ${n.owner === "tyler" ? "tyler" : ""}" title="Owner">${icon(n.owner === "tyler" ? "user" : "bot")}${esc(n.owner)}</span>` : `<span></span>`;
    const said = r.last ? (r.last.said ? `<q title="${esc(r.last.said)}">${esc(r.last.said)}</q>` : "") + (r.last.channel ? `<span class="sub ch">${icon(r.last.channel === "upwork" ? "upwork" : r.last.channel === "email" ? "mail" : "reply")}${esc(r.last.channel)}</span>` : "") : "";
    const since = r.last?.at ? (() => { const m = Math.max(0, Math.round((Date.now() - Date.parse(r.last.at)) / 60000)); return m <= 120 ? m + " min" : m < 2880 ? Math.round(m / 60) + " h" : Math.round(m / 1440) + " d"; })() : "";
    return `<div data-row="${esc(x.id)}" class="rrow">
      <div class="nx">${next}</div>
      ${owner}
      <div class="who"><span class="tgt">${esc(r.name)}</span><div class="chips"><span class="tb ${esc(x.type)}">${icon(ICON[x.type] || "client")}${esc(TYPE_ALL[x.type] || x.type)}</span>${r.status ? `<span class="sub">${esc(r.status)}</span>` : ""}${r.origin && r.origin !== x.type && r.origin !== r.status ? `<span class="sub">${esc(r.origin)}</span>` : ""}</div></div>
      <div class="said">${said}</div>
      <span class="age">${since ? `<b>${esc(since)}</b><span>${esc(EE.day(r.last.at))}</span>` : ""}</span>
    </div>`;
  }
  function list(rows) {
    if (!rows.length) return `<div class="empty">${EE.icon("client")}No roosts</div>`;
    return `<div class="rhead"><span>Next</span><span>Owner</span><span>Who</span><span>Last said</span><span>Last</span></div>` + rows.map(row).join("");
  }
  function bar(rows) {
    const {icon} = EE, due = rows.filter(r => r.roost.next?.due && Date.parse(r.roost.next.due) - Date.now() < day).length;
    return `<span class="inline-flex h-7 items-center gap-1.5 rounded-md border border-line px-2 text-[13px] text-mute">${icon("client", "!w-3.5 !h-3.5")}<b class="text-ink font-semibold">${rows.length}</b></span>
      <span class="inline-flex h-7 items-center gap-1.5 rounded-md border border-line px-2 text-[13px] text-mute">${icon("rec", "!w-3.5 !h-3.5")}<b class="text-pale font-semibold">${due}</b>24 h</span>
      <span class="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[13px] text-dim">${icon("down", "!w-3.5 !h-3.5")}Due</span>`;
  }
  setInterval(() => document.querySelectorAll(".due[data-due]").forEach(el => { el.className = "due " + dueClass(el.dataset.due); }), 30000);
  return {load, list, row, bar, map};
})();
window.EERoosts = EERoosts;
