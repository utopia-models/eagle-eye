// Eagle Eye: one screen for every outreach pipeline you run. The eye in the middle, your hunts (what you send out)
// on the outer ring, your roosts (what comes back) on the inner ring, and the live lane's funnel in a card.
// Copyright 2026 Utopia Models, Inc. Licensed under the Apache License, Version 2.0 (see LICENSE).
// Config: window.EAGLE_EYE = {feed, title, pipes, doors, stages, key4, liveLabel, hero:false, pipelines:false}
// (config.js documents every key). Feed shape: docs/FEED.md.
const keep = {};
const CFG = (typeof window!=='undefined' && window.EAGLE_EYE) || {};
const TAU = Math.PI*2;
const PIPES = [
  {id:'applications', ring:0, hk:'applications', name:'Applications', short:'Applications', w:3},
  {id:'outreach', ring:0, hk:'outreach', name:'Outreach', short:'Outreach', w:1},
  {id:'network', ring:1, rk:'network', name:'Network', short:'Network', w:1},
];
const DOORS = {};   // lane -> {agent, kind:'desk'|'view', url, where}; config.js (window.EAGLE_EYE.doors) fills it
if(CFG.doors){ for(const k in DOORS) delete DOORS[k]; Object.assign(DOORS, CFG.doors); }
if(CFG.pipes) PIPES.splice(0, PIPES.length, ...CFG.pipes.map(p=>({...p})));
const FEED = CFG.feed || '/data.json';
const SRCNAME = {};
const ago = ts => { const m=Math.max(0,Math.round((Date.now()-Date.parse(ts))/60000)); return m<90?`${m} min ago`:m<2880?`${Math.round(m/60)} h ago`:`${Math.round(m/1440)} d ago`; };
const lastRow = h => h&&h.last_action&&h.last_action.ts ? `last row ${ago(h.last_action.ts)} · ${String(h.last_action.event||'').replace(/_/g,' ')}` : '';
const srcName = h => h ? (SRCNAME[h] || String(h).replace(/_/g,' ')) : '—';
Object.assign(SRCNAME, CFG.srcname||{});
const NR = [PIPES.filter(p=>p.ring===0).length, PIPES.filter(p=>p.ring===1).length];
{ const c=[0,0], tw=[0,0]; PIPES.forEach(p=>tw[p.ring]+=(p.w||1));
  PIPES.forEach((p,i)=>{p.i=i; p.k=c[p.ring]++; p.aw=TAU*(p.w||1)/tw[p.ring]; p.a0=PIPES.slice(0,i).filter(o=>o.ring===p.ring).reduce((s,o)=>s+TAU*(o.w||1)/tw[o.ring],0);}); }
const LIVE = Math.max(0, PIPES.findIndex(p=>p.live));
const GAP = 0.03;
const OUT = [0.64,0.98], INN = [0.34,0.58], PUPIL = 0.26;
const RING = [OUT, INN];
const STAGES = [['proposals_sent','sent'],['proposals_answered','answered'],['videos_sent','video'],['video_clients','clients'],['contracts','won'],['paid_events','paid']];
const KEY4 = [['proposals_sent','sent'],['proposals_answered','answered'],['contracts','won'],['paid_events','paid']];
if(CFG.stages) STAGES.splice(0, STAGES.length, ...CFG.stages);
if(CFG.key4) KEY4.splice(0, KEY4.length, ...CFG.key4);

if(!document.querySelector('link[data-cinzel]')){ const fl=document.createElement('link'); fl.rel='stylesheet'; fl.dataset.cinzel=1; fl.href='https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500&display=block'; document.head.appendChild(fl); }
const style = document.createElement('style');
style.textContent = `
:root{--bg:#0a0a09;--gold:#d9b35b;--pale:#f3dc9a}
#e2{position:fixed;inset:0;font-family:"Cinzel","Trajan Pro","Optima","Palatino Linotype",Georgia,serif;color:var(--pale)}
#e2 canvas.main{position:fixed;inset:0;width:100vw;height:100vh;display:block}
#e2 .hud{position:fixed;font-size:var(--u);pointer-events:none;display:flex}
#e2 .tall #lv{}
#e2 #lv{left:0;right:0;bottom:0;height:calc(50% - var(--ey));align-items:center;justify-content:center;padding:0 2em 3.4em}
#e2 #gl{left:0;right:0;top:0;height:calc(50% - var(--ey));flex-direction:column;align-items:center;justify-content:center;gap:1.2em;padding:1.5em 1.5em 0}
#e2.wide #lv{left:0;right:auto;top:0;bottom:0;height:auto;width:calc(50% - var(--ex));padding:0 1.6em 0 2.2em}
#e2.wide #gl{left:auto;right:0;top:0;bottom:0;height:auto;width:calc(50% - var(--ex));padding:0 2.2em 0 1.6em;align-items:flex-start;justify-content:center;gap:1.6em}
#e2 .grp{display:flex;flex-direction:column;align-items:center;gap:.6em}
#e2.wide .grp{align-items:flex-start;width:100%}
#e2 .grp h3{font-weight:300;font-size:.78em;letter-spacing:.5em;text-indent:.5em;color:var(--gold);opacity:.7;margin:0}
#e2 .row{display:flex;flex-wrap:wrap;justify-content:center;gap:.4em .3em}
#e2.wide .row{flex-direction:column;flex-wrap:nowrap;gap:.35em;width:100%}
#e2 .gly{pointer-events:auto;display:flex;flex-direction:column;align-items:center;gap:.3em;width:8.6em;text-align:center;cursor:default;
  opacity:.5;transition:opacity .3s,filter .3s;font-weight:300;font-size:.72em;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);line-height:1.25}
#e2.wide .gly{flex-direction:row;width:auto;text-align:left;gap:1em;font-size:.78em}
#e2 .gly svg{width:2.6em;height:2.6em;flex:none;overflow:visible}
#e2 .gly small{display:block;font-size:.8em;letter-spacing:.28em;opacity:.6}
#e2 .gly.on{opacity:1;filter:drop-shadow(0 0 .6em rgba(217,179,91,.8));color:var(--pale)}
#e2 .card{pointer-events:auto;position:relative;width:min(100%,38em);padding:1.2em 1.5em 1em;text-align:center;
  background:radial-gradient(ellipse at 50% 0,rgba(217,179,91,.08),rgba(10,10,9,.55) 70%);
  border:1px solid rgba(217,179,91,.22);border-radius:2px;transition:opacity .4s,border-color .4s}
#e2 .card::before,#e2 .card::after{content:"";position:absolute;width:.9em;height:.9em;border:1px solid var(--pale);opacity:.7}
#e2 .card::before{left:-1px;top:-1px;border-right:0;border-bottom:0}
#e2 .card::after{right:-1px;bottom:-1px;border-left:0;border-top:0}
#e2.wide #lv .card{font-size:1.2em}
#e2 .card.lifted{opacity:.18}
#e2 .eyebrow{font-weight:300;font-size:.72em;letter-spacing:.5em;text-indent:.5em;color:var(--gold);display:flex;align-items:center;justify-content:center;gap:.9em}
#e2 .dot{width:.55em;height:.55em;border-radius:50%;background:var(--pale);box-shadow:0 0 .8em var(--gold);animation:e2p 2s ease-in-out infinite}
@keyframes e2p{50%{opacity:.25}}
#e2 h2{margin:.35em 0 .6em;font-weight:400;font-size:1.28em;letter-spacing:.22em;text-indent:.22em;text-transform:uppercase;text-shadow:0 0 14px rgba(217,179,91,.7)}
#e2 .nums{display:grid;grid-template-columns:repeat(4,1fr);gap:.3em}
#e2 .nums b{display:block;font-weight:400;font-size:2.5em;line-height:1;text-shadow:0 0 16px rgba(217,179,91,.75),0 0 2px #000;font-variant-numeric:tabular-nums;transition:color .6s}
#e2 .nums b.flash{color:#fff}
#e2 .nums i{display:block;font-style:normal;font-weight:300;font-size:.66em;letter-spacing:.32em;text-indent:.32em;text-transform:uppercase;color:var(--gold);margin-top:.5em}
#e2 #lv .age{font-size:.62em;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);opacity:.7;margin-top:.55em;text-align:center;min-height:1.2em}
#e2 canvas.stream{width:100%;height:5.6em;display:block;margin-top:.7em}
#e2 #lift{position:fixed;left:0;top:0;width:19em;pointer-events:none;opacity:0;transform-origin:50% 50%;font-size:var(--u);
  transition:transform .55s cubic-bezier(.2,.8,.2,1),opacity .35s ease;z-index:5}
#e2 #lift .card{background:radial-gradient(ellipse at 50% 0,rgba(217,179,91,.14),rgba(10,10,9,.95) 75%);box-shadow:0 0 3em rgba(217,179,91,.2);padding:1em 1.1em .9em;width:100%}
#e2 #lift h2{font-size:1.05em;margin:.3em 0 .5em}
#e2 #lift .nums b{font-size:1.9em}
#e2 #lift .nums i{font-size:.6em;letter-spacing:.22em;text-indent:.22em}
#e2 #lift .idle{font-weight:300;font-size:.72em;letter-spacing:.4em;text-indent:.4em;color:var(--gold);opacity:.75;margin:.2em 0 .1em}
#e2 #stg{position:fixed;inset:0;transition:transform 1s cubic-bezier(.55,0,.85,.35),opacity .9s ease .1s;will-change:transform,opacity}
#e2 #stg.out{transform:scale(9);opacity:0}
#e2 #hero{position:fixed;inset:0;width:100vw;height:100vh;border:0;background:#0a0a09;opacity:0;transform:scale(1.18);visibility:hidden;
  transition:opacity .8s ease .35s,transform 1s cubic-bezier(.2,.8,.2,1) .25s;z-index:10}
#e2 #hero.in{opacity:1;transform:none;visibility:visible}
#e2 #back{position:fixed;left:1.6vmin;top:1.6vmin;z-index:20;display:none;opacity:0;transition:opacity .5s;cursor:pointer;
  background:rgba(10,10,9,.7);border:1px solid rgba(217,179,91,.35);color:#f3dc9a;font:300 12px Cinzel,Georgia,serif;letter-spacing:.35em;padding:.9em 1.2em;text-transform:uppercase}
#e2 #back.show{opacity:1}
#e2 #mark{position:fixed;left:50%;bottom:1.6vmin;transform:translateX(-50%);font:300 clamp(8px,1.1vmin,12px)/1 Georgia,serif;letter-spacing:.9em;color:var(--gold);opacity:.35;text-indent:.9em;pointer-events:none}

#e2 .gly{cursor:pointer;font-size:max(.72em,9px);opacity:.85}
#e2 .gly svg{width:3.3em;height:3.3em}
#e2 .gly small.why{letter-spacing:.04em;text-transform:none;opacity:.75;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;font-size:.78em;line-height:1.25;margin-top:.15em}
#e2 .gly.dim{opacity:.62}
#e2 .gly .gt{min-width:0}
#e2 .gly i.ag{display:block;font-style:normal;font-size:.68em;letter-spacing:.2em;opacity:.55;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#e2.wide .gly .gt{max-width:19em}
#e2 .gly.dim.on{opacity:.9}
#e2 .gly small.num{letter-spacing:.12em;opacity:.85;font-size:.82em}
#e2 .row{align-items:flex-start}
#e2 .lg{font-size:.62em;letter-spacing:.25em;color:var(--gold);opacity:.55;margin:.1em 0 0;text-transform:uppercase;font-weight:300}
#e2 #lift .idle.why{letter-spacing:.04em;text-indent:0;text-transform:none;font-size:.7em;line-height:1.35;padding:0 .4em}
#e2 #lift .nums.two{grid-template-columns:repeat(2,1fr)}
#e2 #scrim{position:fixed;inset:0;z-index:30;display:none;align-items:center;justify-content:center;background:rgba(10,10,9,.62);opacity:0;transition:opacity .3s;padding:3vmin;box-sizing:border-box}
#e2 #scrim.show{opacity:1}
#e2 .sheet{width:min(100%,46em);max-height:100%;overflow:hidden;box-sizing:border-box;font-size:max(11px,var(--u));padding:1.1em 1.3em 1em;position:relative;
  background:radial-gradient(ellipse at 50% 0,rgba(217,179,91,.12),rgba(10,10,9,.94) 70%);border:1px solid rgba(217,179,91,.3);box-shadow:0 0 3em rgba(217,179,91,.15)}
#e2 .sheet::before,#e2 .sheet::after{content:"";position:absolute;width:.9em;height:.9em;border:1px solid var(--pale);opacity:.7}
#e2 .sheet::before{left:-1px;top:-1px;border-right:0;border-bottom:0}
#e2 .sheet::after{right:-1px;bottom:-1px;border-left:0;border-top:0}
#e2 .ph{display:flex;align-items:baseline;gap:.9em;margin-bottom:.7em}
#e2 .ph h2{margin:0;font-size:1.25em;text-align:left;text-indent:0}
#e2 .ph span{font-weight:300;font-size:.7em;letter-spacing:.4em;color:var(--gold);flex:1}
#e2 .ph button{background:none;border:1px solid rgba(217,179,91,.35);color:var(--pale);font:300 1em Cinzel,Georgia,serif;width:1.9em;height:1.9em;cursor:pointer;line-height:1;padding:0}
#e2 .big{display:grid;grid-template-columns:1fr 1fr;gap:.5em;text-align:center;margin:.3em 0 .8em}
#e2 .big b{display:block;font-weight:400;font-size:3em;line-height:1;text-shadow:0 0 16px rgba(217,179,91,.75);font-variant-numeric:tabular-nums}
#e2 .big i{display:block;font-style:normal;font-weight:300;font-size:.66em;letter-spacing:.32em;color:var(--gold);margin-top:.5em}
#e2 dl{margin:0 0 .8em;font-size:.82em;line-height:1.45;display:grid;grid-template-columns:5.5em 1fr;gap:.35em .8em}
#e2 dt{color:var(--gold);letter-spacing:.2em;text-transform:uppercase;font-size:.8em;font-weight:300;padding-top:.2em}
#e2 dd{margin:0;opacity:.9;font-family:Georgia,serif;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;word-break:break-word}
#e2 .notrack{text-align:center;margin:.6em 0 1em;font-family:Georgia,serif;font-size:.95em;line-height:1.4;opacity:.9}
#e2 .notrack b{display:block;font:300 .8em Cinzel,Georgia,serif;letter-spacing:.4em;color:var(--gold);margin-bottom:.5em}
#e2 table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.84em}
#e2 th{font-weight:300;letter-spacing:.16em;text-transform:uppercase;font-size:.78em;color:var(--gold);text-align:left;padding:.35em .4em;border-bottom:1px solid rgba(217,179,91,.3)}
#e2 td{padding:.38em .4em;border-bottom:1px solid rgba(217,179,91,.1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:Georgia,serif}
#e2 th:nth-child(1),#e2 td:nth-child(1){width:27%}#e2 th:nth-child(2),#e2 td:nth-child(2){width:20%}
#e2 th:nth-child(4),#e2 td:nth-child(4){width:15%;text-align:right}#e2 th:nth-child(5),#e2 td:nth-child(5){width:17%;text-align:right}
#e2 td:nth-child(1){color:var(--pale)}
#e2 .more{font-size:.74em;letter-spacing:.2em;color:var(--gold);opacity:.7;margin-top:.6em;text-align:center}
#e2 .chip{display:inline-flex;align-items:center;gap:.8em;max-width:100%;box-sizing:border-box;cursor:pointer;background:rgba(10,10,9,.8);border:1px solid rgba(217,179,91,.5);color:var(--pale);padding:.7em 1em;font:300 .78em Cinzel,Georgia,serif;letter-spacing:.2em}
#e2 .chip code{font:400 1.05em ui-monospace,Menlo,monospace;letter-spacing:0;color:var(--gold);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
#e2 .chip em{font-style:normal;color:var(--gold);opacity:.8}
#e2 a.chip{text-decoration:none}#e2 .chip.door code{letter-spacing:.12em}
#e2 .chip.done{border-color:var(--pale);box-shadow:0 0 1.2em rgba(243,220,154,.5)}
#e2 .nodesk{font:300 .76em Georgia,serif;letter-spacing:.04em;opacity:.7;line-height:1.4}
#e2 .nodesk b{font:300 1em Cinzel,Georgia,serif;letter-spacing:.2em;color:var(--gold);display:block;margin-bottom:.3em}
#e2 .deskrow{text-align:center}
#e2 #dock{position:fixed;left:2vmin;bottom:2vmin;z-index:22;display:none;max-width:min(94vw,40em);font-size:max(11px,var(--u));text-align:left}
#e2 #dock .nodesk{background:rgba(10,10,9,.8);padding:.6em 1em;border:1px solid rgba(217,179,91,.25)}
#e2 #stg.dimmed{opacity:.3;transition:opacity .3s}
/* ---- v2 layout ---- */
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
#e2.top #gl .grp{background:rgba(10,10,9,.82);box-shadow:0 0 40px 24px rgba(10,10,9,.82)}
#e2.top .gly i.ag{opacity:.85;font-size:max(.62em,11px)}
#e2.top .gly small.why{-webkit-line-clamp:4!important;font:400 max(.62em,13px)/1.35 Georgia,"Palatino Linotype",serif!important;letter-spacing:.01em!important;text-transform:none!important;opacity:.85}
#e2.top .gly small.why::first-letter{text-transform:uppercase}
#e2.top .gly small.num em{font-style:normal;font-size:.42em;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);opacity:.8;margin:0 .9em 0 .35em;vertical-align:.25em}
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
`;
document.head.appendChild(style);

const root = document.createElement('div'); root.id='e2';
const arc = (r,a0,a1)=>{const p=a=>[Math.cos(a)*r,Math.sin(a)*r];const[x0,y0]=p(a0),[x1,y1]=p(a1);return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;};
const rr = v => v>0 ? 1.6+8.2*Math.min(1,Math.log10(1+v)/Math.log10(2001)) : 0;
const esc = t => String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let data = keep.data || {};
function gstate(p){
  if(p.ring===0){
    const h=(data.hunts||{})[p.hk];
    if(!data.hunts) return {empty:true,reason:'loading'};
    if(!h) return {empty:true,reason:'not in the feed'};
    if(h.sent==null||h.status==='empty') return {empty:true,reason:h.reason||'not tracked yet',h};
    return {sent:h.sent,ans:h.answered||0,h,partial:h.status==='partial'};
  }
  const r=(data.roosts||{})[p.rk];
  if(!data.roosts) return {empty:true,reason:'loading'};
  if(!r) return {empty:true,reason:'not in the feed'};
  const rows=r.rows||[];
  if(!rows.length) return {empty:true,reason:r.reason||r.note||'no rows yet',r};
  return {sent:rows.length,ans:rows.reduce((a,x)=>a+(+x.contracts||0),0),r,rows};
}
function glyphSvg(s){
  let g='<circle r="10.4" fill="none" stroke="#d9b35b" stroke-opacity=".16"/>';
  if(s.empty) g+='<circle r="6.5" fill="none" stroke="#d9b35b" stroke-opacity=".4" stroke-dasharray="1.2 2.2"/>';
  else{
    g+=`<circle r="${rr(s.sent).toFixed(2)}" fill="rgba(217,179,91,.08)" stroke="#f3dc9a" stroke-width="1.1"/>`;
    g+= s.ans>0 ? `<circle r="${rr(s.ans).toFixed(2)}" fill="rgba(243,220,154,.3)" stroke="#d9b35b" stroke-width="1"/>` : '<circle r="1" fill="#d9b35b" opacity=".55"/>';
  }
  return `<svg viewBox="-11 -11 22 22">${g}</svg>`;
}
function glyphText(p,s){
  const nm=`${p.short}<i class="ag" title="the agent working this lane">${esc(String((DOORS[p.hk||p.rk]||{}).agent||'').toUpperCase())}</i>`;
  if(s.empty) return `${nm}<small class="why">${esc(s.reason)}</small>`;
  if(p.ring===0) return `${nm}<small class="num">${s.sent}<em>sent</em> ${s.ans}<em>back</em></small>`;
  const unit = (CFG.units||{})[p.rk] || (p.rk==='clients' ? (s.sent===1?'client':'clients') : (s.sent===1?'person':'people'));
  return `${nm}<small class="num">${s.sent}<em>${unit}</em></small>`;
}
const laneHref = p => !CFG.lanePages ? null : (CFG.laneBase||'') + '/' + (p.ring?'roost':'hunt') + '/' + (p.hk||p.rk);
const glyphs = PIPES.map(p=>{ const h=laneHref(p); return h ? `<a class="gly dim" data-i="${p.i}" href="${h}" aria-label="${esc(p.name)}: open its page"><span class="gs"></span><span class="gt"></span></a>` : `<div class="gly dim" data-i="${p.i}" role="button" tabindex="0"><span class="gs"></span><span class="gt"></span></div>`; });
const grp = (r,t)=>`<div class="grp" id="grp${r}" data-region="${r?'roosts':'hunts'}"><h3>${t}</h3><div class="row">${PIPES.filter(p=>p.ring===r).map(p=>glyphs[p.i]).join('')}</div></div>`;
const numsHtml = ()=>KEY4.map(([k,l])=>`<div><b data-k="${k}">0</b><i>${l}</i></div>`).join('');
root.innerHTML = `<div id="stg"><canvas class="main"></canvas>
<div id="gl" class="hud">${grp(0,'HUNTS')}${grp(1,'ROOSTS')}</div>
<div id="lv" class="hud"><div class="card" id="livecard" data-region="live"><div class="eyebrow"><span class="dot"></span>${esc(CFG.liveLabel||'HUNT')} &middot; LIVE</div>
<h2>${PIPES[LIVE].name}</h2><div class="nums">${numsHtml()}</div><canvas class="stream"></canvas><div class="age" title="the newest hand-action row in this lane's ledger"></div></div></div>
<div id="gr" class="hud"></div><div id="eyebox" data-region="eye"></div><div id="lift"></div><div id="mark" data-region="mark">${esc(CFG.title||'EAGLE EYE')}</div></div>
<iframe id="hero" title="pipeline"></iframe><button id="back">&larr; &nbsp;EAGLE EYE</button>
<div id="dock"></div><div id="scrim"><div class="sheet" id="sheet"></div></div>`;
document.body.appendChild(root);
const stg = root.querySelector('#stg'), ifr = root.querySelector('#hero'), backBtn = root.querySelector('#back');
const cv = root.querySelector('canvas.main'), ctx = cv.getContext('2d');
const stCv = root.querySelector('canvas.stream'), sctx = stCv.getContext('2d');
const liveCard = root.querySelector('#livecard'), lift = root.querySelector('#lift');
liveCard.remove(); root.querySelector('#lv').remove();
const scrim = root.querySelector('#scrim'), sheet = root.querySelector('#sheet'), dock = root.querySelector('#dock');
const glA = root.querySelector('#gl'), glB = root.querySelector('#gr'), lvBox = root.querySelector('#lv'), eyeBox = root.querySelector('#eyebox');
const grpH = root.querySelector('#grp0'), grpR = root.querySelector('#grp1');
const glyEl = {}; root.querySelectorAll('.gly').forEach(g=>glyEl[g.dataset.i]=g);
const actV = PIPES.map(()=>.1), actT = PIPES.map(()=>.1);
function updateGlyphs(){
  for(const p of PIPES){
    const s=gstate(p), el=glyEl[p.i];
    el.querySelector('.gs').innerHTML=glyphSvg(s); el.querySelector('.gt').innerHTML=glyphText(p,s);
    el.classList.toggle('dim',!!s.empty);
    el.title = s.empty ? s.reason : (p.ring===0 ? `${p.name}: sent ${s.sent}, came back ${s.ans}` : `${p.name}: ${s.sent} rows, ${s.ans} contracts`);
    actT[p.i] = s.empty ? .04 : Math.min(.8,.1+.55*Math.log10(1+s.sent)/3.3);
  }
}
let pipeIds = new Set();
const pipesReady = CFG.pipelines===false ? Promise.resolve() : fetch(CFG.pipelines||'/pipelines.json',{cache:'no-store'}).then(r=>r.json()).then(j=>{pipeIds=new Set((j.pipelines||[]).map(x=>x.id));}).catch(()=>{});
const numEls = {}; liveCard.querySelectorAll('b[data-k]').forEach(b=>numEls[b.dataset.k]=b);
const ageEl = liveCard.querySelector('.age'); const paintAge = ()=>{ if(ageEl) ageEl.textContent = lastRow((data.hunts||{})[PIPES[LIVE].hk]); };

let liveAct = keep.liveAct ?? 0.5, liveTarget = liveAct;
const shown = {}; for(const [k] of STAGES) shown[k] = data[k]||0;
async function pull(){
  try{
    const r = await fetch(FEED+(FEED.includes('?')?'&':'?')+Date.now(), {cache:'no-store'});
    const d = await r.json();
    for(const [k] of KEY4) if(d[k]!==data[k]) { const el=numEls[k]; if(el){el.classList.add('flash'); setTimeout(()=>el.classList.remove('flash'),900);} }
    data = d; paintAge(); updateGlyphs(); refit(); if(liftFor>=0) lift.innerHTML=liftHtml(PIPES[liftFor]); refreshPanel();
    const s = (d.proposals_sent||0)+6*(d.proposals_answered||0)+8*(d.videos_sent||0)+25*(d.contracts||0)+40*(d.paid_events||0);
    liveTarget = Math.min(1, 0.4+Math.log10(1+s)/3.2);
  }catch(e){}
}
updateGlyphs(); pull(); const poll = setInterval(pull, 5000);

function sprite(rgb,size){const c=document.createElement('canvas');c.width=c.height=size;const g=c.getContext('2d'),h=size/2;
  const gr=g.createRadialGradient(h,h,0,h,h,h);gr.addColorStop(0,`rgba(${rgb},1)`);gr.addColorStop(.18,`rgba(${rgb},.75)`);gr.addColorStop(.5,`rgba(${rgb},.14)`);gr.addColorStop(1,`rgba(${rgb},0)`);
  g.fillStyle=gr;g.fillRect(0,0,size,size);return c;}
const spGold=sprite('217,179,91',32), spPale=sprite('243,220,154',32);

let W,H,DPR,cx,cy,R,lidW,wide,rot=[0,0];
function resize(){
  DPR=Math.min(devicePixelRatio||1,2); W=innerWidth; H=innerHeight;
  cv.width=W*DPR; cv.height=H*DPR; cx=W/2;
  wide = false;
  const u = Math.max(11, Math.min(W,H)/74);
  root.style.setProperty('--u', u+'px');
  const narrow = W < 700;
  const stack = narrow || W/H < 1.05;
  root.className = 'top rows'+(narrow?' narrow':'')+(stack?' stack':'');
  let gf = narrow ? 1.5 : (W>2400 ? 2.9 : 2.5);
  const setGf = ()=>root.style.setProperty('--gf', gf+'em');
  const gp = (narrow?1:2.4)*u, lw = stack ? Math.min(W-2*gp, 70*u) : Math.min(W-2*gp, Math.max(60*u, 0.62*W), 150*u);
  root.style.setProperty('--gg', (narrow?1:3.2)*u+'px'); root.style.setProperty('--lw', lw+'px'); root.style.setProperty('--gx', ((W-lw)/2)+'px');
  if(grpH.parentNode!==glA || grpR.parentNode!==glA){ glA.appendChild(grpH); glA.appendChild(grpR); }
  const pt = (narrow?1.2:2.2)*u, markH = 3.2*u, minR = Math.max(40, Math.min(H*.13, W*.11));
  const fits = ()=>[...glA.querySelectorAll('.gt')].every(e=>e.scrollWidth<=e.clientWidth+1);
  for(let k=0;k<40;k++){ setGf(); root.style.setProperty('--pt', pt+'px');
    const hh = stack ? grpH.offsetHeight + grpR.offsetHeight + u : Math.max(grpH.offsetHeight, grpR.offsetHeight), top = pt + hh + (narrow?1.2:2)*u;
    const avail = H - top - markH;
    R = Math.min(avail/2.9, W*.2); lidW = Math.min(W*.44, R*1.75, (W-2*gp)/2 - 8); R = Math.min(R, lidW/1.5);
    cy = top + avail/2;
    if((R >= minR && hh <= H*.6 && fits()) || gf <= .8) break;
    gf -= .05; }
  R = Math.max(R, 20); lidW = Math.max(lidW, 30);
  root.style.setProperty('--u', u+'px');
  root.style.setProperty('--ex', lidW+'px');
  root.style.setProperty('--ey', (R*1.44)+'px');
  Object.assign(eyeBox.style, {left:(cx-lidW-8)+'px', top:(cy-R*1.42)+'px', width:(2*lidW+16)+'px', height:(R*2.84)+'px'});
  const face = wide ? 0 : Math.PI/2;
  rot[0] = face - (PIPES[LIVE].a0+PIPES[LIVE].aw/2);
  { const r1=PIPES.find(p=>p.ring===1); rot[1] = -Math.PI/2 + (r1?r1.aw/2:0); }
}
addEventListener('resize', resize); resize();
let fitSig = '';
function refit(){ const s = root.querySelector('#gl').textContent + glB.textContent; if(s!==fitSig){ fitSig=s; resize(); } }
if(document.fonts && document.fonts.ready) document.fonts.ready.then(()=>{ fitSig=''; refit(); });

const rnd=(a,b)=>a+Math.random()*(b-a);
const segMid=(p)=>rot[p.ring]+p.a0+p.aw/2;
const parts=[];
PIPES.forEach(p=>{ const n=p.live?650:150; for(let j=0;j<n;j++) parts.push({pi:p.i, ring:p.ring, k:p.k, off:rnd(-1,1), p:Math.random(), sp:rnd(.04,.12), w:rnd(.05,.16)*(Math.random()<.5?-1:1), s:rnd(.5,1.5), tw:rnd(0,TAU), pale:Math.random()<.25, del:Math.random()*1.4, sw:rnd(-1.5,1.5), gate:Math.random()}); });
const fibres=[];for(let i=0;i<900;i++)fibres.push({a:rnd(0,TAU),r:rnd(.3,1.02),l:rnd(.03,.12),tw:rnd(0,TAU),del:Math.random()*1.5});
const conv=[];for(let i=0;i<420;i++)conv.push({a:rnd(0,TAU),p:Math.random(),sp:rnd(.15,.4),sw:rnd(.6,2)});
const lid=[];for(let i=0;i<900;i++)lid.push({t:Math.random(),up:Math.random()<.5,off:rnd(-1,1),tw:rnd(0,TAU),s:rnd(.6,1.4)});
const stars=[];for(let i=0;i<160;i++)stars.push({x:Math.random(),y:Math.random(),tw:rnd(0,TAU),s:rnd(.3,.9)});
const fp=[];for(let i=0;i<170;i++)fp.push({s:Math.random()*5,y:rnd(-1,1),sp:rnd(.25,.6),tw:rnd(0,TAU)});

let mx=-1,my=-1,hover=-1,glyHover=-1,hv=new Array(PIPES.length).fill(0);
const onMove=e=>{mx=e.clientX;my=e.clientY;}, onLeave=()=>{mx=my=-1;};
addEventListener('pointermove',onMove); document.addEventListener('pointerleave',onLeave);
root.querySelectorAll('.gly').forEach(g=>{g.addEventListener('pointerenter',()=>glyHover=+g.dataset.i);g.addEventListener('pointerleave',()=>glyHover=-1);});
liveCard.addEventListener('pointerenter',()=>glyHover=LIVE); liveCard.addEventListener('pointerleave',()=>glyHover=-1);
function segAt(x,y){
  const dx=x-cx,dy=y-cy,d=Math.hypot(dx,dy)/R; if(d<.3||d>1.04) return -1;
  const ring = d<.61?1:0; let a=Math.atan2(dy,dx)-rot[ring]; a=((a%TAU)+TAU)%TAU;
  const p=PIPES.find(p=>p.ring===ring&&a>=p.a0&&a<p.a0+p.aw);
  return p?p.i:-1;
}

let liftFor=-2;
function liftHtml(p){
  const s=gstate(p), kind=p.ring?'ROOST':'HUNT';
  if(s.empty) return `<div class="card"><div class="eyebrow">${kind}</div><h2>${p.name}</h2><div class="idle why">${esc(s.reason)}</div></div>`;
  if(p.live) return `<div class="card"><div class="eyebrow"><span class="dot"></span>LIVE</div><h2>${p.name}</h2><div class="nums">${KEY4.map(([k,l])=>`<div><b>${data[k]||0}</b><i>${l}</i></div>`).join('')}</div><div class="idle why">${esc(s.h.window||'')}</div>${lastRow(s.h)?`<div class="idle why">${esc(lastRow(s.h))}</div>`:''}</div>`;
  if(p.ring===0) return `<div class="card"><div class="eyebrow">${kind}</div><h2>${p.name}</h2><div class="nums two"><div><b>${s.sent}</b><i>sent</i></div><div><b>${s.ans}</b><i>came back</i></div></div><div class="idle why">${esc(s.h.window||'')}</div>${lastRow(s.h)?`<div class="idle why">${esc(lastRow(s.h))}</div>`:''}</div>`;
  return `<div class="card"><div class="eyebrow">${kind}</div><h2>${p.name}</h2><div class="nums two"><div><b>${s.sent}</b><i>${s.sent===1?'person':'people'}</i></div><div><b>${s.ans}</b><i>contracts</i></div></div></div>`;
}
function setLift(i){
  if(i===liftFor) return; liftFor=i;
  liveCard.classList.toggle('lifted', i===LIVE);
  root.querySelectorAll('.gly').forEach(g=>g.classList.toggle('on', +g.dataset.i===i));
  if(i<0){ lift.style.opacity=0; return; }
  const p=PIPES[i]; lift.innerHTML=liftHtml(p);
  const src = p.live? liveCard : root.querySelector(`.gly[data-i="${i}"]`);
  const sr = src.getBoundingClientRect();
  const m = segMid(p), rr = R*.46;
  let tx = cx+Math.cos(m)*rr, ty = cy+Math.sin(m)*rr;
  const lw = lift.offsetWidth, lh = lift.offsetHeight;
  tx = Math.max(lw/2+8, Math.min(W-lw/2-8, tx)); ty = Math.max(lh/2+8, Math.min(H-lh/2-8, ty));
  lift.style.transition='none'; lift.style.opacity=0;
  lift.style.transform=`translate(${sr.left+sr.width/2-lw/2}px,${sr.top+sr.height/2-lh/2}px) scale(.35)`;
  void lift.offsetWidth;
  lift.style.transition=''; lift.style.opacity=1;
  lift.style.transform=`translate(${tx-lw/2}px,${ty-lh/2}px) scale(1)`;
}

const ease=t=>t<0?0:t>1?1:1-Math.pow(1-t,3);
function lidY(x,openness,up){const k=1-x*x;return(up?-1:1)*(R*1.16)*openness*Math.pow(k,.9);}

function drawStream(t,dt){
  const w=stCv.clientWidth,h=stCv.clientHeight; if(!w||!h) return;
  if(stCv.width!==Math.round(w*DPR)||stCv.height!==Math.round(h*DPR)){stCv.width=Math.round(w*DPR);stCv.height=Math.round(h*DPR);}
  sctx.setTransform(DPR,0,0,DPR,0,0); sctx.clearRect(0,0,w,h);
  const n=STAGES.length, pad=w*.07, X=s=>pad+s*(w-2*pad)/(n-1), fs=Math.max(10,w/38), lab=Math.max(10,fs*.8)+5, my0=(h-lab)*.56;
  const v=STAGES.map(([k])=>data[k]||0), vmax=Math.max(1,...v), lm=Math.log(1+vmax);
  const half=s=>{const i=Math.min(n-1,Math.floor(s)),f=s-i,a=Math.log(1+v[i])/lm,b=Math.log(1+v[Math.min(n-1,i+1)])/lm;return (.06+.94*(a+(b-a)*f))*Math.max(2,Math.min(h*.3,(h-lab)*.36,my0-fs*1.15-12));};
  sctx.globalCompositeOperation='lighter';
  for(const q of fp){
    const before=Math.floor(q.s); q.s+=q.sp*dt*1.3;
    const after=Math.floor(q.s);
    if(after>before){
      const prev=v[before], next=v[after]||0, keepP = after>=n? 0 : (prev>0? Math.pow(Math.min(1,next/prev),.5):0);
      if(Math.random()>keepP){ q.s=Math.random()*.3; q.y=rnd(-1,1); continue; }
    }
    if(q.s>=n-1){ q.s=Math.random()*.3; q.y=rnd(-1,1); continue; }
    const x=X(q.s), y=my0+q.y*half(q.s)+Math.sin(t*2+q.tw)*.8;
    sctx.globalAlpha=Math.min(1,Math.sin(Math.PI*(q.s/(n-1)))*1.6+.25)*(.55+.4*Math.sin(t*3+q.tw)); const z=5;
    sctx.drawImage(q.tw>3?spPale:spGold,x-z/2,y-z/2,z,z);
  }
  sctx.globalCompositeOperation='source-over';
  sctx.textAlign='center';
  for(let i=0;i<n;i++){
    const x=X(i);
    sctx.globalAlpha=.9; sctx.strokeStyle='#f3dc9a'; sctx.lineWidth=1; sctx.beginPath(); sctx.moveTo(x,my0-half(i)-3); sctx.lineTo(x,my0+half(i)+3); sctx.stroke();
    sctx.fillStyle='#f3dc9a'; sctx.font=`400 ${fs*1.15}px Cinzel,Georgia,serif`; sctx.globalAlpha=1;
    sctx.fillText(String(v[i]),x,my0-half(i)-9);
    sctx.fillStyle='#d9b35b'; const lt=STAGES[i][1].toUpperCase(), slot=(w-2*pad)/(n-1)*.94; let lf=Math.max(11,fs*.8); sctx.font=`300 ${lf}px Cinzel,Georgia,serif`;
    const lw=sctx.measureText(lt).width; if(lw>slot){ lf=Math.max(10,lf*slot/lw); sctx.font=`300 ${lf}px Cinzel,Georgia,serif`; } sctx.globalAlpha=.85;
    sctx.fillText(lt,x,h-1);
  }
}

let route = 'home', busy = false, curP = null, panelFor = -1, panelSig = '';
function sliceXY(p){ const m=segMid(p), rr=R*(p.ring?.46:.81)*1; return [cx+Math.cos(m)*rr, cy+Math.sin(m)*rr]; }
const deskHtml = p => { const d=DOORS[p.hk||p.rk]||{}, who=String(d.agent||'?').toUpperCase();
  return d.url
  ? `<a class="chip door" href="${esc(d.url)}" target="desk-${esc(p.id)}" title="${esc(d.where||'')}"><span>GO TO</span><code>${esc(who)}&#39;S ${d.kind==='desk'?'DESK':'VIEW'}</code><em>&rsaquo;</em></a>`
  : `<div class="nodesk"><b>GO TO THE DESK</b>${esc(who)} &middot; no desk and no view declared for this lane</div>`; };
function hashFor(p){ return p.live?'#hero':'#pipe-'+p.pid; }
function goHero(p,instant){
  if(route!=='home'||busy) return; route='hero'; busy=true; curP=p;
  const [ox,oy]=sliceXY(p);
  setLift(-1);
  ifr.src = p.live ? '/hero.html' : '/pipeline.html?p='+encodeURIComponent(p.pid);
  if(!p.live){ dock.innerHTML=deskHtml(p); dock.style.display='block'; }
  if(instant){ stg.style.transition='none'; ifr.style.transition='none'; backBtn.style.transition='none'; }
  stg.style.transformOrigin=ox+'px '+oy+'px'; ifr.style.transformOrigin=ox+'px '+oy+'px';
  stg.classList.add('out'); ifr.classList.add('in'); backBtn.style.display='block';
  setTimeout(()=>{ backBtn.classList.add('show'); busy=false; stg.style.transition=ifr.style.transition=backBtn.style.transition=''; }, instant?30:1200);
}
function goHome(){
  if(route!=='hero'||busy) return; route='home'; busy=true; dock.style.display='none';
  backBtn.classList.remove('show');
  ifr.classList.remove('in'); stg.classList.remove('out');
  setTimeout(()=>{ backBtn.style.display='none'; ifr.src='about:blank'; busy=false; }, 1100);
}
function sheetHead(p,kind){ return `<div class="ph"><h2>${esc(p.name)}</h2><span>${kind}</span><button class="x" aria-label="close">&times;</button></div>`; }
function renderSheet(p,nRows){
  const s=gstate(p);
  if(p.ring===0){
    const h=s.h||{};
    let body;
    if(s.empty) body=`<div class="notrack"><b>NOT TRACKED YET</b>${esc(s.reason)}</div>`;
    else body=`<div class="big"><div><b>${s.sent}</b><i>SENT</i></div><div><b>${s.ans}</b><i>CAME BACK</i></div></div>`;
    const dl=[['last row',h.last_action&&h.last_action.ts?`${ago(h.last_action.ts)} · ${h.last_action.event} · ${h.last_action.ts}`:null],['window',h.window],['counts',h.what],['source',h.source],['note',s.empty?null:h.reason]].filter(x=>x[1]).map(([k,v])=>`<dt>${k}</dt><dd title="${esc(v)}">${esc(v)}</dd>`).join('');
    return sheetHead(p,'HUNT')+body+(dl?`<dl>${dl}</dl>`:'')+`<div class="deskrow">${deskHtml(p)}</div>`;
  }
  const r=(data.roosts||{})[p.rk]||{};
  if(s.empty) return sheetHead(p,'ROOST')+`<div class="notrack"><b>NOTHING HERE YET</b>${esc(s.reason)}</div>`+(r.source?`<dl><dt>source</dt><dd title="${esc(r.source)}">${esc(r.source)}</dd></dl>`:'')+`<div class="deskrow">${deskHtml(p)}</div>`;
  let rows=s.rows.slice();
  if(p.rk==='network'){ const rk=x=>/offer/i.test(x.stage)?0:/interview/i.test(x.stage)?1:/screen|call/i.test(x.stage)?2:3; rows=rows.map((x,i)=>[x,i]).sort((a,b)=>rk(a[0])-rk(b[0])||String(b[0].at||'').localeCompare(String(a[0].at||''))||a[1]-b[1]).map(a=>a[0]); }
  const shown=rows.slice(0,Math.max(1,nRows));
  const tr=shown.map(x=>`<tr><td title="${esc(x.name)}">${esc(x.name)}</td><td title="${esc(srcName(x.hunt))}">${esc(srcName(x.hunt))}</td><td title="${esc(x.stage)}">${esc(x.stage)}</td><td>${+x.contracts||0}</td><td title="${esc(x.paid)}">${esc(x.paid||'$0')}</td></tr>`).join('');
  const more=rows.length-shown.length;
  return sheetHead(p,`ROOST &middot; ${rows.length} ${rows.length===1?'ROW':'ROWS'}`)+`<table><thead><tr><th>Name</th><th>Source</th><th>Stage</th><th>Contracts</th><th>Paid</th></tr></thead><tbody>${tr}</tbody></table>`+(more>0?`<div class="more">+ ${more} MORE</div>`:'')+`<div class="deskrow">${deskHtml(p)}</div>`;
}
function fillSheet(p){
  const maxH=innerHeight*.94-2;
  if(p.ring===0||gstate(p).empty){ sheet.innerHTML=renderSheet(p,0); return; }
  const total=gstate(p).rows.length;
  sheet.innerHTML=renderSheet(p,1);
  const tr=sheet.querySelector('tbody tr'); const rowH=tr?tr.offsetHeight:20, base=sheet.offsetHeight;
  let n=Math.max(1,Math.min(total,1+Math.floor((maxH-base-(total>1?rowH*.2:0))/rowH)));
  sheet.innerHTML=renderSheet(p,n);
  while(n>1 && sheet.scrollHeight>maxH){ n--; sheet.innerHTML=renderSheet(p,n); }
}
function openSheet(p){
  panelFor=p.i; setLift(-1); scrim.style.display='flex'; fillSheet(p); panelSig=JSON.stringify([gstate(p)]);
  void scrim.offsetWidth; scrim.classList.add('show'); stg.classList.add('dimmed');
}
function closeSheet(){
  if(panelFor<0) return; panelFor=-1; scrim.classList.remove('show'); stg.classList.remove('dimmed');
  setTimeout(()=>{ if(panelFor<0) scrim.style.display='none'; },320);
}
function refreshPanel(){
  if(panelFor<0) return; const p=PIPES[panelFor], sig=JSON.stringify([gstate(p)]);
  if(sig!==panelSig){ panelSig=sig; fillSheet(p); }
}
function select(i){
  if(route!=='home'||busy||panelFor>=0) return;
  const p=PIPES[i];
  if(p.ring===0 && ((p.live && CFG.hero!==false) || (p.pid && pipeIds.has(p.pid)))){ try{history.pushState({r:p.id},'',hashFor(p))}catch(_){} goHero(p); }
  else openSheet(p);
}
function copyText(t,btn){
  const done=()=>{ btn.classList.add('done'); const e=btn.querySelector('em'); if(e) e.textContent='COPIED'; setTimeout(()=>{btn.classList.remove('done'); if(e) e.textContent='COPY';},1600); };
  const fb=()=>{ try{ const a=document.createElement('textarea'); a.value=t; a.style.cssText='position:fixed;opacity:0'; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }catch(_){} done(); };
  try{ navigator.clipboard.writeText(t).then(done,fb); }catch(_){ fb(); }
}
const onClick=e=>{
  const chip=e.target.closest&&e.target.closest('.chip'); if(chip){ if(chip.dataset.copy) copyText(chip.dataset.copy,chip); return; }
  if(panelFor>=0){ if(e.target===scrim||e.target.closest('.x')) closeSheet(); return; }
  if(route!=='home') return;
  const g=e.target.closest&&e.target.closest('.gly'); if(g){ if(g.tagName==='A') return; select(+g.dataset.i); return; }
  if(liveCard.contains(e.target)){ select(LIVE); return; }
  const s=segAt(e.clientX,e.clientY); if(s>=0){ const h=laneHref(PIPES[s]); if(h){ location.href=h; return; } select(s); }
};
const onPop=()=>{
  if(panelFor>=0) closeSheet();
  const h=location.hash;
  if(h==='#hero'){ goHero(PIPES[LIVE]); return; }
  if(h.startsWith('#pipe-')){ const p=PIPES.find(p=>p.pid&&'#pipe-'+p.pid===h); if(p){ goHero(p); return; } }
  goHome();
};
const onKey=e=>{ if(e.key==='Escape'){ if(panelFor>=0) closeSheet(); else if(route==='hero'){ try{history.back()}catch(_){goHome()} } }
  if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('gly')){ e.preventDefault(); select(+e.target.dataset.i); } };
backBtn.addEventListener('click',()=>{ try{ if(location.hash) history.back(); else goHome(); }catch(_){goHome()} });
addEventListener('click',onClick); addEventListener('popstate',onPop); addEventListener('hashchange',onPop); addEventListener('keydown',onKey);
pipesReady.then(()=>{ if(location.hash) onPop(); });

const skip=parseFloat(new URLSearchParams(location.search).get('t')||0);
let first=true;
const t0 = performance.now()-skip*1000;
let last=performance.now(), raf=0;
function frame(now){
  raf=requestAnimationFrame(frame);
  if(route==='hero'&&!busy){ last=now; return; }
  const t=(now-t0)/1000, dt=Math.min(.05,(now-last)/1000); last=now;
  liveAct+=(liveTarget-liveAct)*Math.min(1,dt*1.5);
  for(const [k] of STAGES){ shown[k]+=((data[k]||0)-shown[k])*Math.min(1,dt*4); if(numEls[k]) numEls[k].textContent=Math.round(shown[k]); }
  const sm=u=>{u=Math.max(0,Math.min(1,u));return u*u*(3-2*u);};
  const open = sm((t-.3)/2.4);
  const hs = (mx>=0 && panelFor<0) ? segAt(mx,my) : -1; hover = panelFor>=0 ? -1 : (hs>=0 ? hs : glyHover);
  setLift(hover);
  for(let i=0;i<PIPES.length;i++) hv[i]+=((hover===i?1:0)-hv[i])*Math.min(1,dt*6);
  root.style.cursor=hover>=0?'pointer':'default';
  for(let i=0;i<actV.length;i++) actV[i]+=(actT[i]-actV[i])*Math.min(1,dt*1.5);
  const act=i=>PIPES[i].live?liveAct:actV[i];

  ctx.setTransform(DPR,0,0,DPR,0,0); ctx.globalCompositeOperation='source-over';
  ctx.fillStyle='#0a0a09'; ctx.fillRect(0,0,W,H);
  const intro=Math.max(ease(t/3.2)*.6,sm((t-.3)/2.4));
  ctx.globalCompositeOperation='lighter';
  for(const s of stars){ctx.globalAlpha=Math.max(0,(.12+.18*Math.sin(t*.7+s.tw))*intro);const z=5*s.s;ctx.drawImage(spGold,s.x*W-z/2,s.y*H-z/2,z,z);}
  const bl=ctx.createRadialGradient(cx,cy,R*.2,cx,cy,R*1.25);
  bl.addColorStop(0,`rgba(217,179,91,${.10*intro})`);bl.addColorStop(.6,`rgba(217,179,91,${.04*intro})`);bl.addColorStop(1,'rgba(217,179,91,0)');
  ctx.globalAlpha=1;ctx.fillStyle=bl;ctx.fillRect(0,0,W,H);

  ctx.save(); ctx.beginPath();
  const steps=48;
  for(let i=0;i<=steps;i++){const x=-1+2*i/steps;const px=cx+x*lidW,py=cy+lidY(x,open,true);i?ctx.lineTo(px,py):ctx.moveTo(px,py);}
  for(let i=steps;i>=0;i--){const x=-1+2*i/steps;ctx.lineTo(cx+x*lidW,cy+lidY(x,open,false));}
  ctx.closePath(); ctx.clip(); ctx.globalCompositeOperation='lighter';

  for(const p of PIPES){
    const a=act(p.i), h=hv[p.i];
    const a0=rot[p.ring]+p.a0+GAP, a1=rot[p.ring]+p.a0+p.aw-GAP;
    const [r0,r1]=RING[p.ring], rm=(r0+r1)/2*R;
    ctx.lineWidth=(r1-r0)*R; ctx.strokeStyle='rgb(217,179,91)';
    ctx.globalAlpha=(.004+.035*a+(p.live?.05:0)+.16*h)*intro; ctx.beginPath(); ctx.arc(cx,cy,rm,a0,a1); ctx.stroke();
    ctx.lineWidth=1; ctx.strokeStyle='rgb(243,220,154)'; ctx.globalAlpha=(.10+.5*a+.4*h)*intro;
    ctx.beginPath(); ctx.arc(cx,cy,r0*R,a0,a1); ctx.stroke(); ctx.beginPath(); ctx.arc(cx,cy,r1*R,a0,a1); ctx.stroke();
  }
  for(const f of fibres){const e=ease((t-f.del*.7)/2.2);if(e<=0)continue;const a=f.a+Math.sin(t*.1+f.tw)*.01,r0=f.r*R*e,r1=(f.r+f.l)*R*e;
    ctx.globalAlpha=(.03+.03*Math.sin(t*.8+f.tw))*e;ctx.strokeStyle='#d9b35b';ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(cx+Math.cos(a)*r0,cy+Math.sin(a)*r0);ctx.lineTo(cx+Math.cos(a)*r1,cy+Math.sin(a)*r1);ctx.stroke();}
  const rim=(r,al,lw)=>{ctx.globalAlpha=al*intro;ctx.lineWidth=lw;ctx.strokeStyle='#f3dc9a';ctx.beginPath();ctx.arc(cx,cy,r*R,0,TAU);ctx.stroke();};
  rim(1.005,.45,1.2);rim(1.03,.12,5);rim(PUPIL,.4,1.2);rim(PUPIL+.01,.08,5);

  for(const q of parts){
    const a=act(q.pi), h=hv[q.pi], vis=a*(.55+.9*h)+h*.25;
    if(q.gate>vis*1.15+.04) continue;
    q.p+=q.sp*dt*(.5+a*1.2+h*1.2); if(q.p>=1){q.p-=1;q.off=rnd(-1,1);}
    const pp=PIPES[q.pi], sw=pp.aw, lim=sw/2-GAP, c=rot[q.ring]+pp.a0+sw/2;
    q.off+=q.w*dt*(.6+h*2)/lim*.5; q.off=Math.max(-1,Math.min(1,q.off));
    const lo=RING[q.ring], f=q.ring?1-q.p:q.p, r=lo[0]+(lo[1]-lo[0])*f;
    const e=ease((t-q.del)/2); if(e<=0) continue;
    const ang=c+q.off*lim+(1-e)*q.sw*2.2, rr=(PUPIL+(r-PUPIL)*e)*R;
    const x=cx+Math.cos(ang)*rr, y=cy+Math.sin(ang)*rr, edge=Math.sin(Math.PI*q.p);
    ctx.globalAlpha=Math.min(1,(.35+.65*Math.min(1,a*1.2))*edge*(.7+.3*Math.sin(t*3+q.tw))*(1+h*.8))*e;
    const z=(3.2*q.s+h*2+a*1.5)*(R/420+.4);
    ctx.drawImage(q.pale||h>.5?spPale:spGold,x-z/2,y-z/2,z,z);
  }
  for(const c of conv){c.p+=c.sp*dt;if(c.p>=1){c.p-=1;c.a=rnd(0,TAU);}
    const r=(PUPIL+(.5-PUPIL)*(1-c.p))*R,a=c.a+c.p*c.sw*.9+t*.05;ctx.globalAlpha=Math.sin(Math.PI*c.p)*.7*intro;const z=3.4;ctx.drawImage(spPale,cx+Math.cos(a)*r-z/2,cy+Math.sin(a)*r-z/2,z,z);}

  ctx.globalCompositeOperation='source-over';
  const pg=ctx.createRadialGradient(cx,cy,0,cx,cy,PUPIL*R);
  pg.addColorStop(0,'rgba(10,10,9,1)');pg.addColorStop(.82,'rgba(10,10,9,.97)');pg.addColorStop(1,'rgba(10,10,9,.6)');
  ctx.globalAlpha=intro;ctx.fillStyle=pg;ctx.beginPath();ctx.arc(cx,cy,PUPIL*R,0,TAU);ctx.fill();
  ctx.globalCompositeOperation='lighter';
  const pulse=.5+.5*Math.sin(t*1.2), ig=ctx.createRadialGradient(cx,cy,PUPIL*R*.6,cx,cy,PUPIL*R*1.35);
  ig.addColorStop(0,'rgba(243,220,154,0)');ig.addColorStop(.55,`rgba(243,220,154,${(.10+.06*pulse)*intro})`);ig.addColorStop(1,'rgba(217,179,91,0)');
  ctx.globalAlpha=1;ctx.fillStyle=ig;ctx.beginPath();ctx.arc(cx,cy,PUPIL*R*1.4,0,TAU);ctx.fill();
  ctx.globalAlpha=.5*intro*open;const cz=R*.09;ctx.drawImage(spPale,cx-R*.09-cz/2,cy-R*.1-cz/2,cz*2,cz*2);
  ctx.restore();

  ctx.globalCompositeOperation='lighter';
  for(const d of lid){const e=Math.min(1,.15+ease((t-.2-d.t*1.6)/1.6));const x=-1+2*d.t,y=lidY(x,open,d.up);
    const px=cx+x*lidW,py=cy+y+d.off*(4+(1-Math.abs(x))*6);
    ctx.globalAlpha=(.55+.4*Math.sin(t*2+d.tw))*e*(.5+.5*Math.min(1,1.2-Math.abs(x)*.6));const z=4.2*d.s;ctx.drawImage(d.tw>3?spPale:spGold,px-z/2,py-z/2,z,z);}
  for(let i=0;i<260;i++){const u=i/259,e=ease((t-.8-u*1.8)/1.4);if(e<=0)continue;const x=-1+2*u;
    const by=cy-R*1.16*open*Math.pow(1-x*x,.9)-R*.17*open-Math.sin(u*Math.PI)*R*.05;
    const j=Math.sin(i*12.9898)*43758.5453,off=(j-Math.floor(j)-.5)*9;
    ctx.globalAlpha=.4*e*(.6+.4*Math.sin(t*1.5+i));const z=3.2;ctx.drawImage(spGold,cx+x*lidW*.98-z/2,by+off-z/2,z,z);}
  ctx.globalCompositeOperation='source-over';

  drawStream(t,dt);
}
raf=requestAnimationFrame(frame);
