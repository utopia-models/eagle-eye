// The sand: utopiamodels.ai / live.utopiamodels.ai's grain renderer (OGL points, additive gold grains with a slow
// pearl sheen, one grain in five a pearl glint: C4's fragment shader, verbatim) on a fixed full-viewport canvas.
// Grains move between FORMATIONS (field, ground, the eye's outline, a falcon wing, the sun disk and horizon);
// GSAP tweens the mix, so every move uses the Utopia sites' eases (power2.inOut, sine.inOut).
import { Renderer, Program, Geometry, Mesh } from 'ogl';

const FS = `precision highp float; varying float vL; varying float vSeed; uniform float uT;
  uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
  void main(){ vec2 q = gl_PointCoord - 0.5; float r = length(q)*2.0; if(r > 1.0) discard; float a = pow(1.0 - r, 1.6);
    vec3 col = mix(uC1, uC2, vSeed); float sh = 0.5 + 0.5*sin(vSeed*23.0 + uT*0.7 + vL*2.0);
    vec3 pearl = mix(vec3(0.72,0.84,1.0), vec3(0.88,0.80,1.0), 0.5+0.5*sin(uT*0.31 + vSeed*9.0));
    col = mix(col, pearl, (0.28 + 0.3*clamp(vL-0.6, 0.0, 1.0))*sh*sh + 0.08);
    float glint = step(0.8, fract(vSeed*7.13)); col = mix(col, pearl*vec3(0.92,1.0,1.12), glint*(0.55 + 0.35*sh));
    col = mix(col, uC3, clamp(vL-1.0, 0.0, 0.5));
    gl_FragColor = vec4(col, a*clamp(vL, 0.0, 1.5)*0.85); }`;

const VS = `attribute vec2 aFrom; attribute vec2 aTo; attribute vec4 aS;
  uniform vec2 uRes; uniform float uDpr, uT, uK, uDrift, uLum, uSize, uScroll, uAttachFrom, uAttachTo, uSweep, uField, uSink, uHz;
  varying float vL; varying float vSeed;
  void main(){
    float k = clamp(uK*1.6 - aS.x*0.6, 0.0, 1.0); k = k*k*(3.0-2.0*k);
    float fieldG = step(aS.w, uField);                // a share of grains always drifts in the viewport (dust behind every section)
    vec2 a = aFrom - vec2(0.0, uAttachFrom*(1.0-fieldG)*uScroll), b = aTo - vec2(0.0, uAttachTo*(1.0-fieldG)*uScroll);
    vec2 p = mix(a, b, k);
    p = mix(p, vec2(fract(aS.y*7.31)*uRes.x, fract(aS.z*5.17 + uT*0.004*(0.5+aS.x))*uRes.y), fieldG);   // dust behind every section
    float fly = sin(3.14159*k);                       // in flight, grains lift and stream
    p += vec2(uSweep*fly*(0.6+aS.w), -fly*40.0*aS.y);
    p += vec2(sin(uT*0.31 + aS.y*40.0), cos(uT*0.27 + aS.z*33.0)) * uDrift*(0.35+aS.w);
    // the sun sets: grains above the horizon sink toward it and go out as they cross it
    float hz = uHz - uScroll, above = step(p.y, hz - 3.0) * (1.0 - fieldG);
    p.y += above * uSink * (hz - p.y) * (0.75 + 0.25*aS.x);
    vL = (0.45 + 0.75*aS.w) * uLum * (0.62 + 0.38*sin(uT*1.7 + aS.x*50.0)) * (1.0 + 0.5*fly);
    vL *= mix(1.0, 0.35, fieldG*step(0.001, uField)) * (1.0 - above*uSink*0.85);
    vSeed = aS.z;
    gl_PointSize = (1.0 + 1.6*aS.y) * uSize * uDpr * (1.0 + 0.4*fly);
    gl_Position = vec4(p.x/uRes.x*2.0-1.0, 1.0-p.y/uRes.y*2.0, 0.0, 1.0);
  }`;

export function mountSand({ canvas, gsap, reduced = false, count }) {
  const phone = Math.min(innerWidth, innerHeight) < 600;
  const N = count || (phone ? 2600 : 4800);
  let DPR = Math.min(devicePixelRatio || 1, 1.5);
  const renderer = new Renderer({ canvas, alpha: false, antialias: false, dpr: DPR, preserveDrawingBuffer: true, powerPreference: 'high-performance' });   // a still frame must survive a recomposite (WebKit)
  // opaque, cleared to the page ink, exactly like the Utopia sites: additive grains on a solid ground
  const gl = renderer.gl; gl.clearColor(10 / 255, 10 / 255, 9 / 255, 1);
  const seeds = new Float32Array(N * 4); for (let i = 0; i < seeds.length; i++) seeds[i] = Math.random();
  const from = new Float32Array(N * 2), to = new Float32Array(N * 2);
  const geometry = new Geometry(gl, { aFrom: { size: 2, data: from }, aTo: { size: 2, data: to }, aS: { size: 4, data: seeds } });
  const u = {
    uRes: { value: [innerWidth, innerHeight] }, uDpr: { value: DPR }, uT: { value: 0 }, uK: { value: 0 }, uDrift: { value: 10 },
    uLum: { value: 1 }, uSize: { value: phone ? 1.5 : 1.75 }, uScroll: { value: 0 }, uAttachFrom: { value: 0 }, uAttachTo: { value: 0 }, uSweep: { value: 0 }, uField: { value: 0 }, uSink: { value: 0 }, uHz: { value: 0 },
    uC1: { value: [212 / 255, 169 / 255, 78 / 255] }, uC2: { value: [240 / 255, 210 / 255, 138 / 255] }, uC3: { value: [1, 244 / 255, 214 / 255] },
  };
  const program = new Program(gl, { vertex: VS, fragment: FS, uniforms: u, transparent: true, depthTest: false, depthWrite: false });
  program.setBlendFunc(gl.SRC_ALPHA, gl.ONE);
  const mesh = new Mesh(gl, { mode: gl.POINTS, geometry, program });

  let sizedW = 0;
  function size() {
    if (innerWidth === sizedW) return; sizedW = innerWidth;
    renderer.setSize(innerWidth, innerHeight); u.uRes.value = [innerWidth, innerHeight];
  }
  size(); addEventListener('resize', size);

  const draw = () => renderer.render({ scene: mesh });
  // set a move: grains travel from one formation to the next as GSAP tweens uK 0 -> 1
  function move(f, t, { attachFrom = 0, attachTo = 0 } = {}) {
    from.set(f); to.set(t); geometry.attributes.aFrom.needsUpdate = true; geometry.attributes.aTo.needsUpdate = true;
    u.uAttachFrom.value = attachFrom; u.uAttachTo.value = attachTo; u.uK.value = 0;
  }
  let running = true;
  const tick = (time) => { if (!running) return; u.uT.value = time; u.uScroll.value = scrollY; draw(); };
  if (!reduced) gsap.ticker.add(tick);
  function degrade(tier) {
    if (tier === 1) { geometry.setDrawRange(0, Math.floor(N / 2)); renderer.dpr = DPR = 1; u.uDpr.value = 1; u.uSize.value *= 1.3; sizedW = 0; size(); return; }
    running = false;   // still grains; one coalesced redraw per scroll frame keeps page-attached formations in place
    let queued = false;
    addEventListener('scroll', () => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; u.uScroll.value = scrollY; draw(); }); }, { passive: true });
  }
  return { N, u, move, draw, size, degrade, pause: (v) => { running = !v; }, seeds };
}

// ---------- formations: Float32Array(N*2) of CSS-pixel points (page coords when attached, viewport otherwise) ----------
const rand = Math.random;
export function field(N, W = innerWidth, H = innerHeight) { const a = new Float32Array(N * 2); for (let i = 0; i < N; i++) { a[i * 2] = rand() * W; a[i * 2 + 1] = rand() * H; } return a; }
export function ground(N, W = innerWidth, H = innerHeight) { const a = new Float32Array(N * 2); for (let i = 0; i < N; i++) { a[i * 2] = (rand() * 1.2 - .1) * W; a[i * 2 + 1] = H * (.9 + Math.pow(rand(), .6) * .14); } return a; }
// the eye's open outline: both lids, the brow, the iris rim and pupil rim (same curves as the canvas eye)
export function eyeOutline(N, g, { LID_W = 1.75, LID_H = 1.16 } = {}) {
  const a = new Float32Array(N * 2), { cx, cy, R } = g, lidW = R * LID_W;
  for (let i = 0; i < N; i++) {
    const s = rand(); let x, y;
    if (s < .52) { const u = -1 + 2 * rand(), up = rand() < .5; x = cx + u * lidW; y = cy + (up ? -1 : 1) * R * LID_H * Math.pow(1 - u * u, .9); }
    else if (s < .7) { const u = -1 + 2 * rand(); x = cx + u * lidW * .98; y = cy - R * LID_H * Math.pow(1 - u * u, .9) - R * .17 - Math.sin((u + 1) / 2 * Math.PI) * R * .05; }
    else if (s < .9) { const t = rand() * Math.PI * 2; x = cx + Math.cos(t) * R; y = cy + Math.sin(t) * R; }
    else { const t = rand() * Math.PI * 2; x = cx + Math.cos(t) * R * .26; y = cy + Math.sin(t) * R * .26; }
    a[i * 2] = x + (rand() - .5) * 5; a[i * 2 + 1] = y + (rand() - .5) * 5;
  }
  return a;
}

// sample N points from a shape drawn on a 2D canvas (the Utopia sites' sampler, C4)
function sampleShape(N, w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d', { willReadFrequently: true });
  g.fillStyle = g.strokeStyle = '#fff'; g.lineCap = g.lineJoin = 'round'; draw(g);
  const d = g.getImageData(0, 0, w, h).data, hit = [];
  for (let i = 3; i < d.length; i += 16) if (d[i] > 100) hit.push((i - 3) / 4);
  const a = new Float32Array(N * 2);
  for (let k = 0; k < N; k++) { const j = hit[(rand() * hit.length) | 0] || 0; a[k * 2] = (j % w) + rand() * 2; a[k * 2 + 1] = Math.floor(j / w) + rand() * 2; }
  return a;
}
// the Wadjet markings under the eye: the falcon's tear line dropping from the lower lid, and the spiral tail
export function wadjetMarks(N, g) {
  const { cx, cy, R } = g, S = R / 100;   // drawn in a 400x300 box, the eye's centre at (200, 60), R = 100
  const pts = sampleShape(N, 400, 300, (c) => {
    c.lineWidth = 7;
    c.beginPath(); c.moveTo(160, 172); c.bezierCurveTo(156, 210, 150, 248, 140, 286); c.stroke();                       // tear line
    c.beginPath(); c.moveTo(224, 174); c.bezierCurveTo(240, 236, 300, 262, 344, 244); c.bezierCurveTo(376, 230, 372, 192, 346, 188);
    c.bezierCurveTo(326, 186, 318, 206, 332, 214); c.stroke();                                                          // spiral tail
  });
  for (let i = 0; i < N; i++) { pts[i * 2] = cx + (pts[i * 2] - 200) * S; pts[i * 2 + 1] = cy + (pts[i * 2 + 1] - 60) * S; }
  return pts;
}
