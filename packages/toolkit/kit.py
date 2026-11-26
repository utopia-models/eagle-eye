"""kit.py: resolve kit and library ids to files. Stdlib only.

  kit:<path>   a file or folder under <library>/kit/     (kit:writeups/ocp-wiki)
  lib:<path>   a file under <library>/                   (lib:playbooks/upwork-oneshot)

<library> is $EE_KIT (a consumer's pinned checkout: <checkout>/library) or this repository's library/.
$EE_KIT_OVERLAY is a second, private library/ folder; its sources/<name>/ is read as extra material for basis <name>.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUFFIXES = ("", ".md", ".yaml")


def library():
    return Path(os.environ.get("EE_KIT") or REPO / "library").resolve()


def resolve(ref, root=None):
    """The path a citation id names. Raises KeyError when it names nothing or points outside the library."""
    root = Path(root or library()).resolve()
    scheme, sep, rest = ref.partition(":")
    if not sep or scheme not in ("kit", "lib") or not rest:
        raise KeyError(f"not a citation id: {ref!r}")
    base = root / "kit" if scheme == "kit" else root
    for suffix in SUFFIXES:
        p = (base / (rest + suffix)).resolve()
        if p.exists() and p.is_relative_to(base):
            if p.is_file() or scheme == "kit":
                return p
    raise KeyError(f"{ref}: no such file under {base}")


def read(ref, root=None, limit=12000):
    """Text of a citation id; a folder is its Markdown files joined. Cut at `limit` characters."""
    p = resolve(ref, root)
    files = [p] if p.is_file() else sorted(p.rglob("*.md"))
    return "\n\n".join(f.read_text(encoding="utf-8") for f in files)[:limit]


def overlay(name, limit=12000):
    """The user's private copy of a source, if $EE_KIT_OVERLAY holds one. Empty string otherwise."""
    base = os.environ.get("EE_KIT_OVERLAY")
    folder = Path(base) / "sources" / name if base else None
    if not folder or not folder.is_dir():
        return ""
    return "\n\n".join(f.read_text(encoding="utf-8", errors="replace") for f in sorted(folder.rglob("*.md")))[:limit]
