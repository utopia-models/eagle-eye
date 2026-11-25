#!/usr/bin/env python3
"""vsl_agent.py: the 24/7 loop of agent `vsl`, owner of the whole one-shot VSL backend (knowledge#17978; Tyler 2026-11-24: "agent VSL should be a
24x7 agent like the rest of our 24x7 agents"). Runs AS the unix user `vsl` from vsl-tick.timer every 120 s. No model in the path: the decisions are
oneshot_auto.py's (build the package of a new fit job, the intro timers) and the contract's; a model only runs when the fleetmail postman starts a
`claude -p` turn for a message, in vsl's own brain (net/work/vsl/agent/CLAUDE.md).

  vsl_agent.py tick        one cycle: sync the clone, `oneshot_auto.py tick` (scan the feed, build the next package, refresh stage feed),
                           hand every due intro to upwork once (fleetmail), count unread mail, write the OCC feed. Exit 0 even when a step failed:
                           the failure is recorded as `dark` (the OCC shows the loop red with the real error), never swallowed.
  vsl_agent.py status      the last cycle: when, what it did, what failed.
  vsl_agent.py --self-test

State: ~/.claude/state/vsl-agent/{last.json,actions.jsonl,handed.json}; the OCC feed is ~/.claude/state/occ-usage.json (occ-usage-publish.sh reads it
as `vsl=sudo:vsl`, the file name is the registry id). The Sent ledger is NOT written here on a due intro: sending belongs to the upwork seat, and a
stage is stamped (`oneshot_auto.py mark JOB vsl_sent`) only when upwork reports the send."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
STATE = HOME / ".claude/state/vsl-agent"
FEED = HOME / ".claude/state/occ-usage.json"
CLONE = Path(os.environ.get("VSL_CLONE") or HOME / "kb")
# TODO (Tyler 2026-11-24): move to a vsl-owned source clone, nova not in the chain (this is read-only source, still nova's home today).
SRC_REMOTE = os.environ.get("VSL_SRC") or "/home/nova/dev/utopia-models/knowledge"
INTERVAL = 120
BUILDER_SSH = os.environ.get("VSL_BUILDER_SSH") or "upwork@100.127.249.81"
BUILDER = "/home/upwork/oneshot/kb-v2/net/work/_tools/vsl/oneshot_auto.py"


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd, timeout=150, cwd=None):
    """-> (rc, stdout, stderr). A timeout is rc 124, never an exception."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout {timeout}s: {' '.join(map(str, cmd))}"
    except OSError as e:
        return 127, "", str(e)


SYNC_DIRS = ("net", "wi", "_infra", "_process")


def sync_clone():
    """A private COPY (no .git) of the shared novaserver clone's tracked tree: rsync of the four directories the VSL tools read. Not a git clone: a
    full clone is 4.4 GB of history and two attempts (full, then --depth 1 over file://, 1.6 GB tmp pack) were killed mid-pack; no GitHub credential
    is needed either. Incremental, so a no-change cycle costs a stat pass."""
    CLONE.mkdir(parents=True, exist_ok=True)
    for d in SYNC_DIRS:
        rc, _, err = sh(["rsync", "-a", "--delete", "--exclude", ".git", "--exclude", "node_modules", f"{SRC_REMOTE}/{d}/", f"{CLONE}/{d}/"], timeout=300)
        if rc not in (0, 24):   # 24 = a source file vanished mid-copy (a concurrent reset): the next cycle fixes it
            return f"rsync {d}: rc={rc} {err.strip()[:160]}"
    return None


def mail_stats():
    rc, out, err = sh(["fleetmail", "inbox", "--json"], timeout=30)
    if rc:
        return {"error": (err or out).strip()[:160] or f"rc {rc}"}
    try:
        rows = json.loads(out or "[]")
    except ValueError:
        return {"error": "inbox --json not JSON"}
    ages = []
    for r in rows:
        ts = r.get("sent_at") or r.get("sent") or ""
        try:
            ages.append(int((now() - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds()))
        except ValueError:
            pass
    return {"unread": len(rows), "oldest_unread_age_s": max(ages) if ages else 0}


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def build_vsls():
    """Rebuild the vsls feed (vsls.utopiamodels.ai) from the clone's entries each cycle (knowledge#18122, ask 3316): agent vsl owns the upload.
    Output: ~/.claude/state/vsl-agent/site, which desk-vsl publishes behind Cloudflare Access. Returns an error string or None."""
    rc, out, err = sh(["python3", str(CLONE / "net/work/vsl/vsls/build.py"), "--out", str(STATE / "site")], timeout=120)
    return None if rc == 0 else f"vsls build rc={rc}: {(err or out).strip()[-200:]}"


def publish(last):
    dark = [last["error"]] if last.get("error") else []
    mail = last.get("mail") or {}
    doc = {"agent": "vsl", "fetchedAt": iso(),
           "liveness": {"kind": "timer", "intervalSeconds": INTERVAL, "cycleSeconds": last["cycle_s"], "lastCycleAt": last["at"],
                        "timer": {"unit": "vsl-tick.timer", "active": last["timer_active"]}, "dark": dark,
                        "fleetmail": mail,
                        "stats": {"lastAction": last["action"], "lastActionAt": last["action_at"],
                                  "summary": f"{last['action']} · {last['action_at']}"}}}
    tmp = FEED.with_suffix(".tmp")
    FEED.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(doc, indent=1))
    tmp.replace(FEED)


def tick():
    STATE.mkdir(parents=True, exist_ok=True)
    t0 = now()
    errs, did = [], []
    e = sync_clone()
    if e:
        errs.append(e)
    # The builder (`oneshot_auto.py serve`, 20 s) runs on Ra as `upwork` beside the Eagle Eye feed and the hunts it reads (knowledge#17917); a second
    # builder here would fork the job records. vsl supervises it: `live` carries the builder's last tick (new, started, due_intros) and its heartbeat.
    # Moving the process itself under vsl on Ra is the follow-up (no `vsl` account exists on Ra yet).
    res = {}
    rc, out, err = sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", BUILDER_SSH, f"python3 {BUILDER} live"], timeout=40)
    try:
        live = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        live = None
        errs.append(f"builder probe rc={rc}: {(err or out).strip()[-200:]}")
    if live is not None:
        res = live.get("last") or {}
        if not live.get("live"):
            errs.append(f"builder not ticking: {live.get('why') or live.get('error') or live}"[:240])
        elif live.get("error"):
            errs.append(f"builder last tick failed: {live['error']}"[:240])
    if res.get("new"):
        did.append(f"detected {len(res['new'])} new job(s): {','.join(res['new'][:3])}")
    if res.get("started"):
        did.append(f"building package {res['started']}")
    snd = res.get("intro_send") or {}   # the builder (Ra) runs intro_sender.py: one send order per due job to the upwork seat (knowledge#18249)
    if snd.get("handed"):
        did.append(f"handed {len(snd['handed'])} due intro(s) to upwork: {','.join(snd['handed'][:3])}")
    if snd.get("held"):
        errs.append("intro held: " + ", ".join(f"{k}={v}" for k, v in list(snd["held"].items())[:4]))
    if snd.get("errors"):
        errs.append("intro send failed: " + "; ".join(f"{k}: {v}" for k, v in list(snd["errors"].items())[:2]))
    e = build_vsls()
    if e:
        errs.append(e)
    mail = mail_stats()
    if mail.get("error"):
        errs.append("fleetmail: " + mail["error"])
    prev = load(STATE / "last.json", {})
    rc, _, _ = sh(["systemctl", "--user", "is-active", "vsl-tick.timer"], timeout=10)
    last = {"at": iso(), "cycle_s": int((now() - t0).total_seconds()), "mail": mail, "timer_active": rc == 0,
            "error": "; ".join(errs)[:400] or None,
            "action": "; ".join(did) if did else prev.get("action", "cycle: nothing new"),
            "action_at": iso() if did else prev.get("action_at", iso())}
    (STATE / "last.json").write_text(json.dumps(last, indent=1))
    if did:
        with open(STATE / "actions.jsonl", "a") as f:
            f.write(json.dumps({"at": last["at"], "did": did}) + "\n")
    publish(last)
    print(json.dumps(last))
    return 0


def self_test():
    global STATE, FEED, HOME
    import tempfile
    d = Path(tempfile.mkdtemp())
    STATE, FEED = d / "s", d / "occ-usage.json"
    last = {"at": "2026-11-24T00:00:00Z", "cycle_s": 3, "mail": {"unread": 0, "oldest_unread_age_s": 0}, "timer_active": True,
            "error": None, "action": "built 1", "action_at": "2026-11-24T00:00:00Z"}
    STATE.mkdir()
    publish(last)
    f = json.loads(FEED.read_text())
    assert f["agent"] == "vsl" and f["liveness"]["dark"] == [] and f["liveness"]["stats"]["lastAction"] == "built 1", f
    publish(dict(last, error="boom"))
    assert json.loads(FEED.read_text())["liveness"]["dark"] == ["boom"]
    assert sh(["false"])[0] == 1 and sh(["sleep", "5"], timeout=1)[0] == 124 and sh(["/no/such"])[0] == 127
    print("vsl_agent self-test ok")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--self-test"]:
        sys.exit(self_test())
    if a == ["tick"]:
        sys.exit(tick())
    if a == ["status"]:
        print(json.dumps(load(STATE / "last.json", {"error": "no cycle yet"}), indent=1))
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
