
// REFRESH (Tyler 2026-11-17, fleetmail 8591): a click target on the desk view so he can reload Eagle Eye while the cursor is driven.
(function(){ var b=document.createElement('button'); b.type='button'; b.id='ee-refresh'; b.textContent='REFRESH'; b.setAttribute('aria-label','Reload Eagle Eye');
  b.style.cssText='position:fixed;right:12px;bottom:12px;z-index:30;font:500 11px/1 Cinzel,Georgia,serif;letter-spacing:.22em;color:#d9b35b;background:rgba(7,7,6,.7);border:1px solid rgba(217,179,91,.5);border-radius:3px;padding:10px 14px;cursor:pointer;opacity:.75';
  b.onclick=function(){ location.reload(); }; document.body.appendChild(b); })();
// VSL SYSTEM link beside REFRESH (Architect, 2026-11-17): the animated diagram of how a VSL is made and sent.
(function(){ var a=document.createElement('a'); a.id='ee-vslsys'; a.href='https://architecture.utopiamodels.ai/vsl-system'; a.target='_blank'; a.rel='noopener'; a.textContent='VSL SYSTEM ↗';
  a.style.cssText='position:fixed;right:110px;bottom:12px;z-index:30;font:500 11px/1 Cinzel,Georgia,serif;letter-spacing:.22em;color:#d9b35b;background:rgba(7,7,6,.7);border:1px solid rgba(217,179,91,.5);border-radius:3px;padding:10px 14px;text-decoration:none;opacity:.75';
  document.body.appendChild(a); })();
