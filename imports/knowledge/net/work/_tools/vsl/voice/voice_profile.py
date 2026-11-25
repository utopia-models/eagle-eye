#!/usr/bin/env python3
"""The one voice source (voice/profile.yaml). `voice_profile.py check <render.json>` = the VERIFY step of knowledge#18736:
exit 0 only when a pick exists, the reference file still hashes to the pinned sha256, and the render sidecar names this profile id."""
import hashlib, json, sys
from pathlib import Path
import yaml

PROFILE = Path(__file__).with_name("profile.yaml")


def load(path=PROFILE):
    return yaml.safe_load(Path(path).read_text())


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check(sidecar, profile=None):
    """-> list of problems (empty = pass)."""
    p = profile or load()
    if not p.get("picked"):
        return ["no voice picked yet (voice/profile.yaml picked: false)"]
    bad = []
    ref = p.get("reference")
    if not ref or not Path(ref).is_file():
        bad.append(f"reference wav missing: {ref}")
    elif sha256(ref) != p.get("reference_sha256"):
        bad.append("reference wav hash differs from the pinned reference_sha256")
    s = json.loads(Path(sidecar).read_text())
    if s.get("voice_profile") != p.get("id"):
        bad.append(f"render voice_profile={s.get('voice_profile')!r} != profile id {p.get('id')!r}")
    if s.get("voice_reference_sha256") != p.get("reference_sha256"):
        bad.append("render voice_reference_sha256 does not match the profile")
    return bad


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit("usage: voice_profile.py check <render-sidecar.json>")
    problems = check(sys.argv[2])
    for x in problems:
        print("FAIL", x)
    print("PASS" if not problems else "FAILED")
    sys.exit(1 if problems else 0)
