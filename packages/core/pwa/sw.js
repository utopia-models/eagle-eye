// sw.js: Eagle Eye's service worker (knowledge#14243). Offline shell only: it caches the icons and answers a failed
// page load with a small offline page. It never caches pages, scripts or any /*.json feed (all private, all live).
// It also shows the push alerts the Worker sends (a reply or a booked interview/call) and opens their page on tap.
const V = 'ee-shell-2';   // bumped with the Horus icon so installed apps drop the cached old icons
const OFFLINE = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
  + '<title>Eagle Eye</title><style>html,body{margin:0;height:100%;background:#0a0a09;color:#d9b35b;font:500 13px/1.6 Georgia,serif;'
  + 'letter-spacing:.2em;text-transform:uppercase;display:grid;place-items:center;text-align:center}img{width:96px;opacity:.9}</style></head>'
  + '<body><div><img src="/icons/icon-192.png" alt=""><p>Eagle Eye is offline</p><p style="opacity:.6">It reloads when the phone is back online</p></div>'
  + '<script>addEventListener("online",()=>location.reload())</script></body></html>';
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(V).then(c => c.addAll(['/icons/icon-192.png', '/icons/badge-96.png'])));
});
self.addEventListener('activate', e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== V) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  if (r.mode === 'navigate') {
    e.respondWith(fetch(r).catch(() => new Response(OFFLINE, {headers: {'content-type': 'text/html; charset=utf-8'}})));
  } else if (u.pathname.startsWith('/icons/')) {
    e.respondWith(caches.match(r).then(m => m || fetch(r)));
  }
});
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = {body: e.data ? e.data.text() : ''}; }
  e.waitUntil(self.registration.showNotification(d.title || 'Eagle Eye', {
    body: d.body || '', tag: d.tag, renotify: !!d.tag, icon: '/icons/icon-192.png', badge: '/icons/badge-96.png',
    data: {url: d.url || '/'},
  }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', location.origin).href;
  e.waitUntil((async () => {
    for (const c of await self.clients.matchAll({type: 'window', includeUncontrolled: true})) {
      if ('navigate' in c) { await c.focus(); return c.navigate(url); }
    }
    return self.clients.openWindow(url);
  })());
});
