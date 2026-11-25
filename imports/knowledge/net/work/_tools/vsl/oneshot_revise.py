#!/usr/bin/env python3
"""oneshot_revise.py: `oneshot revise <job> "<change in his words>"` (Tyler 2026-11-22 6:50 AM ET: every change comes through the one-shot system).
A scripted, LLM-light loop: classify the change to ONE artifact, a single short worker edits that one file, only that artifact is re-rendered,
only the affected gates re-run, the same URLs are republished, and before/after evidence is stored. Target: under 5 minutes.

  oneshot_revise.py revise JOB "WORDS" [--artifact diagram|script|app] [--pkg-root DIR] [--test]   (--test: a proof run, not counted in the revisions KPI or the delay tags)
  oneshot_revise.py inbox [--pkg-root DIR]       process STATE/revise-inbox/*.json ({"job": slug, "text": words}); Eagle Eye's text box writes these
  oneshot_revise.py --self-test

Artifacts -> file, re-render, gates re-run:  diagram: architecture.yaml, animate.py + republish, gates 2 and 4 | script: script-source.yaml,
gen_scripts (intro, entire, action script, tabs), gates 3, 4 and 5 | app: config.json, oneshot-deploy, gates 1 and 4.
Hard stops, named: the words match no artifact or two equally (say --artifact, never a guess); the worker changed another file (all restored,
the revision fails); a re-run gate fails (the revision is recorded as failed with the gate's reason and the previous files are restored).
Evidence per revision in PKG/revisions/NN/: words.txt, record.json, before.png and after.png (diagram, app) or script.diff (script).
PKG/reload.json {rev, artifact, at} is the reload request for Tyler's tabs and the prompter (Eagle polls it). The record is also appended to the
job's `revisions` (words, artifact, the gates that ran, minutes) so a revision count and the gate that should have caught it can be reported.
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oneshot_auto as A  # noqa: E402

PROMPT = A.KNOW / "net/work/vsl/oneshot-revise-prompt.md"
TARGET_MIN = 5

KEYWORDS = {
    "diagram": r"diagram|architecture|beat|\bbox(es)?\b|\bnode|arrow|\bedge|column|enlarge|zoom|caption|layout|enterprise|c4\b|reference",
    "script": r"script|\bline\b|\blines\b|\bsay\b|\bsaid\b|sentence|\bintro\b|voice|\bwords?\b|wording|narrat|prompter|shorter|longer|rephrase|phrase|spoken",
    "app": r"\bapp\b|terminal|command|\bcli\b|output|mvp|screen|\bpage\b|button|kpi|briefing|queue|workflow|colou?r|palette|\bui\b|\blook|table|number|dashboard|view",
}
ARTIFACTS = {
    "diagram": {"file": "architecture.yaml", "gates": [2, 4], "shot": ("diagram", 1)},
    "script": {"file": "script-source.yaml", "gates": [3, 4, 5], "shot": None},
    "app": {"file": "config.json", "gates": [1, 4], "shot": ("app", None)},
}
RULES = {
    "diagram": "Same keys as before (title, subtitle, view, note, mode, paths, nodes, hosts, edges). Every edge uses a declared path; every node id an edge names must exist. Keep the beat count and keep it readable on one 1920x1080 screen.",
    "script": "Keep section ids intro, app, diagram in that order and no close. Every spoken row: at most 15 words, at most 2 sentences, plain words, contractions are fine (I'm, it's: he talks that way), at most one ', and' per sentence, no question mark, no price, no rate, no milestone, no link, never the words sample, first version or mock. Keep each `do:` (tab, click or beat) that still makes sense. The diagram section stays at most 15 seconds of speech (about 41 words).",
    "terminal": "Valid JSON with the same keys (title, tenant, session, prompt, commands). Keep 4 to 8 commands, each with label, cmd and out; the script clicks term-cmd-1 to term-cmd-N in order, so keep the order and the count unless the words ask otherwise. Realistic output, no links, emails, phone numbers or price.",
    "app": "Valid JSON with the same keys. Keep queue ids and the workflow step ids (the script clicks them). No links, emails, phone numbers or price. Keep at least one KPI with drift 1.",
}


class Ambiguous(Exception):
    pass


def classify(words):
    sc = {k: len(re.findall(p, words, re.I)) for k, p in KEYWORDS.items()}
    best = sorted(sc.items(), key=lambda kv: -kv[1])
    if best[0][1] == 0:
        raise Ambiguous(f"the words name no artifact ({', '.join(KEYWORDS)}); say --artifact")
    if best[0][1] == best[1][1]:
        raise Ambiguous(f"the words fit {best[0][0]} and {best[1][0]} equally; say --artifact")
    return best[0][0]


def hashes(pkg):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(pkg).iterdir() if p.is_file() and p.suffix in (".json", ".yaml", ".md", ".txt")
            and p.name not in ("gates.json",)}


def spec_for(artifact, pkg):
    """The artifact's spec; for the app it is terminal.json on a terminal job and config.json on a web-app job."""
    spec = dict(ARTIFACTS[artifact])
    if artifact == "app" and (Path(pkg) / "terminal.json").is_file():
        spec["file"] = "terminal.json"
    return spec


def edit_worker(artifact, words, pkg, c):
    spec = spec_for(artifact, pkg)
    prompt = PROMPT.read_text()
    for k, v in (("{FILE}", str(Path(pkg) / spec["file"])), ("{ARTIFACT}", artifact), ("{WORDS}", words), ("{RULES}", RULES["terminal" if spec["file"] == "terminal.json" else artifact])):
        prompt = prompt.replace(k, v)
    r = subprocess.run(["claude", "-p", prompt, "--model", c["author"]["model"], "--permission-mode", "acceptEdits", "--allowedTools", "Read", "Write",
                        "--add-dir", str(pkg)], capture_output=True, text=True, timeout=300, cwd=str(pkg))
    if r.returncode:
        raise RuntimeError(f"revise worker failed: {(r.stderr or r.stdout)[-200:]}")


def rerender(artifact, j, pkg):
    if artifact == "diagram":
        A.build_diagram(j, pkg)
    elif artifact == "app" and (Path(pkg) / "terminal.json").is_file():
        A.build_terminal(j, pkg)
    elif artifact == "script":
        import gen_scripts
        gen_scripts.generate(pkg)
    else:
        if not A.build_app(j, pkg) and not A.prereview(j["slug"], pkg):
            raise RuntimeError("the app failed its pre-review twice")


def shoot(url, out, beat=None):
    import gates
    args = [str(out)] + ([beat] if beat is not None else [])
    gates.probe("shot", url, *args)


def urls(pkg):
    import yaml
    return yaml.safe_load((Path(pkg) / "script-source.yaml").read_text())["urls"]


def next_rev(pkg):
    d = Path(pkg) / "revisions"
    d.mkdir(exist_ok=True)
    return len([p for p in d.iterdir() if p.is_dir()]) + 1


def revise(slug, words, artifact=None, pkg_root=None, steps=None, c=None, test=False):
    """-> the revision record. `steps` replaces the outward functions in tests: worker, rerender, gates, shoot."""
    c = c or A.cfg()
    steps = steps or {}
    t0 = time.time()
    pkg = Path(pkg_root or A.PKG_ROOT) / slug
    if not (pkg / "script-source.yaml").is_file():
        raise FileNotFoundError(f"no package for {slug} in {pkg.parent}")
    artifact = artifact or classify(words)
    if artifact == "app" and (pkg / "copied_from.json").is_file():
        raise Ambiguous("this app is a copy of a real application: revising its content (several files in app/src, then a rebuild) is not built yet; "
                        "ask the Architect, or re-run oneshot_copy.py build for the job")
    spec = spec_for(artifact, pkg)
    n = next_rev(pkg)
    rdir = pkg / "revisions" / f"{n:02d}"
    rdir.mkdir(parents=True)
    (rdir / "words.txt").write_text(words + "\n")
    j = A.load_job(slug) if (A.jobs_dir() / f"{slug}.json").is_file() else {"slug": slug, "title": slug, "text": "", "t": {}}
    u = urls(pkg)
    before_files = hashes(pkg)
    backup = {f: (pkg / f).read_bytes() for f in before_files}
    shooter = steps.get("shoot") or shoot
    rec = {"rev": n, "words": words, "artifact": artifact, "file": spec["file"], "gates_run": spec["gates"], "started": A.iso(), "ok": False, "test": bool(test)}
    texts_before = {f: (pkg / f).read_text() for f in ("intro-script.md",) if (pkg / f).is_file()}
    try:
        if spec["shot"]:
            shooter(u["diagram" if spec["shot"][0] == "diagram" else "app"], rdir / "before.png", spec["shot"][1])
        (steps.get("worker") or (lambda a, w, p, c: edit_worker(a, w, p, c)))(artifact, words, pkg, c)
        after = hashes(pkg)
        changed = sorted(f for f in set(before_files) | set(after) if before_files.get(f) != after.get(f))
        if changed != [spec["file"]]:
            raise RuntimeError(f"the worker must change only {spec['file']}, it changed {changed or 'nothing'}")
        t1 = time.time()
        (steps.get("rerender") or rerender)(artifact, j, pkg)
        rec["render_s"] = round(time.time() - t1, 1)
        doc = (steps.get("gates") or (lambda p, only: __import__("gates").run_package(p, only=only)))(pkg, spec["gates"])
        bad = [g for g in doc["gates"] if g["id"] in spec["gates"] and g["status"] == "fail"]
        rec["gates"] = [{"id": g["id"], "name": g["name"], "status": g["status"]} for g in doc["gates"] if g["id"] in spec["gates"]]
        if bad:
            raise RuntimeError("; ".join(f"gate {g['id']} {g['name']}: {g['why'][0]}" for g in bad))
        if spec["shot"]:
            shooter(u["diagram" if spec["shot"][0] == "diagram" else "app"], rdir / "after.png", spec["shot"][1])
        if artifact == "script":
            a = texts_before.get("intro-script.md", "").splitlines()
            b = (pkg / "intro-script.md").read_text().splitlines()
            (rdir / "script.diff").write_text("\n".join(difflib.unified_diff(a, b, "before", "after", lineterm="")) + "\n")
        rec["ok"] = True
    except Exception as e:
        rec["error"] = str(e)[:300]
        for f, data in backup.items():   # a failed revision leaves the previous files, never a half edit
            (pkg / f).write_bytes(data)
    rec["finished"] = A.iso()
    rec["minutes"] = round((time.time() - t0) / 60, 2)
    rec["within_target"] = rec["minutes"] <= TARGET_MIN
    (rdir / "record.json").write_text(json.dumps(rec, indent=1) + "\n")
    if rec["ok"]:
        (pkg / "reload.json").write_text(json.dumps({"rev": n, "artifact": artifact, "at": rec["finished"], "slug": slug}) + "\n")
    if (A.jobs_dir() / f"{slug}.json").is_file():
        jj = A.load_job(slug)
        jj.setdefault("revisions", []).append({**{k: rec.get(k) for k in ("rev", "words", "artifact", "gates_run", "ok", "minutes", "error", "finished")},
                                              "opened": rec["started"], "closed": rec["finished"], "test": rec["test"]})   # the request is open from the start of the work to its end (oneshot_delay.py)
        A.save_job(jj)
    return rec


def inbox(pkg_root=None, **kw):
    """Process the Eagle Eye text-box drops, oldest first; each file is removed once handled and its result written beside it."""
    d = A.STATE / "revise-inbox"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(d.glob("*.json")):
        req = json.loads(f.read_text())
        try:
            rec = revise(req["job"], req["text"], req.get("artifact"), pkg_root, **kw)
        except (Ambiguous, FileNotFoundError, KeyError) as e:
            rec = {"ok": False, "error": str(e)}
        (d / (f.stem + ".result")).write_text(json.dumps(rec, indent=1) + "\n")
        f.unlink()
        out.append(rec)
    return out


def selftest():
    import tempfile
    root = Path(tempfile.mkdtemp())
    A.STATE = Path(tempfile.mkdtemp())
    pkg = root / "up-x-1111"
    pkg.mkdir()
    for f, t in (("architecture.yaml", "title: a\n"), ("script-source.yaml", "slug: up-x-1111\nurls: {app: http://a/, diagram: http://d/}\n"),
                 ("config.json", "{}"), ("intro-script.md", "## [Tyler] Intro (1 s)\nHi.\n")):
        (pkg / f).write_text(t)
    ok = [classify("make the diagram bigger") == "diagram", classify("shorter first line of the script") == "script", classify("the briefing page needs a reject button") == "app"]
    for w in ("make it nicer", "the diagram and the script both"):
        try:
            classify(w)
            ok.append(False)
        except Ambiguous:
            ok.append(True)
    ran = {}

    def worker(a, w, p, c):
        f = p / ARTIFACTS[a]["file"]
        f.write_text(f.read_text() + "# edited: " + w + "\n")   # an edit that keeps the file valid

    def gates_ok(p, only):
        ran["only"] = only
        return {"gates": [{"id": i, "name": f"g{i}", "status": "pass", "why": []} for i in range(1, 6)]}
    shots = []
    steps = {"worker": worker, "rerender": lambda a, j, p: None, "gates": gates_ok, "shoot": lambda u, o, b: (shots.append((u, b)), Path(o).write_bytes(b"png"))}
    r = revise("up-x-1111", "make the diagram bigger", pkg_root=root, steps=steps)
    ok += [r["ok"], r["artifact"] == "diagram", ran["only"] == [2, 4], len(shots) == 2 and shots[0][0] == "http://d/", (pkg / "revisions/01/before.png").is_file(),
           (pkg / "revisions/01/after.png").is_file(), json.loads((pkg / "reload.json").read_text())["rev"] == 1, r["within_target"]]
    r2 = revise("up-x-1111", "shorter first line of the script", pkg_root=root, steps=dict(steps, shoot=None))
    ok += [r2["ok"], ran["only"] == [3, 4, 5], (pkg / "revisions/02/script.diff").is_file(), r2["rev"] == 2]

    def sneaky(a, w, p, c):
        (p / "config.json").write_text("changed")
        (p / "architecture.yaml").write_text("changed")
    keep = (pkg / "architecture.yaml").read_text()
    r3 = revise("up-x-1111", "make the diagram bigger", pkg_root=root, steps=dict(steps, worker=sneaky))
    ok += [not r3["ok"] and "must change only architecture.yaml" in r3["error"], (pkg / "config.json").read_text() == "{}", (pkg / "architecture.yaml").read_text() == keep]
    failing = dict(steps, gates=lambda p, only: {"gates": [{"id": 2, "name": "Diagram", "status": "fail", "why": ["caption repeats the title"]}]})
    r4 = revise("up-x-1111", "make the diagram bigger", pkg_root=root, steps=failing)
    ok += [not r4["ok"] and "caption repeats" in r4["error"] and (pkg / "architecture.yaml").read_text() == keep]   # a failed gate restores the files
    (A.STATE / "revise-inbox").mkdir(parents=True)
    (A.STATE / "revise-inbox" / "a.json").write_text(json.dumps({"job": "up-x-1111", "text": "make it nicer"}))
    res = inbox(root, steps=steps)
    ok += [len(res) == 1 and not res[0]["ok"] and "name no artifact" in res[0]["error"], not list((A.STATE / "revise-inbox").glob("*.json"))]
    print("self-test", "PASS" if all(ok) else f"FAIL {[i for i, v in enumerate(ok) if not v]}")
    return 0 if all(ok) else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    root = Path(argv[argv.index("--pkg-root") + 1]) if "--pkg-root" in argv else None
    if argv[:1] == ["revise"] and len(argv) >= 3:
        art = argv[argv.index("--artifact") + 1] if "--artifact" in argv else None
        try:
            rec = revise(argv[1], argv[2], art, root, test="--test" in argv)
        except (Ambiguous, FileNotFoundError) as e:
            print("REFUSED:", e)
            return 2
        print(json.dumps(rec, indent=1))
        return 0 if rec["ok"] else 1
    if argv[:1] == ["inbox"]:
        print(json.dumps(inbox(root), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
