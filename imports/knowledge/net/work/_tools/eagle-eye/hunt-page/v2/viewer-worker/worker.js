// utopiamodels.ai/v/<slug>/... : serve the one-shot viewer from R2 (key v/<slug>/<file>), forward the watch beacon to Eagle
// Eye. The page, video, poster and GIF are the exact files the sender renders on Ra (send/hunt_send.py publish), so the
// tailnet copy (eagle-server /v/*) and the public copy are byte-identical. If the beacon forward fails, it is kept in
// R2 under beacons/ and the sender's drain replays it (send/hunt_send.py drain), so a watch is never lost.
const SLUG = /^[a-z0-9][a-z0-9-]{3,80}$/, FILE = /^[a-z0-9][a-z0-9._-]{0,60}$/;
const TYPES = { html: "text/html; charset=utf-8", mp4: "video/mp4", jpg: "image/jpeg", gif: "image/gif", png: "image/png", vtt: "text/vtt" };

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const m = url.pathname.match(/^\/v\/([^/]+)(?:\/([^/]*))?$/);
    if (!m || !SLUG.test(m[1])) return new Response("Not found", { status: 404 });
    const slug = m[1], file = m[2];
    if (file === undefined) return Response.redirect(`${url.origin}/v/${slug}/${url.search}`, 301);

    if (file === "e" && req.method === "POST") {
      const body = (await req.text()).slice(0, 2000);
      ctx.waitUntil(forward(env, slug, body));
      return new Response(null, { status: 202 });
    }
    if (req.method !== "GET" && req.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
    const name = file === "" ? "index.html" : file;
    if (!FILE.test(name)) return new Response("Not found", { status: 404 });

    const key = `v/${slug}/${name}`;
    const range = req.headers.get("range");
    const obj = await env.V.get(key, range ? { range: req.headers } : {});
    if (!obj) return new Response("Not found", { status: 404 });
    const h = new Headers();
    obj.writeHttpMetadata(h);
    h.set("etag", obj.httpEtag);
    h.set("accept-ranges", "bytes");
    h.set("x-robots-tag", "noindex");
    h.set("content-type", TYPES[name.split(".").pop()] || "application/octet-stream");
    h.set("cache-control", name.endsWith(".html") ? "no-cache" : "public, max-age=86400");
    if (range && obj.range) {
      const off = obj.range.offset ?? 0, len = obj.range.length ?? (obj.size - off);
      h.set("content-range", `bytes ${off}-${off + len - 1}/${obj.size}`);
      h.set("content-length", String(len));
      return new Response(req.method === "HEAD" ? null : obj.body, { status: 206, headers: h });
    }
    h.set("content-length", String(obj.size));
    return new Response(req.method === "HEAD" ? null : obj.body, { status: 200, headers: h });
  },
};

async function forward(env, slug, body) {
  try {
    // redirect "manual": an Access login 302 (no/invalid service token) followed to the login page answers 200 and would
    // drop the beacon; only a 2xx from the Eagle Eye API itself counts as delivered, everything else is parked in R2.
    const r = await fetch(`${env.EAGLE_BEACON_ORIGIN}/v/${slug}/e`, {
      method: "POST", body, redirect: "manual", headers: { "content-type": "text/plain",
        "CF-Access-Client-Id": env.EAGLE_ACCESS_CLIENT_ID || "", "CF-Access-Client-Secret": env.EAGLE_ACCESS_CLIENT_SECRET || "" } });
    if (r.status >= 200 && r.status < 300) return;
  } catch (e) {}
  await env.V.put(`beacons/${slug}/${Date.now()}-${crypto.randomUUID()}.json`, body, { httpMetadata: { contentType: "application/json" } });
}
