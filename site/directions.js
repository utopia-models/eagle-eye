// The eagleeye.sh hero, direction A "Born of Sand" (Tyler's pick, 2026-11-16): the real Eagle Eye (eagle-eye-hero.js)
// and the Utopia sites' sand (sand.js: OGL grains, C4's shader, GSAP eases). Lit sand lifts off the floor and gathers
// into the eye's outline; the eye opens inside it; the sand settles into the Wadjet tear line and spiral under the eye.
// Wadjet rules draw themselves in gold as each section arrives.
import { mountEagleEye, followPointer } from './eagle-eye-hero.js';
import { mountSand, field, ground, eyeOutline, wadjetMarks } from './sand.js';

export function mountDirection(v, { gsap, ScrollTrigger, reduced }) {
  const sandCv = document.querySelector('canvas.sand');
  const eyeCv = document.querySelector('canvas.ee-canvas');
  const slot = document.querySelector('.eye-slot');
  const hero = document.querySelector('.hero');
  const eye = mountEagleEye({ canvas: eyeCv, slot, gsap, reduced, start: 0.5 });
  const sand = mountSand({ canvas: sandCv, gsap, reduced });
  const N = sand.N, U = sand.u; window.__ee = { sand, eye };
  // the eye's geometry in page coordinates (the hero sits at the top of the page)
  const geo = () => { const g = eye.geometry(), r = eyeCv.getBoundingClientRect(); return { cx: g.cx + r.left, cy: g.cy + r.top + scrollY, R: g.R }; };
    let settle = () => {};   // re-lays the resting formation after a width change
  let intro = null;         // the sand's opening timeline, if the direction has one

  if (reduced) {
    const g = geo(), hb = hero.getBoundingClientRect().bottom + scrollY, rest = field(N, innerWidth, hb), nm = Math.floor(N * .24);
    rest.set(wadjetMarks(nm, g), (N - nm) * 2); sand.move(rest, rest, { attachFrom: 1, attachTo: 1 }); U.uK.value = 1; sand.draw();
    return;
  }

  if (v === 'a') {
    followPointer(eye, gsap);
    U.uDrift.value = 4;
    // at rest: dust over the hero and the Wadjet markings (tear line and spiral) in sand under the eye
    const rest = () => {
      const share = innerWidth < 600 ? .34 : .24, nm = Math.floor(N * share);
      const g = geo(), hb = hero.getBoundingClientRect().bottom + scrollY, f = field(N, innerWidth, hb), m = wadjetMarks(nm, g);
      f.set(m, (N - nm) * 2); return f;
    };
    sand.move(ground(N), eyeOutline(N, geo()), { attachTo: 1 });
    intro = gsap.timeline({ delay: 0.15 })
      .to(U.uK, { value: 1, duration: innerWidth < 600 ? 1.2 : 1.7, ease: 'power2.inOut' })
      .add(() => { sand.move(eyeOutline(N, geo()), rest(), { attachFrom: 1, attachTo: 1 }); })
      .to(U.uDrift, { value: 6, duration: 2.6, ease: 'sine.inOut' }, '<')
      .to(U.uK, { value: 1, duration: 2.4, ease: 'sine.inOut' }, '<')
      .to(U.uLum, { value: 0.85, duration: 2.4, ease: 'sine.inOut' }, '<');
    settle = () => { const f = rest(); sand.move(f, f, { attachFrom: 1, attachTo: 1 }); U.uK.value = 1; };
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
        if (gaps[gaps.length >> 1] > 34 && !/[?&]q=hi/.test(location.search)) { tier++; sand.degrade(tier); if (tier === 1) eye.degrade(1); if (tier === 2) { gsap.ticker.remove(watch); stillSand(); lastChance(); } }
        gaps = [];
      }
    }
    last = now;
  };
  gsap.ticker.add(watch);
  // still sand shows the finished formation (A's Wadjet marks, C's sun), never a frame from the middle of the intro
  function stillSand() { if (intro) intro.kill(); gsap.killTweensOf(U.uK); U.uLum.value = Math.max(U.uLum.value, .85); settle(); U.uScroll.value = scrollY; sand.draw(); }
  // with the sand still, the eye keeps running unless even that cannot hold ~20 fps; then it becomes a still too
  function lastChance() {
    let n = 0, t0 = performance.now();
    const probe = () => { n++; const dt = performance.now() - t0; if (dt > 1500) { gsap.ticker.remove(probe); if (n / (dt / 1000) < 20) eye.degrade(2); } };
    gsap.ticker.add(probe);
  }

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
