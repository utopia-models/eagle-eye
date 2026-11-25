#!/usr/bin/env python3
"""raw_orb.py: the VSL's voice-agent card rendered by the RAW phone's own orb (Tyler 2026-11-21 on v3-B: "I would really like
this to look more like the RAW phone gold orb (magic look), literally the same").

  .venv/bin/python raw_orb.py <audio-or-video> <out.mp4> [--from S] [--w 270] [--h 480]

raw-orb/index.html is the Architect app's orb, copied byte for byte from its build (utopia repo
apps/voice-v3/android/orb/dist/index.html: OGL point-sprite gold sand, GSAP easing, knowledge#13408). It is driven exactly as
the phone drives it: window.orb(agentLevel, userLevel, state) with the voice's level 0..1, here the clone narration's RMS per
frame (levels() below: -38 dB -> 0, -14 dB -> 1). Frames are rendered deterministically: Playwright's fake clock advances one
frame (1/30 s) per capture, so the card stays in sync with the narration whatever the render speed. Capture = the canvas's
own pixels (toDataURL; the WebGL context is opened with preserveDrawingBuffer so the frame survives to be read): 0.05 s a
frame on Ra's CPU (swiftshader) where a page screenshot took 1.1 s. No text on it: the RAW orb has none.
"""
from __future__ import annotations

import argparse, base64, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS, SR = 30, 16000


def levels(src, start, n_frames):
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    import numpy as np
    a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    hop = SR // FPS
    n = min(n_frames, len(a) // hop) if n_frames else len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
    lv = np.clip((20 * np.log10(rms + 1e-6) + 38) / 24, 0, 1)        # -38 dB -> 0 (pauses), -14 dB -> 1 (his loud words)
    out, cur = np.zeros_like(lv), 0.0
    up, down = 1 - np.exp(-1 / (0.08 * FPS)), 1 - np.exp(-1 / (0.25 * FPS))
    for i, v in enumerate(lv):
        cur += (v - cur) * (up if v > cur else down)
        out[i] = cur
    return out

PAGE = HERE / "raw-orb" / "index.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--from", dest="start", type=float, default=0.0)
    ap.add_argument("--w", type=int, default=270); ap.add_argument("--h", type=int, default=480); ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--gain", type=float, default=0.55, help="level scale: the phone's levels come from LiveKit's AudioVisualizer "
                    "(speech ~0.2-0.6); levels()'s RMS map reaches 1.0 on the -16 LUFS narration and holds the orb in full spiral, so the ring "
                    "the phone shows was lost (2350 v3-B2 vs the phone capture)")
    ap.add_argument("--alpha", action="store_true", help="v6 look (Architect 22408): TRANSPARENT background; out is a ProRes 4444 .mov with alpha (glow over black -> alpha = brightest channel, colour un-premultiplied)")
    ap.add_argument("--css-w", type=int, default=392, help="the RAW Pixel's CSS width (1080 px / DPR 2.75): grain size is in CSS px, so the "
                                                           "page is laid out at the phone's width and scaled down, or the grains read 1.45x too big")
    a = ap.parse_args()
    lv = [min(1.0, float(v) * a.gain) for v in levels(a.src, a.start, 0)]
    from playwright.sync_api import sync_playwright
    page = PAGE
    if a.alpha:   # the same page, cleared to pure black instead of #0a0907: the glow over black IS its alpha
        t = PAGE.read_text().replace("clearColor(.039,.035,.027,1)", "clearColor(0,0,0,1)").replace("background:#0a0907", "background:#000")
        page = HERE / "raw-orb" / "index-black.html"; page.write_text(t)
        vf = (f"scale={a.w}:{a.h}:flags=lanczos,format=rgba,geq=r='min(255,r(X,Y)*255/max(1,max(r(X,Y),max(g(X,Y),b(X,Y)))))':"
              "g='min(255,g(X,Y)*255/max(1,max(r(X,Y),max(g(X,Y),b(X,Y)))))':b='min(255,b(X,Y)*255/max(1,max(r(X,Y),max(g(X,Y),b(X,Y)))))':"
              "a='if(lt(max(r(X,Y),max(g(X,Y),b(X,Y))),14),0,max(r(X,Y),max(g(X,Y),b(X,Y))))',format=yuva444p10le")
        enc = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    else:
        vf = f"scale={a.w}:{a.h}:flags=lanczos"; enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"]
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                           "-vf", vf, *enc, a.out], stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": a.css_w, "height": round(a.css_w * a.h / a.w)}, device_scale_factor=a.scale)
        pg.add_init_script("""(() => { const g = HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext = function (k, o) { return g.call(this, k, Object.assign({}, o || {}, { preserveDrawingBuffer: true })) } })()""")
        pg.clock.install()
        pg.goto(page.as_uri() + "?t=6")          # t: skip the sand-gathering intro, the orb is already formed
        pg.clock.run_for(3000)                   # settle at rest
        step = round(1000 / FPS, 3)
        for i, v in enumerate(lv):
            pg.evaluate("([a, s]) => window.orb(a, 0, s)", [float(v), "speaking" if v > 0.05 else "listening"])
            pg.clock.run_for(step)
            ff.stdin.write(base64.b64decode(pg.evaluate("document.getElementById('orb').toDataURL('image/jpeg', 0.95)").split(",", 1)[1]))
            if i % 300 == 0:
                print(f"orb frame {i}/{len(lv)}", flush=True)
        b.close()
    ff.stdin.close(); ff.wait()
    if ff.returncode:
        sys.exit("ffmpeg failed")


if __name__ == "__main__":
    main()
