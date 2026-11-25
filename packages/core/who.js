// who.js: the person switcher on eagle.utopiamodels.ai (knowledge#14128). The Worker (handler-dev.js) injects it into
// `/` and every /hunt/<key>, /roost/<key> page. It reads /me.json: Tyler (people = tyler, osman, claire) gets a picker;
// a non-admin person (people = just them) get a fixed name tag. Picking a person reloads with ?p=<person>; the Worker
// remembers it in cookie ee_p and answers /data.json, /lanes.json and /apps.json from that person's own stores only.
(() => {
  const css = `#ee-who{position:fixed;top:8px;right:10px;z-index:2147483000;display:flex;align-items:center;gap:.5em;
font:500 11px/1 "Cormorant SC","Cinzel",ui-serif,Georgia,serif;letter-spacing:.24em;text-transform:uppercase;color:#d9b35b;
background:rgba(10,10,9,.82);border:1px solid rgba(217,179,91,.32);padding:5px 4px 5px 9px;border-radius:2px;
-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
#ee-who select{font:inherit;letter-spacing:.18em;text-transform:uppercase;color:#f1e3bd;background:transparent;border:0;
padding:2px 2px;cursor:pointer;outline:none}#ee-who select:focus-visible{outline:1px solid #d9b35b}
#ee-who option{background:#0a0a09;color:#f1e3bd}#ee-who b{font-weight:600;color:#f1e3bd;padding-right:5px}
#ee-who select{-webkit-appearance:none;appearance:none;border-radius:0;padding-right:16px;background:no-repeat right 2px center/8px 5px
url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 5'%3E%3Cpath d='M.5.5 4 4 7.5.5' fill='none' stroke='%23d9b35b'/%3E%3C/svg%3E")}
#ee-who.ph{position:absolute;background:none;border:0;padding:0;min-height:44px;-webkit-backdrop-filter:none;backdrop-filter:none;letter-spacing:.5em}
#ee-who.ph label{display:none}#ee-who.ph select{min-height:44px}#ee-who.ph select,#ee-who.ph b{letter-spacing:.32em;color:#d9b35b;font-size:11px}`;
  fetch('/me.json', {cache: 'no-store'}).then(r => r.ok ? r.json() : null).then(m => {
    if (!m || !m.people || !m.people.length) return;
    const N = m.names || {}, nm = p => N[p] || p;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const el = document.createElement('div'); el.id = 'ee-who';
    if (m.people.length > 1) {
      el.innerHTML = `<label for="ee-who-s">Eagle Eye of</label><select id="ee-who-s" aria-label="Whose Eagle Eye">${
        m.people.map(p => `<option value="${p}"${p === m.view ? ' selected' : ''}>${nm(p)}</option>`).join('')}</select>`;
      el.querySelector('select').addEventListener('change', e => {
        const q = new URLSearchParams(location.search); q.set('p', e.target.value); location.search = q.toString();
      });
    } else {
      el.innerHTML = `<b>${nm(m.view)}'s Eagle Eye</b>`;
    }
    document.body.appendChild(el);
    // a phone (Tyler 2026-11-16, the RAW Pixel: "components are overlapping"): no box; the name has its own line at the
    // top right, aligned to the lanes' right edge, and the page (v2_layout.py) starts HUNTS below it; it scrolls with the page
    // when the page is taller than the screen (round 3: the eye keeps its desktop width, knowledge#14223)
    const seat = () => {
      const phone = !!document.querySelector('#e2.narrow'), h = phone && document.querySelector('#e2 #grp0 h3');
      const was = el.classList.contains('ph');
      el.classList.toggle('ph', phone);
      if (was !== phone) requestAnimationFrame(() => dispatchEvent(new Event('resize')));   // lay out again with the switcher's new height
      if (!h) { el.style.top = el.style.right = ''; return; }
      el.style.top = '6px';
      el.style.right = Math.round(innerWidth - h.getBoundingClientRect().right) + 'px';
    };
    seat(); dispatchEvent(new Event('resize'));   // the page lays out again, now with room for it
    addEventListener('resize', () => requestAnimationFrame(seat));
    addEventListener('ee-layout', seat);   // the page (v2_layout.py) announces each layout: it may boot after this script
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(seat);
  }).catch(() => {});
})();
