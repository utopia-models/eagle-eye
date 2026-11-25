#!/usr/bin/env python3
"""vsl_oneshot.py: one command, one script artifact, no live session (knowledge#16483, Tyler's ask 1292).

  vsl_oneshot.py speaker --variant V --job FILE|--target FILE --out FILE [--slug S]
  vsl_oneshot.py eagle   (--script SPEAKER.md | --variant V --job/--target ...) --out FILE [--slug S]

speaker -> the Vizier speaker script (script.md), written by the full pipeline (model call, gate-checked).
eagle   -> the Eagle script (horus-script.md cue table). From --script it is deterministic and makes no model call;
           with --variant it runs the pipeline first and emits that run's Eagle script.
Exit 0 only when the artifact is written and (pipeline path) qc.json passed. No change to Vizier's runtime.
"""
import argparse
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vsl_pipeline  # noqa: E402

ARTIFACT = {"speaker": "script.md", "eagle": "horus-script.md"}


def run(kind, out, variant=None, job=None, target=None, script=None, slug=None, pipeline=None):
    """-> (artifact Path, qc dict or None). Raises SystemExit on a missing input (no plausible fill)."""
    out = Path(out)
    if kind == "eagle" and script:
        src = Path(script)
        if not src.is_file():
            raise SystemExit(f"--script {src} does not exist")
        slug = slug or src.parent.name or src.stem
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(vsl_pipeline.make_horus_script(src.read_text(), slug))
        return out, None
    if not variant:
        raise SystemExit(f"kind={kind} needs --variant with --job/--target" + (" (or --script FILE)" if kind == "eagle" else ""))
    with tempfile.TemporaryDirectory(prefix="vsl-oneshot-") as d:
        doc = (pipeline or vsl_pipeline.run)(variant, job, target, d, slug)
        made = Path(d) / ARTIFACT[kind]
        if not made.is_file():
            raise SystemExit(f"pipeline did not produce {ARTIFACT[kind]}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(made.read_text())
    return out, doc


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kind", choices=list(ARTIFACT))
    ap.add_argument("--variant")
    ap.add_argument("--job")
    ap.add_argument("--target")
    ap.add_argument("--script")
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug")
    a = ap.parse_args(argv)
    path, doc = run(a.kind, a.out, a.variant, a.job, a.target, a.script, a.slug)
    ok = doc is None or doc["pass"]
    print(("OK" if ok else "QC-FAIL"), a.kind, path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
