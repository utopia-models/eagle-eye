// pwa.js: makes Eagle Eye an installable app (knowledge#14243; a stopgap until the store app, knowledge#14249). The
// Worker adds it to every page's <head> with the manifest link. It registers /sw.js and, inside the installed app,
// asks once for notification permission on the first tap: no button or alerts control on the page (Tyler: preferences
// never sit on the main view; Android's own app-notification settings turn them off). Alerts are only a company or
// client reply and a booked interview or call, and each person gets only their own.
// Stays current (Tyler 2026-11-17, "is this Eagle Eye not updated? how long does it stay open?"): the numbers refresh
// every few seconds, but the page's own code only changed on a reload, so a tab left open for hours kept an old
// version. Every two minutes this fingerprints the page and its scripts; when a deploy changed them, it reloads once
// the person has been idle for 20 s (at once if the tab is in the background). A failed fetch never reloads.
(() => {
  const EVERY = window.EE_CHECK_MS || 120000, IDLE = window.EE_IDLE_MS === undefined ? 20000 : window.EE_IDLE_MS;
  let base = null, touched = Date.now();
  for (const ev of ['pointerdown', 'keydown', 'touchstart', 'wheel']) addEventListener(ev, () => { touched = Date.now(); }, {passive: true, capture: true});
  const urls = () => [location.pathname + location.search, ...[...document.scripts].map(x => x.src).filter(u => u && new URL(u).origin === location.origin)];
  async function fingerprint() {
    const parts = await Promise.all(urls().map(u => fetch(u, {cache: 'no-store'}).then(r => r.ok ? r.text() : null).catch(() => null)));
    if (parts.some(x => x === null)) return null;
    let h = 0; for (const c of parts.join('\u0000')) h = (h * 31 + c.charCodeAt(0)) | 0;
    return h + ':' + parts.reduce((n, x) => n + x.length, 0);
  }
  async function check() {
    const f = await fingerprint();
    if (f === null) return;
    if (base === null) { base = f; return; }
    if (f === base) return;
    if (document.hidden || Date.now() - touched >= IDLE) location.reload();
  }
  setTimeout(check, 3000);
  setInterval(check, EVERY);
})();

(() => {
  if (!('serviceWorker' in navigator)) return;
  const u8 = s => { s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; return Uint8Array.from(atob(s), c => c.charCodeAt(0)); };
  const save = sub => fetch('/push/subscribe', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(sub)});
  async function subscribe(reg) {
    const key = (await (await fetch('/push/key', {cache: 'no-store'})).text()).trim();
    if (!key) return;
    await save(await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: u8(key)}));
  }
  navigator.serviceWorker.register('/sw.js', {scope: '/'}).then(async reg => {
    if (!('PushManager' in window) || !('Notification' in window)) return;
    if (Notification.permission === 'granted') {
      const sub = await reg.pushManager.getSubscription();
      return sub ? save(sub) : subscribe(reg);   // keep the Worker's copy current
    }
    let asked = false; try { asked = localStorage.getItem('ee-alerts-asked') === '1'; } catch (_) {}
    const app = matchMedia('(display-mode: standalone)').matches;
    if (Notification.permission !== 'default' || !app || asked) return;
    addEventListener('pointerup', async () => {
      try { localStorage.setItem('ee-alerts-asked', '1'); } catch (_) {}
      try { if (await Notification.requestPermission() === 'granted') await subscribe(reg); } catch (_) {}
    }, {once: true, capture: true});
  }).catch(() => {});
})();
