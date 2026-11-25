#!/usr/bin/env python3
"""library_index.py: build and query the Eagle Eye library index. Stdlib only.

  library_index.py build  [--root DIR] [--overlay DIR]   write index.json + llms.txt under --root
  library_index.py search QUERY [--root DIR] [--overlay DIR] [--limit N] [--json]
  library_index.py check  [--root DIR]                   exit 1 when a public path holds private/third-party text

An entry is any .md/.yaml/.yml/.txt/.tsv file. Markdown front-matter (---) supplies id, title, kind, tags;
without it the title is the first heading (or the file name) and the tags are the path parts.
--overlay is a second library tree (the private overlay's library/); its entries carry origin "overlay"
and override a public entry with the same id (Fabric-style override by name).
Search is lexical: every query word must appear in title, tags, path or body; score = title 5, tags 3, path 2, body hits capped at 5.
"""
import argparse, json, re, sys
from pathlib import Path

EXT = {".md", ".yaml", ".yml", ".txt", ".tsv"}
SKIP = {"index.json", "llms.txt", "library_index.py"}
PRIVATE_MARKERS = ("Private course content", "Do not publish", "learn.clientascension.com")
PRIVATE_PATHS = ("sources/fazio", "_private")


def front(text, whole=False):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m or whole:
        for line in (m.group(1) if m else text).splitlines():
            k, _, v = line.partition(":")
            if k.strip() and not line.startswith((" ", "-")):
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                meta[k.strip()] = v.strip("'\"") if isinstance(v, str) else v
    return meta, (text[m.end():] if m else text)


def entries(root, origin):
    root = Path(root)
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in EXT or p.name in SKIP or p.name.startswith("."):
            continue
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        meta, body = front(text, p.suffix in (".yaml", ".yml"))
        h = re.search(r"^#\s+(.+)$", body, re.M)
        parts = rel.rsplit(".", 1)[0].split("/")
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        out.append({"id": meta.get("id") or (".".join(parts[:2]) if len(parts) > 1 else parts[0]),
                    "title": meta.get("title") or (h.group(1).strip() if h else p.stem.replace("-", " ")),
                    "kind": meta.get("kind") or parts[0], "tags": list(tags) + [x for x in parts[:-1]],
                    "path": rel, "origin": origin, "version": meta.get("version", ""), "_body": body.lower()})
    return out


def load(root, overlay=None):
    es = {e["path"]: e for e in entries(root, "public")}
    if overlay:
        for e in entries(overlay, "overlay"):
            es[e["path"]] = e          # same path in the overlay overrides the public entry
    return sorted(es.values(), key=lambda e: e["path"])


def score(e, words):
    t, tg, pa = e["title"].lower(), " ".join(e["tags"]).lower(), e["path"].lower()
    s = 0
    for w in words:
        hit = (w in t) * 5 + (w in tg) * 3 + (w in pa) * 2 + min(e["_body"].count(w), 5)
        if not hit:
            return 0
        s += hit
    return s


def search(es, query, limit=10):
    words = re.findall(r"[a-z0-9]+", query.lower())
    scored = sorted(((score(e, words), e) for e in es), key=lambda x: (-x[0], x[1]["path"]))
    return [{k: v for k, v in e.items() if k != "_body"} | {"score": s} for s, e in scored if s][:limit]


def build(root, overlay):
    es = load(root, overlay)
    pub = [{k: v for k, v in e.items() if k != "_body"} for e in es if e["origin"] == "public"]
    (Path(root) / "index.json").write_text(json.dumps(pub, indent=1) + "\n")
    lines = ["# Eagle Eye library", "", "> Playbooks, meta prompts, templates, research and copy rules. Plain Markdown and YAML; any LLM or human can read them.", ""]
    for kind in sorted({e["kind"] for e in pub}):
        lines += [f"## {kind}"] + [f"- [{e['title']}]({e['path']})" for e in pub if e["kind"] == kind] + [""]
    (Path(root) / "llms.txt").write_text("\n".join(lines))
    return len(pub)


def check(root):
    bad = []
    for e in entries(root, "public"):
        if any(e["path"].startswith(p) or f"/{p}" in e["path"] for p in PRIVATE_PATHS):
            bad.append((e["path"], "private path in the public tree"))
        for m in PRIVATE_MARKERS:
            if m.lower() in e["_body"]:
                bad.append((e["path"], f"private marker: {m}"))
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "search", "check"])
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--root", default=str(Path(__file__).parent))
    ap.add_argument("--overlay")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(f"indexed {build(a.root, a.overlay)} public entries")
    elif a.cmd == "check":
        bad = check(a.root)
        for p, why in bad:
            print(f"FAIL {p}: {why}")
        print("ok: no private text in public paths" if not bad else f"{len(bad)} findings")
        return 1 if bad else 0
    else:
        hits = search(load(a.root, a.overlay), a.query, a.limit)
        if a.json:
            print(json.dumps(hits, indent=1))
        else:
            for h in hits:
                print(f"{h['score']:>3} [{h['origin']}] {h['path']}  {h['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
