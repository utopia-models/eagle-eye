#!/usr/bin/env python3
"""vsl-captions.py — Tyler's spoken words -> WebVTT, verbatim (net/subprocesses/interactive/vsl.md §3.4).

    <whisper-python> vsl-captions.py <video-or-audio> <out.vtt> [--model large-v3-turbo] [--compute int8]

Runs faster-whisper directly: the same model and venv quo-calls.py uses (wi/components/comms-ingest.md). On
novaserver that venv is nova's, so vsl-publish.sh calls this as `sudo -n -u nova <venv>/bin/python` (TODO 2026-11-24: move to vsl-owned venv, nova not in the chain; vsl-publish.sh now prefers /opt/voice-v3/venv).
The words are never edited into copy: each cue is one recognised segment, re-wrapped to at most two
42-character lines (the WebVTT/BBC reading-width convention) and split at word timestamps when a segment
runs longer than that.
"""
import argparse
import subprocess
import sys
import time

MAX_LINE = 42
MAX_CUE_CHARS = 2 * MAX_LINE


def ts(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def wrap(text):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > MAX_LINE:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def cues_for(seg):
    """One segment -> one or more (start, end, text) cues, split on word timings when too long to read."""
    text = seg.text.strip()
    if len(text) <= MAX_CUE_CHARS or not seg.words:
        return [(seg.start, seg.end, text)]
    out, buf, start = [], [], None
    for w in seg.words:
        word = w.word.strip()
        if not word:
            continue
        if buf and len(" ".join(buf + [word])) > MAX_CUE_CHARS:
            out.append((start, prev_end, " ".join(buf)))
            buf, start = [], None
        if start is None:
            start = w.start
        buf.append(word)
        prev_end = w.end
    if buf:
        out.append((start, prev_end, " ".join(buf)))
    return out


def pcm16k(media):
    """ffmpeg -> 16 kHz mono s16 -> float32 samples. faster-whisper's own decoder goes through PyAV, whose version in
    the shared whisper venv rejects the keyword faster-whisper passes (`metadata_errors`); quo-calls.py does the same."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", media, "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("out")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--compute", default="int8")
    ap.add_argument("--language", default="en")
    a = ap.parse_args()

    from faster_whisper import WhisperModel  # imported late so --help works outside the venv

    t0 = time.time()
    model = WhisperModel(a.model, device="cpu", compute_type=a.compute)
    segments, info = model.transcribe(pcm16k(a.media), language=a.language, vad_filter=True, word_timestamps=True)
    n = 0
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            for start, end, text in cues_for(seg):
                if not text:
                    continue
                n += 1
                f.write(f"{n}\n{ts(start)} --> {ts(end)}\n{wrap(text)}\n\n")
    took = time.time() - t0
    print(f"vsl-captions: {n} cues · {info.duration:.1f}s of audio in {took:.1f}s "
          f"({took / max(info.duration, 0.1):.1f}x) · {a.out}", file=sys.stderr)
    if n == 0:
        print("vsl-captions: no speech recognised — refusing to publish an empty caption file", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
