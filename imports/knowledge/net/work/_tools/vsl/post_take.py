#!/usr/bin/env python3
"""post_take.py: agent vsl's post-take clock (knowledge#18931). Starts when Vizier stops recording Tyler's take (or Tyler gives feedback on a cut)
and ends when the finished MP4 is in Tyler's chat; budget 600 s. Everything not dependent on the take is pre-built before it (`prebuild`).

  post_take.py prebuild JOB     the take-independent stages: capture (FIFO seat), demo pages, Gmail clip, script. Run before Tyler records.
  post_take.py run JOB --take FILE [--feedback]   the clock: fetch -> align -> compose -> encode -> deliver. Each stage is one command from the
                                job's stages.json (see STAGES); a stage that exceeds its timeout is substituted (`sub`) or fails loud, never waited on.
  post_take.py watch            poll for a take-stop marker (TAKE_STOP_DIR/*.stop, written by the ETH watcher `eth-sh.sh --vsl`) and `run` it.
  post_take.py queue acquire|release NAME   the capture seat as a FIFO queue (one job at a time, order of arrival), replacing the ad hoc lock.
  post_take.py ledger JOB       print the stage ledger: every stage with work s / wait s and, for a wait, the agent waited on.
  post_take.py --self-test

Ledger: $VSL_ROOT/<job>/ledger.json. A stage is {name, kind work|wait, waited_on, start, end, s, rc, note}. The clock total and the 600 s verdict are
computed from the ledger, never stated. Files live in ONE group-readable dir (setgid, umask 002): VSL_ROOT default /srv/vsl."""
import json, os, subprocess, sys, tempfile, time, fcntl, shlex
from pathlib import Path

ROOT = Path(os.environ.get("VSL_ROOT") or "/srv/vsl")
BUDGET_S = 600
INPUT_TIMEOUT_S = 600          # any outside input: after 10 min vsl does it itself (#18908 scope b)
SEAT_LOCK = Path(os.environ.get("VSL_SEAT_DIR") or ROOT / ".seat-queue")
HERE = Path(__file__).resolve().parent
# name, kind, default command template ({job} {take} {dir} {here}); override per job via <dir>/stages.json {"name": "cmd"}
STAGES = [
    ("fetch",   "work", "bash -c 'cp {take} {dir}/take.mkv'"),   # ETH -> Ra copy is done by the watcher; this lands it in the job dir
    ("align",   "work", "python3 {here}/render/align_take.py {dir}/take.mkv {dir}/align.json"),
    ("compose", "work", "python3 {here}/render/compose_final.py {dir} --take {dir}/take.mkv --align {dir}/align.json"),
    ("encode",  "work", "bash {here}/render/encode_final.sh {dir}"),
    ("deliver", "work", "python3 {here}/render/deliver_final.py {dir}"),
]


def now():
    return time.time()


def umask_group():
    os.umask(0o002)


def jobdir(job):
    d = ROOT / job
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_ledger(d):
    try:
        return json.loads((d / "ledger.json").read_text())
    except (OSError, ValueError):
        return {"stages": []}


def add(d, st):
    L = load_ledger(d)
    L["stages"].append(st)
    tmp = d / "ledger.json.tmp"
    tmp.write_text(json.dumps(L, indent=1))
    tmp.replace(d / "ledger.json")


def run_stage(d, name, kind, cmd, timeout, sub=None, waited_on=None):
    """One stage, timed. On timeout: run `sub` (vsl does it itself) and say so in the note, else rc 124 recorded and the run stops."""
    t0 = now()
    note = ""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        rc, tail = p.returncode, (p.stderr or p.stdout)[-200:]
    except subprocess.TimeoutExpired:
        rc, tail = 124, f"timeout {timeout}s"
        if sub:
            note = f"outside input timed out after {timeout}s (waited on {waited_on}); vsl substituted"
            p = subprocess.run(sub, shell=True, capture_output=True, text=True)
            rc, tail = p.returncode, (p.stderr or p.stdout)[-200:]
    t1 = now()
    add(d, {"name": name, "kind": kind, "waited_on": waited_on, "start": t0, "end": t1, "s": round(t1 - t0, 1), "rc": rc, "note": note or (tail if rc else "")})
    return rc


def summarize(d):
    L = load_ledger(d)["stages"]
    if not L:
        return {"total_s": None, "within_budget": None, "stages": []}
    total = round(L[-1]["end"] - L[0]["start"], 1)
    ok = all(s["rc"] == 0 for s in L)
    return {"total_s": total, "within_budget": ok and total <= BUDGET_S, "all_ok": ok,
            "work_s": round(sum(s["s"] for s in L if s["kind"] == "work"), 1), "wait_s": round(sum(s["s"] for s in L if s["kind"] == "wait"), 1),
            "stages": [{k: s[k] for k in ("name", "kind", "waited_on", "s", "rc", "note")} for s in L]}


def run(job, take, feedback=False):
    umask_group()
    d = jobdir(job)
    (d / "ledger.json").write_text(json.dumps({"stages": [], "clock_started": now(), "feedback": feedback}))
    over = {}
    try:
        over = json.loads((d / "stages.json").read_text())
    except (OSError, ValueError):
        pass
    for name, kind, tpl in STAGES:
        cmd = over.get(name, tpl).format(job=job, take=shlex.quote(str(take)), dir=shlex.quote(str(d)), here=shlex.quote(str(HERE)))
        remaining = max(30, BUDGET_S * 2 - (now() - json.loads((d / "ledger.json").read_text())["clock_started"]))
        if run_stage(d, name, kind, cmd, timeout=remaining):
            break
    s = summarize(d)
    (d / "clock.json").write_text(json.dumps(s, indent=1))
    print(json.dumps({k: s[k] for k in ("total_s", "within_budget", "work_s", "wait_s")}))
    return 0 if s.get("within_budget") else 1


def queue(op, name):
    """FIFO seat: acquire appends a ticket and blocks until it is first; a dead holder's ticket is dropped (pid check). release removes it."""
    SEAT_LOCK.mkdir(parents=True, exist_ok=True)
    mine = SEAT_LOCK / f"{time.time_ns()}-{os.getpid()}-{name}"
    if op == "release":
        for f in SEAT_LOCK.glob(f"*-{name}"):
            f.unlink(missing_ok=True)
        return 0
    mine.write_text(str(os.getpid()))
    while True:
        tickets = sorted(SEAT_LOCK.iterdir())
        for t in tickets:
            try:
                os.kill(int(t.name.split("-")[1]), 0)
            except (ProcessLookupError, ValueError):
                t.unlink(missing_ok=True)
        tickets = sorted(SEAT_LOCK.iterdir())
        if tickets and tickets[0] == mine:
            return 0
        time.sleep(1)


def watch():
    stopdir = Path(os.environ.get("TAKE_STOP_DIR") or ROOT / "take-stop")
    stopdir.mkdir(parents=True, exist_ok=True)
    while True:
        for m in sorted(stopdir.glob("*.stop")):
            info = json.loads(m.read_text())          # {"job": ..., "take": path on Ra, "feedback": bool}
            m.rename(m.with_suffix(".taken"))
            run(info["job"], info["take"], info.get("feedback", False))
        time.sleep(2)


def self_test():
    global ROOT, SEAT_LOCK
    ROOT = Path(tempfile.mkdtemp()); SEAT_LOCK = ROOT / ".q"
    (ROOT / "j1").mkdir()
    take = ROOT / "t.mkv"; take.write_text("x")
    (ROOT / "j1" / "stages.json").write_text(json.dumps({n: "true" for n, _, _ in STAGES} | {"fetch": f"cp {take} {ROOT}/j1/take.mkv"}))
    assert run("j1", take) == 0
    s = json.loads((ROOT / "j1" / "clock.json").read_text())
    assert s["within_budget"] and [x["name"] for x in s["stages"]] == [n for n, _, _ in STAGES], s
    # a failing stage stops the chain and is not within budget
    (ROOT / "j2").mkdir(); (ROOT / "j2" / "stages.json").write_text(json.dumps({"align": "false"}) )
    d = ROOT / "j2"; (d / "ledger.json").write_text(json.dumps({"stages": []}))
    assert run_stage(d, "x", "wait", "sleep 5", timeout=1, sub="true", waited_on="upwork") == 0
    st = load_ledger(d)["stages"][0]
    assert st["waited_on"] == "upwork" and "substituted" in st["note"], st
    assert run_stage(d, "y", "wait", "sleep 5", timeout=1) == 124
    # FIFO
    queue("acquire", "a"); queue("release", "a")
    print("post_take self-test ok")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--self-test"]:
        sys.exit(self_test())
    if a[:1] == ["run"] and "--take" in a:
        sys.exit(run(a[1], a[a.index("--take") + 1], "--feedback" in a))
    if a == ["watch"]:
        watch()
    if a[:2] in (["queue", "acquire"], ["queue", "release"]) and len(a) == 4:
        sys.exit(queue(a[1], a[2 + 1]))
    if a[:1] == ["ledger"] and len(a) == 2:
        print(json.dumps(summarize(jobdir(a[1])), indent=1)); sys.exit(0)
    print(__doc__); sys.exit(2)
