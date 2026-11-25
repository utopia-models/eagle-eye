#!/usr/bin/env python3
"""vsl_script.py: the VSL script framework. The Upwork agent calls it; it never edits a take script by itself.

  vsl_script.py new SLUG [--job-post FILE] [--dir DIR]   scaffold DIR/SLUG/brief.yaml (the structured brief)
  vsl_script.py new SLUG --brief BRIEF --template NAME|take [--out FILE] [--reference]   fill the versioned templates/ from the brief, then gate
  vsl_script.py check FILE [--require-vale] [--judge] [--variant V]     the whole gate: script_check --asset + vsl_copy + beats; exit 0/1. Always prints the
                                                          per-beat reference-match table; --judge adds the rubric judge vs the nearest exemplar (vsl_judge.py)
  vsl_script.py rewrite BRIEF --out FILE [--from SCRIPT]  outline -> draft -> critic -> rewrite (<= MAX_LOOPS) -> gate
  vsl_script.py stamp FILE                                 re-stamp FILE's <stem>.build.yaml after a hand edit, only if the whole gate passes
Every script `new --template take` or `rewrite` writes leaves a <stem>.build.yaml (tool, template versions, references, sha256);
`script_check.py --asset` fails a take script without a matching one, so a script typed from nothing never reaches Ready (#15137).

Pipeline = prompts/*.md (versioned files) + a model command (VSL_LLM_CMD, default `claude -p`; one backend, no API key).
Every pass is graded by the same gate, so a script leaves only when `check` passes; after MAX_LOOPS it exits 1 with the findings.
The brief holds what a model may NOT invent: job facts, verified capabilities, persona rules, target length, beats.
Prior art surveyed, nothing worth importing for ~150 lines: DSPy (MIT) and BAML (Apache-2.0) optimise prompts against a metric
(add later: our gate IS that metric); promptfoo (MIT) runs prompt evals (golden tests here are plain unittest).
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import script_check  # noqa: E402
import vsl_copy  # noqa: E402
import vsl_build  # noqa: E402
import vsl_judge  # noqa: E402
import vsl_ref  # noqa: E402
import vsl_template  # noqa: E402

MAX_LOOPS = 3
DEFAULT_BEATS = [  # the order Tyler settled (take 1 v14): roadmap, architecture diagram, live demo, next step
    {"id": "roadmap", "name": "The roadmap", "seconds": 15, "must": "address the role; say what you will show in one sentence"},
    {"id": "architecture", "name": "How it fits together", "seconds": 25, "must": "walk the architecture diagram, name each component and the control point"},
    {"id": "demo", "name": "Running it live", "seconds": 30, "must": "describe the run on sample data and what the audit log shows"},
    {"id": "next", "name": "What I'd do next", "seconds": 15, "must": "a thesis the demo proved, then one next-step statement (no question, no reply ask)"}]
BRIEF_TEMPLATE = """# VSL brief: {slug}. Facts a model may use; nothing outside this file.
job:
  title: ""
  url: ""
  facts: []            # what the post says, verbatim fragments
capabilities: []       # verified, built and demoable: one line each, with the number or component name
persona:
  speaker: Tyler Youk
  rules: ["first person singular", "no hedge", "no hype"]
banned: []             # extra phrases beyond vsl_copy.BANNED
target: {{seconds: 90, words_per_second: 2.5}}
beats:
{beats}
"""


def load_yaml(path):
    import yaml
    return yaml.safe_load(Path(path).read_text())


def prompt(name, **kw):
    t = (HERE / "prompts" / f"{name}.md").read_text()
    return re.sub(r"<!--.*?-->\n?", "", t).format(**kw)


def llm(text):
    cmd = os.environ.get("VSL_LLM_CMD", "claude -p").split()
    p = subprocess.run(cmd, input=(prompt("system") + "\n\n" + text), capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError(f"model command failed: {p.stderr[:200]}")
    return p.stdout.strip() + "\n"


def vsl_variants_closing_none(variant):   # youtube / eagle-eye have no client
    return script_check.vsl_variants_closing_none(variant)


def gate(text, require_vale=False, variant=None):
    """-> findings; the whole gate in one call. No claim/provenance gate (Tyler 2026-11-18, knowledge#16020)."""
    rs = script_check.check(text, asset=True, variant=variant, client_first=None if variant and vsl_variants_closing_none(variant) else True)
    rs += vsl_copy.check_copy(text, require_vale=require_vale)[0]
    return list(dict.fromkeys(rs))


def judge_findings(script, judge=vsl_judge.llm):
    """The rubric judge as a loop stage: [] when the draft beats its nearest exemplar in both orderings, else one finding. VSL_JUDGE=off skips it."""
    if os.environ.get("VSL_JUDGE", "on") == "off":
        return []
    out = []
    for h in vsl_judge.exemplars(script, 1):
        ex = vsl_judge.beats(vsl_judge.body_of(vsl_judge.WORK / h["path"]))
        draft = vsl_judge.beats(script)
        if ex and draft:
            ok, d = vsl_judge.wins_both(draft, ex, judge)
            if not ok:
                out.append(f"judge: draft does not outscore {h['path']} ({h['status']}) in both orderings {d}; raise specificity and professionalism beat by beat")
    return out


def _ref_paths(brief):
    try:
        return [h["path"] for h in vsl_ref.references_md(brief)[1]]
    except Exception:   # an unbuilt index must not stop a stamp; the stamp then names the templates only
        return []


def _template_ids(brief):
    import re
    ids = []
    for t in vsl_template.TEMPLATES:
        fs = sorted(vsl_template.TDIR.glob(f"{t}.v*.yaml"), key=lambda p: int(re.search(r"\.v(\d+)\.yaml", p.name).group(1)))
        if fs:
            ids.append(fs[-1].stem)
    return ids


def stamp(out, tool, brief, refs=None):
    vsl_build.write(out, tool, _template_ids(brief) if tool != "vsl_script.rewrite" else [], refs or _ref_paths(brief))


def rewrite(brief_path, out, start=None, model=llm, loops=MAX_LOOPS, refs=None, judge=vsl_judge.llm, variant=None):
    brief = load_yaml(brief_path)
    b = Path(brief_path).read_text()
    beats = brief.get("beats") or DEFAULT_BEATS
    secs = brief.get("target", {}).get("seconds", 90)
    words = int(secs * brief.get("target", {}).get("words_per_second", 2.5))
    refs = vsl_ref.references_md(brief)[0] if refs is None else refs
    if start:
        script = Path(start).read_text()
    else:
        outline = model(prompt("outline", brief=b, references=refs, beats=", ".join(x["name"] for x in beats)))
        script = model(prompt("draft", brief=b, references=refs, outline=outline, seconds=secs, max_words=words))
    for i in range(loops + 1):
        found = gate(script, variant=variant) or judge_findings(script, judge)
        if not found:
            Path(out).write_text(script)
            stamp(out, "vsl_script.rewrite", brief, refs=None if refs is None else _ref_paths(brief))
            return 0, []
        if i == loops:
            break
        crit = model(prompt("critic", references=refs, findings="\n".join(found), script=script, brief=b))
        script = model(prompt("rewrite", brief=b, findings="\n".join(found), critic=crit, script=script))
    Path(out).write_text(script)
    stamp(out, "vsl_script.rewrite", brief, refs=_ref_paths(brief))
    return 1, found


def main(argv):
    if not argv or argv[0] not in ("new", "check", "rewrite", "stamp"):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    opt = lambda k: args[args.index(k) + 1] if k in args else None  # noqa: E731
    if cmd == "new" and opt("--template"):
        brief_file = Path(opt("--brief"))
        brief = load_yaml(brief_file)
        try:
            text = vsl_template.take(brief, brief_file.resolve().parent) if opt("--template") == "take" else \
                "\n".join(vsl_template.render(brief, opt("--template"), brief_file.resolve().parent)) + "\n"
        except vsl_template.MissingSlot as e:
            print(f"missing slot: {e}", file=sys.stderr)
            return 1
        if opt("--reference"):
            refs, hits = vsl_ref.references_md(brief)
            rp = Path(opt("--out") or args[0]).with_name("references.md")
            rp.write_text(refs)
            print(f"references: {', '.join(h['path'] for h in hits)} -> {rp}")
        if opt("--out"):
            Path(opt("--out")).write_text(text)
        else:
            print(text)
        if opt("--template") == "take" and opt("--out"):
            stamp(opt("--out"), "vsl_script.new", brief)
        if opt("--template") == "take":   # a full take is graded by the gate before it leaves
            found = gate(text)
            print(("FAIL" if found else "PASS"), "gate", file=sys.stderr)
            for f in found:
                print("   ", f, file=sys.stderr)
            return 1 if found else 0
        return 0
    if cmd == "new":
        d = Path(opt("--dir") or ".") / args[0]
        d.mkdir(parents=True, exist_ok=True)
        beats = "\n".join(f"  - {{id: {b['id']}, name: \"{b['name']}\", seconds: {b['seconds']}, must: \"{b['must']}\"}}" for b in DEFAULT_BEATS)
        (d / "brief.yaml").write_text(BRIEF_TEMPLATE.format(slug=args[0], beats=beats))
        if opt("--job-post"):
            (d / "job-post.md").write_text(Path(opt("--job-post")).read_text())
        print(d / "brief.yaml")
        return 0
    if cmd == "stamp":
        text = Path(args[0]).read_text()
        found = gate(text)
        if found:
            print("FAIL no stamp: the script does not pass the gate")
            for f in found:
                print("   ", f)
            return 1
        prev = vsl_build.sidecar(args[0])
        old = __import__("yaml").safe_load(prev.read_text()) if prev.exists() else {}
        if not (old or {}).get("templates") and not (old or {}).get("references"):
            print(f"FAIL no stamp: {prev.name} has no pipeline origin to carry forward; build the script with new --template take or rewrite")
            return 1
        vsl_build.write(args[0], "vsl_script.stamp", old["templates"], old["references"])
        print("STAMPED", args[0])
        return 0
    if cmd == "check":
        text = Path(args[0]).read_text()
        found = gate(text, require_vale="--require-vale" in args, variant=opt("--variant"))
        found += vsl_build.check(args[0])   # not a pipeline output = FAIL (#15137)
        rows, _ = vsl_judge.match_table(text)
        vsl_judge.print_table(rows)
        if "--judge" in args and not found:
            found = judge_findings(text)
        print(("FAIL" if found else "PASS"), args[0])
        for f in found:
            print("   ", f)
        return 1 if found else 0
    rc, found = rewrite(args[0], opt("--out"), opt("--from"))
    print(("FAIL" if rc else "PASS"), opt("--out"))
    for f in found:
        print("   ", f)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
