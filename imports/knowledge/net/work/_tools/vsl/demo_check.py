#!/usr/bin/env python3
"""demo_check.py: a package's demo page must be a real page, never the architecture diagram (Tyler 2026-11-22 6:20 AM ET: job 1's
"working app" was the diagram in an iframe).  Fails the package when the demo page
  - holds an iframe, a meta refresh or a script redirect to the architecture page, or any reference to architecture.html
  - ends up (after redirects) on an architecture URL
  - shows the diagram's words: the visible words of all its frames overlap the diagram's by WORDS_MIN or more (Jaccard)
Reported, not failed: `controls` (buttons, inputs), `kind` (interactive or static; a terminal-output demo is static) and `distance` (a 576-bit
dHash of the screenshots). The hash does NOT gate: calibrated 2026-11-22 on real pages it could not separate the diagram from itself (0.064 of bits
differ, the page animates) from different dark pages (0.07-0.12), so a threshold either missed the iframe or flagged real demos.
  python3 demo_check.py DEMO_URL [ARCH_URL]    exit 1 on a failure, prints one JSON line
  python3 demo_check.py --package SLUG BASE    BASE like https://host:8450/hunts ; checks BASE/SLUG/demo/index.html and BASE/SLUG/mvp/
  python3 demo_check.py --self-test"""
import json
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDS_MIN = 0.6   # Jaccard of the visible word sets: at or above this the demo is the diagram
ARCH = re.compile(r"architecture(?:/architecture)?\.html|/architecture/", re.I)


def static_reasons(html):
    rs = []
    if re.search(r"<iframe\b", html, re.I):
        rs.append("demo page holds an iframe (the diagram in a frame is not a working app)")
    if ARCH.search(html):
        rs.append("demo page references the architecture page")
    if re.search(r"<meta[^>]+http-equiv=[\"']?refresh", html, re.I):
        rs.append("demo page redirects with a meta refresh")
    if re.search(r"location(?:\.href|\.replace|\.assign)?\s*(?:=|\()", html) and ARCH.search(html):
        rs.append("demo page redirects by script to the architecture page")
    return rs


def hamming(a, b):
    return sum(x != y for x, y in zip(a, b)) if len(a) == len(b) else 64


def overlap(a, b):
    a, b = set(a), set(b)
    return round(len(a & b) / len(a | b), 3) if (a | b) else 0.0


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "demo-check"})
    return urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()).read().decode("utf-8", "replace")


def shot(url, out):
    r = subprocess.run(["node", str(HERE / "demo_shot.cjs"), url, str(out)], capture_output=True, text=True, timeout=110)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-200:] or "shot failed")
    return json.loads(r.stdout.strip().splitlines()[-1])


def check(demo_url, arch_url=None, workdir=None):
    """-> {"pass", "reasons", "controls", "bytes", "distance", "kind"}."""
    out = {"url": demo_url, "pass": True, "reasons": [], "controls": None, "distance": None}
    try:
        html = fetch(demo_url)
    except Exception as e:
        return dict(out, **{"pass": False, "reasons": [f"demo page unreachable: {e}"]})
    out["reasons"] += static_reasons(html)
    wd = Path(workdir or tempfile.mkdtemp(prefix="demo-check-"))
    try:
        d = shot(demo_url, wd / "demo.png")
        out["controls"], out["bytes"] = d["controls"], d["bytes"]
        if ARCH.search(d["final"]):
            out["reasons"].append(f"demo page ends on the architecture page ({d['final']})")
        if arch_url:
            try:
                a = shot(arch_url, wd / "arch.png")
                out["distance"] = round(hamming(d["dhash"], a["dhash"]) / max(1, len(d["dhash"])), 3)
                out["word_overlap"] = overlap(d.get("words", []), a.get("words", []))
                if out["word_overlap"] >= WORDS_MIN:
                    out["reasons"].append(f"demo page shows the diagram (visible words overlap {out['word_overlap']} >= {WORDS_MIN})")
            except Exception as e:   # no diagram to compare against is neither a pass nor a fail by itself
                out["arch_note"] = f"no diagram screenshot: {e}"
    except Exception as e:
        out["reasons"].append(f"could not render the demo page: {e}")
    out["pass"] = not out["reasons"]
    out["kind"] = "interactive" if (out["controls"] or 0) >= 3 else "static"
    return out


def package(slug, base):
    """Both the demo page and the MVP page of one job; the diagram is the reference."""
    arch = f"{base}/{slug}/demo/architecture/architecture.html"
    return {u: check(u, arch) for u in (f"{base}/{slug}/demo/index.html", f"{base}/{slug}/mvp/")}


def selftest():
    ok = [static_reasons('<iframe src="architecture/architecture.html"></iframe>') != [],
          static_reasons('<meta http-equiv="refresh" content="0;url=x">') != [],
          static_reasons('<script>location.href="/hunts/x/demo/architecture/architecture.html"</script>') != [],
          static_reasons("<main><button>Run</button><pre>1196 orders kept</pre></main>") == [],
          overlap(["a", "b"], ["a", "b"]) == 1.0, overlap(["a"], ["b"]) == 0.0, overlap([], []) == 0.0,
          hamming("0" * 64, "0" * 64) == 0, hamming("0" * 64, "1" * 12 + "0" * 52) == 12, hamming("01", "0") == 64]
    print("self-test", "PASS" if all(ok) else f"FAIL {ok}")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--self-test"]:
        sys.exit(selftest())
    if a[:1] == ["--package"]:
        res = package(a[1], a[2].rstrip("/"))
        for r in res.values():
            print(json.dumps(r))
        sys.exit(0 if all(r["pass"] for r in res.values()) else 1)
    r = check(a[0], a[1] if len(a) > 1 else None)
    print(json.dumps(r))
    sys.exit(0 if r["pass"] else 1)
