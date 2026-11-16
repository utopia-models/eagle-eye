// Eagle Eye site: Lenis smooth scroll on GSAP's ticker, SplitText hero, ScrollTrigger reveals,
// NumberFlow stats, the sand eye (eye.js), the copy button and the live GitHub star count.
const { gsap, ScrollTrigger, SplitText, Lenis } = window;
const root = document.documentElement;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── copy the install line ───────────────────────────
for (const b of document.querySelectorAll('[data-copy]')) {
  b.addEventListener('click', async () => {
    const text = b.dataset.copy;
    try { await navigator.clipboard.writeText(text); }
    catch {
      const t = document.createElement('textarea');
      t.value = text; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.append(t); t.select(); document.execCommand('copy'); t.remove();
    }
    const label = b.querySelector('.copy-label');
    b.classList.add('done'); if (label) label.textContent = 'Copied';
    b.setAttribute('aria-label', 'Copied');
    setTimeout(() => { b.classList.remove('done'); if (label) label.textContent = 'Copy'; b.setAttribute('aria-label', 'Copy install command'); }, 1800);
  });
}

// ── GitHub stars (shown once there are enough to mean something) ──
fetch('https://api.github.com/repos/utopia-models/eagle-eye', { headers: { Accept: 'application/vnd.github+json' } })
  .then((r) => (r.ok ? r.json() : null))
  .then((d) => {
    const n = d && d.stargazers_count;
    if (typeof n !== 'number' || n < 10) return;
    const c = document.querySelector('.star-count');
    c.textContent = n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(n);
    c.hidden = false;
    const stat = document.querySelector('[data-stars]');
    if (stat && n >= 25) {
      stat.dataset.to = String(n);
      stat.closest('.stat').querySelector('dt').textContent = 'GitHub stars';
    }
  })
  .catch(() => {});

// ── the demo runs only while it is near the screen (its own eye is a live canvas) ──
const demo = document.querySelector('iframe[data-src]');
if (demo) {
  new IntersectionObserver(([e]) => {
    if (e.isIntersecting) { if (!demo.src || demo.src === 'about:blank') demo.src = demo.dataset.src; }
    else if (demo.src && demo.src !== 'about:blank') demo.src = 'about:blank';
  }, { rootMargin: '300px 0px' }).observe(demo);
}

// ── nav state ───────────────────────────────────────
const nav = document.querySelector('.nav');
const onScroll = () => nav.classList.toggle('scrolled', scrollY > 40);
addEventListener('scroll', onScroll, { passive: true }); onScroll();

// ── motion ──────────────────────────────────────────
if (!gsap || !ScrollTrigger) {
  root.classList.remove('js'); root.classList.add('no-sand');
} else {
  gsap.registerPlugin(ScrollTrigger, SplitText);

  if (!reduced && Lenis) {
    const lenis = new Lenis({ autoRaf: false, lerp: 0.1, anchors: { offset: -64 } });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
    window.__lenis = lenis;
  }

  // the eye
  const canvas = document.querySelector('.sand');
  import('./eye.js')
    .then(({ mountEye }) => {
      mountEye({ canvas, slot: document.querySelector('.eye-slot'), hero: document.querySelector('.hero'), gsap, ScrollTrigger, reduced });
      root.classList.add('js-sand');
    })
    .catch(() => root.classList.add('no-sand'));

  const mm = gsap.matchMedia();
  mm.add('(prefers-reduced-motion: no-preference)', () => {
    // hero copy: the line rises out of the sand once the eye has mostly gathered
    const ready = document.fonts ? Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 1200))]) : Promise.resolve();
    ready.then(() => {
      const split = SplitText.create('#hero-title', { type: 'words,chars', mask: 'words' });
      const tl = gsap.timeline({ delay: 0.5 });
      tl.from(split.chars, { yPercent: 115, duration: 1.1, ease: 'power4.out', stagger: 0.022 })
        .from('.hero .lead, .hero .install, .hero-ctas, .hero .fine, .scroll-cue',
          { autoAlpha: 0, y: 18, filter: 'blur(8px)', duration: 0.9, ease: 'power3.out', stagger: 0.09, clearProps: 'filter' }, '-=0.7');
    });

    // section reveals (IntersectionObserver triggers, GSAP animates)
    const io = new IntersectionObserver((entries) => {
      const els = entries.filter((e) => e.isIntersecting).map((e) => e.target);
      if (!els.length) return;
      els.forEach((el) => io.unobserve(el));
      gsap.fromTo(els, { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0, duration: 0.75, ease: 'power3.out', stagger: 0.08, overwrite: true });
    }, { rootMargin: '0px 0px -6% 0px' });
    document.querySelectorAll('.reveal').forEach((el) => io.observe(el));

    // the frame draws itself in
    gsap.from('.frame .tick', {
      scale: 0, transformOrigin: 'center', duration: 0.8, ease: 'back.out(2)', stagger: 0.08,
      scrollTrigger: { trigger: '.frame', start: 'top 85%', once: true },
    });
    gsap.from('.paths .divider', {
      scaleY: 0, transformOrigin: 'top center', duration: 1.4, ease: 'power3.inOut',
      scrollTrigger: { trigger: '.paths-grid', start: 'top 80%', once: true },
    });
  });
  mm.add('(prefers-reduced-motion: reduce)', () => { gsap.set('.reveal', { autoAlpha: 1 }); });
  // never leave content hidden if a trigger misses (e.g. a deep link)
  setTimeout(() => {
    for (const el of document.querySelectorAll('.reveal')) {
      if (el.getBoundingClientRect().top < innerHeight && getComputedStyle(el).opacity === '0') gsap.to(el, { autoAlpha: 1, y: 0, duration: 0.6 });
    }
  }, 2500);
}

// ── stats count up when they arrive ─────────────────
import('number-flow')
  .then(() => {
    const els = [...document.querySelectorAll('number-flow')];
    const start = { 0: 9 };
    for (const el of els) { el.update(start[el.dataset.to] ?? 0); }
    const run = () => els.forEach((el, i) => setTimeout(() => el.update(Number(el.dataset.to)), i * 140));
    if (ScrollTrigger && !reduced) ScrollTrigger.create({ trigger: '.stats', start: 'top 85%', once: true, onEnter: run });
    else run();
  })
  .catch(() => {});
