#!/usr/bin/env python3
"""copy_lint.py: the one linter for every copy-rules/*.yaml file. Stdlib + PyYAML.

  copy_lint.py RULES FILE [FILE...]     RULES is a name (letter-caveats) or a path; exit 0 PASS, 1 FAIL, 2 usage
  copy_lint.py --self-test

A rules file is DATA: `checks` are patterns that must NOT appear (mode: forbid), `require` are patterns that MUST appear.
The tool-specific linters (letter_lint, upwork_lint, copygate) are this script plus one rules file each:
  letter_lint -> letter-caveats    upwork_lint -> upwork-circumvention    script gate -> video-script    cold email -> outbound-email
"""
import re, subprocess, sys
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent


def load(rules):
    p = Path(rules)
    if not p.exists():
        p = HERE / "copy-rules" / f"{rules}.yaml"
    return yaml.safe_load(p.read_text())


def text_of(path):
    if str(path).lower().endswith(".pdf"):
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    return Path(path).read_text(encoding="utf-8")


def lint(text, rules):
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        for c in rules.get("checks", []):
            m = re.search(c["pattern"], line, re.I)
            if m:
                findings.append((i, c["name"], m.group(0), line.strip()[:100]))
    for c in rules.get("require", []):
        if not re.search(c["pattern"], text, re.I):
            findings.append((0, c["name"], "(missing)", c.get("why", "required pattern absent")))
    return findings


def self_test():
    L = load("letter-caveats")
    assert lint("Hi, I recorded a short video (attached) that walks through your ask.", L) == []
    assert any(f[1] == "cant" for f in lint("I can't do this. Video attached.", L))
    assert any(f[1] == "attachment-line" for f in lint("Hi, I can build this.", L))
    U = load("upwork-circumvention")
    assert lint("Reply here and we will schedule a meeting.", U) == []
    assert {f[1] for f in lint("email me, or pay via paypal", U)} >= {"off-platform-payment", "contact-exchange"}
    V = load("video-script")
    assert lint("I'm Tyler. Here's how the queue retries.", V) == []
    assert any(f[1] == "hype" for f in lint("It's amazing, I'm sure.", V))
    print("self-test ok")
    return 0


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    if len(argv) < 2:
        print(__doc__)
        return 2
    rules, bad = load(argv[0]), 0
    for p in argv[1:]:
        fs = lint(text_of(p), rules)
        for i, n, m, l in fs:
            print(f"{p}:{i}: {n}: '{m}' in: {l}")
        print(f"{p}: {'PASS' if not fs else f'FAIL ({len(fs)} findings)'}")
        bad += len(fs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
