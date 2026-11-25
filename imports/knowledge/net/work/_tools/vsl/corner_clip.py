#!/usr/bin/env python3
"""Trim the head off a VSL clip and park it, resized, flush bottom-right of a canvas.

Asks 3739 (cut "Hi Russell") and 3740 (resize, bottom right), knowledge#18918.
  corner_clip.py IN.mp4 OUT.mp4 [--cut-head SECONDS] [--width 512] [--canvas 2048x1152] [--bg BG.mp4|BG.png]
Without --bg the canvas is black. Margin is 0 (Tyler 2026-11-22: "very bottom right, on the edges").
Audio is kept (trimmed with the video). Prints the ffmpeg command it ran.
"""
import argparse, subprocess, sys

def build(a):
    cw, ch = (int(x) for x in a.canvas.split("x"))
    w = a.width - a.width % 2
    trim = f"trim=start={a.cut_head},setpts=PTS-STARTPTS," if a.cut_head else ""
    atrim = f"atrim=start={a.cut_head},asetpts=PTS-STARTPTS" if a.cut_head else "anull"
    cmd = ["ffmpeg", "-y", "-i", a.src]
    if a.bg:
        cmd += ["-loop", "1", "-i", a.bg] if a.bg.lower().endswith((".png", ".jpg")) else ["-i", a.bg]
        base = f"[1:v]scale={cw}:{ch}[bg];"
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={cw}x{ch}"]
        base = ""
    fc = (f"{base}[0:v]{trim}scale={w}:-2[clip];"
          f"{'[bg]' if a.bg else '[1:v]'}[clip]overlay=W-w:H-h:shortest=1[v];[0:a]{atrim}[a]")
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", a.dst]
    return cmd

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("src"); p.add_argument("dst")
    p.add_argument("--cut-head", type=float, default=0.0)
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--canvas", default="2048x1152")
    p.add_argument("--bg")
    a = p.parse_args()
    c = build(a); print(" ".join(c), file=sys.stderr)
    sys.exit(subprocess.call(c))
