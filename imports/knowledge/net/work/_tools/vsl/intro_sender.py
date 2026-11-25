#!/usr/bin/env python3
"""intro_sender.py: the intro auto-send SENDER (knowledge#18249; autosend.py only decides, this acts).

Tyler's card ~13:30Z 2026-11-24: "Cut every gate that blocks a send; fix forward". A DUE job (autosend.due_jobs: 45/30/0 min after READY by fit,
or claimed and not recorded in time) is sent unless exactly one of these holds:
  - the job is closed or private (the record says so: `closed`, `private`, state expired/closed, or `job_status` closed/filled/private)
  - the intro MP4 is missing (`<package>/intro.mp4`, or the record's `intro_mp4`), because the contract delivers an MP4 attached, never a link.
  - VERIFY has not passed for exactly this file (knowledge#18734: `<package>/verify.json`, written by intro_verify.py, with the mp4's sha256): verify_missing |
    verify_stale | verify_failed. Chief receives the failing checks once per file. Tyler 2026-11-24: "VERIFY blocks every send".
Nothing else runs here: gates, script_check, screening and rehearsal are advisories on the record, never a stop.

The send itself is the Upwork seat's (the `upwork` agent, human-style input only: net/work/upwork/RULES.md; Upwork is never driven by CDP or a
script, the account carries a circumvention warning). This module hands the seat one SEND ORDER (fleetmail `upwork`, thread vsl-send) that names the
job link, the MP4 path and the proposal text, once per job (state file), and records the hold reason on the job record when it does not send, so Eagle Eye
shows WHY. The seat stamps the send: `oneshot_auto.py mark JOB vsl_sent`.

  intro_sender.py selftest"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import intro_verify

CLOSED_STATES = {"expired", "closed", "filled", "cancelled", "private"}
PROPOSAL = "I made a short video for you about your project. It's attached."


def hold_reason(job, pkg_root):
    """None when the intro may send, else the one named reason (closed | private | mp4_missing)."""
    if job.get("private") or str(job.get("job_status", "")).lower() == "private":
        return "private"
    if job.get("closed") or job.get("state") in CLOSED_STATES or str(job.get("job_status", "")).lower() in CLOSED_STATES:
        return "closed"
    mp4 = mp4_path(job, pkg_root)
    if not (mp4.is_file() and mp4.stat().st_size > 0):
        return "mp4_missing"
    ok, why = intro_verify.verified(mp4.parent if job.get("intro_mp4") else Path(pkg_root) / job["slug"], mp4)
    return None if ok else why


def mp4_path(job, pkg_root):
    return Path(job.get("intro_mp4") or Path(pkg_root) / job["slug"] / "intro.mp4")


def order_text(job, pkg_root):
    return (f"vsl SEND ORDER (no gates, Tyler 13:30Z): send the intro for job {job['slug']} now. Job: {job.get('link')} . "
            f"Attach the MP4 {mp4_path(job, pkg_root)} (a file, never a link). Proposal text: \"{PROPOSAL}\" signed per RULES. "
            f"Then stamp it: `python3 net/work/_tools/vsl/oneshot_auto.py mark {job['slug']} vsl_sent`.")


def failing_text(job, pkg_root):
    try:
        v = json.loads((mp4_path(job, pkg_root).parent / "verify.json").read_text())
        why = "; ".join(f"{c['id']}: {c['detail']}" for c in v.get("checks", []) if not c["pass"])
    except (OSError, ValueError):
        why = "unreadable verify.json"
    return f"vsl VERIFY FAILED for job {job['slug']}; the intro was NOT sent. Failing checks: {why}"[:900]


def fleetmail_send(to, text, thread):
    p = subprocess.run(["fleetmail", "send", to, text, "--thread", thread], capture_output=True, text=True, timeout=30)
    return p.returncode == 0, (p.stderr or p.stdout).strip()[-200:]


def run(due, load_job, save_job, pkg_root, state_file, now_iso, send=fleetmail_send):
    """-> {"handed": [slug], "held": {slug: reason}, "errors": {slug: msg}}. Each slug is handed once; a hold is recorded on the job record and retried next tick."""
    state_file = Path(state_file)
    try:
        handed = json.loads(state_file.read_text())
    except (OSError, ValueError):
        handed = {}
    out = {"handed": [], "held": {}, "errors": {}}
    for slug in due:
        if slug in handed:
            continue
        j = load_job(slug)
        why = hold_reason(j, pkg_root)
        if why:
            out["held"][slug] = why
            if j.get("send_hold") != why:
                j["send_hold"] = why
                j["send_hold_at"] = now_iso
                if why == "verify_failed":
                    send("chief", failing_text(j, pkg_root), "vsl-verify")
                save_job(j)
            continue
        ok, msg = send("upwork", order_text(j, pkg_root), "vsl-send")
        if not ok:
            out["errors"][slug] = msg or "fleetmail send failed"
            continue
        handed[slug] = now_iso
        j.pop("send_hold", None)
        j["intro_handed_at"] = now_iso
        save_job(j)
        out["handed"].append(slug)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(handed))
    return out


def selftest():
    import tempfile
    d = Path(tempfile.mkdtemp())
    jobs = {s: {"slug": s, "link": f"https://www.upwork.com/jobs/{s}", "state": "ready"} for s in ("ok", "nomp4", "gone", "priv", "bad")}
    jobs["gone"]["closed"] = True
    jobs["priv"]["private"] = True
    jobs["bad"]["gates"] = [{"status": "fail"}]   # a failing gate never holds the send
    for s in ("ok", "gone", "priv", "bad"):
        (d / s).mkdir()
        (d / s / "intro.mp4").write_bytes(b"x")
        (d / s / "verify.json").write_text(json.dumps({"pass": True, "sha256": hashlib.sha256(b"x").hexdigest()}))
    sent = []
    load = lambda s: jobs[s]
    save = lambda j: jobs.__setitem__(j["slug"], j)
    snd = lambda to, text, th: (sent.append((to, th, text)) or (True, ""))
    st = d / "handed.json"
    r = run(["ok", "nomp4", "gone", "priv", "bad"], load, save, d, st, "2026-11-24T13:00:00Z", snd)
    ok = [r["handed"] == ["ok", "bad"], r["held"] == {"nomp4": "mp4_missing", "gone": "closed", "priv": "private"},
          jobs["nomp4"]["send_hold"] == "mp4_missing", len(sent) == 2, sent[0][0] == "upwork" and "intro.mp4" in sent[0][2]]
    r2 = run(["ok", "bad"], load, save, d, st, "2026-11-24T13:01:00Z", snd)       # idempotent: never handed twice
    ok += [r2["handed"] == [] and len(sent) == 2]
    (d / "nomp4").mkdir()
    (d / "nomp4" / "intro.mp4").write_bytes(b"x")
    (d / "nomp4" / "verify.json").write_text(json.dumps({"pass": True, "sha256": hashlib.sha256(b"x").hexdigest()}))
    r3 = run(["nomp4"], load, save, d, st, "2026-11-24T13:02:00Z", snd)           # the MP4 lands: the hold clears and it sends
    ok += [r3["handed"] == ["nomp4"] and "send_hold" not in jobs["nomp4"]]
    r4 = run(["priv"], load, save, d, st, "x", lambda *a: (False, "boom"))
    ok += [r4["held"] == {"priv": "private"}]
    jobs["e"] = {"slug": "e", "link": "l"}
    (d / "e").mkdir()
    (d / "e" / "intro.mp4").write_bytes(b"x")
    (d / "e" / "verify.json").write_text(json.dumps({"pass": True, "sha256": hashlib.sha256(b"x").hexdigest()}))
    r5 = run(["e"], load, save, d, st, "x", lambda *a: (False, "boom"))
    ok += [r5["errors"] == {"e": "boom"} and "e" not in json.loads(st.read_text())]   # a failed send is retried next tick
    jobs["unv"] = {"slug": "unv", "link": "l"}                     # an mp4 with no VERIFY pass is held, and a FAILED one tells chief
    (d / "unv").mkdir()
    (d / "unv" / "intro.mp4").write_bytes(b"x")
    r6 = run(["unv"], load, save, d, st, "x", snd)
    ok += [r6["held"] == {"unv": "verify_missing"} and not r6["handed"]]
    (d / "unv" / "verify.json").write_text(json.dumps({"pass": False, "sha256": hashlib.sha256(b"x").hexdigest(), "checks": [{"id": "orb", "pass": False, "detail": "no orb"}]}))
    n = len(sent)
    r7 = run(["unv"], load, save, d, st, "y", snd)
    ok += [r7["held"] == {"unv": "verify_failed"} and sent[n][0] == "chief" and "orb: no orb" in sent[n][2] and len(sent) == n + 1]
    print("self-test " + ("PASS" if all(ok) else f"FAIL {ok}"))
    return all(ok)


if __name__ == "__main__":
    sys.exit(0 if sys.argv[1:] == ["selftest"] and selftest() else 1)
