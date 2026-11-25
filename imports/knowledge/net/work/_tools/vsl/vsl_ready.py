#!/usr/bin/env python3
"""vsl_ready.py: the ONE path to Ready for a take (knowledge#15168). Horus runs it; nothing else marks a take Ready.

  vsl_ready.py [--url http://127.0.0.1:8786] [--out DIR]

Reads Vizier's GET /approval and GET /state, re-runs gate 6a (script_check --asset, client-first, copy stage on) on the LIVE script text so a
stale report cannot pass it, and refuses unless every non-advisory gate in the gate report passes for THIS script version. There is NO approval step
(Tyler 2026-11-24, knowledge#18086: "Remove all gates"): passing checks alone make a take READY; any `approval:` refusal Vizier still
reports is ignored. Refusals name the failing gate. On READY it writes
`<out>/<sha>.json` (sha, approver, approved-at, gates) and exits 0; any refusal exits 1, Vizier unreachable exits 2.
"""
import json, os, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import script_check

OUT = Path(os.environ.get("VSL_READY_DIR", "~/.local/state/vizier-ready")).expanduser()


def get(url, path):
    with urllib.request.urlopen(url.rstrip("/") + path, timeout=10) as r:
        return json.load(r)


def decide(approval, text):
    """-> refusals (empty = READY). `approval` is GET /approval, `text` the live speaker script."""
    rs = [r for r in approval.get("ready", {}).get("refusals", []) if not str(r).lstrip().lower().startswith("approval")]
    if text is None:
        rs.append("script: no speaker script text")
        return rs
    own = script_check.check(text, asset=True, copy=True, client_first=True)
    rs += [f"gate 6a failed (rechecked live): {r}" for r in own]
    return rs


def main(argv):
    url = os.environ.get("VIZIER_URL", "http://127.0.0.1:8786")
    out = OUT
    a = list(argv)
    while a:
        k = a.pop(0)
        if k == "--url" and a:
            url = a.pop(0)
        elif k == "--out" and a:
            out = Path(a.pop(0)).expanduser()
        else:
            print(__doc__); return 2
    try:
        approval, state = get(url, "/approval"), get(url, "/state")
    except Exception as e:
        print(f"REFUSED: Vizier unreachable at {url}: {e}"); return 2
    text = (state.get("speaker_script") or {}).get("text")
    sha = approval.get("sha")
    if (state.get("speaker_script") or {}).get("sha") != sha:
        print("REFUSED: the script changed while reading; run again"); return 1
    rs = decide(approval, text)
    if rs:
        print("REFUSED: not Ready")
        for r in rs:
            print("  -", r)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    ap = approval.get("approval") or {}
    (out / f"{sha}.json").write_text(json.dumps({"sha": sha, "approver": ap.get("approver"), "approved_at": ap.get("at"),
                                                  "ready_at": time.time(), "gates": approval.get("gates")}, indent=1) + "\n")
    print(f"READY {sha} (checks passed, no approval step)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
