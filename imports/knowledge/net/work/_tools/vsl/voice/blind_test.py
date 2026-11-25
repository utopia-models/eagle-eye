#!/usr/bin/env python3
"""Voice blind test (knowledge#18736). Renders the SAME script through each candidate TTS adapter, cloned from Tyler's reference,
loudness-matched to -16 LUFS, into voice/samples/<model>.wav + <model>.json (model, license, render time, lufs, ref sha).
  blind_test.py --script rows.txt --ref tyler-ref.wav [--models chatterbox,cosyvoice,indextts2] [--energy 0.7]
`rows.txt` = one spoken row per line (the 3307 package's `say` rows; build_intro.py --rows-only writes it). A model that cannot load is
REPORTED and skipped, never faked; exit 2 if fewer than --min samples (default 3) were produced. Blind labels A/B/C go to samples/blind-key.json
(kept apart from the files Eagle shows Tyler)."""
import argparse, json, random, re, subprocess, sys, tempfile, time
from pathlib import Path



HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from adapters import ADAPTERS, AdapterUnavailable  # noqa: E402
from voice_profile import sha256  # noqa: E402

TARGET = -16.0
DEFAULT_MODELS = "chatterbox,cosyvoice,indextts2,orpheus"


def loudnorm(src, dst, target=TARGET):
    """two-pass ffmpeg loudnorm to `target` LUFS; returns the measured integrated LUFS of dst."""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    j = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", m.stderr, re.S).group(0))
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", af, "-ar", "24000", "-ac", "1", str(dst)], check=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(dst), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


def render(name, rows, ref, energy, outdir):
    t0 = time.time()
    ad = ADAPTERS[name]()
    import numpy as np, soundfile as sf
    load_s = time.time() - t0
    t1 = time.time(); parts = []; sr = None
    for r in rows:
        a, sr = ad.synth(r, ref, energy)
        parts += [a, np.zeros(int(sr * 0.45), np.float32)]
    render_s = time.time() - t1
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d) / "raw.wav"; sf.write(raw, np.concatenate(parts), sr)
        out = outdir / f"{name}.wav"; lufs = loudnorm(raw, out)
    side = {"model": name, "license": ad.license, "render_time_s": round(render_s, 1), "model_load_s": round(load_s, 1), "lufs": lufs, "target_lufs": TARGET,
            "energy": energy, "rows": len(rows), "reference": str(ref), "reference_sha256": sha256(ref), "audio_s": round(sum(len(p) for p in parts) / sr, 1)}
    (outdir / f"{name}.json").write_text(json.dumps(side, indent=1) + "\n")
    return side


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True); ap.add_argument("--ref", required=True)
    ap.add_argument("--models", default=DEFAULT_MODELS); ap.add_argument("--energy", type=float, default=0.7)
    ap.add_argument("--out", default=str(HERE / "samples")); ap.add_argument("--min", type=int, default=3)
    a = ap.parse_args()
    rows = [l.strip() for l in Path(a.script).read_text().splitlines() if l.strip()]
    if not rows or not Path(a.ref).is_file():
        sys.exit(f"blocked: need a non-empty script ({a.script}) and a reference wav ({a.ref})")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    done, skipped = [], {}
    for name in a.models.split(","):
        if name not in ADAPTERS:
            skipped[name] = "unknown adapter"; continue
        try:
            done.append(render(name, rows, a.ref, a.energy, out)); print("OK", name, done[-1]["lufs"], "LUFS", done[-1]["render_time_s"], "s")
        except AdapterUnavailable as e:
            skipped[name] = str(e); print("SKIP", name, "-", e, file=sys.stderr)
    if len(done) >= 2:
        labels = list("ABCDEFG")[:len(done)]; order = [d["model"] for d in done]; random.shuffle(order)
        (out / "blind-key.json").write_text(json.dumps(dict(zip(labels, order)), indent=1) + "\n")
    print(json.dumps({"rendered": [d["model"] for d in done], "skipped": skipped}))
    sys.exit(0 if len(done) >= a.min else 2)


if __name__ == "__main__":
    main()
