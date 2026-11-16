// The real Eagle Eye, ported from the eagle.utopiamodels.ai renderer (home-v2.js, knowledge net/work/_tools/eagle-eye)
// with the geometry fixed on 2026-11-16 (knowledge#14285): the iris is a true circle (one uniform DPR scale, the
// canvas's CSS box pinned to its bitmap), the lids reach 1.75 R and open to 1.16 R, so the lid ratio is ~1.36.
// Same lid clip, lane rings, fibres, rims, lane particles, convergence dust, pupil, highlight, lash dust and brow.
// It runs on demo lanes. Added for the landing page: a blink, and a gaze (the pupil, its dust and the highlight
// follow a look vector: the pointer, or the scroll when a direction asks for it). GSAP's ticker drives every frame.
const TAU = Math.PI * 2;
const GAP = 0.03;
const OUT = [0.64, 0.98], INN = [0.34, 0.58], PUPIL = 0.26;
const RING = [OUT, INN];
export const LID_W = 1.75, LID_H = 1.16, BOX_H = 2.84;   // lid half-width, lid half-height, drawn extent (x R)

// demo lanes, shaped like the live eye's (Upwork the live hunt, the biggest slice)
const DEMO = [
  { ring: 0, name: 'Upwork', w: 3, live: true, sent: 214 },
  { ring: 0, name: 'Cold apps', w: 2, sent: 120 },
  { ring: 0, name: 'In person', w: 1, sent: 9 },
  { ring: 1, name: 'Clients', w: 1, sent: 2 },
  { ring: 1, name: 'Network', w: 1, sent: 3 },
];

function sprite(rgb, size) {
  const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d'), h = size / 2;
  const gr = g.createRadialGradient(h, h, 0, h, h, h);
  gr.addColorStop(0, `rgba(${rgb},1)`); gr.addColorStop(.18, `rgba(${rgb},.75)`); gr.addColorStop(.5, `rgba(${rgb},.14)`); gr.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = gr; g.fillRect(0, 0, size, size); return c;
}

export function mountEagleEye({ canvas, slot, gsap, reduced = false, start = 0 }) {
  // the canvas is screen-blended (it can only add light), so the pupil's dark comes from a shade behind it
  const shade = document.createElement('div'); shade.className = 'ee-shade'; canvas.before(shade);
  const ctx = canvas.getContext('2d');
  const spGold = sprite('217,179,91', 32), spPale = sprite('243,220,154', 32);
  const PIPES = DEMO.map((p, i) => ({ ...p, i }));
  { const tw = [0, 0]; PIPES.forEach((p) => (tw[p.ring] += p.w));
    PIPES.forEach((p, i) => { p.aw = TAU * p.w / tw[p.ring]; p.a0 = PIPES.slice(0, i).filter((o) => o.ring === p.ring).reduce((s, o) => s + TAU * o.w / tw[o.ring], 0); }); }
  const act = PIPES.map((p) => (p.live ? 1 : Math.min(0.8, 0.25 + 0.55 * Math.log10(1 + p.sent) / 2.4)));   // a busy demo fleet
  const LIVE = PIPES.findIndex((p) => p.live);

  let W, H, DPR, cx, cy, R, lidW, dk = 1; const rot = [0, 0];
  let lite = false, frozen = false, dprCap = 2;
  function resize() {
    // the canvas is the eye's own box (the slot plus a margin for the glow and lash dust), never the whole hero
    const sr = slot.getBoundingClientRect(), pad = Math.round(sr.width * .1);
    DPR = Math.min(devicePixelRatio || 1, dprCap); W = Math.round(sr.width + 2 * pad); H = Math.round(sr.height + 2 * pad);
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    Object.assign(canvas.style, { width: W + 'px', height: H + 'px', left: -pad + 'px', top: -pad + 'px' });   // one uniform scale: the iris stays a circle
    lidW = Math.max(30, (sr.width - 16) / 2); R = Math.max(20, lidW / LID_W);   // a canvas gradient throws on a negative radius
    cx = W / 2; cy = H / 2;
    dk = Math.min(1, R / 200);
    rot[0] = Math.PI / 2 - (PIPES[LIVE].a0 + PIPES[LIVE].aw / 2);
    { const r1 = PIPES.find((p) => p.ring === 1); rot[1] = -Math.PI / 2 + (r1 ? r1.aw / 2 : 0); }
    const d = PUPIL * R * 2.5; Object.assign(shade.style, { width: d + 'px', height: d + 'px', left: (sr.width - d) / 2 + 'px', top: (sr.height - d) / 2 + 'px' });
    if (reduced || frozen) frame(performance.now());
  }

  const rnd = (a, b) => a + Math.random() * (b - a);
  const parts = [];
  PIPES.forEach((p) => { const n = p.live ? 650 : 150; for (let j = 0; j < n; j++) parts.push({ pi: p.i, ring: p.ring, off: rnd(-1, 1), p: Math.random(), sp: rnd(.04, .12), w: rnd(.05, .16) * (Math.random() < .5 ? -1 : 1), s: rnd(.5, 1.5), tw: rnd(0, TAU), pale: Math.random() < .25, del: Math.random() * 1.4, sw: rnd(-1.5, 1.5), gate: Math.random() }); });
  const fibres = []; for (let i = 0; i < 900; i++) fibres.push({ a: rnd(0, TAU), r: rnd(.3, 1.02), l: rnd(.03, .12), tw: rnd(0, TAU), del: Math.random() * 1.5 });
  const conv = []; for (let i = 0; i < 420; i++) conv.push({ a: rnd(0, TAU), p: Math.random(), sp: rnd(.15, .4), sw: rnd(.6, 2) });
  const lid = []; for (let i = 0; i < 900; i++) lid.push({ t: Math.random(), up: Math.random() < .5, off: rnd(-1, 1), tw: rnd(0, TAU), s: rnd(.6, 1.4) });

  const ease = (t) => (t < 0 ? 0 : t > 1 ? 1 : 1 - Math.pow(1 - t, 3));
  const sm = (u) => { u = Math.max(0, Math.min(1, u)); return u * u * (3 - 2 * u); };
  const lidY = (x, openness, up) => (up ? -1 : 1) * (R * LID_H) * openness * Math.pow(1 - x * x, .9);

  // state GSAP animates: blink (0 open, 1 shut), look (-1..1 each axis), glow (extra light, e.g. the sun disk)
  const st = { blink: 0, lx: 0, ly: 0, glow: 0 };
  let t0 = performance.now() + start * 1000, last = performance.now(), visible = true;

  function frame(now) {
    const t = Math.max(0, (now - t0) / 1000), dt = Math.min(.05, (now - last) / 1000); last = now;
    const open = sm((t - .3) / 2.4) * (1 - st.blink);
    const intro = Math.max(ease(t / 3.2) * .6, sm((t - .3) / 2.4));
    const gx = st.lx * R * .1, gy = st.ly * R * .08;   // the gaze: pupil, iris dust and highlight move together
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over';
    // additive light needs an opaque ground (on a transparent canvas the grains come out several times dimmer):
    // black, and the canvas is screen-blended onto the sand, so black adds nothing and the box never shows
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    const bl = ctx.createRadialGradient(cx, cy, R * .2, cx, cy, R * 1.25);
    bl.addColorStop(0, `rgba(217,179,91,${(.10 + .08 * st.glow) * intro})`); bl.addColorStop(.6, `rgba(217,179,91,${(.04 + .04 * st.glow) * intro})`); bl.addColorStop(1, 'rgba(217,179,91,0)');
    ctx.globalAlpha = 1; ctx.fillStyle = bl; ctx.fillRect(0, 0, W, H);

    ctx.save(); try { ctx.beginPath();
    const steps = 48;
    for (let i = 0; i <= steps; i++) { const x = -1 + 2 * i / steps; const px = cx + x * lidW, py = cy + lidY(x, open, true); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
    for (let i = steps; i >= 0; i--) { const x = -1 + 2 * i / steps; ctx.lineTo(cx + x * lidW, cy + lidY(x, open, false)); }
    ctx.closePath(); ctx.clip(); ctx.globalCompositeOperation = 'lighter';
    const ix = cx + gx * .35, iy = cy + gy * .35;   // the iris follows the gaze a little, the pupil fully
    for (const p of PIPES) {
      const a = act[p.i];
      const a0 = rot[p.ring] + p.a0 + GAP, a1 = rot[p.ring] + p.a0 + p.aw - GAP;
      const [r0, r1] = RING[p.ring], rm = (r0 + r1) / 2 * R;
      ctx.lineWidth = (r1 - r0) * R; ctx.strokeStyle = 'rgb(217,179,91)';
      ctx.globalAlpha = (.004 + .035 * a + (p.live ? .05 : 0)) * intro; ctx.beginPath(); ctx.arc(ix, iy, rm, a0, a1); ctx.stroke();
      ctx.lineWidth = 1; ctx.strokeStyle = 'rgb(243,220,154)'; ctx.globalAlpha = (.10 + .5 * a) * intro;
      ctx.beginPath(); ctx.arc(ix, iy, r0 * R, a0, a1); ctx.stroke(); ctx.beginPath(); ctx.arc(ix, iy, r1 * R, a0, a1); ctx.stroke();
    }
    const stp = lite ? 2 : 1;
    for (let fi = 0; fi < fibres.length; fi += stp) { const f = fibres[fi]; const e = ease((t - f.del * .7) / 2.2); if (e <= 0) continue; const a = f.a + Math.sin(t * .1 + f.tw) * .01, r0 = f.r * R * e, r1 = (f.r + f.l) * R * e;
      ctx.globalAlpha = (.03 + .03 * Math.sin(t * .8 + f.tw)) * e; ctx.strokeStyle = '#d9b35b'; ctx.lineWidth = .6; ctx.beginPath(); ctx.moveTo(ix + Math.cos(a) * r0, iy + Math.sin(a) * r0); ctx.lineTo(ix + Math.cos(a) * r1, iy + Math.sin(a) * r1); ctx.stroke(); }
    const rim = (r, al, lw, x, y) => { ctx.globalAlpha = al * intro; ctx.lineWidth = lw; ctx.strokeStyle = '#f3dc9a'; ctx.beginPath(); ctx.arc(x, y, r * R, 0, TAU); ctx.stroke(); };
    rim(1.005, .45, 1.2, ix, iy); rim(1.03, .12, 5, ix, iy); rim(PUPIL, .4, 1.2, cx + gx, cy + gy); rim(PUPIL + .01, .08, 5, cx + gx, cy + gy);
    for (let qi = 0; qi < parts.length; qi += stp) { const q = parts[qi];
      const a = act[q.pi], vis = a * .55;
      if (q.gate > vis * 1.15 + .04) continue;
      q.p += q.sp * dt * (.5 + a * 1.2); if (q.p >= 1) { q.p -= 1; q.off = rnd(-1, 1); }
      const pp = PIPES[q.pi], sw = pp.aw, lim = sw / 2 - GAP, c = rot[q.ring] + pp.a0 + sw / 2;
      q.off += q.w * dt * .6 / lim * .5; q.off = Math.max(-1, Math.min(1, q.off));
      const lo = RING[q.ring], f = q.ring ? 1 - q.p : q.p, r = lo[0] + (lo[1] - lo[0]) * f;
      const e = ease((t - q.del) / 2); if (e <= 0) continue;
      const ang = c + q.off * lim + (1 - e) * q.sw * 2.2, rr = (PUPIL + (r - PUPIL) * e) * R;
      const x = ix + Math.cos(ang) * rr, y = iy + Math.sin(ang) * rr, edge = Math.sin(Math.PI * q.p);
      ctx.globalAlpha = Math.min(1, (.35 + .65 * Math.min(1, a * 1.2)) * edge * (.7 + .3 * Math.sin(t * 3 + q.tw))) * e;
      const z = (3.2 * q.s + a * 1.5) * (R / 420 + .4);
      ctx.drawImage(q.pale ? spPale : spGold, x - z / 2, y - z / 2, z, z);
    }
    for (const c of conv) { c.p += c.sp * dt; if (c.p >= 1) { c.p -= 1; c.a = rnd(0, TAU); }
      const r = (PUPIL + (.5 - PUPIL) * (1 - c.p)) * R, a = c.a + c.p * c.sw * .9 + t * .05; ctx.globalAlpha = Math.sin(Math.PI * c.p) * .7 * intro; const z = 3.4;
      ctx.drawImage(spPale, cx + gx + Math.cos(a) * r - z / 2, cy + gy + Math.sin(a) * r - z / 2, z, z); }
    ctx.globalCompositeOperation = 'source-over';
    const px = cx + gx, py = cy + gy;
    if (gx !== shade._gx || gy !== shade._gy) { shade._gx = gx; shade._gy = gy; shade.style.transform = `translate(${gx.toFixed(1)}px,${gy.toFixed(1)}px)`; }
    const pg = ctx.createRadialGradient(px, py, 0, px, py, PUPIL * R);
    pg.addColorStop(0, 'rgba(10,10,9,1)'); pg.addColorStop(.82, 'rgba(10,10,9,.97)'); pg.addColorStop(1, 'rgba(10,10,9,.6)');
    ctx.globalAlpha = intro; ctx.fillStyle = pg; ctx.beginPath(); ctx.arc(px, py, PUPIL * R, 0, TAU); ctx.fill();
    ctx.globalCompositeOperation = 'lighter';
    const pulse = .5 + .5 * Math.sin(t * 1.2), ig = ctx.createRadialGradient(px, py, PUPIL * R * .6, px, py, PUPIL * R * 1.35);
    ig.addColorStop(0, 'rgba(243,220,154,0)'); ig.addColorStop(.55, `rgba(243,220,154,${(.10 + .06 * pulse) * intro})`); ig.addColorStop(1, 'rgba(217,179,91,0)');
    ctx.globalAlpha = 1; ctx.fillStyle = ig; ctx.beginPath(); ctx.arc(px, py, PUPIL * R * 1.4, 0, TAU); ctx.fill();
    ctx.globalAlpha = .5 * intro * open; const cz = R * .09; ctx.drawImage(spPale, px - R * .09 - cz / 2, py - R * .1 - cz / 2, cz * 2, cz * 2);
    } finally { ctx.restore(); }   // never leave a clip on the stack: the next frame's clear would be clipped to it
    ctx.globalCompositeOperation = 'lighter';
    for (let di = 0; di < lid.length; di += stp) { const d = lid[di]; const e = Math.min(1, .15 + ease((t - .2 - d.t * 1.6) / 1.6)); const x = -1 + 2 * d.t, y = lidY(x, open, d.up);
      const lx = cx + x * lidW, ly = cy + y + d.off * (4 + (1 - Math.abs(x)) * 6) * dk;
      ctx.globalAlpha = (.55 + .4 * Math.sin(t * 2 + d.tw)) * e * (.5 + .5 * Math.min(1, 1.2 - Math.abs(x) * .6)); const z = 4.2 * d.s * Math.max(.7, dk); ctx.drawImage(d.tw > 3 ? spPale : spGold, lx - z / 2, ly - z / 2, z, z); }
    const openB = sm((t - .3) / 2.4) * (1 - st.blink * .35);   // the brow barely moves in a blink
    for (let i = 0; i < 260; i++) { const u = i / 259, e = ease((t - .8 - u * 1.8) / 1.4); if (e <= 0) continue; const x = -1 + 2 * u;
      const by = cy - R * LID_H * openB * Math.pow(1 - x * x, .9) - R * .17 * openB - Math.sin(u * Math.PI) * R * .05;
      const j = Math.sin(i * 12.9898) * 43758.5453, off = (j - Math.floor(j) - .5) * 9 * dk;
      ctx.globalAlpha = .4 * e * (.6 + .4 * Math.sin(t * 1.5 + i)); const z = 3.2 * Math.max(.7, dk); ctx.drawImage(spGold, cx + x * lidW * .98 - z / 2, by + off - z / 2, z, z); }
    ctx.globalCompositeOperation = 'source-over';
  }

  const tick = () => { if (visible && !frozen) frame(performance.now()); };
  resize();
  let lastW = innerWidth, lastSlotW = 0;
  addEventListener('resize', () => { if (innerWidth !== lastW || !reduced) { lastW = innerWidth; resize(); } });
  if (document.fonts) document.fonts.ready.then(resize);
  new ResizeObserver(() => { if (slot.getBoundingClientRect().width !== lastSlotW) { lastSlotW = slot.getBoundingClientRect().width; resize(); } }).observe(slot);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { rootMargin: '80px' }).observe(canvas);
  if (reduced) { t0 = -9e5; frame(performance.now()); return { st, resize, geometry: () => ({ cx, cy, R, lidW }), degrade() {} }; }
  gsap.ticker.add(tick);

  // blink every few seconds, sometimes twice
  const blink = gsap.timeline({ repeat: -1, repeatDelay: 4.2, delay: start + 4.2 });
  blink.to(st, { blink: 1, duration: .1, ease: 'power2.in' }).to(st, { blink: 0, duration: .18, ease: 'power2.out' })
       .to(st, { blink: 1, duration: .09, ease: 'power2.in' }, '+=3.1').to(st, { blink: 0, duration: .16, ease: 'power2.out' })
       .to(st, { blink: 1, duration: .08, ease: 'power2.in' }, '+=.14').to(st, { blink: 0, duration: .15, ease: 'power2.out' });
  // a device that cannot hold the frame rate: 1x pixels, then a still eye (fully open, drawn once)
  function degrade(tier) {
    if (tier === 1) { dprCap = 1; resize(); return; }   // keep every grain: the eye is the hero
    frozen = true; blink.kill(); st.blink = 0; t0 = performance.now() - 9e5; frame(performance.now());
  }
  return { st, resize, degrade, geometry: () => ({ cx, cy, R, lidW, W, H }) };
}

// the pupil follows the pointer; with no pointer (phones) it glances on its own
export function followPointer(eye, gsap) {
  const lx = gsap.quickTo(eye.st, 'lx', { duration: .7, ease: 'power3.out' }), ly = gsap.quickTo(eye.st, 'ly', { duration: .7, ease: 'power3.out' });
  let lastMove = 0, enabled = true;
  addEventListener('pointermove', (e) => {
    if (!enabled || e.pointerType === 'touch') return;
    const g = eye.geometry(), r = eye.canvas || null;
    const rect = document.querySelector('.ee-canvas').getBoundingClientRect();
    lx(gsap.utils.clamp(-1, 1, (e.clientX - rect.left - g.cx) / (innerWidth * .4)));
    ly(gsap.utils.clamp(-1, 1, (e.clientY - rect.top - g.cy) / (innerHeight * .4)));
    lastMove = performance.now();
  }, { passive: true });
  gsap.delayedCall(4, function wander() {
    if (enabled && performance.now() - lastMove > 3000) { lx(gsap.utils.random(-.8, .8)); ly(gsap.utils.random(-.5, .6)); }
    gsap.delayedCall(gsap.utils.random(1.6, 3.2), wander);
  });
  return { set: (v) => { enabled = v; }, lx, ly };
}
