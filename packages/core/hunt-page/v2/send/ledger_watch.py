#!/usr/bin/env python3
"""ledger_watch.py: the FALLBACK path from outward-send facts to Eagle Eye. The main path is push at the source
(ledger.append -> eagle_emit.emit, hunt_send's own forward(), the desk observer, takeflow's render hook); this catches any
writer that does not push yet (a hand `>>` row, proposals.py record_outcome's direct append, a push that hit a down server).

Run by eagle-facts.path (inotify: PathModified on each source file) -> eagle-facts.service (oneshot). Each source is read
from its stored byte offset; every complete new line that states a fact is POSTed to /rest/events (idempotent by key at the
server, forward-only), and the offset advances only past lines the server answered. A 422 (no card and nothing to build one
from) is written to unmatched.jsonl, never dropped; the nightly drift audit reports it. A 5xx or network error stops the run
with exit 1 (systemd retries) and the offset stays, so nothing is lost.

  ledger_watch.py [--source NAME] [--from-start] [--dry-run]
Sources: upwork-ledger (Ra: ~upwork/.claude/state/net/upwork/ledger.jsonl), hunt-send (send/state/send.log).
"""
from __future__ import annotations

import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# the very module the push runs (agent upwork's own clone on Ra; architect reads it through an ACL), so the push and this
# fallback can never map a row two different ways
EMIT_DIR = Path(os.environ.get("EAGLE_EMIT_DIR", "/home/upwork/dev/utopia-models/knowledge/net/work/_tools/upwork"))
sys.path.insert(0, str(EMIT_DIR))
import eagle_emit  # noqa: E402  (knowledge repo: the one mapping from a ledger row to a fact, shared with the push)

# facts older than this predate Eagle Eye v2's live cards (first live ingest 2026-11-21): the 11-15..17 proposals have no
# card and are not re-boarded as 22 auto-created "Sent" rows; the drift audit lists them once as history.
SINCE = os.environ.get("EAGLE_FACTS_SINCE", "2026-11-21T00:00:00Z")
STATE = Path(os.environ.get("EAGLE_FACTS_STATE", Path.home() / ".local/state/eagle-facts"))
SOURCES = {
    "upwork-ledger": os.environ.get("EAGLE_UPWORK_LEDGER", "/home/upwork/.claude/state/net/upwork/ledger.jsonl"),
    "hunt-send": os.environ.get("EAGLE_HUNT_SEND_LOG", str(HERE / "state/send.log")),
}
# hunt_send.py log lines (it already writes the card in the same function; this is only the net under it)
EMAIL = re.compile(r"^(\S+) EMAIL (\S+) (\S+) -> (\S+) \| .* \| gmail (\w+)")
RECORDED = re.compile(r"^(\S+) RECORDED (\S+) (\S+) (\S+) \S+ item ([0-9a-f-]{36})")


def fact_of(source: str, line: str) -> dict | None:
    if source == "upwork-ledger":
        try:
            row = json.loads(line)
        except ValueError:
            return None
        return eagle_emit.fact_from_row(row) if isinstance(row, dict) else None
    if source == "hunt-send":
        m = EMAIL.match(line)
        if m and m.group(2) != "dryrun":
            at, _, slug, to, gid = m.groups()
            return {"kind": "video_attached", "key": f"hunt_send_email:{gid}", "at": at, "itemRef": {"messageId": gid, "slug": slug},
                    "proof": {"gmail_id": gid, "to": to, "source_line": line[:300]}, "source": "hunt-send-log"}
        m = RECORDED.match(line)
        if m and m.group(2) != "dryrun":
            at, _, slug, mp4, item = m.groups()
            return {"kind": "vsl_recorded", "key": f"hunt_send_recorded:{item}:{mp4}", "at": at, "itemRef": {"itemId": item, "slug": slug},
                    "proof": {"render": mp4}, "source": "hunt-send-log"}
    return None


def _load(name: str) -> dict:
    try:
        return json.loads((STATE / f"{name}.offset").read_text())
    except (OSError, ValueError):
        return {}


def _save(name: str, st: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    p = STATE / f"{name}.offset"
    p.with_suffix(".tmp").write_text(json.dumps(st))
    p.with_suffix(".tmp").replace(p)


def run(name: str, path: str, from_start=False, dry=False, post=None, since=None) -> dict:
    since = since or SINCE
    post = post or eagle_emit.post
    out = {"source": name, "facts": 0, "applied": 0, "unchanged": 0, "auto_created": 0, "unmatched": 0}
    try:
        stt = os.stat(path)
    except OSError as e:
        out["error"] = f"unreadable: {e.strerror}"
        return out
    st = {} if from_start else _load(name)
    off = st.get("offset", 0) if st.get("inode") == stt.st_ino and st.get("offset", 0) <= stt.st_size else 0
    with open(path, "rb") as f:
        f.seek(off)
        data = f.read()
    pos = off
    for raw in data.splitlines(keepends=True):
        if not raw.endswith(b"\n"):
            break                                   # a half-written line: wait for the writer's next append
        fact = fact_of(name, raw.decode("utf-8", "replace").strip())
        if fact and fact["at"] < since:
            fact = None                     # before Eagle Eye v2 held cards (history the audit lists, never re-boarded)
        if fact:
            out["facts"] += 1
            if dry:
                print(json.dumps(fact))
            else:
                try:
                    code, body = post([fact])
                except Exception as e:      # Eagle Eye down / no route: stop, keep the offset, systemd retries
                    out["error"] = f"http net: {type(e).__name__}: {str(e)[:150]}"
                    break
                if code >= 500 or code in (401, 403):
                    out["error"] = f"http {code}: {str(body)[:200]}"
                    break                           # offset stays here: the retry starts from this line
                if code == 422 or code == 400:
                    out["unmatched"] += 1
                    STATE.mkdir(parents=True, exist_ok=True)
                    with open(STATE / "unmatched.jsonl", "a") as u:
                        u.write(json.dumps({"source": name, "fact": fact, "http": code, "error": body.get("error")}) + "\n")
                else:
                    r = (body.get("data") or {}).get("applyFacts", [{}])[0]
                    k = {"updated": "applied"}.get(r.get("status"), r.get("status"))
                    if k in out:
                        out[k] += 1
        pos += len(raw)
    if not dry:
        _save(name, {"inode": stt.st_ino, "offset": pos, "path": path})
    out["offset"] = pos
    return out


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--source", choices=sorted(SOURCES))
    a.add_argument("--from-start", action="store_true", help="replay the whole source (idempotent at the server)")
    a.add_argument("--dry-run", action="store_true")
    o = a.parse_args(argv)
    rc = 0
    for name in [o.source] if o.source else SOURCES:
        r = run(name, SOURCES[name], o.from_start, o.dry_run)
        print(json.dumps(r))
        rc |= 1 if r.get("error", "").startswith("http") else 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
