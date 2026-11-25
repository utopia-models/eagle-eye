// knowledge#17946 + #18326: click the "One-shot system" chip (hunt list or hunt detail) -> full-screen one-shot pipeline view.
// Served by the LIVE Eagle Eye origin (Ra :8797, public/opt/arch.js). Everything shown is read from feeds:
//   /pipelines.json (wi/registry/pipelines.yaml): stages + each stage's provenance (inputs, generator, checks, output)
//   /offer.json     (MAX-FOUNDER-PACKAGE-FINAL.md "The offer" via _infra/scripts/offer-feed.py): THE OFFER panel
// The chip carries the row (data-oss-row = its r.oss record), so the view shows THIS row's stage and facts.
// Pure render (archFlow, stageDetail, offerPanel) is exported for opt/test_arch.mjs.
(function (root) {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Tyler 11-24: the system is "Upwork"; intro vs entire is a property of the job (its take), never part of the system name.
  const sysName = s => String(s || "").replace(/\s+(entire|intro)\s+vsl\b.*$/i, "").replace(/\s+one-shot$/i, "").trim() || String(s || "");
  const pick = (P, name) => {
    const ps = (P && P.pipelines) || [], n = sysName(name).toLowerCase();
    return ps.find(p => p.id === n) || ps.find(p => String(p.title).toLowerCase().includes(n)) || ps[0] || null;
  };
  const NONE = "source not recorded";
  const list = v => (Array.isArray(v) ? v : v ? [v] : []);
  const isOffer = s => /offer/i.test(s.stage);
  // The row's current stage: the feed's own `stage` when the row carries it, else the stage its demo state has reached.
  const AT = { "Not built": /^(build|component built)$/i, "Working demo": /^(validate|diagram)$/i, "MVP live": /^(record|vsl)$/i };
  function currentStage(pl, row) {
    if (!pl || !row) return null;
    const by = n => pl.stages.find(s => s.stage.toLowerCase() === String(n).toLowerCase());
    if (row.stage && by(row.stage)) return { name: by(row.stage).stage, via: "row stage" };
    const re = AT[row.state]; const s = re && pl.stages.find(x => re.test(x.stage));
    return s ? { name: s.stage, via: 'demo state "' + row.state + '"' } : null;
  }
  function archFlow(P, name, row) {
    const pl = pick(P, name);
    if (!pl) return `<p class="arch-empty">No architecture feed: /pipelines.json is empty.</p>`;
    const cur = currentStage(pl, row);
    const boxes = pl.stages.map((s, i) => `<button type="button" class="arch-box${cur && cur.name === s.stage ? " hl" : ""}${isOffer(s) ? " offer" : ""}" data-stage="${esc(s.stage)}"><span class="arch-n">${i + 1}</span><b>${esc(s.stage)}</b><i>${esc(s.tool)}</i>` +
      `<small>owner · ${esc(s.owner)}</small><small>machine · ${esc(s.machine)}</small><small>hands off · ${esc(s.handoff)}</small></button>`);
    return `<h2>${esc(sysName(pl.title))} · one-shot pipeline</h2><p class="arch-src">${pl.stages.length} stages · from ${esc((P && P.source) || "pipelines.yaml")}` +
      (row ? ` · this row: ${esc(row.system || "")}${cur ? ` · at <b>${esc(cur.name)}</b> (${esc(cur.via)})` : " · current stage not recorded"}` : "") + ` · click a stage for its inputs, generator, checks and output</p>` +
      `<div class="arch-flow">${boxes.join('<span class="arch-arrow" aria-hidden="true">→</span>')}</div>`;
  }
  // One stage: provenance from the pipeline spec, then this row's own facts. A missing field says so, never invented.
  function stageDetail(P, name, stageName, row) {
    const pl = pick(P, name), s = pl && pl.stages.find(x => x.stage === stageName);
    if (!s) return "";
    const sec = (k, items) => `<section><h4>${k}</h4>` + (items.length ? `<ul>${items.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="arch-none">${NONE}</p>`) + `</section>`;
    const mine = row ? [["Target", row.target || row.hunt], ["Demo state", row.state], ["Take", row.take], ["Niche", row.niche], ["Output", row.url]].filter(x => x[1]) : [];
    return `<div class="arch-detail"><h3>${esc(s.stage)}</h3><p class="arch-tool">${esc(s.tool)}</p><div class="arch-prov">` +
      sec("Inputs", list(s.inputs)) + sec("Generator", list(s.generator)) + sec("Checks passed", list(s.checks)) + sec("Output", list(s.output)) + `</div>` +
      (mine.length ? `<section class="arch-row"><h4>This row</h4><ul>${mine.map(([k, v]) => `<li>${esc(k)}: ${/^https?:/.test(v) ? `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(v)}</a>` : esc(v)}</li>`).join("")}</ul></section>` : "") + `</div>`;
  }
  function offerPanel(O) {
    if (!O || !O.headline) return `<section class="arch-offer"><h3>THE OFFER</h3><p class="arch-none">No offer feed: /offer.json is missing (source MAX-FOUNDER-PACKAGE-FINAL.md).</p></section>`;
    return `<section class="arch-offer"><h3>THE OFFER</h3><div class="arch-offer-t">${esc(O.title)}</div><p class="arch-offer-h">${esc(O.headline)}</p>` +
      `<ul>${(O.lines || []).map(l => `<li>${esc(l)}</li>`).join("")}</ul><p class="arch-src">from ${esc(O.source)}${O.generatedAt ? " · " + esc(O.generatedAt) : ""}</p></section>`;
  }
  root.EagleArch = { archFlow, stageDetail, offerPanel, currentStage, sysName };
  if (typeof document === "undefined") return;

  const css = `#arch-ov{position:fixed;inset:0;z-index:99999;background:var(--ink-1,#0a0a09);color:var(--gold-12,#f3dc9a);overflow:auto;padding:28px 32px;font:14px/1.45 Inter,system-ui,sans-serif}
#arch-ov[hidden]{display:none}#arch-ov h2{font:600 22px Cinzel,Georgia,serif;letter-spacing:.12em;text-transform:uppercase;color:var(--gold-11,#d9b35b);margin:0 0 4px;padding-right:110px}
#arch-ov .arch-src{color:var(--ink-10,#8a7f64);margin:0 0 22px}#arch-ov .arch-src b{color:var(--gold-11,#d9b35b)}
#arch-ov .arch-x{position:fixed;top:16px;right:20px;background:none;border:1px solid var(--gold-8,#d9b35b);color:var(--gold-11,#d9b35b);padding:6px 14px;border-radius:4px;cursor:pointer;letter-spacing:.14em}
#arch-ov .arch-flow{display:flex;flex-wrap:wrap;gap:10px;align-items:stretch}#arch-ov .arch-arrow{align-self:center;color:var(--gold-11,#d9b35b);font-size:22px}
#arch-ov .arch-box{position:relative;width:230px;text-align:left;font:inherit;color:inherit;border:1px solid var(--ink-7,#4a4130);border-radius:6px;padding:12px 12px 10px;background:var(--ink-2,#14130f);display:flex;flex-direction:column;gap:3px;cursor:pointer}
#arch-ov .arch-box:hover,#arch-ov .arch-box.sel{border-color:var(--gold-8,#d9b35b)}#arch-ov .arch-box.hl{border-color:var(--gold-9,#d9b35b);background:rgba(217,179,91,.16);box-shadow:0 0 0 1px var(--gold-9,#d9b35b)}
#arch-ov .arch-box b{color:var(--gold-12,#f3dc9a);letter-spacing:.1em;text-transform:uppercase}#arch-ov .arch-box i{color:var(--gold-11,#d9b35b);font-style:normal;font-size:13px}
#arch-ov .arch-box small{color:var(--ink-10,#8a7f64);font-size:12px}#arch-ov .arch-n{position:absolute;top:8px;right:10px;color:var(--ink-9,#6b5f44);font-size:12px}
#arch-ov .arch-detail{margin:26px 0 0;border:1px solid var(--ink-7,#4a4130);border-radius:8px;padding:18px 20px;background:var(--ink-2,#14130f);max-width:1100px}
#arch-ov .arch-detail h3,#arch-ov .arch-offer h3{font:600 15px Cinzel,Georgia,serif;letter-spacing:.2em;color:var(--gold-11,#d9b35b);margin:0 0 6px;text-transform:uppercase}
#arch-ov .arch-tool{color:var(--ink-11,#cdbf9b);margin:0 0 14px}#arch-ov .arch-prov{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px 24px}
#arch-ov h4{margin:0 0 4px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold-11,#d9b35b)}#arch-ov ul{margin:0;padding-left:18px}#arch-ov li{margin:2px 0}
#arch-ov .arch-none{color:var(--ink-10,#8a7f64);font-style:italic;margin:0}#arch-ov .arch-row{margin-top:16px}#arch-ov a{color:var(--gold-11,#d9b35b)}
#arch-ov .arch-offer{margin:34px 0 20px;max-width:1100px;border:1px solid var(--gold-9,#d9b35b);border-radius:10px;padding:28px 32px;background:rgba(217,179,91,.08)}
#arch-ov .arch-offer-t{font:600 clamp(22px,3vw,34px) Cinzel,Georgia,serif;color:var(--gold-12,#f3dc9a);margin:6px 0 10px}
#arch-ov .arch-offer-h{font-size:clamp(20px,2.6vw,30px);line-height:1.3;color:var(--gold-12,#f3dc9a);margin:0 0 16px}#arch-ov .arch-offer li{font-size:16px}
@media (max-width:600px){#arch-ov{padding:18px 14px}#arch-ov .arch-box{width:100%}#arch-ov .arch-arrow{display:none}}`;
  const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  const ov = document.createElement("div"); ov.id = "arch-ov"; ov.hidden = true; ov.setAttribute("role", "dialog"); ov.setAttribute("aria-label", "One-shot pipeline");
  ov.innerHTML = `<button class="arch-x" type="button">CLOSE</button><div class="arch-b"></div>`;
  document.body.appendChild(ov);
  const body = ov.querySelector(".arch-b"), close = () => { ov.hidden = true; };
  ov.querySelector(".arch-x").onclick = close;
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  const get = async u => { try { const r = await fetch(u + "?" + Date.now(), { cache: "no-store" }); return r.ok ? await r.json() : null; } catch (e) { return null; } };
  async function open(name, row) {
    ov.hidden = false; body.innerHTML = `<p class="arch-src">loading the pipeline…</p>`;
    const [P, O] = await Promise.all([get("/pipelines.json"), get("/offer.json")]);
    const pl = pick(P, name), hasOffer = !!(pl && pl.stages.some(isOffer));
    body.innerHTML = archFlow(P, name, row) + `<div class="arch-d"></div>` + (hasOffer ? offerPanel(O) : "");
    const d = body.querySelector(".arch-d");
    body.addEventListener("click", e => {
      const b = e.target.closest && e.target.closest(".arch-box"); if (!b) return;
      body.querySelectorAll(".arch-box").forEach(x => x.classList.toggle("sel", x === b));
      d.innerHTML = stageDetail(P, name, b.getAttribute("data-stage"), row);
      if (isOffer({ stage: b.getAttribute("data-stage") })) body.querySelector(".arch-offer")?.scrollIntoView({ behavior: "smooth" });
    });
    const cur = currentStage(pl, row); const first = cur && body.querySelector(`.arch-box[data-stage="${CSS.escape(cur.name)}"]`);
    if (first) first.click();
  }
  root.EagleArch.open = open;
  // capture phase: the chip's own inline onclick stops propagation, and a row click would navigate away
  document.addEventListener("click", e => {
    const t = e.target.closest && e.target.closest("[data-oss-system]");
    if (!t) return;
    e.preventDefault(); e.stopPropagation();
    let row = null; try { row = JSON.parse(t.getAttribute("data-oss-row") || "null"); } catch (x) {}
    open(t.getAttribute("data-oss-system"), row);
  }, true);
})(typeof window !== "undefined" ? window : globalThis);
