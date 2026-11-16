// Three directions for the eagleeye.sh hero and its atmosphere (html[data-v]). Every one uses the real Eagle Eye
// (eagle-eye-hero.js) and the Utopia sites' sand (sand.js: OGL grains, C4's shader, GSAP eases).
//   a  BORN OF SAND   sand lifts off the ground and gathers into the eye's outline; the eye opens inside it and
//                     the sand lets go into drifting dust. Wadjet flourishes draw themselves in gold as sections arrive.
//   b  THE FALCON     the eye follows your scroll down the page; at every section a falcon wing of sand sweeps
//                     across the screen and falls back to dust.
//   c  THE SUN DISK   the eye opens inside a molten sun disk of sand above the Akhet horizon (C4's motif); the sun
//                     breathes, and sets as you scroll away.
import { mountEagleEye, followPointer } from './eagle-eye-hero.js';
import { mountSand, field, ground, eyeOutline, wing, sunAndHorizon, wadjetMarks } from './sand.js';

export function mountDirection(v, { gsap, ScrollTrigger, reduced }) {
  const sandCv = document.querySelector('canvas.sand');
  const eyeCv = document.querySelector('canvas.ee-canvas');
  const slot = document.querySelector('.eye-slot');
  const hero = document.querySelector('.hero');
  const eye = mountEagleEye({ canvas: eyeCv, slot, gsap, reduced, start: v === 'a' ? 1.1 : v === 'c' ? 0.5 : 0.15 });
  const sand = mountSand({ canvas: sandCv, gsap, reduced });
  const N = sand.N, U = sand.u; window.__ee = { sand, eye };
  // the eye's geometry in page coordinates (the hero sits at the top of the page)
  const geo = () => { const g = eye.geometry(), r = eyeCv.getBoundingClientRect(); return { cx: g.cx + r.left, cy: g.cy + r.top + scrollY, R: g.R }; };
  const horizon = () => { const g = geo(); return g.cy + g.R * 1.3; };   // just under the lower lid
  let settle = () => {};   // re-lays the resting formation after a width change

  if (reduced) {
    const rest = v === 'c' ? sunAndHorizon(N, geo(), horizon()) : field(N);
    sand.move(rest, rest, { attachFrom: v === 'c' ? 1 : 0, attachTo: v === 'c' ? 1 : 0 }); U.uK.value = 1; sand.draw();
    return;
  }

  if (v === 'a') {
    followPointer(eye, gsap);
    U.uDrift.value = 4;
    // at rest: dust over the hero and the Wadjet markings (tear line and spiral) in sand under the eye
    const rest = () => {
      const g = geo(), hb = hero.getBoundingClientRect().bottom + scrollY, f = field(N, innerWidth, hb), m = wadjetMarks(Math.floor(N * .24), g);
      f.set(m, (N - Math.floor(N * .24)) * 2); return f;
    };
    sand.move(ground(N), eyeOutline(N, geo()), { attachTo: 1 });
    gsap.timeline({ delay: 0.15 })
      .to(U.uK, { value: 1, duration: 1.7, ease: 'power2.inOut' })
      .add(() => { sand.move(eyeOutline(N, geo()), rest(), { attachFrom: 1, attachTo: 1 }); })
      .to(U.uDrift, { value: 6, duration: 2.6, ease: 'sine.inOut' }, '<')
      .to(U.uK, { value: 1, duration: 2.4, ease: 'sine.inOut' }, '<')
      .to(U.uLum, { value: 0.85, duration: 2.4, ease: 'sine.inOut' }, '<');
    settle = () => { const f = rest(); sand.move(f, f, { attachFrom: 1, attachTo: 1 }); U.uK.value = 1; };
    drawFlourishes(gsap);
  }

  if (v === 'b') {
    const look = followPointer(eye, gsap); look.set(false);
    sand.move(ground(N), field(N));
    gsap.to(U.uK, { value: 1, duration: 2.6, ease: 'power2.inOut', delay: 0.1 });
    // the gaze rides the scroll: the eye looks down the page as you go, and sideways with the direction you move
    ScrollTrigger.create({
      start: 0, end: () => innerHeight * 0.9,
      onUpdate: (self) => { look.ly(-0.25 + 1.25 * self.progress); look.lx(gsap.utils.clamp(-0.6, 0.6, self.getVelocity() / 2500)); },
    });
    let flying = false, side = 1, lastWing = null;
    // the wing spreads in the upper band of the screen, above the section that is arriving
    const wingAt = (d) => { const w = wing(N, innerWidth, innerHeight, d), dy = -innerHeight * .2; for (let i = 1; i < w.length; i += 2) w[i] += dy; return w; };
    const sweep = () => {
      if (flying) return; flying = true; side = -side;
      const rest = field(N);
      lastWing = wingAt(side); sand.move(field(N), lastWing);
      gsap.timeline({ onComplete: () => { flying = false; } })
        .to(U.uLum, { value: 0.8, duration: 0.3 }, 0)
        .to(U.uK, { value: 1, duration: 0.9, ease: 'power2.inOut' }, 0)
        .fromTo(U.uSweep, { value: 0 }, { value: 90 * side, duration: 0.9, ease: 'power2.inOut' }, 0)
        .add(() => { sand.move(lastWing, rest); U.uSweep.value = 0; }, '+=0.28')   // the wing holds, then falls to dust
        .to(U.uK, { value: 1, duration: 1.5, ease: 'sine.inOut' })
        .to(U.uLum, { value: 1, duration: 1.5 }, '<');
    };
    document.querySelectorAll('main > section:not(.hero)').forEach((s) => ScrollTrigger.create({ trigger: s, start: 'top 70%', onEnter: sweep, onEnterBack: sweep }));
    // ?pose=wing holds the formed wing (a still for design review)
    if (/[?&]pose=wing/.test(location.search)) gsap.delayedCall(3, () => { flying = true; sand.move(field(N), wingAt(1)); U.uK.value = 1; });
    settle = () => { const f = field(N); sand.move(f, f); U.uK.value = 1; };
  }

  if (v === 'c') {
    followPointer(eye, gsap);
    U.uDrift.value = 3; U.uLum.value = 1.2; U.uField.value = 0.2;
    // sunrise: every grain starts on the horizon (visible from the first frame), then the sun disk rises out of it
    const g0 = geo(), hz = horizon(); U.uHz.value = hz;
    const sun = sunAndHorizon(N, g0, hz);
    sand.move(sun.map((val, i) => (i % 2 ? hz + (Math.random() - .5) * 3 : val)), sun, { attachFrom: 1, attachTo: 1 });
    gsap.to(U.uK, { value: 1, duration: 1.8, ease: 'power2.out', delay: 0.05 });
    gsap.to(eye.st, { glow: 0.5, duration: 3.2, ease: 'sine.inOut', yoyo: true, repeat: -1, delay: 2.2 });
    gsap.fromTo('.sun-glow', { autoAlpha: 0, scale: 0.6 }, { autoAlpha: 1, scale: 1, duration: 2.6, ease: 'power2.out', delay: 0.3 });
    // the sun sets as you scroll away: the disk sinks into the horizon and its light goes out
    gsap.timeline({ scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom 30%', scrub: 0.6 } })
      .to(U.uSink, { value: 1, ease: 'none' }, 0)
      .to('.sun-glow', { yPercent: 40, autoAlpha: 0, ease: 'none' }, 0);
    settle = () => { const g = geo(), h = horizon(); U.uHz.value = h; const f = sunAndHorizon(N, g, h); sand.move(f, f, { attachFrom: 1, attachTo: 1 }); U.uK.value = 1; };
    drawFlourishes(gsap);
  }

  // adaptive quality: watch the frame gaps; a slow device steps down twice (half density at 1x, then still)
  let tier = 0, last = 0, gaps = [], warm = performance.now();
  const watch = () => {
    const now = performance.now();
    if (last && now - warm > 600 && tier < 2) {
      gaps.push(now - last);
      if (gaps.length >= 30 || gaps.reduce((a, b) => a + b, 0) > 800) {
        gaps.sort((a, b) => a - b);
        if (gaps[gaps.length >> 1] > 34 && !/[?&]q=hi/.test(location.search)) { tier++; eye.degrade(tier); sand.degrade(tier); if (tier === 2) gsap.ticker.remove(watch); }
        gaps = [];
      }
    }
    last = now;
  };
  gsap.ticker.add(watch);

  let lastW = innerWidth;
  addEventListener('resize', () => { if (innerWidth === lastW) return; lastW = innerWidth; eye.resize(); sand.size(); settle(); });
}

// Wadjet flourishes (the eye's tear line and spiral, drawn as a gold rule) under each section label
function drawFlourishes(gsap) {
  const els = document.querySelectorAll('.flourish');
  els.forEach((svg) => {
    const paths = svg.querySelectorAll('path');
    gsap.set(paths, { drawSVG: '0%' });
    gsap.to(paths, { drawSVG: '100%', duration: 1.6, ease: 'power2.inOut', stagger: 0.08, scrollTrigger: { trigger: svg, start: 'top 88%', once: true } });
  });
}
