#!/usr/bin/env python3
"""quote_check.py: fail when a quoted line is not in the file it cites. Stdlib only.

Checked: every {"cite", "text"} in systems/*/system.json `quotes` (the cite must be one of that system's copies or
basis cites), and every `> the line (kit:id)` or `(lib:id)` in library/kit/writeups/. Runs of whitespace compare as
one space; nothing else is normalised. Also fails on a manifest that is malformed or cites a missing file.
"""
import re
import sys

import kit
import systems

QUOTE_LINE = re.compile(r"^>\s+(.+?)\s+\(((?:kit|lib):[\w./-]+)\)\s*$", re.M)


def squash(text):
    return " ".join(text.split())


def contains(ref, quote, library=None):
    p = kit.resolve(ref, library)
    files = [p] if p.is_file() else sorted(p.rglob("*.md"))
    q = squash(quote)
    return bool(q) and any(q in squash(f.read_text(encoding="utf-8")) for f in files)


def check(systems_root=None, library=None):
    """(number of quotes checked, list of failures)."""
    n, bad = 0, []
    found = systems.load_all(systems_root)
    if not found:
        bad.append("no systems/*/system.json found")
    for name, system in found.items():
        shape = systems.problems(name, system, library)
        bad += [f"{name}: {p}" for p in shape]
        if shape:
            continue
        allowed = set(systems.cited(system))
        for quote in system["quotes"]:
            n += 1
            ref, text = quote.get("cite", ""), quote.get("text", "")
            if ref not in allowed:
                bad.append(f"{name}: quote cites {ref!r}, which the system neither copies nor lists in a basis")
            elif not contains(ref, text, library):
                bad.append(f"{name}: not in {ref}: {text!r}")
    writeups = (library or kit.library()) / "kit" / "writeups"
    for f in sorted(writeups.glob("*.md")):
        for text, ref in QUOTE_LINE.findall(f.read_text(encoding="utf-8")):
            n += 1
            try:
                if not contains(ref, text, library):
                    bad.append(f"{f.name}: not in {ref}: {text!r}")
            except KeyError as e:
                bad.append(f"{f.name}: {e.args[0]}")
    return n, bad


if __name__ == "__main__":
    count, failures = check()
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"{count} quotes checked, {len(failures)} failures")
    sys.exit(1 if failures else 0)
