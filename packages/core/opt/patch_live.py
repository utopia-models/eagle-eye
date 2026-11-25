#!/usr/bin/env python3
"""knowledge#17946 + #18326: wire the One-shot system chip to the architecture overlay in the LIVE Eagle Eye origin (Ra :8797,
architect's eagle-eye-spike/public, not in git). Idempotent; backs up each file first. Run as root on Ra:
    sudo python3 patch_live.py <public-dir> <arch.js> <pipelines.json> <offer.json>"""
import shutil, sys, time, os
pub, arch, feed, offer = sys.argv[1:5]
stamp = time.strftime("%Y%m%d%H%M%S")
def edit(rel, pairs):
    p = os.path.join(pub, rel); s = open(p).read(); o = s
    for a, b in pairs:
        if b in s: continue
        assert s.count(a) == 1, f"{rel}: anchor not unique/found: {a[:60]!r}"
        s = s.replace(a, b)
    if s != o:
        shutil.copy(p, p + f".bak-17946-{stamp}"); open(p, "w").write(s); print("patched", rel)
    else: print("unchanged", rel)
shutil.copy(arch, os.path.join(pub, "opt/arch.js")); shutil.copy(feed, os.path.join(pub, "pipelines.json")); shutil.copy(offer, os.path.join(pub, "offer.json")); print("installed arch.js + pipelines.json + offer.json")
SYS = "(s=>String(s||'').replace(/\\s+(entire|intro)\\s+vsl\\b.*$/i,'').replace(/\\s+one-shot$/i,'').trim()||String(s||''))"
edit("index.html", [
  ('const oss = r => !r.oss ? "" : r.oss.key\n  ? `<${r.oss.page ? `a href="${esc(r.oss.page)}" target="_blank" rel="noopener" onclick="event.stopPropagation()"` : "span"} class="oss" title=',
   'const ossName = ' + SYS + ';\nconst oss = r => !r.oss ? "" : r.oss.key\n  ? `<a href="#" data-oss-system="${esc(r.oss.system)}" data-oss-row="${esc(JSON.stringify({...r.oss, target: r.target}))}" class="oss" title="Open the one-shot pipeline. '),
  ('<span class="truncate">${esc(r.oss.system)}</span></${r.oss.page ? "a" : "span"}>`', '<span class="truncate">${esc(ossName(r.oss.system))}</span></a>`'),
  ('  : `<span class="oss none" title="No one-shot has been chosen or built for this hunt yet">${esc(r.oss.hunt)} · No one-shot yet</span>`;',
   '  : `<a href="#" data-oss-system="Founder 14-Day Build" data-oss-row="${esc(JSON.stringify({...r.oss, target: r.target, system: "Founder 14-Day Build"}))}" class="oss" title="Open the one-shot pipeline"><span class="k">One-shot system:</span><span class="truncate">Founder 14-Day Build</span></a>`;'),
  ('<script src="/opt/roosts.js"></script>', '<script src="/opt/roosts.js"></script>\n<script src="/opt/arch.js"></script>'),
])
edit("opt/detail.js", [
  ('(r.oss.page ? `<a class="ed-sub gold wrap" href="${esc(r.oss.page)}" target="_blank" rel="noopener" title="How this one-shot works">${icon("video")}<span class="ed-k">One-shot system:</span>${esc(r.oss.system)}</a>`\n         : sub(`${icon(r.oss.take === "entire" ? "film" : "video")}<span class="ed-k">One-shot system:</span>${esc(r.oss.system)}`, "gold wrap"))',
   '`<a class="ed-sub gold wrap" href="#" data-oss-system="${esc(r.oss.system)}" data-oss-row="${esc(JSON.stringify({...r.oss, target: r.target}))}" title="Open the one-shot pipeline">${icon("video")}<span class="ed-k">One-shot system:</span>${esc((' + SYS + ')(r.oss.system))}</a>`'),
])
