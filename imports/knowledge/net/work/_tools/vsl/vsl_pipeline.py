#!/usr/bin/env python3
"""vsl_pipeline.py: ONE command from a variant and a job or target to the six files a take needs (knowledge#16076, spec B6).

  vsl_pipeline.py --variant V --job FILE|--target FILE --out DIR [--slug S]

Emits in DIR: brief.yaml, diagram.spec.json, demo.md, script.md (+ script.build.yaml; the speaker script), cues.md, horus-script.md
(the Eagle script, linted by horus/vsl_cue_lint.py; knowledge#16486), qc.json. Exit 0 only if qc.json says pass.
The variant (vsl_variants.py) fixes the length bound, the closing rule and whether Eagle Eye may be named; the same gate grades every pass.
Model calls: VSL_GEN_CMD (diagram, falls back to the generic spec) and VSL_LLM_CMD (script, default `claude -p`).
A variant that wants a --job refuses a --target and the reverse: a missing input is a hard stop, never a plausible fill.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vsl-viewer"))
import script_check  # noqa: E402
import vsl_build  # noqa: E402
import vsl_script  # noqa: E402
import vsl_variants  # noqa: E402

STACK_DIRS = ("fastapi-fullstack", "supabase-next", "django", "rails", "generic")


def make_brief(variant, src_text, slug):
    v = vsl_variants.get(variant)
    beats = "\n".join(f"  - {{id: {b['id']}, name: \"{b['name']}\", seconds: {b['seconds']}, must: \"{b['must']}\"}}"
                      for b in vsl_script.DEFAULT_BEATS)
    body = vsl_script.BRIEF_TEMPLATE.format(slug=slug, beats=beats)
    secs = min(v["max_s"], 150)
    body = body.replace("target: {seconds: 90,", f"target: {{seconds: {secs},")
    banned = "" if v["eagle_eye"] else "Eagle Eye"
    body = body.replace("banned: []", f'banned: [{banned and chr(34) + banned + chr(34)}]')
    head = f"variant: {variant}\ndemo_source: {v['demo_source']}\nclosing: {v['closing']}\n"
    quoted = "\n".join("# " + l for l in src_text.strip().splitlines()[:60])
    return head + body + "\n# source text (the only facts about the client):\n" + quoted + "\n"


def make_demo(spec, variant):
    stack = spec.get("stack", "generic")
    d = stack if stack in STACK_DIRS else "generic"
    nouns = ", ".join(n["label"] for n in spec.get("nodes", []))
    return (f"# Demo plan ({variant})\n\n- stack template: net/work/_tools/vsl-demo/{d}/ (`make demo`; loopback on a desk, never the laptop)\n"
            f"- source of the client's nouns: {vsl_variants.get(variant)['demo_source']}\n- fixture nouns for the seed: {nouns}\n"
            f"- before the take: `python3 net/work/_tools/vsl-demo/take_ready.py` must pass all four checks\n")


def make_cues(script_text, spec):
    out = ["# Cue sheet (read order on the capture)", "", "1. Diagram, full screen, FIRST: pop-in order " + " > ".join(spec.get("order", []))]
    n = 2
    for line in script_text.splitlines():
        if line.startswith("## "):
            out.append(f"{n}. {line[3:]}")
            n += 1
        elif script_check.CUE.match(line):
            out.append("   " + line.strip())
    return "\n".join(out) + "\n"


def make_horus_script(script_text, slug):
    """The Eagle script (knowledge#16486): the cue table vsl-follow and Vizier's EAGLE SCRIPT tab read (horus-script.md).
    One row per part: it fires LEAD seconds before the part starts, so `on` is the first five words of the PREVIOUS part's last
    spoken line and `do` is the part's own [horus] cue. Parts with no cue line get no row (nothing to execute)."""
    parts, cur = [], None
    for line in script_text.splitlines():
        if line.startswith("## "):
            cur = {"name": line[3:].strip(), "cue": "", "said": []}
            parts.append(cur)
        elif cur is None:
            continue
        elif script_check.CUE.match(line):
            cur["cue"] = re.sub(r"^\s*(?:\[[^\]]*\]|\([^)]*\))\s*[:\-]?\s*", "", line).strip()
        elif line.strip() and not line.lstrip().startswith(("#", "<!--")):
            cur["said"].append(line.strip())
    rows = ["| id | on (previous line says) | lead | do (before the next line) | wait for | on fail |", "|---|---|---|---|---|---|",
            "| C0 | (take starts) | 0 | diagram tab front; mark START | | |"]
    n, prev = 1, ""
    for part in parts:
        if part["cue"] and prev:
            rows.append(f"| C{n} | {prev.replace('|', '/')} | 4 | {part['cue'].replace('|', '/')} | | |")
            n += 1
        if part["said"]:
            prev = " ".join(part["said"][-1].split()[:5])
    rows.append(f"| C{n} | (take ends) | 0 | mark STOP | | |")
    head = (f"# horus-script.md: {slug}. The Eagle script, built from script.md by vsl_pipeline.py. Every cue fires `lead` seconds "
            "BEFORE its line is spoken, so `on` is the PREVIOUS line's first five words.\n\n")
    return head + "\n".join(rows) + "\n"


def qc(script_text, variant, findings, spec_problems, build_problems):
    lines = script_check.spoken(script_text)
    secs = sum(int(s) for s in script_check.PART.findall(script_text))
    v = vsl_variants.get(variant)
    doc = {"variant": variant, "seconds": secs, "max_seconds": v["max_s"], "words": sum(len(l.split()) for l in lines),
           "eagle_eye_allowed": v["eagle_eye"], "eagle_eye_hits": vsl_variants.eagle_reasons(script_text, variant),
           "gate_findings": findings, "diagram_problems": spec_problems, "build_problems": build_problems}
    doc["pass"] = not (findings or spec_problems or build_problems)
    return doc


def run(variant, job, target, out, slug=None, model=None, gen=None):
    v = vsl_variants.get(variant)
    given = {"job": job, "target": target}
    if not given[v["input"]]:
        raise SystemExit(f"variant {variant} needs --{v['input']} FILE (hard stop: no input, no fill)")
    src = Path(given[v["input"]])
    if not src.is_file():
        raise SystemExit(f"--{v['input']} {src} does not exist")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    text = src.read_text()
    slug = slug or re.sub(r"\W+", "-", src.stem).strip("-").lower()
    (out / "brief.yaml").write_text(make_brief(variant, text, slug))
    import gen_spec
    import validate_spec
    spec, why = (gen or gen_spec.generate)(text)
    sp = list(validate_spec.problems(spec)) + ([f"fallback to generic: {why}"] if why else [])
    (out / "diagram.spec.json").write_text(json.dumps(spec, indent=1) + "\n")
    (out / "demo.md").write_text(make_demo(spec, variant))
    script_path = out / "script.md"
    kw = {"model": model} if model else {}
    _, loop_found = vsl_script.rewrite(out / "brief.yaml", script_path, variant=variant, **kw)
    stext = script_path.read_text()
    found = list(dict.fromkeys(vsl_script.gate(stext, variant=variant) + loop_found))
    (out / "cues.md").write_text(make_cues(stext, spec))
    (out / "horus-script.md").write_text(make_horus_script(stext, slug))
    import vsl_cue_lint_bridge
    cue_problems = vsl_cue_lint_bridge.lint((out / "horus-script.md").read_text())
    doc = qc(stext, variant, found, [p for p in sp if not p.startswith("fallback")], vsl_build.check(script_path))
    doc["cue_problems"] = cue_problems
    doc["pass"] = doc["pass"] and not cue_problems
    doc["diagram_fallback"] = next((p for p in sp if p.startswith("fallback")), None)
    (out / "qc.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variant", required=True, choices=list(vsl_variants.VARIANTS))
    ap.add_argument("--job")
    ap.add_argument("--target")
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug")
    a = ap.parse_args(argv)
    doc = run(a.variant, a.job, a.target, a.out, a.slug)
    print(("PASS" if doc["pass"] else "FAIL"), Path(a.out) / "qc.json")
    for f in doc["gate_findings"] + doc["diagram_problems"] + doc["build_problems"]:
        print("   ", f)
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
