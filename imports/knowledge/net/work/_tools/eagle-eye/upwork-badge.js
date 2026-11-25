// knowledge#14038: a quiet count on the home page's Upwork eye: new Upwork jobs + client replies since this browser
// last opened /hunt/upwork (lane.html stores the time), else the last 24 h. Data: /upwork.json (upwork_feed.py).
(()=>{
  let n = 0, tip = '';
  const seen = () => { try{ return +localStorage.getItem('eagle-upwork-seen') || 0; }catch(e){ return 0; } };
  async function load(){
    try{ const r = await fetch('/upwork.json?'+Date.now(), {cache:'no-store'}); if(!r.ok) return; const d = await r.json();
      const since = seen() || Date.now() - 864e5, after = t => Date.parse(t) > since;
      const j = (d.jobs||[]).filter(x=>after(x.postedAt)).length, c = (d.replies||[]).filter(x=>after(x.ts)).length;
      n = j + c; tip = `${j} new ${j===1?'job':'jobs'} · ${c} client ${c===1?'reply':'replies'}`; place(); }catch(e){}
  }
  let rs = null;
  function room(px){
    if(!rs){ rs = document.createElement('style'); document.head.appendChild(rs); }
    const t = px ? `#e2.narrow a.gly[href="/hunt/upwork"] .gt i.ag{padding-left:${Math.round(px)}px}` : '';
    if(rs.textContent !== t) rs.textContent = t;
  }
  function place(){
    const a = document.querySelector('a.gly[href="/hunt/upwork"]'); if(!a) return;
    const gs = a.querySelector('.gs'); let b = a.querySelector('.upb');
    if(!n){ if(b) b.remove(); room(0); return; }
    if(!b){ b = document.createElement('span'); b.className = 'upb'; a.appendChild(b); }
    if(getComputedStyle(a).position === 'static') a.style.position = 'relative';
    b.textContent = n > 99 ? '99+' : String(n); b.title = tip; b.setAttribute('aria-label', tip);
    const ar = a.getBoundingClientRect(), gr = (gs||a).getBoundingClientRect();
    const bw = b.offsetWidth || 18, bh = b.offsetHeight || 16;
    // a phone (the RAW Pixel, 2026-11-16): the glyph is too small to carry it on its corner, and above it the badge hit
    // the HUNTS rule, so it rides after the lane's name instead
    const gt = innerWidth < 700 && a.querySelector('.gt'), nm = gt && gt.firstChild;
    let left = gr.right - ar.left - 9, top = gr.top - ar.top - 3;
    if(nm && nm.nodeType === 3){ const rg = document.createRange(); rg.selectNodeContents(nm); const nr = rg.getBoundingClientRect();
      if(nr.width){ left = nr.right - ar.left + 9; top = nr.top - ar.top + nr.height/2 - bh/2; } }
    // the agent name after it makes room for it; a rule, not an inline style, because the page re-renders the row's text
    room(nm && nm.nodeType === 3 ? bw + 10 : 0);
    Object.assign(b.style, {position:'absolute', left:left+'px', top:top+'px', minWidth:'1.5em',
      padding:'0 .35em', boxSizing:'border-box', textAlign:'center', font:'500 11px/1.5 "Cormorant Garamond",Georgia,serif',
      letterSpacing:'0', color:'#f3dc9a', background:'#0a0a09', border:'1px solid rgba(217,179,91,.55)', borderRadius:'1em',
      pointerEvents:'none', zIndex:'2'});
  }
  load(); setInterval(load, 60000); setInterval(place, 2000); addEventListener('resize', place);
})();
