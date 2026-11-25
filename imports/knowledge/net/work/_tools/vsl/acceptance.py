#!/usr/bin/env python3
"""acceptance.py: the measured acceptance of a package's app (Architect 2026-11-22 8:12 MT: "measured, not claimed"). For each package dir it records
  1. the served app: every file and its byte count (wc -c) as Ra serves it, the total, the file count; no iframe, meta refresh or redirect to the diagram
  2. copied_from.md: the real product copied (url, licence, commit), the palette decision and why (copy apps), or "terminal demo, exempt"
  3. a headless click run: every button clicked, which ones changed the page (the click log), contact details seen (must be none)
  4. screenshots of the app and the diagram at 1920x1080 (paths) and the visible-word overlap of the app against the diagram (a perceptual hash cannot
     separate these dark pages: calibrated 2026-11-22, see demo_check.py)
  5. the tab order: tab 1 the app, tab 2 the diagram
Writes PKG/acceptance/report.json, report.md, app.png, diagram.png and PKG/copied_from.md.
  acceptance.py PKG_DIR [PKG_DIR ...]      acceptance.py --self-test
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import demo_check  # noqa: E402
import gates  # noqa: E402


def copied_md(pkg):
    f = Path(pkg) / "copied_from.json"
    if not f.is_file():
        return None
    d = json.loads(f.read_text())
    cands = "\n".join(f"- {c['id']}: {c['why']}" for c in d.get("candidates", []))
    return (f"# Copied from\n\n**Product:** {d['repo']}  \n**URL:** {d['url']}  \n**License:** {d['license']} (read from the GitHub API)  \n**Commit:** {d['commit']}\n\n"
            f"**Why this one:** {d['why']}\n\n**Candidates considered:**\n{cands}\n\n**Palette decision:** {d['palette']['decision']}. {d['palette']['why']}\n\n"
            f"**Diagram source:** {d['diagram_source']['name']}, {d['diagram_source']['url']}. {d['diagram_source'].get('why', '')}\n\n"
            f"**Content files changed:** {', '.join(d.get('content_files_changed', []))}\n")


def measure(pkg):
    import yaml
    pkg = Path(pkg)
    src = yaml.safe_load((pkg / "script-source.yaml").read_text())
    app, dia = src["urls"]["app"], src["urls"]["diagram"]
    out = {"slug": src["slug"], "app_url": app, "diagram_url": dia, "kind": "copy" if (pkg / "copied_from.json").is_file() else "terminal" if (pkg / "terminal.json").is_file() else "template"}
    files = gates.served_files(app)
    out["served_files"] = len(files) if files else None
    out["served_bytes"] = sum(b for _, b in files) if files else None
    out["largest"] = sorted(files, key=lambda x: -x[1])[:4] if files else None
    adir = pkg / "acceptance"
    adir.mkdir(exist_ok=True)
    html = demo_check.fetch(app)
    out["index_html_bytes"] = len(html.encode())
    out["iframe_or_redirect"] = demo_check.static_reasons(html)
    c = gates.probe("clicks", app, 14)
    out["click_log"], out["controls_changed"], out["contact_seen"] = c.get("log", []), c["changed"], c.get("contact", [])
    gates.probe("shot", app, str(adir / "app.png"))
    gates.probe("shot", dia, str(adir / "diagram.png"), 1)
    out["screenshots"] = [str(adir / "app.png"), str(adir / "diagram.png")]
    r = demo_check.check(app, dia)
    out["word_overlap_with_diagram"] = r.get("word_overlap")
    tabs = json.loads((pkg / "tabs.json").read_text())
    out["tab_order"] = [t["name"] for t in tabs]
    md = copied_md(pkg)
    if md:
        (pkg / "copied_from.md").write_text(md)
    out["copied_from_md"] = str(pkg / "copied_from.md") if md else ("terminal demo, exempt" if out["kind"] == "terminal" else "MISSING (template-built)")
    problems = []
    if out["kind"] != "terminal" and (out["served_bytes"] or 0) < 20000:
        problems.append("app under 20 KB or not on Ra")
    if out["iframe_or_redirect"]:
        problems.append("iframe or redirect to the diagram")
    if out["controls_changed"] < 3:
        problems.append("fewer than 3 controls change the page")
    if out["contact_seen"]:
        problems.append("contact details on screen")
    if (out["word_overlap_with_diagram"] or 0) >= demo_check.WORDS_MIN:
        problems.append("the app shows the diagram's words")
    if out["tab_order"] != ["App", "Diagram"]:
        problems.append("tab 1 is not the app and tab 2 the diagram")
    if out["kind"] == "template":
        problems.append("template-built, not a copy of a real application")
    out["pass"] = not problems
    out["problems"] = problems
    (adir / "report.json").write_text(json.dumps(out, indent=1) + "\n")
    (adir / "report.md").write_text(render_md(out))
    return out


def render_md(o):
    lines = [f"# Acceptance: {o['slug']} ({o['kind']}) {'PASS' if o['pass'] else 'FAIL: ' + '; '.join(o['problems'])}",
             f"- app: {o['app_url']}", f"- served: {o['served_files']} files, {o['served_bytes']} bytes; index.html {o['index_html_bytes']} bytes; largest {o['largest']}",
             f"- iframe/redirect/reference to the diagram: {o['iframe_or_redirect'] or 'none'}",
             f"- clicks: {o['controls_changed']} of {len(o['click_log'])} changed the page; contact details seen: {o['contact_seen'] or 'none'}",
             f"- word overlap with the diagram: {o['word_overlap_with_diagram']} (threshold {demo_check.WORDS_MIN})",
             f"- tabs: {o['tab_order']}", f"- screenshots: {', '.join(o['screenshots'])}", f"- copied_from: {o['copied_from_md']}", "", "Click log:"]
    lines += [f"  {c['n']:>2}. {c['button']!r}: {'changed the page' if c['changed'] else 'no change'}" for c in o["click_log"]]
    return "\n".join(lines) + "\n"


def selftest():
    o = {"slug": "x", "kind": "copy", "pass": False, "problems": ["p"], "app_url": "u", "served_files": 2, "served_bytes": 10, "index_html_bytes": 5, "largest": [],
         "iframe_or_redirect": [], "controls_changed": 1, "click_log": [{"n": 1, "button": "Run", "changed": True}], "contact_seen": [], "word_overlap_with_diagram": 0.2,
         "tab_order": ["App", "Diagram"], "screenshots": ["a.png"], "copied_from_md": "x"}
    m = render_md(o)
    ok = ["FAIL: p" in m, "'Run': changed the page" in m, copied_md("/nonexistent") is None]
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "copied_from.json").write_text(json.dumps({"repo": "a/b", "url": "https://github.com/a/b", "license": "MIT", "commit": "abc", "why": "closest",
                                                    "candidates": [{"id": "a", "why": "w"}], "palette": {"decision": "keep", "why": "stronger"},
                                                    "diagram_source": {"name": "C4", "url": "https://c4model.com/"}, "content_files_changed": ["f"]}))
    md = copied_md(d)
    ok += ["**License:** MIT" in md and "Palette decision:** keep" in md]
    print("self-test", "PASS" if all(ok) else f"FAIL {ok}")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--self-test"]:
        sys.exit(selftest())
    res = [measure(p) for p in a]
    for o in res:
        print(render_md(o))
    sys.exit(0 if all(o["pass"] for o in res) else 1)
