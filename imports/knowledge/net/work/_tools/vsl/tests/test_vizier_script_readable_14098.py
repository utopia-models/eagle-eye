#!/usr/bin/env python3
"""knowledge#14098 (repeat correction, Tyler 2026-11-16): "the script is so shit ... there is no context, so I can't read
context on what is going on". For the newest staged script of every job that has a package, Vizier must have:
  - a sibling `-context.md` (the CONTEXT tab; without it the tab is hidden), in point form, naming the job post URL
  - a script of short rows: no spoken row over MAX_WORDS words (the prompter shows one short row per cue, never a paragraph)
  python3 net/work/_tools/vsl/tests/test_vizier_script_readable_14098.py     exit 0 = pass
"""
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "vsl" / "scripts"
MAX_WORDS = 25


def latest_staged():
    best = {}
    for p in SCRIPTS.glob("*-v*.package"):
        m = re.match(r"(.+)-v(\d+)\.package$", p.name)
        if m and (m.group(1) not in best or int(m.group(2)) > best[m.group(1)][0]):
            best[m.group(1)] = (int(m.group(2)), m.group(0)[:-8])
    return [SCRIPTS / f"{stem}.md" for _, stem in best.values()]


def problems():
    out = []
    scripts = latest_staged()
    if not scripts:
        out.append("no staged script (a *.package dir) found")
    for s in scripts:
        ctx = s.with_name(s.stem + "-context.md")
        if not ctx.exists():
            out.append(f"{s.name}: no {ctx.name}; the CONTEXT tab would be hidden")
        else:
            t = ctx.read_text()
            if sum(1 for l in t.splitlines() if re.match(r"\s*-\s", l)) < 3:
                out.append(f"{ctx.name}: not point form")
            if not re.search(r"https://www\.upwork\.com/jobs/\S+", t):
                out.append(f"{ctx.name}: names no job post URL")
        for i, l in enumerate(s.read_text().splitlines(), 1):
            if l and not l.startswith(("#", "[", "-", "<!--", ">")) and len(l.split()) > MAX_WORDS:
                out.append(f"{s.name}:{i}: a spoken row of {len(l.split())} words (max {MAX_WORDS})")
    return out


if __name__ == "__main__":
    p = problems()
    for x in p:
        print("FAIL", x)
    print("RESULT:", "FAIL" if p else "PASS")
    sys.exit(1 if p else 0)
