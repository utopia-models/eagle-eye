// The hero: gold sand gathers into the Eye of Horus (three.js points, GSAP drives every uniform).
// The pupil follows the pointer, the eye blinks, and scrolling away scatters the sand.
import * as THREE from 'three';

const VB_W = 200, VB_H = 120;
// The same paths as /assets/mark.svg (viewBox 0 0 200 120).
const BROW = 'M24 34 C 60 10 132 2 180 18 L 178 27 C 132 14 64 20 27 42 Z';
const LIDS = 'M28 64 C 62 36 130 32 170 57 C 130 75 70 82 28 64 Z';
const TAIL = 'M168 58 C 178 60 188 60 196 57';
const DROP = 'M84 76 C 82 90 80 102 75 114';
const CURL = 'M110 76 C 118 98 142 110 162 103 C 175 98 174 83 163 81 C 154 80 150 90 157 94';
const PUPIL = { x: 98, y: 57, r: 15.5 };

function sampleMark(count) {
  const S = 5;
  const c = document.createElement('canvas');
  c.width = VB_W * S; c.height = VB_H * S;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.scale(S, S);
  g.fillStyle = g.strokeStyle = '#fff';
  g.lineCap = 'round'; g.lineJoin = 'round';
  g.fill(new Path2D(BROW));
  g.lineWidth = 5.5;
  for (const d of [LIDS, TAIL, DROP, CURL]) g.stroke(new Path2D(d));
  g.beginPath(); g.arc(PUPIL.x, PUPIL.y, PUPIL.r, 0, Math.PI * 2); g.fill();
  const px = g.getImageData(0, 0, c.width, c.height).data;
  const hits = [];
  for (let i = 3; i < px.length; i += 4) if (px[i] > 120) hits.push((i - 3) / 4);
  const out = [];
  for (let k = 0; k < count; k++) {
    const idx = hits[(Math.random() * hits.length) | 0];
    const x = (idx % c.width + Math.random()) / S;
    const y = (Math.floor(idx / c.width) + Math.random()) / S;
    const pupil = Math.hypot(x - PUPIL.x, y - PUPIL.y) < PUPIL.r + 0.5 ? 1 : 0;
    out.push([x - VB_W / 2, y - VB_H / 2, pupil]);
  }
  return out;
}

const VERT = /* glsl */`
  attribute vec2 aTarget;
  attribute vec2 aStart;
  attribute float aSeed;
  attribute float aType;
  uniform vec2 uRes, uCenter, uLook;
  uniform float uScale, uTime, uProgress, uBlink, uDisperse, uDpr;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    vec2 p;
    vSeed = aSeed;
    if (aType > 1.5) {
      // ambient dust: drifts up through the hero
      float H = uRes.y + 40.0;
      float y = mod(aStart.y - uTime * (5.0 + aSeed * 12.0), H) - 20.0;
      float x = aStart.x + sin(uTime * 0.25 + aSeed * 21.0) * 14.0;
      p = vec2(x, y);
      vAlpha = (0.18 + 0.32 * aSeed) * (1.0 - uDisperse * 0.6);
      gl_PointSize = (0.9 + aSeed * 1.5) * uDpr;
    } else {
      vec2 t = aTarget;
      // blink: the lids and pupil close onto the lid line
      float inEye = step(-30.0, t.y) * step(t.y, 22.0) * step(-73.0, t.x) * step(t.x, 72.0);
      t.y = mix(t.y, -1.5 + t.y * 0.08, uBlink * inEye);
      if (aType > 0.5) t += uLook * vec2(7.0, 4.0);
      vec2 target = uCenter + t * uScale;
      float d = clamp(uProgress * 1.7 - aSeed * 0.7, 0.0, 1.0);
      d = 1.0 - pow(1.0 - d, 3.0);
      p = mix(uCenter + aStart, target, d);
      float j = (1.0 - d) * 16.0 + 0.45 * uScale;
      p += vec2(sin(uTime * 1.3 + aSeed * 40.0), cos(uTime * 1.1 + aSeed * 33.0)) * j * 0.6;
      vec2 dir = normalize(t + vec2(0.001, 0.001));
      p += dir * uDisperse * (40.0 + aSeed * 320.0) + vec2(0.0, -uDisperse * aSeed * 160.0);
      float tw = 0.6 + 0.4 * sin(uTime * 2.2 + aSeed * 90.0);
      vAlpha = mix(0.12, 1.0, d) * tw * (1.0 - uDisperse * 0.85) * (aType > 0.5 ? 1.25 : 1.0);
      gl_PointSize = (1.2 + aSeed * 2.0) * uDpr * clamp(uScale / 3.0, 0.75, 1.25);
    }
    gl_Position = vec4(p.x / uRes.x * 2.0 - 1.0, 1.0 - p.y / uRes.y * 2.0, 0.0, 1.0);
  }
`;
const FRAG = /* glsl */`
  precision mediump float;
  varying float vAlpha;
  varying float vSeed;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float r = length(c);
    if (r > 0.5) discard;
    float a = smoothstep(0.5, 0.0, r) * vAlpha;
    vec3 gold = vec3(0.851, 0.702, 0.357);
    vec3 bright = vec3(0.98, 0.90, 0.66);
    vec3 pearl = vec3(0.81, 0.85, 1.0);
    vec3 col = mix(gold, bright, smoothstep(0.55, 1.0, vSeed));
    col = mix(col, pearl, step(0.975, vSeed) * 0.7);
    gl_FragColor = vec4(col * a, a);
  }
`;

export function mountEye({ canvas, slot, hero, gsap, ScrollTrigger, reduced }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  const phone = Math.min(innerWidth, innerHeight) < 600;
  const N = phone ? 5000 : 9000;
  const DUST = phone ? 260 : 620;
  const pts = sampleMark(N);

  const total = N + DUST;
  const aTarget = new Float32Array(total * 2);
  const aStart = new Float32Array(total * 2);
  const aSeed = new Float32Array(total);
  const aType = new Float32Array(total);
  const scatter = Math.max(innerWidth, innerHeight);
  for (let i = 0; i < N; i++) {
    aTarget[i * 2] = pts[i][0]; aTarget[i * 2 + 1] = pts[i][1];
    // sand starts low and wide, as if lifted off the ground
    aStart[i * 2] = (Math.random() - 0.5) * scatter * 1.3;
    aStart[i * 2 + 1] = scatter * (0.15 + Math.random() * 0.6);
    aSeed[i] = Math.random();
    aType[i] = pts[i][2];
  }
  for (let i = N; i < total; i++) {
    aStart[i * 2] = Math.random() * 3000; aStart[i * 2 + 1] = Math.random() * 3000;
    aSeed[i] = Math.random(); aType[i] = 2;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 3), 3));
  geo.setAttribute('aTarget', new THREE.BufferAttribute(aTarget, 2));
  geo.setAttribute('aStart', new THREE.BufferAttribute(aStart, 2));
  geo.setAttribute('aSeed', new THREE.BufferAttribute(aSeed, 1));
  geo.setAttribute('aType', new THREE.BufferAttribute(aType, 1));
  const u = {
    uRes: { value: new THREE.Vector2(1, 1) }, uCenter: { value: new THREE.Vector2() }, uLook: { value: new THREE.Vector2() },
    uScale: { value: 3 }, uTime: { value: 0 }, uProgress: { value: reduced ? 1 : 0 }, uBlink: { value: 0 },
    uDisperse: { value: 0 }, uDpr: { value: 1 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, vertexShader: VERT, fragmentShader: FRAG,
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending,
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  const scene = new THREE.Scene();
  scene.add(points);
  const camera = new THREE.Camera();

  let maxDpr = 1.5;
  function layout() {
    const hr = hero.getBoundingClientRect();
    const sr = slot.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, maxDpr);
    renderer.setPixelRatio(dpr);
    renderer.setSize(hr.width, hr.height, false);
    u.uRes.value.set(hr.width, hr.height);
    u.uCenter.value.set(sr.left - hr.left + sr.width / 2, sr.top - hr.top + sr.height / 2);
    u.uScale.value = sr.width / VB_W;
    u.uDpr.value = dpr;
    if (reduced || frozen) draw();
  }
  function draw() { renderer.render(scene, camera); }


  // Adaptive quality: a device that cannot hold the frame rate gets half the sand at 1x, then a still eye.
  let visible = true, tier = 0, last = 0, gaps = [], frozen = false;
  const tick = (time) => {
    if (!visible || frozen) return;
    const now = performance.now();
    if (last && tier < 2) {
      gaps.push(now - last);
      if (gaps.length === 45) {
        gaps.sort((a, b) => a - b);
        if (gaps[22] > 34) degrade();
        gaps = [];
      }
    }
    last = now;
    u.uTime.value = time; draw();
  };
  function degrade() {
    tier++;
    if (tier === 1) { geo.setDrawRange(0, Math.floor(N / 2)); maxDpr = 1; layout(); return; }
    // still too slow: settle the eye and draw it once, like reduced motion
    frozen = true;
    gsap.killTweensOf(u.uProgress); blink.kill(); u.uProgress.value = 1; u.uBlink.value = 0;
    gsap.ticker.remove(tick);
    draw();
    addEventListener('scroll', () => { if (visible) draw(); }, { passive: true });
  }
  layout();
  addEventListener('resize', layout);
  if (document.fonts) document.fonts.ready.then(layout);

  if (reduced) { draw(); return; }

  gsap.ticker.add(tick);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(hero);

  // gather
  gsap.to(u.uProgress, { value: 1, duration: 2.4, ease: 'power2.inOut', delay: 0.1 });
  // blink every few seconds, sometimes twice
  const blink = gsap.timeline({ repeat: -1, repeatDelay: 4.5, delay: 3.2 });
  blink.to(u.uBlink, { value: 1, duration: 0.09, ease: 'power2.in' })
       .to(u.uBlink, { value: 0, duration: 0.16, ease: 'power2.out' })
       .to(u.uBlink, { value: 1, duration: 0.08, ease: 'power2.in' }, '+=2.6')
       .to(u.uBlink, { value: 0, duration: 0.14, ease: 'power2.out' })
       .to(u.uBlink, { value: 1, duration: 0.08, ease: 'power2.in' }, '+=0.12')
       .to(u.uBlink, { value: 0, duration: 0.14, ease: 'power2.out' });
  // the pupil follows you
  const lookX = gsap.quickTo(u.uLook.value, 'x', { duration: 0.6, ease: 'power3.out' });
  const lookY = gsap.quickTo(u.uLook.value, 'y', { duration: 0.6, ease: 'power3.out' });
  let lastPointer = 0;
  addEventListener('pointermove', (e) => {
    const hr = hero.getBoundingClientRect();
    const dx = (e.clientX - hr.left - u.uCenter.value.x) / (hr.width / 2);
    const dy = (e.clientY - hr.top - u.uCenter.value.y) / (hr.height / 2);
    lookX(gsap.utils.clamp(-1, 1, dx)); lookY(gsap.utils.clamp(-1, 1, dy));
    lastPointer = performance.now();
  }, { passive: true });
  // with no pointer (phones), the eye glances around on its own
  gsap.delayedCall(3, function wander() {
    if (performance.now() - lastPointer > 3000) {
      lookX(gsap.utils.random(-0.9, 0.9)); lookY(gsap.utils.random(-0.5, 0.6));
    }
    gsap.delayedCall(gsap.utils.random(1.4, 2.8), wander);
  });
  // scrolling away scatters the sand
  ScrollTrigger.create({
    trigger: hero, start: 'top top', end: 'bottom top', scrub: true,
    onUpdate: (st) => { u.uDisperse.value = st.progress; if (frozen) draw(); },
  });
}
