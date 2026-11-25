#!/usr/bin/env python3
"""gates.py: the one-shot v2 gates (Tyler 2026-11-22 6:27 AM ET: "so he never catches these"). The gate list lives in the contract
(net/work/vsl/contract/upwork.yaml `gates:`); this file is the mechanism. A package is not built and not READY until every `active`
gate passes; a `needs-recording` gate is reported as pending, never as a pass.

  gates.py run PKG_DIR [PKG_DIR ...]   run every gate, write PKG_DIR/gates.json (plain words for Eagle Eye) and <parent>/gates-feed.json;
                                       exit 1 when an active gate fails
  gates.py plain PKG_DIR               print the last gates.json in plain words
  gates.py --self-test

A package dir holds script-source.yaml (see gen_scripts.py) and its generated files. Page gates run headless WebKit at 1920x1080 on our own
pages (gate_probe.cjs, demo_check.py). Gates 6-8 (orb, sync, pass review) need a recorded take and are pending until one exists.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "vsl" / "contract"))
import contract as C  # noqa: E402
import demo_check  # noqa: E402
import script_check  # noqa: E402

TAG = re.compile(r"^## \[(Tyler|AI voice)\] (.+?)(?: \((\d+) s\))?$")
CONTRACTION = re.compile(r"\b\w+'(?:m|ll|ve|s|re|t|d)\b", re.I)


def contract():
    return C.raw("upwork")


def probe(mode, url, *args):
    r = subprocess.run(["node", str(HERE / "gate_probe.cjs"), mode, url, *map(str, args)], capture_output=True, text=True, timeout=115)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-160:] or "probe failed")
    return json.loads(r.stdout.strip().splitlines()[-1])


def sel(x):
    """A click target: a data-testid (template apps), or an explicit selector (text=..., css=..., role=...) for a copied app that has no test ids."""
    return x if re.match(r"^(text|css|role|xpath)=|^[\[.#]", x) else f'[data-testid="{x}"]'


def reachable(url):
    if url.startswith("file://"):
        return Path(url[7:].split("#")[0].split("?")[0]).is_file()
    try:
        return urllib.request.urlopen(urllib.request.Request(url, method="GET", headers={"User-Agent": "gates"}), timeout=30).status == 200
    except Exception:
        return False


def res(gid, name, why, status=None):
    return {"id": gid, "name": name, "status": status or ("fail" if why else "pass"), "why": why}


# ---------------------------------------------------------------- 1 real app
RA_PUBLIC = Path(__import__("os").environ.get("ONESHOT_RA_PUBLIC") or "/home/architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/public/hunts")


def served_files(app_url):
    """The files Ra serves for an app URL .../hunts/<slug>/mvp/ : [(relative path, bytes)] read from the public dir, or None when not on Ra."""
    m = re.search(r"/hunts/([^/]+)/mvp/?$", app_url)
    d = RA_PUBLIC / m.group(1) / "mvp" if m else None
    if not d or not d.is_dir():
        return None
    return [(str(p.relative_to(d)), p.stat().st_size) for p in sorted(d.rglob("*")) if p.is_file()]


def app_size_reasons(app_url, min_bytes, pkg):
    """A web app is a real multi-file app of at least min_bytes (Architect 2026-11-22: the 1,204-byte iframe page must be impossible to repeat). A terminal
    demo (terminal.json) is a one-page player and exempt from the size floor, never from the iframe and overlap checks."""
    if not min_bytes or ((Path(pkg) / "terminal.json").is_file() and not (Path(pkg) / "copied_from.json").is_file()):   # a copied app is never exempt
        return []
    files = served_files(app_url)
    if files is None:
        return []   # not served from Ra's public dir (a file:// or external URL): the other gate-1 checks still apply
    total = sum(b for _, b in files)
    why = []
    if total < min_bytes:
        why.append(f"the app is {total} bytes in {len(files)} file(s), a real app is at least {min_bytes}")
    if len(files) < 2:
        why.append("the app is a single file, a real app is multi-file")
    return why


def g1_real_app(pkg, src):
    g = contract()["gates"]["real_app"]
    app, diagram = src["urls"]["app"], src["urls"]["diagram"]
    why = []
    d = demo_check.check(app, diagram)
    why += d["reasons"]
    try:
        c = probe("clicks", app, 12)
        if c.get("contact"):   # an email or phone number rendered on a client-facing page (Upwork User Agreement 7.2 covers pages and videos)
            why.append(f"the app shows contact details on screen: {', '.join(c['contact'])}")
        why += app_size_reasons(app, g.get("min_app_bytes", 0), pkg)
        if c["changed"] < g["min_working_controls"]:
            why.append(f"only {c['changed']} of {c['tried']} clicked controls changed the page (need {g['min_working_controls']})")
    except Exception as e:
        why.append(f"could not click through the app: {e}")
    return res(1, "Real app", why)


# ---------------------------------------------------------------- 2 diagram
def g2_diagram(pkg, src):
    g = contract()["gates"]["diagram"]
    why = []
    try:
        d = probe("diagram", src["urls"]["diagram"])
    except Exception as e:
        return res(2, "Diagram", [f"could not read the diagram page: {e}"])
    if d["cap0"] != "none":
        why.append("the caption shows on beat 0 (it repeats the page title)")
    t, h = d.get("pageTitle", "").lower(), d.get("capTitle1", "").lower()
    if t and (h == t or t in h):
        why.append("the caption repeats the page title")
    if d["beats"] < g["min_beats"]:
        why.append(f"{d['beats']} beats, need {g['min_beats']} (an overview plus stepped beats)")
    if any(n == 0 for n in d["lit"]):
        why.append("a beat lights nothing (beats must step through the diagram)")
    if d.get("fontPx", 0) < g["min_font_px"]:
        why.append(f"node text is {d.get('fontPx', 0)} px at 1080p, need {g['min_font_px']}")
    return res(2, "Diagram", why)


# ---------------------------------------------------------------- 3 script
def parse_take(text):
    secs, cur = [], None
    for line in text.splitlines():
        if not line.strip():
            continue
        m = TAG.match(line)
        if m:
            cur = {"tag": m.group(1), "heading": m.group(2), "secs": int(m.group(3) or 0), "cues": [], "lines": []}
            secs.append(cur)
        elif cur is None:
            secs.append(None)
            cur = {"tag": "?", "heading": line, "secs": 0, "cues": [], "lines": []}
        elif line.startswith("[browser]"):
            cur["cues"].append(line)
        else:
            cur["lines"].append(line.strip())
    return secs


def script_reasons(text, take, allow=(), handoff=None, extra_s=0):
    c = contract()
    pr, never = c["prompter"], c["never_spoken"]
    why = []
    first = next((l for l in text.splitlines() if l.strip()), "")
    if first != "## [Tyler] Intro" and not first.startswith("## [Tyler] Intro ("):
        why.append(f"{take}: the file must start at '## [Tyler] Intro' (found {first[:40]!r}: no title row or header strip)")
    if re.search(r"^Rules:|^# ", text, re.M):
        why.append(f"{take}: a title row or rules line is in the file")
    secs = [s for s in parse_take(text) if s]
    for i, s in enumerate(secs):
        want = "Tyler" if (take == "entire" or i == 0) else "AI voice"
        if s["tag"] != want:
            why.append(f"{take}: section '{s['heading']}' is tagged [{s['tag']}], should be [{want}]")
        if not s["cues"]:
            why.append(f"{take}: section '{s['heading']}' has no [browser] cue")
        for l in s["lines"]:
            sents = script_check.sentences(l)
            if len(l.split()) > pr["max_words_per_row"] or len(sents) > pr["max_sentences_per_row"]:
                why.append(f"{take}: row too long for the prompter ({len(l.split())} words, {len(sents)} sentences): '{l[:50]}'")
            for n in script_check.plain_notes([l]):
                if "one idea per line" not in n:
                    why.append(f"{take}: {n}")
            for pat, reason in never.items():
                if "contractions" in reason or (handoff and l == handoff):   # the approved hand-off line says 'voice agent'
                    continue
                m = re.search(pat, l)
                if m and m.group(0).lower().strip("s") not in {a.lower().strip("s") for a in allow}:
                    why.append(f"{take}: '{l[:40]}' breaks: {reason}")
    if "close" in c and secs and len(secs[-1]["lines"]) != c["close"]["max_lines"]:   # Upwork has no close (ADR-card-1122-0750)
        why.append(f"{take}: the close must be exactly {c['close']['max_lines']} spoken line (found {len(secs[-1]['lines'])})")
    if "close" not in c and secs:
        if re.search(r"close", secs[-1]["heading"], re.I):
            why.append(f"{take}: there is no close section; the take ends on the diagram segment")
        dmax = c["length"]["diagram"][1]
        if secs[-1]["secs"] > dmax + extra_s:   # extra_s: the ask + close rows E5 (knowledge#17592) adds after the diagram beats
            why.append(f"{take}: the diagram segment is {secs[-1]['secs']} s, max {dmax} s (short: three or four beats)")
    if take == "intro" and secs:
        body = " ".join(secs[0]["lines"])
        iw = c["intro"]["max_words"]
        if len(body.split()) > iw:
            why.append(f"intro: {len(body.split())} words, max {iw}")
        if not re.search(r"\bmy voice agent\b", body, re.I):
            why.append("intro: no hand-off to 'my voice agent'")
    return why


def g3_script(pkg, src):
    why = []
    order = [s["id"] for s in src["sections"]]
    if order != ["intro", "app", "diagram"]:   # contract sections: intro -> mvp -> diagram, no close
        why.append(f"sections are {order}, the contract order is intro, app (the MVP), diagram")
    allow = src.get("allow_words", [])
    ac = [l["say"] for s in src["sections"] for l in s["lines"] if isinstance(l, dict) and (l.get("ask") or l.get("close"))]
    extra_s = round(sum(len(x.split()) for x in ac) / 2.75)   # the ask + close rows (upwork_rules E5) are spoken after the diagram beats
    for take in ("intro", "entire"):
        f = Path(pkg) / f"{take}-script.md"
        if not f.is_file():
            why.append(f"{take}-script.md is missing")
            continue
        why += script_reasons(f.read_text(), take, allow, src.get("handoff"), extra_s)
    return res(3, "Script", why)


# ---------------------------------------------------------------- 4 action script
def g4_action(pkg, src):
    f = Path(pkg) / "action-script.json"
    if not f.is_file():
        return res(4, "Action script", ["action-script.json is missing"])
    steps = json.loads(f.read_text())["steps"]
    why = []
    if not steps:
        return res(4, "Action script", ["the action script has no steps"])
    tabs = json.loads((Path(pkg) / "tabs.json").read_text())
    app_tab = next((t["tab"] for t in tabs if t["name"] == "App"), 1)
    dia_tab = next((t["tab"] for t in tabs if t["name"] == "Diagram"), 2)
    app_steps = [s for s in steps if s.get("tab") == app_tab and s.get("click")]
    app_sel = [sel(s["click"]) for s in app_steps]
    try:
        if app_sel:   # walk the real app in script order: each target must appear, be enabled and take the click
            found = probe("walk", src["urls"]["app"], *app_sel)
            why += [f"app step '{s['say']}': {k} never became clickable" for s, k in zip(app_steps, app_sel) if not found.get(k)]
        beats = probe("diagram", src["urls"]["diagram"])["beats"]
        why += [f"diagram has no beat {s['beat']} (it has {beats})" for s in steps if s.get("tab") == dia_tab and s.get("beat") is not None and s["beat"] >= beats]
    except Exception as e:
        why.append(f"dry run could not open the pages: {e}")
    return res(4, "Action script", why)


# ---------------------------------------------------------------- 5 tabs
def g5_tabs(pkg, src):
    f = Path(pkg) / "tabs.json"
    if not f.is_file():
        return res(5, "Tabs", ["tabs.json is missing"])
    t = json.loads(f.read_text())
    why = []
    if len(t) != 2:
        why.append(f"{len(t)} tabs, exactly two required")
    for x in t:
        if not x.get("name") or not x.get("reset"):
            why.append(f"tab {x.get('tab')} has no name or no reset state")
        if not reachable(x["url"]):
            why.append(f"tab {x.get('tab')} ({x.get('name')}) is not reachable")
    if len({x.get("name") for x in t}) != len(t):
        why.append("the two tabs share a name")
    txt = (Path(pkg) / "tabs.txt").read_text().split() if (Path(pkg) / "tabs.txt").is_file() else []
    if txt != [x["url"] for x in t]:
        why.append("tabs.txt does not match tabs.json")
    if t and [x.get("name") for x in t] != ["App", "Diagram"]:
        why.append("tab 1 must be the App and tab 2 the Diagram (the MVP comes first)")
    if t and "architecture" in t[0]["url"].lower():
        why.append("tab 1 is the architecture page, not the app")
    return res(5, "Tabs", why)


def g11_copied(pkg, src):
    """The MVP is a COPY of a real application, never a custom design (Tyler 2026-11-22 7:33 AM ET). A web app needs copied_from.json that passes
    oneshot_copy's provenance check (catalog app, permissive license read live, 3 candidates, pick, palette decision, a real diagram source), or a
    waiver written by the Architect (copy-waiver.json: by, why). A terminal demo is not a UI: exempt."""
    pkg = Path(pkg)
    if (pkg / "terminal.json").is_file():
        return res(11, "Copied, not custom", [])
    if (pkg / "copy-waiver.json").is_file():
        w = json.loads((pkg / "copy-waiver.json").read_text())
        if w.get("by") and w.get("why"):
            r = res(11, "Copied, not custom", [])
            r["note"] = f"waived by {w['by']}: {w['why']}"
            return r
    f = pkg / "copied_from.json"
    if not f.is_file():
        return res(11, "Copied, not custom", ["the MVP is not a copy of a real application (no copied_from.json); it is a template-built app"])
    import oneshot_copy
    return res(11, "Copied, not custom", oneshot_copy.provenance_reasons(json.loads(f.read_text()), oneshot_copy.catalog()))


def pending(gid, name, what):
    return res(gid, name, [f"waits for a recorded take: {what}"], "pending")


READY_GATES = {1, 2, 3, 4, 5, 9, 11}   # the gates that decide READY; 6 (orb) and 7 (sync) report preflight but never block a new package (it has no narration yet)


def blocking_gates(out):
    return [x for x in out if x["status"] == "fail" and x["id"] in READY_GATES]


PREFLIGHT = Path(__file__).resolve().parents[2] / "vsl" / "takeflow" / "preflight.py"


def preflight(slug, runner=None):
    """takeflow/preflight.py <slug> --json (chief, knowledge#17017): orb, sync, voice, clip and tabs decided from the take's own files, no test
    recording (Tyler 2026-11-22 18:24Z). Returns {check: {pass, why}} or {"error": why} when it cannot run."""
    import subprocess
    try:
        r = (runner or subprocess.run)([sys.executable, str(PREFLIGHT), slug, "--json"], capture_output=True, text=True, timeout=90)
        return json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:160]}


def preflight_gate(gid, name, key, slug, pf=None):
    pf = pf if pf is not None else preflight(slug)
    if "error" in pf:
        return res(gid, name, [f"preflight did not run: {pf['error']}"], "pending")
    r = pf.get(key) or {}
    return res(gid, name, [] if r.get("pass") else [f"preflight {key}: {r.get('why') or 'no result'}"])


GATES = [g1_real_app, g2_diagram, g3_script, g4_action, g5_tabs]


def run_package(pkg, only=None):
    """Run every gate, or only the gate ids in `only` (a revise re-runs just the affected gates; the others keep their last result)."""
    pkg = Path(pkg)
    src = yaml.safe_load((pkg / "script-source.yaml").read_text())
    prev = {x["id"]: x for x in json.loads((pkg / "gates.json").read_text())["gates"]} if only and (pkg / "gates.json").is_file() else {}
    only = set(only) if only else None
    out = [g(pkg, src) if (not only or i + 1 in only or (i + 1) not in prev) else prev[i + 1] for i, g in enumerate(GATES)]
    pf = preflight(src["slug"])   # gates 6 and 7 are decided from the package files now, no recorded take needed (chief #15729); gate 8 stays the reviewer on the real take
    out += [preflight_gate(6, "Orb", "orb", src["slug"], pf), preflight_gate(7, "Sync", "sync", src["slug"], pf),
            pending(8, "Pass review", "an independent reviewer watches the frames and transcribes the audio of the real take")]
    ok15 = all(x["status"] == "pass" for x in out[:5])
    g11 = g11_copied(pkg, src) if (not only or 11 in only or 11 not in prev) else prev[11]
    out.append(res(9, "Next-job readiness", [] if ok15 and g11["status"] == "pass" and (pkg / "tabs.json").is_file() else ["gates 1 to 5 and 11 must all pass before this package counts as ready"]))
    out.append(res(10, "Eagle Eye row", []))
    out.append(g11)
    doc = {"slug": src["slug"], "ran": sorted(only) if only else "all", "gates": out, "ready": all(x["status"] == "pass" for x in out[:5]) and out[8]["status"] == "pass" and g11["status"] == "pass",
           "blocking": blocking_gates(out)}
    (pkg / "gates.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def plain(doc):
    mark = {"pass": "PASS", "fail": "FAIL", "pending": "WAITING"}
    lines = [f"{doc['slug']}: " + ("READY for the take" if doc["ready"] else "NOT ready")]
    for g in doc["gates"]:
        lines.append(f"  {g['id']:>2} {g['name']:<20} {mark[g['status']]}" + (f"  {g['why'][0]}" if g["why"] else ""))
    return "\n".join(lines)


def run(pkgs):
    docs = [run_package(p) for p in pkgs]
    parent = Path(pkgs[0]).parent
    (parent / "gates-feed.json").write_text(json.dumps([{"slug": d["slug"], "ready": d["ready"], "gates": [{k: g[k] for k in ("id", "name", "status")} | {"why": g["why"][:2]} for g in d["gates"]]} for d in docs], indent=1) + "\n")
    for d in docs:
        print(plain(d))
    return docs


def selftest():
    good = ("## [Tyler] Intro (12 s)\n[browser] none: face on screen\nHi, I am Tyler Youk.\nI read your AI Automation Architect post.\n"
            "I built a diagram and a working app.\nMy voice agent will walk you through it.\n\n"
            "## [AI voice] The diagram (3 s)\n[browser] tab 2: beat 5\nThe next build runs this on your real data.\n")
    HO = "My voice agent will walk you through it."
    ok = [script_reasons(good, "intro", (), HO) == [],
          any("start at" in r for r in script_reasons("# Title\n" + good, "intro")),
          not any("contraction" in r for r in script_reasons(good.replace("I am Tyler", "I'm Tyler"), "intro")),   # contractions are the rule now (knowledge#17441/#17462)
          any("no [browser] cue" in r for r in script_reasons(good.replace("[browser] tab 2: beat 5\n", ""), "intro")),
          any("no close section" in r for r in script_reasons(good.replace("The diagram", "Close"), "intro")),
          any("diagram segment is" in r for r in script_reasons(good.replace("(3 s)", "(40 s)"), "intro")),
          any("tagged" in r for r in script_reasons(good, "entire")),
          any("hand-off" in r for r in script_reasons(good.replace("My voice agent will walk you through it.", "Over to you."), "intro")),
          plain({"slug": "x", "ready": False, "gates": [{"id": 1, "name": "Real app", "status": "fail", "why": ["iframe"]}]}).count("FAIL") == 1]
    print("self-test", "PASS" if all(ok) else f"FAIL {ok}")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--self-test"]:
        sys.exit(selftest())
    if a[:1] == ["plain"]:
        print(plain(json.loads((Path(a[1]) / "gates.json").read_text())))
        sys.exit(0)
    if a[:1] == ["run"] and len(a) > 1:
        sys.exit(1 if any(g["status"] == "fail" for d in run(a[1:]) for g in d["gates"]) else 0)
    print(__doc__)
    sys.exit(2)
