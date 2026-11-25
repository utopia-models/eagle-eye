#!/usr/bin/env python3
"""vsl_build.py: the build stamp. A take script is a PIPELINE OUTPUT or it is refused (knowledge#15137).

Tyler, 2026-11-18: "right now you're doing it from scratch, which is unacceptable ... when you say I just built this out for
you, that's very unprofessional. I want templates." The copy, provenance and judge gates grade prose; none of them could tell a
script the pipeline built from one typed from nothing. This one can.

  vsl_build.py write FILE [--templates a,b] [--refs p1,p2] [--tool NAME]   write FILE's sidecar <stem>.build.yaml
  vsl_build.py check FILE                                                  [] or the reasons the script is not a pipeline output

The sidecar records the tool that produced the script, the template versions filled, the reference scripts retrieved (vsl_ref),
and the sha256 of the text. `check` fails on: no sidecar, no template and no reference named, or a sha that no longer matches
(the script was edited after the build). Re-stamp after an edit with `vsl_script.py stamp FILE`, which refuses unless the whole
gate passes, so an edit never launders a script past the gate. Called by `script_check.py --asset` (what Vizier's Ready check runs).
"""
import hashlib
import sys
import time
from pathlib import Path

TOOLS = ("vsl_script.new", "vsl_script.rewrite", "vsl_script.stamp")


def sidecar(script_path):
    p = Path(script_path)
    return p.with_name(p.stem + ".build.yaml")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(script_path, tool, templates=(), refs=()):
    import yaml
    text = Path(script_path).read_text()
    doc = {"tool": tool, "templates": list(templates), "references": list(refs), "sha256": sha(text),
           "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    sidecar(script_path).write_text(yaml.safe_dump(doc, sort_keys=False))
    return doc


def check(script_path, text=None):
    p = Path(script_path)
    sc = sidecar(p)
    if not sc.exists():
        return [f"build: no {sc.name} beside the script. A take script is built by the pipeline (vsl_ref.py brief, then "
                f"vsl_script.py new --template take or rewrite), never written from scratch; run it, or vsl_script.py stamp after a gated edit"]
    import yaml
    d = yaml.safe_load(sc.read_text()) or {}
    out = []
    if d.get("tool") not in TOOLS:
        out.append(f"build: {sc.name} names tool {d.get('tool')!r}, not one of {', '.join(TOOLS)}")
    if not d.get("templates") and not d.get("references"):
        out.append(f"build: {sc.name} names no template and no reference script; the pipeline always uses at least one")
    if d.get("sha256") != sha(p.read_text() if text is None else text):
        out.append(f"build: the script changed after {sc.name} was written; pass the gate and run vsl_script.py stamp {p.name}")
    return out


def main(argv):
    if len(argv) >= 2 and argv[0] == "check":
        rs = check(argv[1])
        print("FAIL" if rs else "PASS", argv[1])
        for r in rs:
            print("   ", r)
        return 1 if rs else 0
    if len(argv) >= 2 and argv[0] == "write":
        opt = lambda k: argv[argv.index(k) + 1] if k in argv else ""  # noqa: E731
        d = write(argv[1], opt("--tool") or "vsl_script.new", [x for x in opt("--templates").split(",") if x],
                  [x for x in opt("--refs").split(",") if x])
        print(sidecar(argv[1]), d["sha256"][:12])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
