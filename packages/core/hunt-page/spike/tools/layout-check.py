#!/usr/bin/env python3
"""Eagle Eye layout check: fails (exit 1) when any two visible text/chip/badge/button boxes intersect, or a box
spills out of its row, on the feed and the detail page at 1440, 1280 and 390 px wide, and when a detail page opened from a
SCROLLED list lets a list row show in the header band above it (Tyler 11-23 photo). Run after every UI change.

  ~/.local/share/fleet-playwright/bin/python tools/layout-check.py [base_url] [--shots DIR]
"""
import sys, json, os
from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "https://ra.tail4016d7.ts.net:8450/")
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
WIDTHS = (1440, 1280, 390)

# leaf boxes: elements that paint text or are chips; a pair overlaps when neither contains the other
JS = r"""
(scopeSel) => {
  const CHIP = ".tb,.sub,.num,.pill,.vsl,.rep,.ag,.age,.logo,.tgt,.sig,.meta,button,a,img,.chip";
  const vis = e => { const s = getComputedStyle(e); if (s.visibility === "hidden" || s.display === "none" || +s.opacity === 0) return false;
    const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
  const hasText = e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  // the visible part of a box: clipped by every overflow-hidden ancestor (truncate / ellipsis is fine)
  const OV = new Map(), ov = p => { if (!OV.has(p)) { const s = getComputedStyle(p); OV.set(p, s.overflowX !== "visible" || s.overflowY !== "visible" ? p.getBoundingClientRect() : null); } return OV.get(p); };
  const clip = e => { let r = e.getBoundingClientRect(), L = r.left, T = r.top, R = r.right, B = r.bottom;
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const q = ov(p);
      if (q) { L = Math.max(L, q.left); T = Math.max(T, q.top); R = Math.min(R, q.right); B = Math.min(B, q.bottom); } }
    return {L, T, R, B}; };
  const name = e => { const t = (e.innerText || e.alt || "").trim().replace(/\s+/g, " ").slice(0, 50); return `${e.tagName.toLowerCase()}.${[...e.classList].slice(0, 2).join(".")} "${t}"`; };
  const out = [];
  for (const scope of document.querySelectorAll(scopeSel)) {
    if (!vis(scope)) continue;
    const sr = scope.getBoundingClientRect();
    let els = [...scope.querySelectorAll("*")].filter(e => vis(e) && (e.matches(CHIP) || hasText(e)) && !e.closest("svg"));
    // keep the outermost chip: a chip's own children are part of it
    els = els.filter(e => !els.some(o => o !== e && o.contains(e) && o.matches(CHIP)));
    const page = scope.id === "page", lim = page ? {left: 0, right: innerWidth, top: -1e9, bottom: 1e9} : sr;   // detail page: nothing past the viewport edge
    const box = els.map(clip), ord = els.map((e, i) => i).filter(i => box[i].R - box[i].L >= 1 && box[i].B - box[i].T >= 1).sort((i, j) => box[i].T - box[j].T);
    ord.forEach(i => { const b = box[i];
      if (b.L < lim.left - 1 || b.R > lim.right + 1 || b.T < lim.top - 1 || b.B > lim.bottom + 1) out.push({kind: "spill", scope: name(scope).slice(0, 60), a: name(els[i])}); });
    for (let x = 0; x < ord.length; x++) for (let y = x + 1; y < ord.length; y++) { const i = ord[x], j = ord[y];
      if (box[j].T >= box[i].B) break;
      if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
      const a = box[i], b = box[j], w = Math.min(a.R, b.R) - Math.max(a.L, b.L), h = Math.min(a.B, b.B) - Math.max(a.T, b.T);
      if (w > 1 && h > 1) out.push({kind: "overlap", scope: name(scope).slice(0, 60), a: name(els[i]), b: name(els[j]), px: [Math.round(w), Math.round(h)]});
    }
  }
  return out;
}
"""

# what sits in the band between the viewport top and the fixed detail page: every probe point must be the header, none a list row
SCROLLED_JS = r"""
() => { const pg = document.querySelector('#page'), top = Math.round(pg.getBoundingClientRect().top), rows = [];
  let header = top > 0;
  for (let y = 2; y < top; y += 6) for (const x of [12, innerWidth / 2, innerWidth - 24]) {
    const e = document.elementFromPoint(x, y); if (!e) continue;
    if (e.closest('[data-row], #list')) rows.push(`${Math.round(x)},${y}`);
    if (!e.closest('header')) header = false;
  }
  return {hidden: pg.hidden, top, rows, header};
}
"""

def main():
    bad = 0
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", args=["--disable-dev-shm-usage"])
        for w in WIDTHS:
            print(f"-- {w}px", flush=True)
            ctx = br.new_context(viewport={"width": w, "height": 900}, ignore_https_errors=True)
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
            pg.goto(BASE + "?nointro", wait_until="networkidle"); pg.wait_for_timeout(1200)
            found = pg.evaluate(JS, "[data-row]")
            if SHOTS: os.makedirs(SHOTS, exist_ok=True); pg.screenshot(path=f"{SHOTS}/feed-{w}.png")
            rid = pg.evaluate("document.querySelector('[data-row]')?.dataset.row")
            det = []
            ids = pg.evaluate("[...document.querySelectorAll('[data-row]')].map(e=>e.dataset.row)")[:4]
            # ROOSTS tab: same checks on its rows (or its empty state)
            pg.goto(BASE + "?nointro#roosts", wait_until="networkidle"); pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1500)
            found += [dict(d, page="roosts") for d in pg.evaluate(JS, "[data-row]")]
            if SHOTS: pg.screenshot(path=f"{SHOTS}/roosts-{w}.png")
            pg.close()
            for r in ids:   # each detail page in its own tab: Ra runs near its RAM limit, one renderer at a time
                for attempt in (1, 2):
                    dp = ctx.new_page()
                    dp.on("pageerror", lambda e: errs.append(str(e)))
                    dp.on("console", lambda m: m.type == "error" and errs.append(m.text))
                    try:
                        dp.goto(f"{BASE}?nointro#hunts/{r}", wait_until="networkidle"); dp.wait_for_timeout(1500)
                        det += [dict(d, page=r) for d in dp.evaluate(JS, "#page")]
                        if SHOTS and r == rid: dp.screenshot(path=f"{SHOTS}/detail-{w}.png")
                        dp.close(); break
                    except Exception as e:
                        print(f"   renderer crashed on {r} (try {attempt}): {str(e).splitlines()[0]}")
                        if attempt == 2: errs.append(f"detail {r}: renderer crashed twice")
            # detail opened from a SCROLLED list (Tyler 11-23 photo: a list row showed above the breadcrumb): click a row mid-list,
            # then the band above #page must be the header (never a row), the list must not move under a wheel, Esc returns to it
            sp = ctx.new_page()
            sp.on("pageerror", lambda e: errs.append(str(e)))
            sp.on("console", lambda m: m.type == "error" and errs.append(m.text))
            sp.goto(BASE + "?nointro"); sp.wait_for_selector("[data-row]", timeout=30000); sp.wait_for_timeout(1000)
            sp.evaluate("scrollTo(0, Math.min(2400, document.documentElement.scrollHeight - innerHeight))"); sp.wait_for_timeout(500)
            y0 = sp.evaluate("scrollY")
            srid = sp.evaluate("([...document.querySelectorAll('[data-row]')].find(e => { const r = e.getBoundingClientRect(); return r.top > 200 && r.bottom < innerHeight - 40; }) || {dataset: {}}).dataset.row")
            if not y0 or not srid:
                errs.append(f"scrolled-detail: could not scroll the list (scrollY {y0}) or find a row in view")
            else:
                sp.click(f'[data-row="{srid}"] .tgt'); sp.wait_for_timeout(1300)
                st = sp.evaluate(SCROLLED_JS)
                if SHOTS: sp.screenshot(path=f"{SHOTS}/detail-from-scrolled-{w}.png")
                if st["hidden"]: errs.append(f"scrolled-detail {srid}: the page did not open")
                if st["rows"]: errs.append(f"scrolled-detail {srid}: a list row shows above the detail page at {st['rows'][:4]} (header band 0-{st['top']}px)")
                if not st["header"]: errs.append(f"scrolled-detail {srid}: the header is not visible above the detail page")
                det += [dict(d, page="scrolled:" + srid) for d in sp.evaluate(JS, "#page")]
                sp.mouse.move(w // 2, 500); sp.mouse.wheel(0, 800); sp.wait_for_timeout(400)
                if sp.evaluate("scrollY") != y0: errs.append(f"scrolled-detail {srid}: the list behind the page scrolled ({y0} -> {sp.evaluate('scrollY')})")
                sp.keyboard.press("Escape"); sp.wait_for_timeout(700)
                if sp.evaluate("scrollY") != y0: errs.append(f"scrolled-detail {srid}: closing lost the list position ({y0} -> {sp.evaluate('scrollY')})")
            sp.close()
            for d in found + det:
                bad += 1
                print(f"FAIL {w}px {d.get('page', 'feed')} {d['kind']}: {d['a']}" + (f"  x  {d['b']}  {d['px']}" if d['kind'] == 'overlap' else f"  out of  {d['scope']}"))
            for e in errs: bad += 1; print(f"FAIL {w}px console: {e}")
            ctx.close()
    print(("FAIL %d problems" % bad) if bad else "PASS layout: no overlaps, no spills, no console errors at " + ", ".join(map(str, WIDTHS)))
    sys.exit(1 if bad else 0)

main()
