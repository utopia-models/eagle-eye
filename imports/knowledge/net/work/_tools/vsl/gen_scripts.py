#!/usr/bin/env python3
"""gen_scripts.py: ONE source per job -> every take file (Tyler 2026-11-22 6:27 AM ET, one-shot v2 gate 3, 4 and 5).

  gen_scripts.py PKG_DIR        reads PKG_DIR/script-source.yaml, writes in PKG_DIR:
      intro-script.md    [Tyler] Intro, then [AI voice] sections           (take type: intro)
      entire-script.md   every section [Tyler]                             (take type: entire)
      action-script.json one step per AI row (cursor / click / beat, or a hold when the row has no `do`), full words
      tabs.json          exactly two tabs, named, with their reset state
      tabs.txt           the two URLs, diagram first
Source shape (script-source.yaml):
  slug: <job slug>            title: <short name of the app, for the file header in the package only>
  allow_words: [agents]       words the client used themselves (script_check lets them through the banned list)
  urls: {diagram: <url or file://>, app: <url>}
  handoff: "My voice agent will walk you through it."
  sections:
    - {id: intro, heading: Intro, cue: "none: face on screen", lines: ["Hi, I am Tyler Youk, ..."]}
    - {id: app, heading: The working app, cue: "tab 1: ...", lines: [{say: "...", do: {tab: 1, click: nav-workflow}}]}
    - {id: diagram, heading: The diagram, cue: "tab 2: the diagram, beat 1 then 2", lines: ["...", {say: "...", do: {tab: 2, beat: 2}}]}      # short: 12-15 s, the take ends on its last line (no close)
The generated files start at `## [Tyler] Intro`: no title row, no header strip (the prompter adds the job header itself).
"""
import json
import re
import sys
from pathlib import Path

import yaml

import script_rules
WPS = script_rules.rules()["words_per_s"]   # contract length.words_per_s
ROW_WORDS = script_rules.rules()["max_row_words"]   # the row Tyler reads aloud (E6, script_authoring.MAX_ROW_WORDS)


def say(l):
    return l if isinstance(l, str) else l["say"]


def secs(lines):
    return max(1, round(sum(len(say(l).split()) for l in lines) / WPS))


def render(src, take):
    """take = 'intro' (Tyler says the intro only) or 'entire' (every line is Tyler's)."""
    out = []
    for i, s in enumerate(src["sections"]):
        tag = "[Tyler]" if (take == "entire" or i == 0) else "[AI voice]"
        lines = list(s["lines"])
        if take == "intro" and i == 0 and "my ai voice" not in " ".join(say(x) for x in lines).lower():   # v13 intro carries its own handoff
            lines = lines + [src["handoff"]]
        out.append(f"## {tag} {s['heading']} ({secs(lines)} s)")
        out.append(f"[browser] {s['cue']}")
        for l in lines:
            if isinstance(l, dict) and l.get("cue"):
                out.append(f"[browser] {l['cue']}")
            # a row Tyler reads is at most MAX_ROW_WORDS; the filled intro and the verbatim close line are longer, so they are split
            # here at render (phrase breaks, script_rules.split_rows) and stay whole in script-source.yaml for E0/E11 (2026-11-24, 1339/7567)
            t = say(l)
            out += script_rules.split_rows(t, ROW_WORDS) if len(t.split()) > ROW_WORDS else [t]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


SECTION_TAB = {"app": 1, "diagram": 2}   # tab 1 = the app, tab 2 = the diagram (Tyler 7:28 AM ET)


def action_script(src):
    """EXACTLY ONE browser step per AI row, in order, with the row's full words (takeflow/preflight.py sync, chief #15729: the session starts each row's
    step at its audio start). A row with no `do` becomes a hold step (the tab it is spoken over, no click, no beat); the page walk ignores holds."""
    steps = []
    for s in src["sections"]:
        if s["id"] not in SECTION_TAB:
            continue
        for n, l in enumerate(s["lines"]):
            do = dict(l["do"]) if isinstance(l, dict) and l.get("do") else {"tab": SECTION_TAB[s["id"]]}
            steps.append({"section": s["id"], "line": n, "say": say(l), **do})
    return {"slug": src["slug"], "steps": steps}


def tabs(src):
    u = src["urls"]
    return [{"tab": 1, "name": "App", "url": u["app"], "reset": "reload"},          # MVP first (Tyler 7:28 AM ET): tab 1 = the app
            {"tab": 2, "name": "Diagram", "url": u["diagram"], "reset": "#beat=0"}]


def normalize_source(src):
    """A spoken line with an unquoted ': ' inside it ('It is a working app: click the queue') loads from YAML as a one-key mapping, not text (GHL 4047,
    2026-11-23 05:05Z: a KeyError 'say' killed two builds). Repair that shape into {say: 'key: value'}; any other dict line with no `say` is refused by name."""
    for s in src.get("sections", []):
        fixed = []
        for n, l in enumerate(s.get("lines", [])):
            if isinstance(l, dict) and "say" not in l:
                if len(l) == 1 and all(isinstance(k, str) and isinstance(v, str) for k, v in l.items()):
                    (k, v), = l.items()
                    l = {"say": f"{k}: {v}"}
                else:
                    raise ValueError(f"section {s.get('id')} line {n} has no `say` key: {str(l)[:80]}")
            fixed.append(l)
        s["lines"] = fixed
    return src


PLAIN_ITEM = re.compile(r"^(\s*)- (?!say:|do:|\{|\[|\"|')(.*\S.*)$")
LINES_KEY = re.compile(r"^(\s*)lines:\s*$")
SAY_ITEM = re.compile(r"^(\s*)- say: (?![\"'{\[|>])(.*\S.*)$")


def repair_yaml_text(text):
    """Quote every plain spoken row that carries a ': ' INSIDE a `lines:` block (the writer workers keep emitting unquoted colons and YAML then fails with
    'mapping values are not allowed here', GHL 4047 05:10Z). Structure lines (`- id: app`, headings, cues) are never touched: a row is only a list item
    at or below the `lines:` indent, and the block ends at the first line that is not one. Valid text stays byte for byte."""
    out, indent = [], None
    for ln in text.splitlines():
        m = LINES_KEY.match(ln)
        if m:
            indent = len(m.group(1))
            out.append(ln)
            continue
        if indent is not None:
            stripped = ln.lstrip()
            ind = len(ln) - len(stripped)
            if stripped and (ind < indent or (ind == indent and not stripped.startswith("- "))):
                indent = None   # dedented out of the lines block (the next `- id:` section, or a sibling key)
            elif ind != indent or not stripped:
                pass            # a continuation of the previous row (`do:` and its fields): leave it alone
            else:
                m = PLAIN_ITEM.match(ln)
                if m and ": " in m.group(2):
                    q = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
                    ln = f'{m.group(1)}- "{q}"'
                else:
                    m = SAY_ITEM.match(ln)
                    if m and ": " in m.group(2):   # `- say: text: with a colon` (the mapping form) fails the same way
                        q = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
                        ln = f'{m.group(1)}- say: "{q}"'
        out.append(ln)
    return "\n".join(out) + "\n"


def load_source(path):
    """script-source.yaml as a dict; when it is not valid YAML the colon repair runs, the repaired text is WRITTEN BACK (every other reader of the file then
    gets valid YAML) and a note is printed. A file the repair cannot save raises the original error."""
    p = Path(path)
    text = p.read_text()
    try:
        return normalize_source(yaml.safe_load(text))
    except yaml.YAMLError:
        fixed = repair_yaml_text(text)
        src = normalize_source(yaml.safe_load(fixed))   # still invalid: raises, naming the line
        p.write_text(fixed)
        print(f"repaired unquoted colons in {p}", file=sys.stderr)
        return src


def generate(pkg, upwork=False, delivered=False):  # delivered kept for callers; the E5 send-time fill is retired (#17827)
    """upwork=True enforces E1-E5 (upwork_rules, knowledge#17592) BEFORE any file is written: a missing rule raises upwork_rules.Refused and nothing is
    written. delivered=True is the send-time check (two real times, no placeholder)."""
    pkg = Path(pkg)
    if upwork:
        import upwork_rules
        upwork_rules.fill_file(pkg)
        upwork_rules.enforce(pkg, delivered)
    src = load_source(pkg / "script-source.yaml")
    (pkg / "intro-script.md").write_text(render(src, "intro"))
    (pkg / "entire-script.md").write_text(render(src, "entire"))
    (pkg / "action-script.json").write_text(json.dumps(action_script(src), indent=1) + "\n")
    (pkg / "tabs.json").write_text(json.dumps(tabs(src), indent=1) + "\n")
    (pkg / "tabs.txt").write_text("\n".join(t["url"] for t in tabs(src)) + "\n")
    return src


if __name__ == "__main__":
    a = sys.argv[1:]
    up = "--upwork" in a
    try:
        generate(a[0], upwork=up)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ != "Refused":
            raise
        for x in e.fails:
            print(f"REFUSED {x['rule']}: {x['why']}" + (f"  [{x['row']}]" if x["row"] else ""))
        sys.exit(1)
    print("generated", a[0])
