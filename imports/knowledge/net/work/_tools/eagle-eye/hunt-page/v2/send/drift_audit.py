#!/usr/bin/env python3
"""drift_audit.py: the nightly SAFETY NET under the facts path (never the main path). Diffs every store that records an
outward send against Eagle Eye and fleetmails the Architect each mismatch. Read-only: it fixes nothing itself (the fix for a
missed fact is the writer pushing it; ledger_watch.py --from-start re-delivers ledger rows idempotently).

Checks (each since EAGLE_FACTS_SINCE, Eagle Eye v2's first live cards):
  ledger      every Upwork-ledger fact (proposal_sent / vsl_sent / vsl_recorded) has a card at or past the state it implies
  store       every proposals.db send has a ledger proposal_sent row (proposals.py writes both; a split is a lost count)
  desk        every proposal the desk Chrome landed on (/nx/proposals/<id>?success) has an Eagle Eye touch: the send that
              no writer recorded at all (the 11-22 B2 failure mode)
  hunt-send   every real EMAIL/OFFER hunt_send logged has its touch
  unmatched   facts the server could not place (ledger_watch.py's unmatched.jsonl)
  nova        the novaserver ledger copy has no send fact Ra's lacks (two stores claim to be home since the session moved)

  drift_audit.py [--json] [--no-mail]      exit 0 = no drift, 1 = drift (mailed), 2 = a check could not run (mailed)
"""
from __future__ import annotations

import argparse, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger_watch as LW  # noqa: E402  (same sources, same mapping, same SINCE)

E = LW.eagle_emit
API = E.API
PROPOSALS_DB = os.environ.get("EAGLE_PROPOSALS_DB", "/home/upwork/.claude/state/net/upwork/proposals.db")
DESK_HISTORY = os.environ.get("EAGLE_DESK_HISTORY", "/home/desk-upwork/.config/upwork-chrome/Default/History")
NOVA = os.environ.get("EAGLE_NOVA_SSH", "nova@100.71.25.43")
ORDER = {"stage": ["new", "qualified", "one_shot", "sent", "replied"], "vslStage": ["none", "scripted", "recorded", "rendered", "sent", "watched"]}
WANT = {"proposal_sent": {"stage": "sent"}, "video_attached": {"stage": "sent", "vslStage": "sent"}, "vsl_recorded": {"vslStage": "recorded"},
        "reply_received": {"stage": "replied"}}


def get(path, tok):
    req = urllib.request.Request(API + path, headers={"authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def board(tok):
    items, touches = get("/rest/huntItems?limit=200", tok)["data"]["huntItems"], get("/rest/touches?limit=200", tok)["data"]["touches"]
    return items, touches


def at_least(cur, want, col):
    o = ORDER[col]
    return cur in o and o.index(cur) >= o.index(want) or cur not in o   # replied/roosted/passed count as past


def check_ledger(items, touches, since):
    by_job = {i["externalId"]: i for i in items if i["huntType"] == "upwork"}
    by_pid = {t["providerId"]: t["itemId"] for t in touches if t["channel"] == "upwork" and t.get("providerId")}
    by_id = {i["id"]: i for i in items}
    out, history = [], 0
    for line in open(LW.SOURCES["upwork-ledger"], encoding="utf-8", errors="replace"):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        f = E.fact_from_row(row) if isinstance(row, dict) else None
        if not f:
            continue
        if f["at"] < since:
            history += f["kind"] == "proposal_sent" and not (f["itemRef"].get("job") in by_job)
            continue
        r = f["itemRef"]
        card = by_job.get(r.get("job")) or by_id.get(by_pid.get(r.get("proposalId")))
        if not card:
            out.append({"check": "ledger", "fact": f["key"], "at": f["at"], "why": "no card", "ref": r})
            continue
        for col, want in WANT[f["kind"]].items():
            if not at_least(card[col], want, col):
                out.append({"check": "ledger", "fact": f["key"], "at": f["at"], "item": card["id"], "why": f"{col} is {card[col]}, fact says {want}"})
    return out, history


def check_store(since):
    pids = {json.loads(l).get("proposal_id") for l in open(LW.SOURCES["upwork-ledger"], encoding="utf-8", errors="replace") if '"proposal_sent"' in l}
    c = sqlite3.connect(f"file:{PROPOSALS_DB}?mode=ro", uri=True)
    rows = c.execute("select proposal_id, job_key, sent_at from proposals where sent_at >= ?", (since,)).fetchall()
    return [{"check": "store", "proposal": p, "job": j, "at": a, "why": "in proposals.db, no ledger proposal_sent row"} for p, j, a in rows if p and p not in pids]


def check_desk(touches, since):
    pids = {t.get("providerId") for t in touches if t["channel"] == "upwork"}
    with tempfile.TemporaryDirectory() as d:
        dst = Path(d) / "History"
        with open(dst, "wb") as f:   # the live file is locked by Chrome: read a copy (desk-upwork owns it)
            subprocess.run(["sudo", "-n", "cat", DESK_HISTORY], stdout=f, check=True, timeout=30)
        c = sqlite3.connect(str(dst))
        rows = c.execute("""select url, strftime('%Y-%m-%dT%H:%M:%SZ', last_visit_time/1000000-11644473600, 'unixepoch') from urls
                            where url like '%/nx/proposals/%?success%'""").fetchall()
        c.close()
    out = []
    for url, at in rows:
        m = re.search(r"/proposals/(\d+)\?success", url)
        if m and at >= since and m.group(1) not in pids:
            out.append({"check": "desk", "proposal": m.group(1), "at": at, "why": "submitted in the desk Chrome, no Eagle Eye touch"})
    return out


def check_hunt_send(touches, since):
    ids = {t.get("providerId") for t in touches} | {t.get("threadId") for t in touches}
    out = []
    for line in open(LW.SOURCES["hunt-send"], encoding="utf-8", errors="replace"):
        m = re.match(r"^(\S+) (EMAIL|OFFER) (\S+) .* \| gmail (\w+)", line)
        if m and m.group(3) != "dryrun" and m.group(1) >= since and m.group(4) not in ids:
            out.append({"check": "hunt-send", "gmail": m.group(4), "at": m.group(1), "why": f"{m.group(2)} sent, no touch"})
    return out


def check_unmatched():
    p = LW.STATE / "unmatched.jsonl"
    seen_p = LW.STATE / "unmatched.audited"
    lines = p.read_text().splitlines() if p.exists() else []
    seen = int(seen_p.read_text() or 0) if seen_p.exists() else 0
    out = [{"check": "unmatched", **json.loads(l)} for l in lines[seen:]]
    return out, (seen_p, len(lines))


def check_nova(since):
    cmd = "sudo -n grep -E '\"event\": ?\"(proposal_sent|vsl_sent)\"' /home/upwork/.claude/state/net/upwork/ledger.jsonl"
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", NOVA, cmd], capture_output=True, text=True, timeout=90)
    if r.returncode not in (0, 1):
        raise RuntimeError(f"nova ledger unreadable rc={r.returncode}")
    ra = set(open(LW.SOURCES["upwork-ledger"], encoding="utf-8", errors="replace").read().splitlines())
    out = []
    for l in r.stdout.splitlines():
        try:
            row = json.loads(l)
        except ValueError:
            continue
        if row.get("ts", "") >= since and l not in ra:
            out.append({"check": "nova", "at": row.get("ts"), "event": row.get("event"), "job": row.get("job"), "why": "on novaserver's ledger, not on Ra's"})
    return out


def main(argv=None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--json", action="store_true")
    a.add_argument("--no-mail", action="store_true")
    o = a.parse_args(argv)
    since = LW.SINCE
    tok = E._token()
    drift, errors, notes = [], [], {}
    items, touches = board(tok)
    for name, fn in [("ledger", lambda: check_ledger(items, touches, since)), ("store", lambda: check_store(since)),
                     ("desk", lambda: check_desk(touches, since)), ("hunt-send", lambda: check_hunt_send(touches, since)),
                     ("unmatched", check_unmatched), ("nova", lambda: check_nova(since))]:
        try:
            r = fn()
            if name == "ledger":
                r, notes["pre_v2_proposals_without_card"] = r
            if name == "unmatched":
                r, notes["_unmatched_mark"] = r
            drift += r
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:200]}")
    mark = notes.pop("_unmatched_mark", None)
    report = {"since": since, "cards": len(items), "touches": len(touches), "drift": drift, "errors": errors, **notes}
    print(json.dumps(report, indent=1 if o.json else None))
    rc = 2 if errors else 1 if drift else 0
    if rc and not o.no_mail:
        lines = [f"Eagle Eye drift audit: {len(drift)} mismatch(es), {len(errors)} check(s) failed (since {since})."]
        lines += [f"- {d['check']}: {d.get('why')} | {d.get('fact') or d.get('proposal') or d.get('gmail') or d.get('job') or ''} {d.get('at') or ''}" for d in drift[:25]]
        lines += [f"- check failed: {e}" for e in errors]
        lines.append("Re-deliver ledger rows: python3 ~/dev/utopia-models/eagle-eye-v2/send/ledger_watch.py --from-start")
        subprocess.run(["fleetmail", "send", "agent", "\n".join(lines), "--thread", "eagle-drift"], timeout=60)
    if mark and not o.no_mail:
        mark[0].write_text(str(mark[1]))
    return rc


if __name__ == "__main__":
    sys.exit(main())
