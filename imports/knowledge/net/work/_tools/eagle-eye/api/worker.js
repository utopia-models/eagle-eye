// eagle-eye-api: the Eagle Eye mobile app's JSON API (knowledge#14249), served at https://eagle-api.utopiamodels.ai.
//
// The phone app never holds a Cloudflare Access cookie. It signs in with Google natively, posts the Google ID token
// here, and gets an Eagle Eye token (HS256, 30 days). Every other call carries that token as a Bearer.
//
// No data is computed here. Each read is fetched from the eagle-eye Worker (eagle.utopiamodels.ai) with the Access
// service token and `?as=<person>`, so the hunts, roosts and lanes stay assembled in exactly one place (handler-dev.js)
// and the app shows the same numbers the web does. This Worker only decides WHO is asking and WHAT they may see.
//
// Who is who: KV `people` in eagle-eye-data, {"emails": {"<google email>": "<person>"}, "admins": ["tyler"]}.
//
// Routes (all JSON):
//   POST /v1/auth/google   {idToken}                 -> {token, person, expires}
//   GET  /v1/me                                      -> {me, people, names, admin}
//   GET  /v1/eye?p=<person>                          -> the eye: hunts + roosts, the person's page
//   GET  /v1/lane/<key>?p=<person>                   -> one lane: its companies and their latest events
//   GET  /v1/company/<lane>/<company>?p=<person>     -> one company in a lane: every event, its campaign, your network there
//   POST /v1/push/register {token, platform, kind}   -> stores this device's push token for the signed-in person
//   POST /v1/push/unregister {token}
//   GET  /health                                     -> {ok}

const UP = "https://eagle.utopiamodels.ai";
// The app's lanes, in screen order (Tyler, 2026-11-16): LinkedIn and cold email are not lanes; they are each Cold App's
// campaign. Social is not shown. Hunts carry no number for now; Clients carries its client count.
const HUNTS = [["upwork", "Upwork"], ["cold_apps", "Cold Apps"], ["in_person", "In Person"]];
const ROOSTS = [["clients", "Clients"], ["network", "Network"]];
const CAMPAIGN = ["linkedin", "cold_email"]; // folded into a Cold App's detail
const LANES = new Set([...HUNTS, ...ROOSTS].map((x) => x[0]));
const TOKEN_DAYS = 30;

const J = (b, s = 200) => new Response(JSON.stringify(b), {
  status: s, headers: { "content-type": "application/json", "cache-control": "no-store", "access-control-allow-origin": "*" },
});
const te = new TextEncoder();
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const jdec = (s) => JSON.parse(new TextDecoder().decode(unb64u(s)));

// ---- Google ID token -------------------------------------------------------------------------------------------
let certs = null, certsAt = 0;
async function googleKeys() {
  if (certs && Date.now() - certsAt < 3600e3) return certs;
  certs = (await (await fetch("https://www.googleapis.com/oauth2/v3/certs")).json()).keys;
  certsAt = Date.now();
  return certs;
}
async function verifyGoogle(idToken, env) {
  const [h, p, s] = String(idToken || "").split(".");
  if (!s) throw new Error("not a JWT");
  const head = jdec(h), body = jdec(p);
  const jwk = (await googleKeys()).find((k) => k.kid === head.kid);
  if (!jwk) throw new Error("unknown signing key");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  if (!(await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, unb64u(s), te.encode(h + "." + p)))) throw new Error("bad signature");
  const auds = String(env.GOOGLE_AUDIENCES || "").split(",").map((x) => x.trim()).filter(Boolean);
  if (!auds.includes(body.aud)) throw new Error("wrong audience");
  if (!["accounts.google.com", "https://accounts.google.com"].includes(body.iss)) throw new Error("wrong issuer");
  if (body.exp * 1000 < Date.now()) throw new Error("expired");
  if (!body.email || body.email_verified === false) throw new Error("no verified email");
  return body.email.toLowerCase();
}

// ---- Eagle Eye token (HS256) -----------------------------------------------------------------------------------
async function hmac(env) {
  return crypto.subtle.importKey("raw", te.encode(env.SIGNING_KEY), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
async function mint(env, person, email) {
  const h = b64u(te.encode(JSON.stringify({ alg: "HS256", typ: "JWT" })));
  const exp = Math.floor(Date.now() / 1000) + TOKEN_DAYS * 86400;
  const p = b64u(te.encode(JSON.stringify({ sub: person, email, exp, iss: "eagle-api" })));
  const sig = b64u(await crypto.subtle.sign("HMAC", await hmac(env), te.encode(h + "." + p)));
  return { token: `${h}.${p}.${sig}`, expires: new Date(exp * 1000).toISOString() };
}
async function bearer(r, env) {
  const t = (r.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  const [h, p, s] = t.split(".");
  if (!s) return null;
  if (!(await crypto.subtle.verify("HMAC", await hmac(env), unb64u(s), te.encode(h + "." + p)))) return null;
  const b = jdec(p);
  return b.exp * 1000 > Date.now() && b.iss === "eagle-api" ? b : null;
}

// ---- who may see what ------------------------------------------------------------------------------------------
async function people(env) {
  try { return JSON.parse((await env.DATA.get("people")) || "{}"); } catch (e) { return {}; }
}
async function scope(env, me) {
  const pp = await people(env), admins = pp.admins || ["tyler"];
  const all = [...new Set(Object.values(pp.emails || {}))];
  return { admin: admins.includes(me), may: admins.includes(me) ? all : [me] };
}

// ---- upstream (the eagle-eye Worker, through Access with the service token) ------------------------------------
async function up(env, path, who) {
  const u = new URL(UP + path);
  u.searchParams.set("as", who);
  const res = await fetch(u, { headers: { "CF-Access-Client-Id": env.UP_ID, "CF-Access-Client-Secret": env.UP_SECRET } });
  if (!res.ok) throw new Error(`upstream ${path} ${res.status}`);
  return res.json();
}

const pick = (o, ks) => Object.fromEntries(ks.filter((k) => o && o[k] !== undefined).map((k) => [k, o[k]]));
const latestOf = (x) => (x && x.latest ? pick(x.latest, ["ts", "co", "kind", "what"]) : null);

async function eye(env, who, names) {
  const d = await up(env, "/data.json", who);
  const hunts = HUNTS.map(([key, name]) => {
    const h = (d.hunts || {})[key] || {};
    return { key, name, status: h.status || "empty", reason: h.reason || null, latest: latestOf(h) };
  });
  const roosts = ROOSTS.map(([key, name]) => {
    const r = (d.roosts || {})[key] || {};
    const out = { key, name, status: r.status || "empty", reason: r.reason || null, latest: latestOf(r) };
    if (key === "clients") {
      const rows = r.rows || [];
      out.count = rows.length;
      out.rows = rows.map((x) => pick(x, ["name", "stage", "what", "contracts"]));
    }
    return out;
  });
  return { person: who, name: (names || {})[who] || who, updated: d.updated || null, hunts, roosts };
}

async function lanesOf(env, who) { return (await up(env, "/lanes.json", who)).lanes || {}; }

function companies(events) {
  const by = new Map();
  for (const e of events) {
    if (!e.co) continue;
    const c = by.get(e.co) || { co: e.co, events: 0, latest: null };
    c.events += 1;
    if (!c.latest || e.ts > c.latest.ts) c.latest = pick(e, ["ts", "kind", "what"]);
    by.set(e.co, c);
  }
  return [...by.values()].sort((a, b) => (a.latest.ts < b.latest.ts ? 1 : -1));
}

async function route(r, env, u) {
  const p = u.pathname;
  if (p === "/health") return J({ ok: true });
  if (p === "/v1/auth/google" && r.method === "POST") {
    let body = {};
    try { body = await r.json(); } catch (e) { /* empty */ }
    let email;
    try { email = await verifyGoogle(body.idToken, env); } catch (e) { return J({ error: "sign-in refused: " + e.message }, 401); }
    const person = ((await people(env)).emails || {})[email];
    if (!person) return J({ error: "This Google account has no Eagle Eye yet.", email }, 403);
    return J({ person, ...(await mint(env, person, email)) });
  }
  const tok = await bearer(r, env);
  if (!tok) return J({ error: "sign in" }, 401);
  const me = tok.sub, { admin, may } = await scope(env, me);
  const who = u.searchParams.get("p") || me;
  if (!may.includes(who)) return J({ error: "not yours" }, 403);

  if (p === "/v1/me") {
    const m = await up(env, "/me.json", me);
    return J({ me, admin, people: may, names: m.names || {}, email: tok.email });
  }
  if (p === "/v1/eye") return J(await eye(env, who, (await up(env, "/me.json", me)).names));
  let m = p.match(/^\/v1\/lane\/([a-z_]+)$/);
  if (m) {
    if (!LANES.has(m[1])) return J({ error: "no such lane" }, 404);
    const L = await lanesOf(env, who), lane = L[m[1]] || {};
    return J({ person: who, lane: m[1], source: lane.source || null, companies: companies(lane.events || []).slice(0, 200) });
  }
  m = p.match(/^\/v1\/company\/([a-z_]+)\/(.+)$/);
  if (m) {
    if (!LANES.has(m[1])) return J({ error: "no such lane" }, 404);
    const co = decodeURIComponent(m[2]), L = await lanesOf(env, who);
    const of = (k) => ((L[k] || {}).events || []).filter((e) => e.co === co).map((e) => pick(e, ["ts", "kind", "what"]));
    const out = { person: who, lane: m[1], co, events: of(m[1]) };
    if (m[1] === "cold_apps") {
      out.campaign = Object.fromEntries(CAMPAIGN.map((k) => [k, of(k)]));
      out.network = of("network");
    }
    return J(out);
  }
  if (p === "/v1/push/register" && r.method === "POST") {
    let b = {};
    try { b = await r.json(); } catch (e) { /* empty */ }
    if (!b.token || !["android", "ios"].includes(b.platform)) return J({ error: "want {token, platform: android|ios}" }, 400);
    const k = "push/app/" + me, cur = JSON.parse((await env.DATA.get(k)) || "[]");
    const next = [{ token: String(b.token).slice(0, 400), platform: b.platform, kind: b.kind || "fcm", at: new Date().toISOString() },
      ...cur.filter((x) => x.token !== b.token)].slice(0, 10);
    await env.DATA.put(k, JSON.stringify(next));
    return J({ ok: true, person: me, devices: next.length });
  }
  if (p === "/v1/push/unregister" && r.method === "POST") {
    let b = {};
    try { b = await r.json(); } catch (e) { /* empty */ }
    const k = "push/app/" + me, cur = JSON.parse((await env.DATA.get(k)) || "[]");
    await env.DATA.put(k, JSON.stringify(cur.filter((x) => x.token !== b.token)));
    return J({ ok: true });
  }
  return J({ error: "not found" }, 404);
}

export default {
  async fetch(r, env) {
    const u = new URL(r.url);
    try { return await route(r, env, u); } catch (e) { return J({ error: String(e.message || e) }, 502); }
  },
};
