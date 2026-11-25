// Eagle Eye startup intro + the always-on top-bar dust eye. ONE mark everywhere: the gold-dust eye (akhet grains).
// The startup intro assembles THAT eye from its own grains at screen centre, then flies the same grains into the top-bar
// slot, where the top-bar canvas takes over on the same frame with the same grains and the same clock (seamless hand-off).
// It is a copy of the iPhone Face ID scan: a spinning ring of dashes that resolves into the shape.
// Startup = first load in a tab (sessionStorage) or ?intro (forces a replay); a reload in the same tab = the mark's refresh (a blink).
// Grain model copied from docs.utopiamodels.ai AkhetLive (_next/static/chunks/1aicfvx1-zuuv.js): mark drawn in white
// offscreen, alpha rejection-sampled into 1500 jittered grains, iris grains orbit (0.18 + 0.5(1 - r/R)) * 2 rad/s, the rest
// twinkle on a left-to-right wave 0.6 + 0.3 sin(1.3t + 2pi seed + 0.08x), square grains 0.7-1.8 x 0.55 px, additive,
// backing 2 x min(dpr, 2). That page has NO assembly motion: its still SVG paints first and the canvas grains appear in
// place on the first frame while the still fades out over 500 ms. Our still (eye.png) is the old ringed mark, so it never shows.
const TAU = Math.PI * 2;
const rnd = (a, b) => a + Math.random() * (b - a);
const clamp = u => Math.max(0, Math.min(1, u));
const sm = u => { u = clamp(u); return u * u * (3 - 2 * u); };
const inOutCubic = u => { u = clamp(u); return u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
const hex3 = h => { h = (h || "#000").replace("#", ""); if (h.length === 3) h = h.split("").map(c => c + c).join(""); const n = parseInt(h.slice(0, 6), 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; };
const rgb = hx => hex3(hx).map(v => Math.round(v * 255)).join(",");
// colours from the one palette (public/opt/tokens.css). Tyler: lighter golds read yellow -> grains are gold-8/9, gold-12 only as a rare sparkle
function pal() { const cs = getComputedStyle(document.documentElement), v = (k, f) => (cs.getPropertyValue(k) || "").trim() || f;
  return {gold8: v("--gold-8", "#7a6841"), gold9: v("--gold-9", "#9c8452"), gold12: v("--gold-12", "#ddd2bb"), black: v("--ink-1", "#000")}; }

const Q = new URLSearchParams(location.search);
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const SLOW = Math.max(1, +Q.get("eeslow") || 1);          // ?eeslow=N: N x slower, for frame-accurate review strips only
const ss = (k, v) => { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } };
const T0 = performance.now();                              // the one clock the intro and the top-bar eye share
const clockAt = now => (now - T0) / 1000 / SLOW;
const INTRO = {active: false, handoff: false};

// ---------- the dust eye: geometry (the original Eagle Eye eye) and its grains --------------------------------------
const BW = 400, BH = 300, CX = 200, CY = 163, R = 106, LW = 1.75 * R, LH = 1.16 * R, PUP = .26 * R;
const lidY = (x, up, op = 1) => (up ? -1 : 1) * LH * op * Math.pow(Math.max(0, 1 - x * x), .9);
let EYE = null;
function eyeModel() {
  if (EYE) return EYE;
  const u = document.createElement("canvas"); u.width = BW; u.height = BH;
  const c = u.getContext("2d", {willReadFrequently: true});
  const almond = () => { c.beginPath(); for (let i = 0; i <= 64; i++) { const x = -1 + 2 * i / 64; c.lineTo(CX + x * LW, CY + lidY(x, true)); }
    for (let i = 64; i >= 0; i--) { const x = -1 + 2 * i / 64; c.lineTo(CX + x * LW, CY + lidY(x, false)); } c.closePath(); };
  const circ = r => { c.beginPath(); c.arc(CX, CY, r, 0, TAU); };
  c.fillStyle = "#fff"; c.strokeStyle = "#fff"; c.lineJoin = "round"; c.lineCap = "round";
  c.globalAlpha = .07; almond(); c.fill();                                      // faint white of the eye
  c.globalAlpha = .16; circ(R); c.fill();                                       // iris disc
  c.globalAlpha = 1; c.lineWidth = 6; circ(R); c.stroke();                      // limbal rim (Akhet: sun stroke 6)
  c.globalAlpha = .5; circ(.5 * R); c.fill(); c.globalAlpha = 1;                // dense inner iris = Akhet's sun
  c.lineWidth = 4; circ(.61 * R); c.stroke(); c.lineWidth = 3; circ(.34 * R); c.stroke();
  c.globalCompositeOperation = "destination-out"; circ(PUP); c.fill(); c.globalCompositeOperation = "source-over";   // pupil
  c.save(); almond(); c.globalCompositeOperation = "destination-in"; c.fill(); c.restore();                           // iris inside the lids
  c.globalAlpha = 1; c.lineWidth = 7; almond(); c.stroke();                     // lids (Akhet: outline 7)
  c.lineWidth = 5; c.globalAlpha = .9; c.beginPath();                           // brow dust
  for (let i = 0; i <= 64; i++) { const x = -1 + 2 * i / 64; c.lineTo(CX + x * LW * .98, CY + lidY(x, true) - .17 * R - Math.sin((i / 64) * Math.PI) * .05 * R); }
  c.stroke();
  const f = c.getImageData(0, 0, BW, BH).data, m = [];
  for (let y = 0; y < BH; y++) for (let x = 0; x < BW; x++) { const al = f[(BW * y + x) * 4 + 3]; al > 12 && m.push(x, y, al / 255); }
  const sample = (n, extra) => { const g = [];
    for (let k = 0; g.length < n && k < 3e5; k++) {
      const e = (Math.random() * m.length / 3) | 0; if (Math.random() > m[3 * e + 2]) continue;
      const x = m[3 * e] + Math.random() - .5, y = m[3 * e + 1] + Math.random() - .5, dx = x - CX, dy = y - CY, r = Math.hypot(dx, dy), sd = Math.random();
      const xn = Math.max(-1, Math.min(1, dx / LW));
      g.push({x, y, r, a: Math.atan2(dy, dx), s: .7 + 1.1 * Math.random(), sun: r < R * .98, seed: sd, extra,
        c: sd < .6 ? 0 : sd < .94 ? 1 : 2,                                       // 60% gold-9 · 34% gold-8 · 6% gold-12 sparkle
        q1: Math.random(), q2: Math.random(), q3: Math.random(),
        u: dy < 0 ? (xn + 1) / 4 : .5 + (1 - xn) / 4});                          // where the outline passes it: left corner, upper lid, right corner, lower lid
    }
    return g; };
  const grains = sample(1500, false), extra = sample(2600, true);               // the top bar's 1500 + 2600 that only live at intro scale
  const byColour = (a, b) => a.c - b.c;
  EYE = {grains: grains.slice().sort(byColour), all: grains.concat(extra).sort(byColour)};
  return EYE;
}

// one grain's position (eye box coords) and brightness at clock t. o: {op (lid opening 0..1), flare, spin, q, box(e,x,y)->[x,y,a]|null}
function grainAt(e, t, o) {
  let x = e.x, y = e.y, s, a = 1;
  if (e.sun) {
    const an = e.a + t * (.18 + .5 * (1 - e.r / R)) * 2 + (o.spin || 0) * (1.2 - e.r / R) * (o.q || 0), rr = e.r * (1 + .35 * (o.flare || 0) * (1 - e.r / R));
    x = CX + rr * Math.cos(an); y = CY + rr * Math.sin(an);
    s = .85 + .45 * Math.max(0, (e.r / R - .6) / .4) + .2 * Math.sin(2.2 * t + 6.28 * e.seed);
  } else s = .6 + .3 * Math.sin(1.3 * t + 6.28 * e.seed + .08 * x);
  if (o.box) { const b = o.box(e, x, y); if (!b) return null; x = b[0]; y = b[1]; a = b[2]; }
  const op = o.op ?? 1;
  if (op < 1) { const lim = Math.abs(lidY((x - CX) / LW, true, op)) + .5; y = CY + Math.max(-lim, Math.min(lim, (y - CY) * (e.sun ? 1 : op))); }
  return [x, y, s * (1 + 1.4 * (o.flare || 0)) * a];
}
const COLOURS = () => { const C = pal(); return [rgb(C.gold9), rgb(C.gold8), rgb(C.gold12)]; };
const ALPHA = [.8, .8, .4];

// ---------- top-bar mark: the dust eye, live (orbit, twinkle, blink on refresh) --------------------------------------
function akhetEye(wrap, img) {
  const cv = document.createElement("canvas"); cv.setAttribute("aria-hidden", "true"); cv.className = "ee-akhet"; wrap.appendChild(cv);
  const a = cv.getContext("2d"); if (!a) return {refresh() {}, paint() {}};
  const l = 2 * Math.min(devicePixelRatio || 1, 2), n = img.getBoundingClientRect(), o = n.width || 53, h = n.height || 40;
  cv.width = Math.round(o * l); cv.height = Math.round(h * l);
  const d = o / BW, M = eyeModel(), COL = COLOURS();
  let raf = 0, refreshAt = -1, on = false;
  const paint = now => {
    a.setTransform(1, 0, 0, 1, 0, 0); a.clearRect(0, 0, cv.width, cv.height);
    if (INTRO.active && !INTRO.handoff) return;                                // the intro overlay is drawing these grains
    if (!on) { on = true; cv.dataset.on = "1"; wrap.classList.add("ee-akhet-on"); }
    const t = clockAt(now), q = refreshAt < 0 ? 9 : (now - refreshAt) / 1000;
    const op = q < .32 ? Math.abs(Math.cos(Math.PI * q / .32)) : 1;             // blink: the lid curve closes and reopens
    const spin = q < 1.1 ? 5 * Math.pow(1 - q / 1.1, 3) : 0;
    const flare = q < .9 ? Math.sin(Math.PI * clamp(q / .9)) * (1 - clamp(q / .9)) : 0;
    a.globalCompositeOperation = "lighter"; let cur = -1;
    for (const e of M.grains) {
      const p = grainAt(e, t, {op, spin, flare, q}); if (!p) continue;
      if (e.c !== cur) { cur = e.c; a.fillStyle = `rgb(${COL[cur]})`; }
      a.globalAlpha = Math.min(1, ALPHA[e.c] * p[2]);
      const z = Math.max(1, Math.round(e.s * l * .55));                         // whole backing pixels: no half-pixel smear
      a.fillRect(Math.round(p[0] * d * l - z / 2), Math.round(p[1] * d * l - z / 2), z, z);
    }
    a.globalAlpha = 1;
  };
  const loop = now => { paint(now); if (!reduce) raf = requestAnimationFrame(loop); };
  raf = requestAnimationFrame(loop);
  return {paint, refresh() { refreshAt = performance.now(); if (reduce) requestAnimationFrame(loop); }};
}

// ---------- the page under the overlay settles in as the eye leaves (header stays put: it holds the eye's slot) ------
function dashIn(delay, dur, from = 1.04) {
  const W = innerWidth, H = innerHeight;
  [...document.body.children].filter(e => !/^ee-/.test(e.id) && !e.matches("script,style,#intro,header,.top") && !e.hidden).forEach(e => {
    const r = e.getBoundingClientRect(), o = `${W / 2 - r.left}px ${H / 2 - r.top}px`;
    e.animate([{transform: `scale(${from})`, opacity: 0}, {transform: "none", opacity: 1}],
      {duration: dur * SLOW, delay: delay * SLOW, easing: "cubic-bezier(.16,1,.3,1)", fill: "backwards"}); });
}

// ---------- intro runner: assemble at centre, fly into the slot, hand off -------------------------------------------
// style: {fly0: s, box(e, t, x, y) -> [x, y, a] | null, op(t), flare(t), under(ctx, t, map), over(ctx, t, map)}
const FLY_DUR = .5;
function dustIntro(style) {
  const W = innerWidth, H = innerHeight, DPR = Math.min(devicePixelRatio || 1, 2), M = eyeModel(), COL = COLOURS(), C = pal();
  const cv = document.createElement("canvas"); cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  const ctx = cv.getContext("2d"); if (!ctx) { document.documentElement.classList.add("ee-ready"); return; }
  const kBig = Math.min(W * .42, H * .62 * BW / BH, 620) / BW;
  const slot = () => { const im = document.querySelector("#mark"), r = im && im.getBoundingClientRect();
    const w = r && r.width ? r.width : (r && r.height || 40) * BW / BH, k = w / BW;
    return {k, cx: (r ? r.left : 24) + CX * k, cy: (r ? r.top : 12) + CY * k}; };
  const FLY0 = style.fly0, FLY1 = FLY0 + FLY_DUR, END = FLY1 + .04;
  INTRO.active = true;
  dashIn(FLY0 * 1000, 560);
  runOverlay(cv, END, FLY0, (t, now) => {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1; ctx.clearRect(0, 0, W, H);
    const bg = 1 - sm((t - FLY0) / (FLY_DUR * .85));
    if (bg > 0) { ctx.globalAlpha = bg; ctx.fillStyle = C.black; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1; }
    if (t >= FLY1) { if (!INTRO.handoff) { INTRO.handoff = true; if (markApi && markApi.paint) markApi.paint(now); } return; }
    const s = slot(), u = inOutCubic((t - FLY0) / FLY_DUR);
    const k = kBig * Math.exp(Math.log(s.k / kBig) * u), cx = W / 2 + (s.cx - W / 2) * u, cy = H / 2 + (s.cy - H / 2) * u;
    const map = (x, y) => [cx + (x - CX) * k, cy + (y - CY) * k];
    const mul = Math.max(1, Math.min(3, .85 * Math.sqrt(k / s.k)));
    const tc = clockAt(now), xf = 1 - sm((t - FLY0) / (FLY_DUR * .6));
    const o = {op: style.op ? style.op(t) : 1, flare: style.flare ? style.flare(t) : 0, box: style.box ? (e, x, y) => style.box(e, t, x, y) : null};
    if (style.under) style.under(ctx, t, map, k);
    drawDust(ctx, M.all, COL, tc, o, map, mul, xf, 1);
    if (style.over) style.over(ctx, t, map, k);
  });
}

// draw the eye's grains through map (box -> screen px); mul > 1 = intro scale; xf = alpha of the intro-only grains
function drawDust(ctx, list, COL, tc, o, map, mul, xf, aMul) {
  const lBar = 2 * Math.min(devicePixelRatio || 1, 2);
  ctx.globalCompositeOperation = "lighter"; let cur = -1;
  for (const e of list) {
    if (e.extra && xf <= 0) continue;
    const p = grainAt(e, tc, o); if (!p) continue;
    const al = Math.min(1, ALPHA[e.c] * p[2]) * (e.extra ? xf : 1) * aMul; if (al <= .003) continue;
    if (e.c !== cur) { cur = e.c; ctx.fillStyle = `rgb(${COL[cur]})`; }
    const [x, y] = map(p[0], p[1]), z = mul > 1.001 ? e.s * .55 * mul : Math.max(1, Math.round(e.s * lBar * .55)) / lBar;
    ctx.globalAlpha = al; ctx.fillRect(x - z / 2, y - z / 2, z, z);
  }
  ctx.globalAlpha = 1;
}

function runOverlay(node, end, pass, draw) {
  node.id = "ee-intro"; node.setAttribute("aria-hidden", "true"); document.body.appendChild(node);
  const t0 = performance.now(), stat = window.__eeIntro = {style: STYLE, t0, frames: 0, gaps: []}; let last = t0;
  draw(0, t0); document.documentElement.classList.add("ee-ready");
  const frame = now => { const t = (now - t0) / 1000 / SLOW; stat.frames++; stat.gaps.push(Math.round(now - last)); last = now;
    if (t >= pass) node.classList.add("ee-pass");
    if (t >= end) { draw(t, now); node.remove(); INTRO.active = false; stat.done = Math.round(now - t0); document.dispatchEvent(new Event("ee-intro-done")); return; }
    const c0 = performance.now(); draw(t, now); (stat.cost || (stat.cost = [])).push(Math.round((performance.now() - c0) * 10) / 10); requestAnimationFrame(frame); };
  requestAnimationFrame(frame);
}

// =============================== i · FACE ID: the scan ring resolves into the eye ===================================
// Copied: iPhone Face ID unlock: a ring of short dashes spins around the face while it scans, then the ring collapses
// and re-forms as the success glyph with a spring. Ours: every grain starts on a spinning dashed ring (60 dashes,
// 0-0.42 s, spinning down), then flows to its place in the eye (0.38-0.85 s, staggered by angle), a glint on arrival.
const RING = 1.42 * R, DASHES = 60;
const I = {
  fly0: .95,
  flare: t => { const u = clamp((t - .74) / .32); return 1.0 * Math.sin(Math.PI * u) * (1 - u); },
  box(e, t, x, y) {
    const appear = sm(t / .16), spin = 5.5 * (t - .35 * t * t);
    const dash = Math.floor(e.seed * DASHES), th = (dash + .55 * e.q2) / DASHES * TAU - Math.PI / 2 + spin;   // grains bunch into dashes
    const rr = RING * (.9 + .1 * appear) + (e.q3 - .5) * 5;
    const rx = CX + rr * Math.cos(th), ry = CY + rr * Math.sin(th);
    const p = inOutCubic((t - .38 - .14 * ((th / TAU % 1 + 1) % 1)) / .4);
    return [rx + (x - rx) * p, ry + (y - ry) * p, appear * (1 + .6 * Math.sin(Math.PI * p))];
  },
};

const STYLE = "i";                                           // the one startup intro (Tyler 11-21: "Yeah ship I")
const startup = !reduce && !Q.has("nointro") && (Q.has("intro") || !ss("ee-intro-seen"));
ss("ee-intro-seen", "1");

// ---------- top-bar mark: wrap #mark, mount the dust eye; refresh on in-session reload and on new live rows ----------
let markApi = null;
function mountMark() {
  const img = document.querySelector("#mark");
  if (!img || img.closest(".ee-mark")) return img && img.closest(".ee-mark");
  const wrap = document.createElement("span"); wrap.className = "ee-mark";
  img.replaceWith(wrap); wrap.appendChild(img);
  const go = () => { markApi = window.__eeMark = akhetEye(wrap, img); };
  if (img.complete && img.getBoundingClientRect().width) go(); else img.addEventListener("load", go, {once: true});
  const seen = new Set(); let armed = false;
  const scan = () => { let fresh = false; document.querySelectorAll("[data-row]").forEach(r => { if (!seen.has(r.dataset.row)) { seen.add(r.dataset.row); fresh = true; } }); return fresh; };
  setTimeout(() => { scan(); armed = true; }, 1500);
  new MutationObserver(() => { if (armed && scan() && markApi) markApi.refresh(); }).observe(document.body, {childList: true, subtree: true});
  return wrap;
}
function whenMark(cb) { if (mountMark()) return cb();
  const mo = new MutationObserver(() => { if (mountMark()) { mo.disconnect(); cb(); } });
  mo.observe(document.documentElement, {childList: true, subtree: true}); setTimeout(() => mo.disconnect(), 5000); }

// ---------- living background behind the dashboard: drifting gold dust, three depth layers, scroll/pointer parallax --
function sprite(core, rgbs, size) { const c = document.createElement("canvas"); c.width = c.height = size; const g = c.getContext("2d"), h = size / 2;
  const gr = g.createRadialGradient(h, h, 0, h, h, h); gr.addColorStop(0, `rgba(${core},1)`); gr.addColorStop(.12, `rgba(${rgbs},1)`); gr.addColorStop(.3, `rgba(${rgbs},.42)`); gr.addColorStop(.6, `rgba(${rgbs},.07)`); gr.addColorStop(1, `rgba(${rgbs},0)`);
  g.fillStyle = gr; g.fillRect(0, 0, size, size); return c; }
function mountBackground() {
  if (document.getElementById("ee-bg")) return;
  const C = pal(), spGold = sprite(rgb(C.gold9), rgb(C.gold9), 32), spPale = sprite(rgb(C.gold9), rgb(C.gold8), 32);
  const cv = document.createElement("canvas"); cv.id = "ee-bg"; cv.setAttribute("aria-hidden", "true");
  document.body.prepend(cv); document.documentElement.classList.add("ee-has-bg");
  const ctx = cv.getContext("2d"); let W, H, D;
  const fit = () => { D = Math.min(devicePixelRatio || 1, 1.5); W = innerWidth; H = innerHeight; cv.width = Math.round(W * D); cv.height = Math.round(H * D); };
  fit(); addEventListener("resize", fit);
  const P = []; for (let i = 0; i < 90; i++) { const z = i < 50 ? rnd(.25, .5) : i < 78 ? rnd(.5, .8) : rnd(.8, 1);
    P.push({x: Math.random(), y: Math.random(), z, tw: rnd(0, TAU), ts: rnd(.5, 1.4), vx: rnd(-4, 4), vy: -rnd(5, 12), pale: Math.random() < .3}); }
  let mx = 0, my = 0, px = 0, py = 0;
  addEventListener("pointermove", e => { mx = e.clientX / W - .5; my = e.clientY / H - .5; }, {passive: true});
  const paint = (t, dt) => {
    px += (mx - px) * Math.min(1, dt * 3); py += (my - py) * Math.min(1, dt * 3);
    const sc = scrollY || 0, fadeIn = sm(t / .8);
    ctx.setTransform(D, 0, 0, D, 0, 0); ctx.clearRect(0, 0, W, H); ctx.globalCompositeOperation = "lighter";
    for (const q of P) {
      q.x += q.vx * q.z * dt / W; q.y += q.vy * q.z * dt / H;
      let x = q.x * W + Math.sin(t * .3 * q.ts + q.tw) * 10 * q.z - px * 40 * q.z, y = q.y * H - sc * .12 * q.z - py * 30 * q.z;
      x = ((x % W) + W) % W; y = ((y % H) + H) % H;
      const a = (.08 + .2 * (.5 + .5 * Math.sin(t * q.ts * 1.6 + q.tw))) * (.35 + .65 * q.z) * fadeIn;
      ctx.globalAlpha = a; const z = (2.5 + 7 * q.z * q.z); ctx.drawImage(q.pale ? spPale : spGold, x - z / 2, y - z / 2, z, z);
    }
    ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  };
  if (reduce) { paint(1, 0); return; }
  const t0 = performance.now(); let last = t0, raf = 0;
  const loop = now => { raf = requestAnimationFrame(loop); if (document.getElementById("ee-intro")) { last = now; return; } const dt = Math.min(.05, (now - last) / 1000); last = now; paint((now - t0) / 1000, dt); };
  const go = () => { cancelAnimationFrame(raf); if (!document.hidden) { last = performance.now(); raf = requestAnimationFrame(loop); } };
  document.addEventListener("visibilitychange", go); go();
}

if (document.body) mountBackground();
if (startup && document.body) dustIntro(I); else document.documentElement.classList.add("ee-ready");
whenMark(() => { if (!startup) { const fire = () => markApi ? markApi.refresh() : setTimeout(fire, 50); fire(); } });
