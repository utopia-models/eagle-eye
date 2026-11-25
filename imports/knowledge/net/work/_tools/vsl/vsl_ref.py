#!/usr/bin/env python3
"""vsl_ref.py: the reference corpus of our own VSL scripts plus curated exemplars, with local BM25 retrieval (Part of #14969).

  vsl_ref.py index                      build the SQLite FTS5 index (default ~/.cache/vsl-ref/index.sqlite, VSL_REF_DB overrides)
  vsl_ref.py search "text" [-k 3]       top-k by BM25, with provenance
  vsl_ref.py brief BRIEF.yaml [-k 3]    the same, queried from a brief's job, capabilities and take facts
  vsl_ref.py stats                      corpus size by kind and status
  Horus / the Upwork agent, one line:   python3 net/work/_tools/vsl/vsl_ref.py brief <brief.yaml> -k 3

Sources (all under the knowledge checkout, net/work/): vsl/**/(tyler-script|horus-script|runsheet|demo|*-script).md, upwork letters,
proposals and templates, _tools/vsl/tests/golden, _tools/vsl/reference/exemplars (public beat sheets: source URL + licence in front matter).
Metadata per document: kind, client_type, role (first heading), stack (technical terms found), seconds, words, status/version/note from
reference/manifest.yaml. No paid API: sqlite3 FTS5 bm25() only (an embedding column can be added later; this is enough at this size).
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]            # net/work
sys.path.insert(0, str(HERE))
import script_check  # noqa: E402

PATTERNS = ["vsl/**/tyler-script.md", "vsl/**/horus-script.md", "vsl/**/runsheet.md", "vsl/**/demo.md", "vsl/**/*-script.md",
            "upwork/letters/*", "upwork/proposals/*", "upwork/templates/**/*.md", "_tools/vsl/tests/golden/*.md",
            "_tools/vsl/reference/exemplars/*.md"]
STACK = re.compile(r"\b(?:Next\.js|Python|Claude|Postgres|SQL|QuickBooks|Gmail|n8n|Cloudflare|Remotion|FastAPI|Telegram|OpenAI|LLM|"
                   r"Stripe|Odoo|Airtable|HubSpot|GoHighLevel|Docker|AWS|Supabase|React|TypeScript|JavaScript|Node)\b", re.I)
STOP = set("the a an and or of to in for on with is are was be it this that your you i we our at by as from but not no so if "
           "then than into how what who will can has have had do does did just about their they them his her its".split())
WEIGHT = {"accepted": 3.0, "won": 3.0, "recorded": 2.0, "draft": 0.5, "unreviewed": 0.0, "rejected": -99.0, "reference": 1.0}


def db_path():
    return Path(os.environ.get("VSL_REF_DB") or Path.home() / ".cache/vsl-ref/index.sqlite")


def manifest():
    import yaml
    doc = yaml.safe_load((HERE / "reference/manifest.yaml").read_text()) or {}
    return {**(doc.get("auto") or {}), **(doc.get("entries") or {})}     # auto labels (vsl_labels.py) under the curated rows


def front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    import yaml
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


def kind_of(rel):
    n = Path(rel).name
    if "exemplars/" in rel:
        return "exemplar"
    if "golden/" in rel:
        return "golden"
    if rel.startswith("upwork/letters"):
        return "cover-letter"
    if rel.startswith("upwork/proposals"):
        return "proposal"
    if rel.startswith("upwork/templates"):
        return "template-letter"
    for k in ("tyler-script", "horus-script", "runsheet", "demo"):
        if n.startswith(k):
            return k
    return "script"


def client_type(rel, fm):
    if fm.get("client_type"):
        return str(fm["client_type"])
    p = rel.split("/")
    if rel.startswith("vsl/network/"):
        return "network contact (Eagle Eye overview)"
    if rel.startswith("vsl/eagle-eye/"):
        return "Eagle Eye prospect"
    if rel.startswith("vsl/"):
        return "Upwork job: " + p[1] if len(p) > 2 else "intro"
    if rel.startswith("upwork/"):
        return "Upwork letter"
    return "internal"


def build(db=None):
    db = Path(db or db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)
    meta = manifest()
    c = sqlite3.connect(db)
    c.execute("create virtual table docs using fts5(path, title, body, stack, client_type, tokenize='porter unicode61')")
    c.execute("create table info(path primary key, kind, role, seconds, words, status, version, note, source_url, licence)")
    seen = set()
    for pat in PATTERNS:
        for f in sorted(WORK.glob(pat)):
            rel = str(f.relative_to(WORK))
            if rel in seen or not f.is_file() or f.suffix not in (".md", ".txt"):
                continue
            seen.add(rel)
            fm, body = front(f.read_text(errors="replace"))
            m = re.search(r"^#\s+(.+)", body, re.M)
            role = (m.group(1).strip() if m else Path(rel).stem)[:120]
            secs = sum(int(s) for s in script_check.PART.findall(body))
            words = len(" ".join(script_check.spoken(body)).split())
            e = meta.get(rel, {})
            status = e.get("status") or fm.get("status") or "unreviewed"
            stack = ", ".join(sorted({x.group(0) for x in STACK.finditer(body)}, key=str.lower)) or str(fm.get("stack", ""))
            c.execute("insert into docs values (?,?,?,?,?)", (rel, role, body, stack, client_type(rel, fm)))
            c.execute("insert into info values (?,?,?,?,?,?,?,?,?,?)",
                      (rel, kind_of(rel), role, secs or fm.get("seconds"), words, status, e.get("version", ""), e.get("note", ""),
                       fm.get("source_url", ""), fm.get("licence", "")))
    c.commit()
    c.close()
    return len(seen)


def conn():
    db = db_path()
    if not db.exists():
        build(db)
    return sqlite3.connect(db)


def terms(text):
    ws = re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{2,}", text)
    out = []
    for w in ws:
        lw = w.lower().strip(".")
        if lw not in STOP and lw not in out:
            out.append(lw)
    return out[:40]


def search(text, k=3, kinds=("tyler-script", "script", "golden", "exemplar", "cover-letter", "proposal", "template-letter")):
    """-> list of dicts, best first. Rejected scripts are returned only as anti-examples after the good ones are exhausted: never."""
    ts = terms(text)
    if not ts:
        return []
    q = " OR ".join('"%s"' % t.replace('"', "") for t in ts)
    c = conn()
    rows = c.execute("select d.path, bm25(docs, 0, 3.0, 1.0, 2.0, 1.0) s, i.kind, i.role, i.seconds, i.words, i.status, i.version, i.note, "
                     "i.source_url, i.licence, d.client_type, d.stack from docs d join info i using(path) where docs match ? limit 80", (q,)).fetchall()
    out = []
    for r in rows:
        if r[2] not in kinds or r[6] == "rejected":
            continue
        out.append({"path": r[0], "score": round(-r[1] + WEIGHT.get(r[6], 0), 3), "kind": r[2], "role": r[3], "seconds": r[4], "words": r[5],
                    "status": r[6], "version": r[7], "note": r[8], "source_url": r[9], "licence": r[10], "client_type": r[11], "stack": r[12]})
    out.sort(key=lambda x: -x["score"])
    return out[:k]


def brief_text(brief):
    parts = [str(brief.get("job", {}).get("title", "")), *map(str, brief.get("job", {}).get("facts", []) or []),
             *map(str, brief.get("capabilities", []) or [])]
    t = brief.get("take", {}) or {}
    parts += [str(t.get(k, "")) for k in ("role", "hiring_for", "system", "next_step")] + [str(v) for v in (t.get("stack") or {}).values()]
    return " ".join(parts)


def excerpt(rel, n=1400):
    """The part of a script worth copying from: the spoken text of its numbered parts, else the head of the file."""
    p = WORK / rel
    text = p.read_text(errors="replace")
    fm, body = front(text)
    sp = script_check.spoken(body)
    return (" ".join(sp) if sp else body.strip())[:n]


def references_md(brief, k=3):
    """Provenance block that goes into the drafting and critic prompts, and into references.md beside the brief."""
    hits = search(brief_text(brief), k)
    out = ["# References: our own accepted scripts and curated exemplars, retrieved by brief similarity (vsl_ref.py).",
           "Copy the structure, the register and the sentence shapes; never copy a fact. Facts come only from the brief.", ""]
    for i, h in enumerate(hits, 1):
        src = h["source_url"] or f"net/work/{h['path']}"
        out += [f"## Reference {i}: {h['role']}", f"- source: {src}  | kind: {h['kind']} | status: {h['status']} {h['version']} | "
                f"client: {h['client_type']} | {h['seconds'] or '?'} s, {h['words']} spoken words" + (f" | licence: {h['licence']}" if h["licence"] else ""),
                f"- note: {h['note']}" if h["note"] else "- note: none", f"- excerpt: {excerpt(h['path'])}", ""]
    return "\n".join(out), hits


def stats():
    c = conn()
    rows = c.execute("select kind, status, count(*) from info group by 1,2 order by 1,2").fetchall()
    total = c.execute("select count(*) from info").fetchone()[0]
    return total, rows


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, a = argv[0], argv[1:]
    k = int(a[a.index("-k") + 1]) if "-k" in a else 3
    if cmd == "index":
        print(f"indexed {build()} documents -> {db_path()}")
    elif cmd == "stats":
        total, rows = stats()
        print(f"{total} documents")
        for r in rows:
            print(f"  {r[0]:16} {r[1]:11} {r[2]}")
    elif cmd in ("search", "brief"):
        import yaml
        text = a[0] if cmd == "search" else brief_text(yaml.safe_load(Path(a[0]).read_text()))
        for h in search(text, k):
            print(f"{h['score']:7.2f}  {h['path']}  [{h['kind']}, {h['status']} {h['version']}]  {h['client_type']}  {h['seconds'] or '?'}s {h['words']}w")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
