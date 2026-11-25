#!/usr/bin/env python3
"""v2_layout.py SRC DST: Eagle Eye v2 layout + per-page config, applied to horus's home-live.js (knowledge#13617).

Tyler 2026-11-15: at full screen HUNTS and ROOSTS get large side panels and the eye takes the room left; on a right
half the eye is compact on top with the lanes below it; nothing overlaps; every browser. Each `sub` fails loudly when
its anchor moved, so a changed home-live.js is never half-patched. Output: the v2 page (`/home-v2.js` on the Worker, page `/v2.html`),
and through oss_build.py the open-source build (github.com/utopia-models/eagle-eye, and `/p/eagle-eye.js`).

    python3 v2_layout.py home-live.js home-v2.js
    python3 oss_build.py home-v2.js eagle-eye.js      # scrub lanes, doors and internal comments for the public repo
"""
import sys
src = open(sys.argv[1]).read()
def sub(old, new, count=1):
    global src
    n = src.count(old)
    if n != count:
        raise SystemExit(f"anchor x{n} (want {count}): {old[:90]!r}")
    src = src.replace(old, new)

# ---- config (window.EAGLE_EYE): lanes, doors, feed, stages, title; defaults = the shipped lanes ----
sub("const keep = {};", "const keep = {};\nconst CFG = (typeof window!=='undefined' && window.EAGLE_EYE) || {};   // knowledge#13617: one UI, many feeds (Tyler, /p/<person>, open source)")
sub("// DOORS:END", "// DOORS:END\nif(CFG.doors){ for(const k in DOORS) delete DOORS[k]; Object.assign(DOORS, CFG.doors); }\nif(CFG.pipes) PIPES.splice(0, PIPES.length, ...CFG.pipes.map(p=>({...p})));")
sub("const SRCNAME = {", "const FEED = CFG.feed || '/data.json';\nconst SRCNAME = {")
sub("const NR = [", "Object.assign(SRCNAME, CFG.srcname||{});\nconst NR = [")
sub("const KEY4 = [['proposals_sent','sent'],['proposals_answered','answered'],['contracts','won'],['paid_events','paid']];",
    "const KEY4 = [['proposals_sent','sent'],['proposals_answered','answered'],['contracts','won'],['paid_events','paid']];\nif(CFG.stages) STAGES.splice(0, STAGES.length, ...CFG.stages);\nif(CFG.key4) KEY4.splice(0, KEY4.length, ...CFG.key4);")
sub("fetch('/data.json?'+Date.now(),", "fetch(FEED+(FEED.includes('?')?'&':'?')+Date.now(),")
sub("const pipesReady = fetch('/pipelines.json',{cache:'no-store'})", "const pipesReady = CFG.pipelines===false ? Promise.resolve() : fetch(CFG.pipelines||'/pipelines.json',{cache:'no-store'})")
sub("if(p.ring===0 && (p.live || (p.pid && pipeIds.has(p.pid))))", "if(p.ring===0 && ((p.live && CFG.hero!==false) || (p.pid && pipeIds.has(p.pid))))")
sub('<div id="mark">EAGLE EYE</div>', '<div id="mark" data-region="mark">${esc(CFG.title||\'EAGLE EYE\')}</div>')
sub("HUNT &middot; LIVE</div>", "${esc(CFG.liveLabel||'HUNT')} &middot; LIVE</div>")
sub('<div class="age" title="the newest hand-action row in the Upwork ledger (knowledge#13160)"></div>', '<div class="age" title="the newest hand-action row in this lane\'s ledger (knowledge#13160)"></div>')

# ---- DOM: hunts and roosts are separate groups; a right column for wide; an eye box for the overlap check ----
sub("const grp = (r,t)=>`<div class=\"grp\"><h3>", "const grp = (r,t)=>`<div class=\"grp\" id=\"grp${r}\" data-region=\"${r?'roosts':'hunts'}\"><h3>")
sub('<div class="card" id="livecard">', '<div class="card" id="livecard" data-region="live">')
sub('<div id="lift"></div>', '<div id="gr" class="hud"></div><div id="eyebox" data-region="eye"></div><div id="lift"></div>')
sub("const glyEl = {};", "const glA = root.querySelector('#gl'), glB = root.querySelector('#gr'), lvBox = root.querySelector('#lv'), eyeBox = root.querySelector('#eyebox');\nconst grpH = root.querySelector('#grp0'), grpR = root.querySelector('#grp1');\nconst glyEl = {};")

# ---- CSS: v2 (Tyler 2026-11-15: HUNTS and ROOSTS get the room, the eye takes what is left; right half = compact eye,
#      lanes below it). Lanes are ROWS at every size (icon · name/agent · numbers); type has a floor, never a zoom.
sub("#e2 #stg.dimmed{opacity:.3;transition:opacity .3s}\n`;", r"""#e2 #stg.dimmed{opacity:.3;transition:opacity .3s}
/* ---- v2 layout (knowledge#13617) ---- */
#e2 #eyebox{position:fixed;pointer-events:none;visibility:hidden}
#e2 #gr{display:none}
#e2 .card,#e2 .gly{box-sizing:border-box}
#e2 canvas.stream{height:6.6em}
#e2 #mark{opacity:.55;font-size:clamp(10px,1.1vmin,16px)}
#e2 .age{font-size:max(.74em,11px);letter-spacing:.18em;text-transform:uppercase;color:var(--gold);opacity:.85;margin-top:.55em;text-align:center;min-height:1.2em}
#e2.rows .grp{align-items:stretch;width:100%;gap:.45em;min-width:0}
#e2.rows .grp h3{font-size:max(.95em,11px);letter-spacing:.55em;opacity:.85;padding-bottom:.5em;border-bottom:1px solid rgba(217,179,91,.22);text-align:left;text-indent:0}
#e2.rows .row{flex-direction:column;flex-wrap:nowrap;align-items:stretch;gap:.1em;width:100%}
#e2.rows .gly{flex-direction:row;font-size:var(--gf);gap:.9em;padding:.42em .5em;width:auto;align-items:center;text-align:left;border-radius:2px;letter-spacing:.18em;transition:opacity .3s,filter .3s,background .3s}
#e2.rows .gly:hover,#e2.rows .gly.on{background:rgba(217,179,91,.07)}
#e2.rows .gly svg{width:2.9em;height:2.9em}
#e2.rows .gly .gt{max-width:none;flex:1;min-width:0;display:grid;grid-template-columns:1fr auto;column-gap:1em;align-items:baseline}
#e2.rows .gly i.ag{grid-column:1;grid-row:2;font-size:max(.68em,10px)}
#e2.rows .gly small.num{grid-column:2;grid-row:1 / span 2;align-self:center;font-size:1.4em;letter-spacing:.06em;color:var(--pale);opacity:1;font-variant-numeric:tabular-nums;white-space:nowrap}
#e2.rows .gly small.why{grid-column:1 / span 2;-webkit-line-clamp:3;font-size:max(.8em,11px);opacity:.9;color:#c9b88f}
#e2.rows.narrow .gly .gt{grid-template-columns:1fr}
#e2.rows.narrow .gly small.num{grid-column:1;grid-row:3;font-size:1.15em;align-self:start}
#e2.rows.narrow .gly small.why{grid-column:1}
#e2.rows.narrow .gly{gap:.6em;padding:.3em .3em}
#e2.rows.narrow .gly svg{width:2.3em;height:2.3em}
#e2.top #gl{left:var(--gx);right:auto;top:var(--pt);bottom:auto;height:auto;width:var(--lw);flex-direction:row;align-items:flex-start;justify-content:center;gap:var(--gg);padding:0}
#e2.top #gl .grp{flex:1.3 1 0;min-width:0}
#e2.top #gl #grp1{flex-grow:1}
#e2 #lv,#e2 #gr{display:none!important}
#e2.top.stack #gl{flex-direction:column;gap:var(--u)}
#e2.top #gl{background:rgba(10,10,9,.78)}
#e2.top .gly .gt{column-gap:1.4em!important}
#e2.top .gly i.ag{opacity:.85;font-size:max(.62em,11px)}
#e2.top .gly small.why{-webkit-line-clamp:4!important;font:500 max(.7em,14px)/1.3 "Cormorant Garamond",Georgia,serif!important;letter-spacing:.01em!important;text-transform:none!important;opacity:.9}
#e2.top .gly small.num em{font-style:normal;font-size:.42em;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);opacity:.8;margin:0 .9em 0 .35em;vertical-align:.25em}
#e2.top .gly small.num em{font-size:max(.42em,11px)}
#e2.top:not(.stack) .gly small.why{-webkit-line-clamp:1!important;font-style:italic!important}
#e2.top.stack .gly small.why{-webkit-line-clamp:2!important}
#e2 #mark{font-size:max(12px,1.1vmin)!important;opacity:.7!important}
#e2.top .gly small.num em:last-child{margin-right:0}
#e2.top.narrow .gly .gt{grid-template-columns:1fr auto}
#e2.top.narrow .gly small.num{grid-column:2;grid-row:1 / span 2;align-self:center}
#e2 #mark{white-space:nowrap}
#e2 a.gly{color:inherit;text-decoration:none}
#e2 a.gly:focus-visible{outline:1px solid var(--gold);outline-offset:2px}
#e2 .nums i{font-size:max(.66em,10px)}
#e2 .eyebrow{font-size:max(.72em,10px)}
#e2 .age,#e2 #lv .age{margin-top:.9em;font-size:max(.74em,11px)}
#e2.rows .gly small.why{-webkit-line-clamp:4}
#e2.rows.narrow .gly small.why{-webkit-line-clamp:6}
#e2.rows .gly .gt{white-space:nowrap}
#e2.rows .gly small.why{white-space:normal}
#e2.rows .gly.dim{opacity:.85}
#e2.rows .gly small.why{color:#dccca4;opacity:1}
`;""")
sub("const n=STAGES.length, pad=w*.07, X=s=>pad+s*(w-2*pad)/(n-1), my0=h*.58, fs=Math.max(8,w/40);",
    "const n=STAGES.length, pad=w*.07, X=s=>pad+s*(w-2*pad)/(n-1), fs=Math.max(10,w/38), lab=Math.max(10,fs*.8)+5, my0=(h-lab)*.56;   // knowledge#13617: stage labels >= 10px, bars end above them")
sub("return (.06+.94*(a+(b-a)*f))*h*.3;};", "return (.06+.94*(a+(b-a)*f))*Math.max(2,Math.min(h*.3,(h-lab)*.36,my0-fs*1.15-12));};")
sub("sctx.fillStyle='#d9b35b'; sctx.font=`300 ${fs*.8}px Cinzel,Georgia,serif`; sctx.globalAlpha=.8;\n    sctx.fillText(STAGES[i][1].toUpperCase(),x,h-1);",
    "sctx.fillStyle='#d9b35b'; const lt=STAGES[i][1].toUpperCase(), slot=(w-2*pad)/(n-1)*.94; let lf=Math.max(11,fs*.8); sctx.font=`300 ${lf}px Cinzel,Georgia,serif`;\n    const lw=sctx.measureText(lt).width; if(lw>slot){ lf=Math.max(10,lf*slot/lw); sctx.font=`300 ${lf}px Cinzel,Georgia,serif`; } sctx.globalAlpha=.85;\n    sctx.fillText(lt,x,h-1);")
sub("sctx.fillText(String(v[i]),x,my0-half(i)-6);", "sctx.fillText(String(v[i]),x,my0-half(i)-9);")

# ---- layout: panels are sized first, the eye takes the room left; a fit loop keeps every lane on screen ----
sub("""  wide = W/H > 1.3;
  // eye ~60% of the viewport width (or 60% of height when height binds), never more than the room allows
  if(wide){ R=Math.min(H*.30, W*.19); lidW=Math.min(W*.255, R*1.5); }
  else    { R=Math.min(H*.30, W*.19); lidW=Math.min(W*.31, R*1.75); }
  const u = Math.max(10, Math.min(W,H)/74);
  root.className = wide?'wide':'tall';""", """  // knowledge#13617 (Tyler 2026-11-15: the right-half layout, at EVERY size): HUNTS and ROOSTS side by side on top,
  // sized first ("hunts and roosts should be bigger, that's what I really want to see"); the eye takes the room below.
  // No live card. Nothing overlaps, nothing scrolls.
  wide = false;
  const u = Math.max(11, Math.min(W,H)/74);
  root.style.setProperty('--u', u+'px');
  const narrow = W < 700;
  const stack = narrow || W/H < 1.05 || PIPES.length <= 4;   // a person's copy (few lanes): one column, larger rows   // portrait: HUNTS above ROOSTS in one column, so the type can grow
  root.className = 'top rows'+(narrow?' narrow':'')+(stack?' stack':'');
  // the lanes are the point: start large and shrink only until they fit beside each other and leave the eye its minimum
  const nl = PIPES.length;   // few lanes (a person's copy) grow larger: the lanes stay the hero
  let gf = (narrow ? 1.5 : (W>2400 ? 3.2 : 2.5)) * (nl <= 4 ? (narrow ? 2.2 : 1.6) : 1);
  const setGf = ()=>root.style.setProperty('--gf', gf+'em');
  const gp = narrow ? Math.max(16,u) : 2.4*u,   /* a phone: 16 px gutters (knowledge#14223) */ lw = stack ? Math.min(W-2*gp, PIPES.length <= 4 && !narrow ? 90*u : 52*u) : Math.min(W-2*gp, Math.max(60*u, (W>2400?.72:.62)*W), 170*u);
  root.style.setProperty('--gg', (narrow?1:3.2)*u+'px'); root.style.setProperty('--lw', lw+'px'); root.style.setProperty('--gx', ((W-lw)/2)+'px');
  if(grpH.parentNode!==glA || grpR.parentNode!==glA){ glA.appendChild(grpH); glA.appendChild(grpR); }
  const who = narrow && document.getElementById('ee-who'), pt = (narrow?1.2:2.2)*u + (who ? who.offsetHeight + 6 : 0),   /* a phone: the person switcher has its own line above HUNTS (knowledge#14223) */ markH = 3.2*u, minR = Math.max(40, Math.min(H*.13, W*.11));
  const fits = ()=>[...glA.querySelectorAll('.gt')].every(e=>e.scrollWidth<=e.clientWidth+1);
  const place = (wk=1)=>{ setGf(); root.style.setProperty('--pt', pt+'px');
    const hh = stack ? grpH.offsetHeight + grpR.offsetHeight + u : Math.max(grpH.offsetHeight, grpR.offsetHeight), top = pt + hh + (narrow?1.2:2)*u;
    const avail = H - top - markH;
    R = Math.min(avail/2.9, W*.2*wk); lidW = Math.min(W*.44, R*1.75, (W-2*gp)/2 - 8); R = Math.min(R, lidW/1.5);
    cy = top + avail/2; return hh; };
  for(let k=0;k<90;k++){ const hh = place();
    if((R >= minR && hh <= H*.6 && fits()) || gf <= .8) break;
    gf -= .05; }
  // round 5 (Tyler 2026-11-15 12:20 MT, on v2 live: "hunts and roosts decreased by about 20%, and the eye itself
  // enlarged by about 20%"): from the fit above, the lanes' type and panel width x0.8, the eye up to x1.2 in the room
  // that frees (never past it: place() still bounds R by the height and width left, so nothing overlaps or scrolls)
  const R0 = R, LANES = .8, EYE = 1.2;
  gf *= LANES; if(!narrow){ const lw2 = lw*LANES; root.style.setProperty('--lw', lw2+'px'); root.style.setProperty('--gx', ((W-lw2)/2)+'px'); }
  place(EYE);   // on a phone the eye was width-capped (W*.2): that cap grows by the same x1.2
  if(R > R0*EYE){ R = R0*EYE; lidW = Math.min(lidW, R*1.75); }
  R = Math.max(R, 20); lidW = Math.max(lidW, 30);   // a canvas gradient throws on a negative radius""")
sub("  DPR=Math.min(devicePixelRatio||1,2); W=innerWidth; H=innerHeight;\n  cv.width=W*DPR; cv.height=H*DPR; cx=W/2; cy=H/2;",
    "  DPR=Math.min(devicePixelRatio||1,2); W=innerWidth; H=innerHeight;\n  cv.width=W*DPR; cv.height=H*DPR; cx=W/2;")
sub("""  root.style.setProperty('--ey', (R*1.44)+'px');""", """  root.style.setProperty('--ey', (R*1.44)+'px');
  // the eye's drawn extent (lids + lash dust), for the no-overlap check (data-region="eye")
  Object.assign(eyeBox.style, {left:(cx-lidW-8)+'px', top:(cy-R*1.42)+'px', width:(2*lidW+16)+'px', height:(R*2.84)+'px'});""")
sub("const face = wide ? Math.PI : Math.PI/2;", "const face = wide ? 0 : Math.PI/2;   // v2: the live card sits in the right panel on wide, below on tall")
sub("    data = d; paintAge(); updateGlyphs();", "    data = d; paintAge(); updateGlyphs(); refit();")
sub("addEventListener('resize', resize); resize();", """addEventListener('resize', resize); resize();
// knowledge#13617: the fit depends on the lanes' text (a reason can wrap to 3 lines) and the web fonts, so lay out again
// whenever either changes, never on a timer
let fitSig = '';
function refit(){ const s = root.querySelector('#gl').textContent + glB.textContent; if(s!==fitSig){ fitSig=s; resize(); } }
if(document.fonts && document.fonts.ready) document.fonts.ready.then(()=>{ fitSig=''; refit(); });""")
sub("const style = document.createElement('style');", "if(!document.querySelector('link[data-cinzel]')){ const fl=document.createElement('link'); fl.rel='stylesheet'; fl.dataset.cinzel=1; fl.href='https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500&family=Cormorant+Garamond:wght@500&display=block'; document.head.appendChild(fl); }   // knowledge#13617: one face in every browser\nconst style = document.createElement('style');")
# ---- numbers carry their unit; a roost counts clients or people, never "rows" (critic round 2) ----
sub("  if(p.ring===0) return `${nm}<small class=\"num\">${s.sent} &middot; ${s.ans}</small>`;\n  return `${nm}<small class=\"num\">${s.sent} ${s.sent===1?'row':'rows'}</small>`;",
    "  if(p.ring===0) return `${nm}<small class=\"num\">${s.sent}<em>sent</em> ${s.ans}<em>back</em></small>`;\n  const unit = (CFG.units||{})[p.rk] || (p.rk==='clients' ? (s.sent===1?'client':'clients') : (s.sent===1?'person':'people'));\n  return `${nm}<small class=\"num\">${s.sent}<em>${unit}</em></small>`;")
sub("  if(s.empty) return `${nm}<small class=\"why\">${esc(s.reason)}</small>`;", "  if(s.empty) return `${nm}<small class=\"why\">${esc(String(s.reason||'').replace(/^./,c=>c.toUpperCase()))}</small>`;")
# ---- lanes are links (knowledge#13617): /hunt/<key>, /roost/<key>; the HUNT·LIVE card is gone ----
sub("const glyphs = PIPES.map(p=>`<div class=\"gly dim\" data-i=\"${p.i}\" role=\"button\" tabindex=\"0\"><span class=\"gs\"></span><span class=\"gt\"></span></div>`);",
    "const laneHref = p => CFG.lanePages===false ? null : (CFG.laneBase||'') + '/' + (p.ring?'roost':'hunt') + '/' + (p.hk||p.rk);\n"
    "const glyphs = PIPES.map(p=>{ const h=laneHref(p); return h ? `<a class=\"gly dim\" data-i=\"${p.i}\" href=\"${h}\" aria-label=\"${esc(p.name)}: open its page\"><span class=\"gs\"></span><span class=\"gt\"></span></a>` : `<div class=\"gly dim\" data-i=\"${p.i}\" role=\"button\" tabindex=\"0\"><span class=\"gs\"></span><span class=\"gt\"></span></div>`; });")
sub("const LIVE = PIPES.findIndex(p=>p.live);", "const LIVE = Math.max(0, PIPES.findIndex(p=>p.live));   // knowledge#13617: no lane need be live (the card is gone)")
sub("const scrim = root.querySelector('#scrim')", "liveCard.remove(); root.querySelector('#lv').remove();   // knowledge#13617: no HUNT·LIVE card on v2\nconst scrim = root.querySelector('#scrim')")
sub("  const g=e.target.closest&&e.target.closest('.gly'); if(g){ select(+g.dataset.i); return; }",
    "  const g=e.target.closest&&e.target.closest('.gly'); if(g){ if(g.tagName==='A') return; select(+g.dataset.i); return; }   // a lane link navigates")
sub("  const s=segAt(e.clientX,e.clientY); if(s>=0) select(s);",
    "  const s=segAt(e.clientX,e.clientY); if(s>=0){ const h=laneHref(PIPES[s]); if(h){ location.href=h; return; } select(s); }")
# ---- knowledge#13746 gap 1: every lane live: its own units (feed `labels`) and the newest thing that moved (feed `latest`) ----
sub("  if(p.ring===0) return `${nm}<small class=\"num\">${s.sent}<em>sent</em> ${s.ans}<em>back</em></small>`;\n  const unit",
    "  const lt = (s.h||s.r||{}).latest, lat = lt&&lt.ts ? `<small class=\"why lt\" title=\"${esc(lt.what||'')}\">${esc(ago(lt.ts))} &middot; ${esc(lt.co||'')}${lt.co&&lt.kind?' &middot; ':''}${esc(lt.kind||'')}</small>` : '';\n"
    "  const lb = (s.h&&s.h.labels) || ['sent','back'];\n"
    "  if(p.ring===0) return `${nm}<small class=\"num\">${s.sent}<em>${esc(lb[0])}</em> ${s.ans}<em>${esc(lb[1])}</em></small>${lat}`;\n  const unit")
sub("  return `${nm}<small class=\"num\">${s.sent}<em>${unit}</em></small>`;",
    "  return `${nm}<small class=\"num\">${s.sent}<em>${unit}</em></small>${lat}`;")
sub("    el.title = s.empty ? s.reason : (p.ring===0 ? `${p.name}: sent ${s.sent}, came back ${s.ans}` :",
    "    el.title = s.empty ? s.reason : (p.ring===0 ? `${p.name}: ${s.sent} ${((s.h||{}).labels||['sent'])[0]}, ${s.ans} ${((s.h||{}).labels||[0,'came back'])[1]}` :")
sub("#e2.rows .gly small.why{color:#dccca4;opacity:1}\n`;", "#e2.rows .gly small.why{color:#dccca4;opacity:1}\n#e2.rows .gly small.why.lt{opacity:.72;font-style:italic;-webkit-line-clamp:1!important;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden}\n`;")
# ---- the phone (Tyler 2026-11-16, on the RAW Pixel in Chrome: "not styled well at all"): the desktop row's hierarchy at
#      412 px. The count is the big figure and its unit the small caps beside it (it was one 13 px run, label-sized);
#      the glyph is large enough to read as an eye; rows part on a hairline; the mark is Cinzel like every other word.
sub("#e2.rows .gly small.why.lt{opacity:.72;", """#e2.rows.narrow .gly{font-size:13px;letter-spacing:.24em;gap:.8em;padding:clamp(4px,1vh,9px) .1em clamp(5px,1.1vh,10px);border-bottom:1px solid rgba(217,179,91,.09);border-radius:0}
#e2.rows.narrow .grp .row .gly:last-child{border-bottom:0}
#e2.rows.narrow .gly svg{width:30px;height:30px}
#e2.top.narrow .gly small.num{font-size:21px;line-height:1;letter-spacing:.02em;font-variant-numeric:lining-nums tabular-nums;color:#f3dc9a}
#e2.top.narrow .gly small.num em{font-size:10px;letter-spacing:.24em;vertical-align:2px;margin:0 .9em 0 .35em}
#e2.top.narrow .gly small.num em:last-child{margin-right:0}
#e2.top.narrow .gly .gt{grid-template-columns:auto minmax(0,1fr) auto;column-gap:0!important;align-items:baseline}
#e2.top.narrow .gly i.ag{grid-column:2;grid-row:1;font-size:10.5px;letter-spacing:.2em;opacity:.7;margin:0 .7em 0 .9em}
#e2.top.narrow .gly small.num{grid-column:3;grid-row:1;align-self:baseline}
#e2.top.narrow .gly small.why{grid-column:1 / -1;grid-row:2}
#e2.top.narrow .gly small.why{font-size:14px!important;margin-top:.3em}
#e2.top.narrow #gl{background:none}
#e2.top.narrow .grp h3{font-size:11px}
@media (max-width:400px){#e2.top.narrow .gly small.num em{letter-spacing:.16em;margin:0 .6em 0 .3em}#e2.top.narrow .gly i.ag{margin-left:.7em}}
@media (max-height:720px){#e2.rows.narrow .gly{padding:2px .1em 3px;font-size:12px}#e2.top.narrow .gly small.why{font-size:13px!important;margin-top:.1em}#e2.top.narrow .gly small.num{font-size:19px}#e2.rows.narrow .gly svg{width:26px;height:26px}}
/* a phone in Chrome: 100vh is the viewport with the toolbar HIDDEN, taller than innerHeight, so the canvas bitmap
   (innerWidth x innerHeight) was stretched down the screen: the eye fell under the mark and off the bottom (knowledge#14223) */
#e2.narrow canvas.main{width:100%;height:100%}
#e2.narrow #mark{font-family:"Cinzel",Georgia,serif!important;font-size:11px!important;letter-spacing:.8em;text-indent:.8em;opacity:.55!important}
#e2.rows .gly small.why.lt{opacity:.72;""")

# ---- round 3 (Tyler 2026-11-16 11:58-12:14 MT, on the RAW Pixel; knowledge#14223) ----
# 1. "remove the data points sent and back ... I'll figure out what I want to see later": a hunt row is its name, agent
#    and latest line, no count. Roosts keep theirs (clients, people).
sub("  const lb = (s.h&&s.h.labels) || ['sent','back'];\n  if(p.ring===0) return `${nm}<small class=\"num\">${s.sent}<em>${esc(lb[0])}</em> ${s.ans}<em>${esc(lb[1])}</em></small>${lat}`;",
    "  if(p.ring===0) return `${nm}${lat}`;")
sub("    el.title = s.empty ? s.reason : (p.ring===0 ? `${p.name}: ${s.sent} ${((s.h||{}).labels||['sent'])[0]}, ${s.ans} ${((s.h||{}).labels||[0,'came back'])[1]}` : `${p.name}: ${s.sent} rows, ${s.ans} contracts`);",
    "    el.title = s.empty ? s.reason : p.name;")
# 2. "Network can stay, remove social for now" (12:14) and "we don't even need LinkedIn and cold email either cause those
#    will be technically folded into cold apps" (12:43): those three lanes are gone from the page, their rows and their
#    slices of the eye alike. Hunts: Upwork, Cold apps, In person. Roosts: Clients, Network.
sub("if(CFG.pipes) PIPES.splice(0, PIPES.length, ...CFG.pipes.map(p=>({...p})));",
    "if(CFG.pipes) PIPES.splice(0, PIPES.length, ...CFG.pipes.map(p=>({...p})));\n"
    "// Tyler 2026-11-16: a person's Eagle Eye hunt Cold apps and In person, no Upwork (Upwork is his alone); /me.json\n"
    "// names whose Eagle Eye this is (the switcher's ?p= or the signed-in person). A configured copy (CFG.pipes) has its own lanes.\n"
    "const VIEW = CFG.pipes ? null : await fetch('/me.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(m=>m&&m.view).catch(()=>null);\n"
    "{ const gone = new Set(CFG.drop || ['linkedin','cold_email','social', ...(VIEW && VIEW!=='tyler' ? ['upwork'] : ['network'])]); PIPES.splice(0, PIPES.length, ...PIPES.filter(p=>!gone.has(p.hk||p.rk))); }\n"
    "// knowledge#14303: on a person's Eagle Eye every lane is worked by their own agent, never Tyler's sekhmet/purser/atlas\n"
    "{ const AG = {claire:'claire-scout', osman:'milli-scout'}[VIEW]; if(AG) for(const k in DOORS) DOORS[k] = {...DOORS[k], agent: AG}; }")
#    A copy with few lanes by design (a /p/<person> page, CFG.pipes) gets the one-column, larger-row layout; Tyler's,
#    a person's home keeps the approved two-column layout however many lanes it now has.
sub("const stack = narrow || W/H < 1.05 || PIPES.length <= 4;", "const stack = narrow || W/H < 1.05 || (CFG.pipes && PIPES.length <= 4);")
sub("const nl = PIPES.length;", "const nl = CFG.pipes ? PIPES.length : 99;")
sub("PIPES.length <= 4 && !narrow ? 90*u : 52*u", "CFG.pipes && PIPES.length <= 4 && !narrow ? 90*u : 52*u")
#    a person's home sizes its type as Tyler's does: the fit runs with a stand-in for the Upwork row they do not
#    have (a clone, removed before anything is drawn), so their rows are his rows minus one, never larger.
sub("  for(let k=0;k<90;k++){ const hh = place();",
    "  const ghost = VIEW && VIEW!=='tyler' && !CFG.pipes && grpH.querySelector('.gly') ? [grpH.querySelector('.row').appendChild(grpH.querySelector('.gly').cloneNode(true))] : [];\n"
    "  ghost.forEach(g=>{ g.querySelector('.gt').innerHTML = 'Upwork<i class=\"ag\">UPWORK</i><small class=\"why lt\">88 min ago &middot; Mohamed Talat &middot; client reply</small>'; });   // Tyler's Upwork row, as it reads\n"
    "  if(ghost.length && !stack && grpR.querySelector('.gly')){ const g = grpR.querySelector('.row').appendChild(grpR.querySelector('.gly').cloneNode(true));   // side by side the roosts' widest row sets the type too: Tyler's Network row\n"
    "    g.querySelector('.gt').innerHTML = 'Network<i class=\"ag\">ATLAS</i><small class=\"num\">380<em>people</em></small><small class=\"why lt\">12 h ago &middot; Onna &middot; whatsapp</small>'; ghost.push(g); }\n"
    "  for(let k=0;k<90;k++){ const hh = place();")
sub("  const R0 = R, LANES = .8, EYE = 1.2;", "  ghost.forEach(g=>g.remove());\n  const R0 = R, LANES = .8, EYE = 1.2;")
# 3. "when I hover, there doesn't need to be a preview on the eye ... just remove": the lift card is gone and hovering the
#    eye does nothing (a row still lights its slice)
import re
n = len(re.findall(r"#e2 #lift[^{]*\{[^}]*\}\n", src))
if n != 8: raise SystemExit(f"lift css x{n}")
src = re.sub(r"#e2 #lift[^{]*\{[^}]*\}\n", "", src)
sub('<div id="lift"></div>', '')
sub(", lift = root.querySelector('#lift');", ";")
sub(" if(liftFor>=0) lift.innerHTML=liftHtml(PIPES[liftFor]);", "")
a, b = src.index("// ---------- lift card"), src.index("// ---------- helpers")
src = src[:a] + src[b:]
sub("  setLift(-1);\n  ifr.src", "  ifr.src")
sub("panelFor=p.i; setLift(-1); ", "panelFor=p.i; ")
sub("  const hs = (mx>=0 && panelFor<0) ? segAt(mx,my) : -1; hover = panelFor>=0 ? -1 : (hs>=0 ? hs : glyHover);\n  setLift(hover);",
    "  hover = panelFor>=0 ? -1 : glyHover;")
sub("let mx=-1,my=-1,hover=-1,", "let hover=-1,")
sub("const onMove=e=>{mx=e.clientX;my=e.clientY;}, onLeave=()=>{mx=my=-1;};\naddEventListener('pointermove',onMove); document.addEventListener('pointerleave',onLeave);\n", "")
if "setLift" in src or "liftHtml" in src or "lift." in src: raise SystemExit("lift left over")
# 4. "the outlining of the eye is still small in terms of the x-axis ... doesn't look the same as the desktop view eye":
#    on a phone the eye is the desktop eye (lids 1.75 R wide, as every desktop size draws them) spanning ~88% of the
#    width, and when the lanes leave it too little height the page scrolls to it instead of shrinking it. Its lash dust
#    scales with it, so the outline keeps the desktop's weight.
sub("  R = Math.max(R, 20); lidW = Math.max(lidW, 30);   // a canvas gradient throws on a negative radius",
    """  R = Math.max(R, 20); lidW = Math.max(lidW, 30);   // a canvas gradient throws on a negative radius
  let need = innerHeight;
  if(narrow){
    const top = pt + grpH.offsetHeight + grpR.offsetHeight + u + 1.2*u;
    lidW = W*.45 - 4; R = lidW/1.75;
    need = Math.ceil(top + 12 + R*2.84 + markH + 10);
    cy = Math.max(top + 12 + R*1.42, top + (innerHeight - top - markH)/2);
  }
  const scroll = need > innerHeight;
  document.documentElement.classList.toggle('ee-scroll', scroll); root.classList.toggle('scroll', scroll);
  root.style.height = scroll ? need+'px' : '';
  if(scroll){ H = need; cv.height = H*DPR; }
  // Tyler 12:22 MT: "make sure the circle of the eye is a circle": on a phone the canvas's CSS box is set to the very
  // W x H its bitmap was made from (one uniform DPR scale), never a percentage of a box the browser sizes on its own
  if(narrow){ cv.style.width = W+'px'; cv.style.height = H+'px'; } else cv.style.width = cv.style.height = '';
  dk = narrow ? Math.min(1, R/200) : 1;   // 200 = R of the eye at 1440x900
  dispatchEvent(new Event('ee-layout'));   // who.js seats the person switcher on every layout (it may load first)""")
sub("let W,H,DPR,cx,cy,R,lidW,wide,rot=[0,0];", "let W,H,DPR,cx,cy,R,lidW,wide,rot=[0,0],dk=1;")
sub("const px=cx+x*lidW,py=cy+y+d.off*(4+(1-Math.abs(x))*6);", "const px=cx+x*lidW,py=cy+y+d.off*(4+(1-Math.abs(x))*6)*dk;")
sub("off=(j-Math.floor(j)-.5)*9;", "off=(j-Math.floor(j)-.5)*9*dk;")
sub("  Object.assign(eyeBox.style, {", "  eyeBox.dataset.r = R; eyeBox.dataset.lid = lidW;\n  Object.assign(eyeBox.style, {")
sub("#e2.rows .gly small.why.lt{opacity:.72;", """html.ee-scroll,html.ee-scroll body{height:auto!important;overflow-x:hidden!important}
html.ee-scroll{overflow-y:auto!important}
#e2.scroll{position:absolute;inset:auto;left:0;top:0;width:100%}
#e2.scroll #stg,#e2.scroll canvas.main,#e2.scroll .hud,#e2.scroll #mark,#e2.scroll #eyebox{position:absolute}
#e2.rows .gly small.why.lt{opacity:.72;""")

# ---- knowledge#14261 (Tyler 2026-11-16, "Same with Roosts, I only need to see clients and the number of clients"): Tyler's
#      roosts are the Clients row alone, its count and nothing else: Network leaves his page (above), and a roost row drops
#      its latest line. a person's Network roost (their only one) stays.
sub("  return `${nm}<small class=\"num\">${s.sent}<em>${unit}</em></small>${lat}`;",
    "  return `${nm}<small class=\"num\">${s.sent}<em>${unit}</em></small>`;")

open(sys.argv[2], "w").write(src)
print("ok", len(src))

