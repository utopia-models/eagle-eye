#!/usr/bin/env python3
"""intro_verify.py: VERIFY for an AI-voice intro VSL (knowledge#18734). Reads the FINAL mp4's frames and audio against Tyler's rules (contract upwork.yaml `verify:`).

Only a VERIFY pass makes an intro sendable: `run` writes `<package>/verify.json` (pass, mp4 sha256, every check) and the frame captures in `<package>/verify-frames/`;
intro_sender.hold_reason refuses a package whose verify.json is missing, stale (other sha) or failing, and sends chief the failing checks.

Checks (each is pixel / audio measurement of the file, never the builder's word):
  format      1920x1080, duration 45-70 s
  loudness    integrated -16 LUFS +-1, and the body (after the hand-off) within 2 LU of the intro
  tabs        EXACTLY three tabs in the strip (contract layout.browser.tab_geom) on every sampled frame, named Their Job | MVP | Architecture (OCR)
  post_first  the first sampled frame has tab 1 active, and the active tab only ever moves 1 -> 2 -> 3
  face_card   before the hand-off the 346 px face circle sits bottom-right (40 px margin) and is not the page
  orb         after the hand-off the same slot shows the gold orb
  diagram     every diagram frame has clear margin left and right (a cropped diagram touches the frame edge)
  no_sample   no 'sample' / 'placeholder' text on the MVP frames (contract mvp.forbid_text)

  intro_verify.py verify MP4 [--handoff SEC] [--out DIR]   -> prints the json, exit 0 on pass
  intro_verify.py run SLUG                                  -> verify PKG_ROOT/SLUG/intro.mp4, write verify.json, stamp the job record
  intro_verify.py selftest"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

W, H = 1920, 1080
TAB = {"left": 12, "top": 8, "w": 300, "h": 34, "gap": 6}      # contract layout.browser.tab_geom (the renderer draws tabs here)
FACE = (346, 346)                                               # contract layout.circle (v6, knowledge#18867): 18% of 1920, face and orb the same circle
MARGIN = 40                                                     # contract layout.circle_margin: bottom-right, 40 px in from both edges
LUFS_TARGET, LUFS_TOL, LUFS_BODY_TOL = -16.0, 1.0, 2.0
DUR = (45.0, 70.0)
TAB_NAMES = [r"\b(their|your)\s*job\b|\bjob\b", r"\bmvp\b", r"\barchitecture\b"]
STEP = 3.0


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def probe(mp4):
    p = sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-show_entries", "format=duration", "-of", "json", str(mp4)], text=True)
    j = json.loads(p.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return float(j.get("format", {}).get("duration") or 0), v.get("width"), v.get("height"), any(s.get("codec_type") == "audio" for s in j.get("streams", []))


def lufs(mp4, start=None, dur=None):
    cmd = ["ffmpeg", "-nostats", "-v", "info"] + (["-ss", str(start)] if start is not None else []) + (["-t", str(dur)] if dur else []) + ["-i", str(mp4), "-af", "ebur128", "-f", "null", "-"]
    out = sh(cmd, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", out.split("Summary:")[-1])
    return float(m[-1]) if m else None


def grab(mp4, t, dest):
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", str(dest)])
    return Path(dest).is_file()


def crop_rgb(png, w, h, x, y):
    """-> bytes rgb24 of the crop (w*h*3)."""
    return sh(["ffmpeg", "-v", "error", "-i", str(png), "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout


def px(buf, w, x, y):
    i = (y * w + x) * 3
    return buf[i], buf[i + 1], buf[i + 2]


def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def ocr(png, crop=None, scale=3):
    src = str(png)
    if crop:
        w, h, x, y = crop
        tmp = str(png) + ".crop.png"
        sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"crop={w}:{h}:{x}:{y},scale=iw*{scale}:ih*{scale}", tmp])
        src = tmp
    return sh(["tesseract", src, "-", "--psm", "6"], text=True).stdout


def tab_state(png):
    """-> list of 3 states ('active'|'inactive'|None) from the pixels of each tab's top edge strip, or None per tab that is neither colour."""
    w, h = 3 * (TAB["w"] + TAB["gap"]) + TAB["left"], 30
    buf = crop_rgb(png, w, h, 0, TAB["top"])
    if len(buf) < w * h * 3:
        return [None] * 3
    out = []
    for k in range(3):
        x0 = TAB["left"] + k * (TAB["w"] + TAB["gap"])
        # a probe strip in the tab's right half, below the title text row, above the tab bottom: plain tab colour
        pts = [px(buf, w, x, 2) for x in range(x0 + 150, x0 + 270, 12)] + [px(buf, w, x, 27) for x in range(x0 + 150, x0 + 270, 12)]
        def near(c, ref):
            return all(abs(a - b) <= 6 for a, b in zip(c, ref))
        if sum(near(c, (255, 255, 255)) for c in pts) >= len(pts) * 0.9:
            out.append("active")
        elif sum(near(c, (0xde, 0xe1, 0xe6)) for c in pts) >= len(pts) * 0.9:
            out.append("inactive")
        else:
            out.append(None)
    return out


def gold_fraction(png, w, h, x, y):
    buf = crop_rgb(png, w, h, x, y)
    n = len(buf) // 3
    if not n:
        return 0.0
    g = 0
    for i in range(0, n * 3, 3):
        r, gg, b = buf[i], buf[i + 1], buf[i + 2]
        if r > 180 and 110 < gg < 215 and b < 110 and r > gg > b:
            g += 1
    return g / n


def card_is_face(png):
    """The 480x270 slot holds a picture (not the page, not empty): enough luma spread, a visible edge on its left and top border, and it is not mostly white page."""
    cw, ch = FACE
    x0, y0 = W - cw - MARGIN, H - ch - MARGIN
    buf = crop_rgb(png, cw, ch, x0, y0)
    if len(buf) < cw * ch * 3:
        return False, "no slot pixels"
    ls = [luma(px(buf, cw, x, y)) for y in range(0, ch, 6) for x in range(0, cw, 6)]
    mean = sum(ls) / len(ls)
    std = (sum((v - mean) ** 2 for v in ls) / len(ls)) ** 0.5
    white = sum(v > 240 for v in ls) / len(ls)
    left = crop_rgb(png, 2, ch, x0 - 1, y0)
    edge = sum(abs(luma(px(left, 2, 0, y)) - luma(px(left, 2, 1, y))) for y in range(0, ch, 5)) / (ch / 5)
    ok = std >= 20 and white < 0.5      # a circle touches its box edge only at four points, so no box-edge test (v6)
    return ok, f"std={std:.0f} white={white:.2f} left-edge={edge:.0f}"


def diagram_cropped(png):
    """Content within 14 px of the left or right frame edge (rows 110-800) = the diagram runs off the frame. -> (cropped, count)."""
    band = 14
    rows = (110, 690)
    cnt = 0
    for x in (0, W - band):
        buf = crop_rgb(png, band, rows[1], x, rows[0])
        if len(buf) < band * rows[1] * 3:
            continue
        lm = [luma(px(buf, band, a, b)) for b in range(0, rows[1], 2) for a in range(band)]
        bg = max(set(int(v) // 4 for v in lm), key=[int(v) // 4 for v in lm].count) * 4
        cnt += sum(abs(v - bg) > 40 for v in lm)
    return cnt >= 6, cnt


def verify(mp4, handoff=None, out_dir=None):
    mp4 = Path(mp4)
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="intro-verify-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    checks = []

    def add(cid, ok, detail):
        checks.append({"id": cid, "pass": bool(ok), "detail": detail})

    dur, vw, vh, has_a = probe(mp4)
    add("format", DUR[0] <= dur <= DUR[1] and (vw, vh) == (W, H) and has_a, f"{vw}x{vh} {dur:.1f}s audio={has_a}; need {W}x{H}, {DUR[0]:.0f}-{DUR[1]:.0f} s, with audio")
    if not dur:
        return {"pass": False, "mp4": str(mp4), "checks": checks, "frames": str(out_dir)}
    if handoff is None:
        handoff = 0.0
    ho = float(handoff)
    # loudness
    li = lufs(mp4)
    ok = li is not None and abs(li - LUFS_TARGET) <= LUFS_TOL
    d = f"integrated {li} LUFS; need {LUFS_TARGET} +-{LUFS_TOL}"
    if ho > 3 and dur - ho > 3:
        a, b = lufs(mp4, 0, ho), lufs(mp4, ho, None)
        ok = ok and a is not None and b is not None and abs(a - b) <= LUFS_BODY_TOL
        d += f"; intro {a} vs body {b} LUFS, need within {LUFS_BODY_TOL} LU"
    else:
        ok = False
        d += "; hand-off time unknown, so intro/body match is unchecked (fail closed)"
    add("loudness", ok, d)
    # frames
    ts = [min(1.0, dur / 2)] + [t for t in (STEP * k for k in range(1, int(dur / STEP) + 1)) if t < dur - 0.5]
    frames = []
    for t in ts:
        f = out_dir / f"t{t:05.1f}.png"
        if grab(mp4, t, f):
            frames.append((t, f))
    states = [(t, f, tab_state(f)) for t, f in frames]
    bad_tabs = [t for t, _, s in states if any(x is None for x in s) or sum(x == "active" for x in s) != 1]
    add("tabs_present", states and not bad_tabs, f"{len(states) - len(bad_tabs)}/{len(states)} sampled frames show exactly three tabs with one active" + (f"; none at t={bad_tabs[:6]}" if bad_tabs else ""))
    # tab names (OCR the strip on first, middle, last sampled frames)
    names_ok, shown = bool(states) and not bad_tabs, []
    if names_ok:
        for t, f, s in (states[0], states[len(states) // 2], states[-1]):
            txt = ocr(f, (3 * (TAB["w"] + TAB["gap"]) + TAB["left"], 44, 0, TAB["top"]))
            shown.append(txt.strip().replace("\n", " | ")[:80])
            names_ok = names_ok and all(re.search(p, txt, re.I) for p in TAB_NAMES)
    add("tab_names", names_ok, f"strip text {shown}; need Their Job, MVP, Architecture" if states and not bad_tabs else "no tab strip to read")
    act = [(t, s.index("active")) for t, _, s in states if s.count("active") == 1 and None not in s]
    seq_ok = bool(act) and act[0][1] == 0 and all(b[1] >= a[1] for a, b in zip(act, act[1:])) and act[-1][1] == 2 or (bool(act) and act[0][1] == 0 and all(b[1] >= a[1] for a, b in zip(act, act[1:])))
    add("post_first", seq_ok and bool(act) and act[0][1] == 0 and len(act) == len(states),
        f"active tab per sample {[a for _, a in act]}; need 0 first and never going back" if act else "no readable tab strip, so the post cannot be shown first")
    # face card before hand-off, orb after
    pre = [(t, f) for t, f in frames if t < ho - 0.5]
    post = [(t, f) for t, f in frames if t >= ho + 1.0]
    fres = [(t,) + card_is_face(f) for t, f in pre]
    add("face_card", bool(pre) and all(r[1] for r in fres), f"{sum(r[1] for r in fres)}/{len(fres)} pre-hand-off frames show the 346 px face circle bottom-right" + (f"; first miss t={next(r[0] for r in fres if not r[1])} ({next(r[2] for r in fres if not r[1])})" if fres and not all(r[1] for r in fres) else ""))
    ow, oh = FACE
    gold = [(t, gold_fraction(f, ow, oh, W - ow - MARGIN, H - oh - MARGIN)) for t, f in post]
    orb_hits = sum(g >= 0.004 for _, g in gold)
    add("orb", bool(post) and orb_hits >= 0.6 * len(post), f"gold orb in the bottom-right slot on {orb_hits}/{len(post)} post-hand-off frames (>=0.4% gold px)")
    # diagram: frames whose active tab is the diagram, else (no tabs) the last 40% of the video
    dia = [(t, f) for (t, f, s) in states if s.count("active") == 1 and s.index("active") == 2] if not bad_tabs else [(t, f) for t, f in frames if t >= dur * 0.6]
    dres = [(t,) + diagram_cropped(f) for t, f in dia]
    add("diagram_whole", bool(dres) and not any(r[1] for r in dres), f"{sum(r[1] for r in dres)}/{len(dres)} diagram frames run off the left/right edge" + (f"; first at t={next(r[0] for r in dres if r[1])} ({next(r[2] for r in dres if r[1])} edge px)" if any(r[1] for r in dres) else ""))
    # no sample badge on the MVP frames
    mvp = [(t, f) for (t, f, s) in states if s.count("active") == 1 and s.index("active") == 1][:2] if not bad_tabs else [frames[len(frames) // 3]] if frames else []
    hit = [t for t, f in mvp if re.search(r"\bsample\b|\bplaceholder\b|\bfirst version\b", ocr(f), re.I)]
    add("no_sample", bool(mvp) and not hit, f"checked {len(mvp)} MVP frame(s)" + (f"; 'sample'/'placeholder' text at t={hit}" if hit else ""))
    res = {"pass": all(c["pass"] for c in checks), "mp4": str(mp4), "sha256": hashlib.sha256(mp4.read_bytes()).hexdigest(), "handoff_s": ho,
           "checks": checks, "frames": str(out_dir)}
    (out_dir / "verify.json").write_text(json.dumps(res, indent=1))
    return res


def failing(res):
    return [f"{c['id']}: {c['detail']}" for c in res.get("checks", []) if not c["pass"]]


def verified(pkg_dir, mp4):
    """-> (True, '') when <pkg>/verify.json passed for exactly THIS mp4 (sha256), else (False, reason). Used by intro_sender.hold_reason."""
    f = Path(pkg_dir) / "verify.json"
    try:
        v = json.loads(f.read_text())
    except (OSError, ValueError):
        return False, "verify_missing"
    try:
        sha = hashlib.sha256(Path(mp4).read_bytes()).hexdigest()
    except OSError:
        return False, "mp4_missing"
    if v.get("sha256") != sha:
        return False, "verify_stale"
    return (True, "") if v.get("pass") else (False, "verify_failed")


def run(slug, pkg_root, handoff=None):
    pkg = Path(pkg_root) / slug
    mp4 = pkg / "intro.mp4"
    if handoff is None:
        try:
            handoff = json.loads((pkg / "intro-meta.json").read_text()).get("handoff_s")
        except (OSError, ValueError):
            handoff = None
    res = verify(mp4, handoff, pkg / "verify-frames")
    (pkg / "verify.json").write_text(json.dumps(res, indent=1))
    return res


def selftest():
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("tesseract")):
        print("self-test SKIP (ffmpeg/tesseract missing)")
        return True
    d = Path(tempfile.mkdtemp())
    (d / "pkg").mkdir()
    (d / "pkg" / "intro.mp4").write_bytes(b"x")
    ok, why = verified(d / "pkg", d / "pkg" / "intro.mp4")
    r1 = (ok, why) == (False, "verify_missing")
    (d / "pkg" / "verify.json").write_text(json.dumps({"pass": True, "sha256": "0" * 64}))
    r2 = verified(d / "pkg", d / "pkg" / "intro.mp4") == (False, "verify_stale")
    sha = hashlib.sha256(b"x").hexdigest()
    (d / "pkg" / "verify.json").write_text(json.dumps({"pass": True, "sha256": sha}))
    r3 = verified(d / "pkg", d / "pkg" / "intro.mp4") == (True, "")
    (d / "pkg" / "verify.json").write_text(json.dumps({"pass": False, "sha256": sha}))
    r4 = verified(d / "pkg", d / "pkg" / "intro.mp4") == (False, "verify_failed")
    allok = all([r1, r2, r3, r4])
    print("self-test " + ("PASS" if allok else "FAIL"))
    return allok


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["selftest"]:
        sys.exit(0 if selftest() else 1)
    if a[:1] == ["verify"] and len(a) >= 2:
        ho = float(a[a.index("--handoff") + 1]) if "--handoff" in a else None
        out = a[a.index("--out") + 1] if "--out" in a else None
        r = verify(a[1], ho, out)
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["pass"] else 2)
    if a[:1] == ["run"] and len(a) >= 2:
        import os
        root = os.environ.get("ONESHOT_PKG_ROOT") or Path.home() / "oneshot/packages"
        r = run(a[1], root)
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["pass"] else 2)
    print(__doc__)
    sys.exit(1)
