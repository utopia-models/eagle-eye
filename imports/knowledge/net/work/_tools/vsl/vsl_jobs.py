#!/usr/bin/env python3
"""vsl_jobs.py: the Upwork VSL job pipeline, lead to attached MP4 (knowledge#16293, Part of #14969).

  vsl_jobs.py scan      [--ledger F] [--rooms DIR]   every lead (job_read / vsl_pick row) with no finished take and no job -> a job
  vsl_jobs.py stage     JOB|--next                   build script + cue sheet + diagram from the lead's own text, load the prompter
  vsl_jobs.py preflight [JOB] [--no-fix]             camera luma, prompter feed, mic peak, window focus, disk: PASS, or the ONE failing item + ETA
  vsl_jobs.py take-done JOB --file MP4 --transcript T   take QA -> hand the MP4 to the Upwork agent -> load the NEXT lead's package
  vsl_jobs.py status    [--json]                     one row per lead: staged / recorded / attached / replied, DERIVED from the
                                                      job record + the Upwork ledger (nothing here is typed by an agent)
  vsl_jobs.py tick                                   scan + stage every queued job (the timer runs this; the 15-minute clock)
  vsl_jobs.py --selftest

A job is a JSON file in $VSL_JOBS_DIR (default ~/.claude/state/net/vsl-jobs/<job-key>.json): key, title, source (the lead's room /
proposal text file), slug, created_at, staged_at, take, handed_at. Its `status` is NEVER stored: `derive()` reads the record and the
ledger (`script_ready`, `vsl_recorded`, `vsl_sent`, `client_reply`).
Hard stops, never a plausible fill: a lead with no text of its own is `blocked: no lead text`; the script is built by vsl_pipeline.py
from that text alone. No outreach before a finished take (upwork_gate.py is the send gate and is untouched here).
Boxes: the job record and the ledger live on the box that runs the timer (Nova). The prompter is Ra's /srv/talk/scripts (vsl_slot.py's
queue); the laptop is read through Ra's fast.py as vsl_slot.py does. Every outward probe is a function you can replace in tests.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "upwork"))

JOBS_DIR = Path(os.environ.get("VSL_JOBS_DIR") or Path.home() / ".claude/state/net/vsl-jobs")
PKG_ROOT = Path(os.environ.get("VSL_PKG_ROOT") or KNOW / "net/work/vsl")
ROOMS = Path(os.environ.get("VSL_ROOMS_DIR") or KNOW / "net/work/upwork/proposals")
STAGE_SLA_MIN = 15          # acceptance: staged on the laptop within 15 minutes of the lead appearing (the issue's number)
MIC_PEAK_MIN_DBFS = -30.0   # a spoken test line must peak above this (quiet) ...
MIC_PEAK_MAX_DBFS = -3.0    # ... and below this (too hot clips; the 11-18 take was "gain too hot")
LUMA_MIN = 25.0             # mean luma 0-255 of a camera frame; a black camera reads < 10
DISK_MIN_GB = 5.0
ETA = {"camera": "2 min (restart the camera source in OBS)", "prompter": "1 min (reload the script)",
       "mic": "2 min (set input gain, re-test)", "window": "1 min (focus the Profile 10 VSL window)",
       "disk": "10 min (delete archived takes)"}
FINISHED = ("vsl_recorded", "vsl_sent", "job_private")


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def jk(k):
    return str(k or "").strip().lstrip("~")


def parse_iso(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ job records
def job_path(key, jobs=None):
    return Path(jobs or JOBS_DIR) / f"{jk(key)}.json"


def load_job(key, jobs=None):
    p = job_path(key, jobs)
    return json.loads(p.read_text()) if p.is_file() else None


def save_job(job, jobs=None):
    p = job_path(job["key"], jobs)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(job, indent=1) + "\n")


def all_jobs(jobs=None):
    out = []
    for p in sorted(Path(jobs or JOBS_DIR).glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except ValueError:
            continue
    return out


def read_ledger(path=None):
    import ledger as L
    p = path or L.path()
    rows = []
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def row_key(r):
    m = re.findall(r"\d{12,}", str(r.get("job") or r.get("key") or r.get("url") or ""))
    return m[0] if m else jk(r.get("job"))


def find_source(key, title, rooms=None):
    """The lead's own text: a room/proposal file named for the job key. None when there is none (never a fill)."""
    for d in (Path(rooms or ROOMS),):
        for p in sorted(d.glob(f"*{jk(key)}*")) if d.is_dir() else []:
            if p.is_file() and len(p.read_text(errors="ignore").split()) >= 20:
                return str(p)
    return None


# ------------------------------------------------------------------ 1. trigger: scan
ROOM_EVENTS = ("client_reply", "call_booked", "call_held")   # a client who wrote to us: a room, so a lead (Adam, Resul)
LEAD_TEXT_FIELDS = ("text", "body", "message", "quote", "note")


def client_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def room_text(rows, slug):
    """What the lead wrote, from its own client_reply rows (never our notes about it). '' when none."""
    out = []
    for r in rows:
        if r.get("event") == "client_reply" and client_slug(r.get("client")) == slug:
            out += [str(r[f]) for f in LEAD_TEXT_FIELDS if r.get(f)][:1]
    return "\n\n".join(out)


def scan(rows, jobs=None, rooms=None, when=None):
    """Leads with no finished take and no job record -> new job records. A lead is a job post (job_read / vsl_pick row, keyed by
    the job) or a client room (client_reply / call_* row, keyed by the client's name). -> list of created jobs."""
    done = {row_key(r) for r in rows if r.get("event") in FINISHED}
    done |= {client_slug(r.get("client")) for r in rows if r.get("event") in ("vsl_sent", "vsl_recorded") and r.get("client")}
    leads = {}
    for r in rows:
        if r.get("event") in ("job_read", "vsl_pick") and row_key(r):
            leads.setdefault(row_key(r), {}).update({k: v for k, v in r.items() if v not in (None, "")})
        elif r.get("event") in ROOM_EVENTS and client_slug(r.get("client")):
            k = client_slug(r["client"])
            leads.setdefault(k, {}).update({"title": r["client"], "room": True})
    made = []
    for key, r in leads.items():
        if key in done or load_job(key, jobs):
            continue
        title = r.get("title") or r.get("job_title") or key
        src = find_source(key, title, rooms)
        if not src and r.get("room") and len(room_text(rows, key).split()) >= 20:
            sp = Path(jobs or JOBS_DIR) / "rooms" / f"{key}.txt"
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(room_text(rows, key) + "\n")
            src = str(sp)
        suffix = "" if r.get("room") else "-" + key[-4:]
        job = {"key": key, "title": title, "url": r.get("url"), "source": src, "slug": r.get("slug") or (re.sub(
            r"[^a-z0-9]+", "-", f"{title}".lower()).strip("-")[:30].strip("-") + suffix),
               "created_at": iso(when), "staged_at": None, "take": None, "handed_at": None,
               "blocked": None if src else "no lead text: no room or proposal text file for this job, nothing to ground a script in"}
        save_job(job, jobs)
        made.append(job)
    return made


# ------------------------------------------------------------------ 2. stage
def load_prompter(slug, script_path, runner=None):
    """Put the script where Vizier's prompter reads it (Ra /srv/talk/scripts/vsl-<slug>.md, vsl_slot.py's queue). -> (ok, detail)."""
    import vsl_slot
    text = Path(script_path).read_text()
    rc, out, err = (runner or vsl_slot.ra_sh)(
        f"d={vsl_slot.QUEUE_DIR}; mkdir -p \"$d\" && cat > \"$d/vsl-{slug}.md\" && echo ok", stdin=text)
    return rc == 0 and "ok" in out, (out or err).strip()[:120]


def stage(job, jobs=None, pkg_root=None, pipeline=None, loader=None, ledger=None, when=None):
    """Build the package from the lead's own text and load the prompter. -> (ok, detail). Records script_ready on success."""
    if job.get("blocked"):
        return False, job["blocked"]
    # Last-words pre-step (Domain 8 item 8): the client's own latest messages outrank any stage.json (the Lanam lesson).
    import vsl_lastwords
    ok, why = vsl_lastwords.check(read_ledger(ledger) if ledger else read_ledger(), job["key"], job.get("title"))
    if not ok:
        job["blocked"] = why
        save_job(job, jobs)
        return False, why
    out = Path(pkg_root or PKG_ROOT) / job["slug"]
    if pipeline is None:
        import vsl_pipeline
        pipeline = vsl_pipeline.run
    doc = pipeline("upwork-job", job["source"], None, out, job["slug"])
    if not doc.get("pass"):
        job["blocked"] = "package gate failed: " + "; ".join((doc.get("gate_findings") or []) + (doc.get("diagram_problems") or [])
                                                            + (doc.get("build_problems") or []))[:300]
        save_job(job, jobs)
        return False, job["blocked"]
    ok, detail = (loader or load_prompter)(job["slug"], out / "script.md")
    if not ok:
        return False, "prompter load failed: " + detail
    cue = out / "horus-script.md"
    if cue.exists():   # the Eagle script rides with the speaker script: one stage, both tabs (knowledge#16486)
        ok2, d2 = (loader or load_prompter)(job["slug"] + "-horus-script", cue)
        if not ok2:
            return False, "eagle script load failed: " + d2
        detail += "; eagle script loaded"
    job.update(staged_at=iso(when), blocked=None, package=str(out))
    save_job(job, jobs)
    import ledger as L
    row = L.build_row("script_ready", job="~" + job["key"], who="vsl_jobs")
    if ledger:
        L.append(row, ledger)
    else:
        import store_home
        store_home.ledger_append(row)
    return True, f"staged {job['slug']}: script, cue sheet, diagram in {out}; prompter loaded ({detail})"


# ------------------------------------------------------------------ 3. preflight
FAST = os.environ.get("VSL_JOBS_FAST", "/home/eagle/dev/utopia-models/knowledge/net/work/_tools/eth-drive/fast.py")   # vsl_slot.FAST still names the retired eagle user
VSL_WINDOW = os.environ.get("VSL_WINDOW_TITLE", "Profile 10")
CAMERA_WIN = os.environ.get("VSL_CAMERA_WIN", "OBS")


def _fast(cmd, runner=None, timeout=25):
    import vsl_slot
    return (runner or vsl_slot.ra_sh)(f"sudo -n -u eagle timeout 20 python3 {FAST} {cmd}", timeout=timeout)


def _last(t):
    ls = [l.strip() for l in (t or "").strip().splitlines() if l.strip()]
    return ls[-1][:90] if ls else "no output"


def probe_camera(runner=None, **_):
    # a real frame of the laptop's OBS window (fast.py shot --win), mean luma read by ffmpeg signalstats on Ra
    rc, out, err = _fast(f"shot /tmp/vsl-jobs-cam.jpg --win {CAMERA_WIN}", runner)
    if rc == 0:
        import vsl_slot
        rc, out, err = (runner or vsl_slot.ra_sh)(
            "sudo -n -u eagle ffmpeg -v error -i /tmp/vsl-jobs-cam.jpg -vf signalstats,metadata=print:key=lavfi.signalstats.YAVG "
            "-f null - 2>&1 | sed -n 's/.*YAVG=/luma=/p' | head -1")
    m = re.search(r"luma[=: ]+([\d.]+)", out)
    if rc != 0 or not m:
        return False, "camera luma not readable: " + _last(err or out)
    v = float(m.group(1))
    return v >= LUMA_MIN, f"mean luma {v:.0f} (need >= {LUMA_MIN:.0f})"


def probe_prompter(slug="", runner=None, **_):
    import vsl_slot
    rc, out, err = (runner or vsl_slot.ra_sh)(
        f"curl -s -m 4 'http://127.0.0.1:8786/prompter/scripts?file=vsl-{slug}'; echo; curl -s -m 3 http://127.0.0.1:8786/health")
    ok = rc == 0 and '"ok": true' in out.replace('"ok":true', '"ok": true') and slug and "parts" in out
    return bool(ok), "prompter serves the staged script and Vizier is live" if ok else "prompter feed: " + (out or err).strip()[:100]


def probe_mic(runner=None, **_):
    rc, out, err = _fast("record 1500", runner)
    m = re.search(r"peak_dbfs=(-?[\d.]+)", out)
    if rc != 0 or not m:
        return False, "mic level not readable: " + _last(err or out)
    v = float(m.group(1))
    return MIC_PEAK_MIN_DBFS <= v <= MIC_PEAK_MAX_DBFS, f"peak {v:.1f} dBFS (want {MIC_PEAK_MIN_DBFS:.0f}..{MIC_PEAK_MAX_DBFS:.0f})"


def probe_window(runner=None, **_):
    rc, out, err = _fast("windows", runner)
    # `windows` lists top of the z-order first; Vizier's own window always rides on top, so the first other window must be the VSL one
    rest = [l for l in out.splitlines() if "Utopia Vizier" not in l and "Ghost" not in l]
    ok = rc == 0 and bool(rest) and VSL_WINDOW in rest[0]
    return ok, f"{VSL_WINDOW} window is in front" if ok else f"{VSL_WINDOW} window not in front (top: {(rest[0] if rest else out or err).strip()[:70]})"


def probe_disk(path="/srv", runner=None, **_):
    import vsl_slot
    rc, out, err = (runner or vsl_slot.ra_sh)(f"df -Pk {path} | tail -1 | awk '{{print $4}}'")
    try:
        gb = int(out.strip()) / 1048576
    except ValueError:
        return False, "disk not readable: " + (out or err).strip()[:80]
    return gb >= DISK_MIN_GB, f"{gb:.1f} GB free on Ra {path} (need {DISK_MIN_GB:.0f})"


def fix_window(runner=None, **_):
    return _fast(f"focus '{VSL_WINDOW}'", runner)[0] == 0


def fix_prompter(slug="", script=None, loader=None, **_):
    return bool(slug and script) and (loader or load_prompter)(slug, script)[0]


PROBES = (("camera", probe_camera, None), ("prompter", probe_prompter, fix_prompter), ("mic", probe_mic, None),
          ("window", probe_window, fix_window), ("disk", probe_disk, None))


def preflight(slug="", script=None, probes=None, fix=True, **kw):
    """Run every probe; a failing item that has a fixer is fixed once and re-probed. -> {pass, items, failing:{item,detail,eta}|None}.
    Reports ONE failing item (the first), with the ETA to fix it, so the report is a single action."""
    items, failing = {}, []
    for name, probe, fixer in (probes or PROBES):
        ok, detail = probe(slug=slug, **kw)
        fixed = False
        if not ok and fix and fixer:
            try:
                if fixer(slug=slug, script=script, **kw):
                    ok, detail = probe(slug=slug, **kw)
                    fixed = ok
            except Exception as e:  # a fixer that raises is a failed fix, not a crash of the report
                detail += f" (fix raised {type(e).__name__})"
        items[name] = {"pass": ok, "detail": detail + (" (self-fixed)" if fixed else "")}
        if not ok:
            failing.append({"item": name, "detail": detail, "eta": ETA.get(name, "unknown")})
    return {"pass": not failing, "at": iso(), "slug": slug, "items": items, "failing": failing[0] if failing else None,
            "also_failing": [f["item"] for f in failing[1:]]}


def render_report(rep):
    if rep["pass"]:
        return "PREFLIGHT PASS: " + ", ".join(f"{k} ok ({v['detail']})" for k, v in rep["items"].items())
    f = rep["failing"]
    more = f" (also failing: {', '.join(rep['also_failing'])})" if rep["also_failing"] else ""
    return f"PREFLIGHT FAIL: {f['item']}: {f['detail']}. ETA to fix: {f['eta']}{more}"


# ------------------------------------------------------------------ 4+5. take done: QA, hand off, load next
def qa_take(video, transcript, script_text=None):
    """Take QA: the file exists and is non-empty, the transcript has >= 20 words, no URL/hostname spoken, <= 100 s per the take refusal
    list (spec upwork-vsl-system §1 step 6). -> list of refusals."""
    rs = []
    if not (video and Path(video).is_file() and Path(video).stat().st_size > 0):
        rs.append(f"video {video!r} is not a non-empty file")
    t = Path(transcript).read_text(errors="ignore") if transcript and Path(transcript).is_file() else ""
    if len(t.split()) < 20:
        rs.append(f"transcript has {len(t.split())} words (< 20)")
    if re.search(r"utopiamodels|dot ai\b|dot com\b|https?://|www\.", t, re.I):
        rs.append("a URL or hostname is spoken in the transcript")
    return rs


def outbox_path(job, video, outbox=None):
    d = Path(outbox or os.environ.get("VSL_OUTBOX") or "/srv/upwork-vsl/outbox") / dt.date.today().isoformat()
    return d / f"{job['key']}--{job['slug']}{Path(video).suffix or '.mp4'}"


def vsl_check_take(video, take_type=None):
    """vsl check (net/work/vsl/takeflow/vsl_check.py) on a laptop take; writes <stem>-qa.json beside it. -> (qa path, failed checks)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vsl" / "takeflow"))
    import vsl_check
    q = vsl_check.check_file(video, kind="take", take_type=take_type)
    out = Path(video).with_name(Path(video).stem + "-qa.json")
    out.write_text(json.dumps(q, indent=1) + "\n")
    return out, q["failed"]


def take_done(job, video, transcript, jobs=None, ledger=None, outbox=None, stager=None, notify=None, root=None, analyzer=None, checker=None):
    """QA -> vsl check (the VSL contract: laptop capture, picture, mic, length, face) -> record the take (upwork_gate.set_vsl, from the
    passing qa.json only) -> copy to the outbox -> fleetmail the Upwork agent with the draft message -> stage the next lead.
    -> (ok, detail, next_job|None)."""
    rs = qa_take(video, transcript)
    if rs:
        return False, "take QA refused: " + "; ".join(rs), None
    qa, failed = (checker or vsl_check_take)(video, job.get("take_type"))
    if failed:
        return False, f"vsl check FAILED ({', '.join(failed)}): {qa}", None
    import upwork_gate
    upwork_gate.set_vsl(job["key"], video, transcript, who="vsl_jobs", root=root or PKG_ROOT, ledger=ledger, qa=str(qa))
    dest = outbox_path(job, video, outbox)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, dest)
    draft = (f"Job {job['key']} ({job['title']}): the finished take is at {dest}. Attach it to the proposal's own attachment field; "
             f"one fresh short message, no links, no off-platform. Use the lead's own words from the room, nothing invented.")
    (notify or send_to_upwork)(draft)
    job.update(take=str(dest), handed_at=iso())
    save_job(job, jobs)
    nxt = next_queued(jobs)
    msg = f"take QA passed; MP4 handed to the Upwork agent at {dest}"
    msg += "; " + (analyzer or analyze_take)(job, video, root or PKG_ROOT)
    if nxt:
        ok, d = (stager or stage)(nxt, jobs=jobs)
        msg += f"; next lead {nxt['slug']}: {d}"
    return True, msg, nxt


def analyze_take(job, video, root):
    """knowledge#16542: score Eagle's driving + Tyler's delivery on every finished take; best effort, never blocks the handoff.
    Needs the package's speaker script + horus-script and a screen source (route.jsonl, refs/ stills) beside them."""
    pkg = Path(root) / job["slug"]
    script = next((p for p in (pkg / "script.md", pkg / "tyler-script.md") if p.exists()), None)
    if not script or not (pkg / "horus-script.md").exists():
        return "take analysis skipped: no script.md + horus-script.md in the package"
    cmd = [sys.executable, str(Path(__file__).with_name("vsl_take_analyze.py")), "analyze", str(video), "--script", str(script),
           "--cues", str(pkg / "horus-script.md"), "--out", str(pkg / "analysis" / Path(video).stem), "--notify"]
    if (pkg / "route.jsonl").exists():
        cmd += ["--route-log", str(pkg / "route.jsonl")]
    elif (pkg / "refs").is_dir():
        cmd += ["--refs", str(pkg / "refs")]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"take analysis failed: {e}"
    return "take analysis filed in " + str(pkg / "analysis") if r.returncode == 0 else "take analysis exit %d: %s" % (r.returncode, (r.stderr or r.stdout).strip()[-200:])


def send_to_upwork(body):
    r = subprocess.run(["fleetmail", "send", "upwork", body, "--thread", "upwork-vsl"], capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def next_queued(jobs=None):
    for j in sorted(all_jobs(jobs), key=lambda j: j.get("created_at") or ""):
        if not j.get("staged_at") and not j.get("blocked") and not j.get("take"):
            return j
    return None


# ------------------------------------------------------------------ 6. status, derived
def derive(job, rows):
    """-> 'blocked' | 'queued' | 'staged' | 'recorded' | 'attached' | 'replied', from the record + the ledger only."""
    k = job["key"]
    ev = {r.get("event") for r in rows if row_key(r) == k or jk(r.get("client")) == k}
    if "client_reply" in ev:
        return "replied"
    if "vsl_sent" in ev:
        return "attached"
    if "vsl_recorded" in ev or job.get("take"):
        return "recorded"
    if job.get("blocked"):
        return "blocked"
    if job.get("staged_at") or "script_ready" in ev:
        return "staged"
    return "queued"


def status_rows(jobs=None, rows=None):
    rows = rows if rows is not None else read_ledger()
    out = []
    for j in all_jobs(jobs):
        c, s = parse_iso(j.get("created_at")), parse_iso(j.get("staged_at"))
        out.append({"key": j["key"], "slug": j["slug"], "title": j["title"], "status": derive(j, rows), "blocked": j.get("blocked"),
                    "staged_in_min": round((s - c).total_seconds() / 60, 1) if c and s else None})
    return out


def tick(jobs=None, rooms=None, rows=None, stager=None):
    rows = rows if rows is not None else read_ledger()
    made = scan(rows, jobs, rooms)
    res = []
    for j in all_jobs(jobs):
        if not j.get("staged_at") and not j.get("blocked") and not j.get("take"):
            ok, d = (stager or stage)(j, jobs=jobs)
            res.append((j["key"], ok, d))
    return made, res


# ------------------------------------------------------------------ selftest
def _selftest():
    import ledger as L
    n = 0

    def check(c, m):
        nonlocal n
        n += 1
        if not c:
            print("FAIL:", m)
            raise SystemExit(1)

    tmp = Path(tempfile.mkdtemp(prefix="vsl-jobs-"))
    try:
        jobs, rooms, pkg, led = tmp / "jobs", tmp / "rooms", tmp / "pkg", str(tmp / "ledger.jsonl")
        rooms.mkdir()
        (rooms / "0221223000000000001-adam.txt").write_text("We need a Zapier replacement. " * 10)
        rows = [L.build_row("job_read", job="~0221223000000000001", fit=80, attach_ok="yes", title="Adam Zapier"),
                L.build_row("job_read", job="~0221223000000000002", fit=80, attach_ok="yes", title="Resul no text"),
                L.build_row("job_read", job="~0221223000000000003", fit=80, attach_ok="yes", title="Done already"),
                L.build_row("vsl_recorded", job="~0221223000000000003", file="x.mp4", who="t")]
        made = scan(rows, jobs, rooms)
        check({m["key"] for m in made} == {"0221223000000000001", "0221223000000000002"}, "scan makes jobs only for leads with no finished take")
        check(load_job("0221223000000000002", jobs)["blocked"].startswith("no lead text"), "no lead text = blocked, never a fill")
        check(scan(rows, jobs, rooms) == [], "scan is idempotent")
        rows_c = [L.build_row("client_reply", client="Adam Gromling", note="We run a freight brokerage and need " + "quotes parsed from email " * 8),
                  L.build_row("client_reply", client="Resul Aksoy"),
                  L.build_row("client_reply", client="Done Client", note="x " * 30), L.build_row("vsl_sent", client="Done Client", file="a.mp4")]
        mc = {m["key"]: m for m in scan(rows_c, jobs, rooms)}
        check(set(mc) == {"adam-gromling", "resul-aksoy"}, "client rooms are leads; a client with a sent video is not")
        check(mc["adam-gromling"]["source"] and "freight brokerage" in Path(mc["adam-gromling"]["source"]).read_text(), "room job is grounded in what the client wrote")
        check(mc["resul-aksoy"]["blocked"], "a room with no text of the lead's own is blocked, never filled")
        j = load_job("0221223000000000001", jobs)
        check(derive(j, rows) == "queued", "derive queued")
        calls = []
        ok, d = stage(j, jobs, pkg, pipeline=lambda *a: calls.append(a) or {"pass": True}, loader=lambda s, p: (True, "ok"), ledger=led)
        check(ok and calls[0][0] == "upwork-job" and calls[0][1] == j["source"], "stage builds from the lead's own text")
        rows2 = rows + [r for r in read_ledger(led)]
        check(derive(load_job(j["key"], jobs), rows2) == "staged", "derive staged from the record + script_ready row")
        j2 = load_job("0221223000000000002", jobs)
        check(stage(j2, jobs, pkg, pipeline=lambda *a: 1 / 0)[0] is False, "a blocked job never calls the pipeline")
        j3 = dict(j, key="9", slug="g", blocked=None, staged_at=None)
        check(stage(j3, jobs, pkg, pipeline=lambda *a: {"pass": False, "gate_findings": ["x"]}, loader=lambda s, p: (True, "ok"))[1].startswith("package gate failed"),
              "a failing package gate blocks")
        # preflight
        okp = ("a", lambda **k: (True, "fine"), None)
        badp = ("mic", lambda **k: (False, "peak -1 dBFS"), None)
        r = preflight(probes=(okp, badp, ("window", lambda **k: (False, "x"), None)))
        check(not r["pass"] and r["failing"]["item"] == "mic" and r["failing"]["eta"] == ETA["mic"] and r["also_failing"] == ["window"],
              "one failing item with its ETA")
        state = {"ok": False}
        fixed = preflight(probes=(("window", lambda **k: (state["ok"], "x"), lambda **k: state.update(ok=True) or True),))
        check(fixed["pass"] and "self-fixed" in fixed["items"]["window"]["detail"], "a fixable item fixes itself and re-probes")
        check(not preflight(probes=(("window", lambda **k: (False, "x"), lambda **k: True),))["pass"], "a fix that does not take still fails")
        check(render_report(r).startswith("PREFLIGHT FAIL: mic") and "ETA" in render_report(r), "report names one item and the ETA")
        check(probe_mic(runner=lambda c, **k: (0, "peak_dbfs=-12.0 rms_dbfs=-30", ""))[0], "mic in range passes")
        check(not probe_mic(runner=lambda c, **k: (0, "peak_dbfs=-0.5 rms_dbfs=-20", ""))[0], "mic too hot fails")
        check(not probe_camera(runner=lambda c, **k: (0, "luma=3.1", ""))[0], "black camera fails")
        # take done + next lead
        v, t = tmp / "t.mp4", tmp / "t.txt"
        v.write_bytes(b"x" * 10)
        t.write_text("word " * 30)
        check(qa_take(v, t) == [], "clean take passes QA")
        t2 = tmp / "t2.txt"
        t2.write_text("word " * 30 + " go to utopiamodels dot ai")
        check(qa_take(v, t2) != [], "a spoken URL fails QA")
        os.environ["VSL_OUTBOX"] = str(tmp / "outbox")
        sent, staged_next = [], []
        # job 1 has a stage.json for the gate
        import upwork_gate
        upwork_gate.skeleton("0221223000000000001", "Adam Zapier", root=pkg, slug="adam")
        j = load_job("0221223000000000001", jobs)
        j2 = load_job("0221223000000000002", jobs)
        j2["blocked"] = None
        save_job(j2, jobs)
        def passing(video, take_type):   # what vsl_check writes for a passing take (the real check runs in takeflow/tests)
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vsl" / "takeflow"))
            import vsl_check
            q = tmp / "t-qa.json"
            q.write_text(json.dumps({"sha256": vsl_check.sha256(Path(video)), "hunt_type": "upwork", "contract_sha": vsl_check.C.load("upwork")["_sha"],
                                     "ok": True, "failed": [], "checks": {}}))
            return q, []
        bad = take_done(j, str(v), str(t), jobs, led, tmp / "outbox", notify=lambda b: 1 / 0, root=pkg,
                        checker=lambda video, tt: (tmp / "t-qa.json", ["non_black", "mic_peak"]))
        check(bad[0] is False and "non_black" in bad[1], "a black, silent take (11-21) is refused by vsl check, never recorded")
        ok, msg, nxt = take_done(j, str(v), str(t), jobs, led, tmp / "outbox", analyzer=lambda *a: "analysis stubbed", stager=lambda nj, **k: staged_next.append(nj["key"]) or (True, "loaded"),
                                 notify=lambda b: sent.append(b) or True, root=pkg, checker=passing)
        check(ok and nxt and nxt["key"] == "0221223000000000002" and staged_next == ["0221223000000000002"], "next lead loads when a take ends")
        check(sent and "attach" in sent[0].lower() and (tmp / "outbox").exists(), "MP4 handed to the Upwork agent with a prepared message")
        led_rows = read_ledger(led)
        check(any(r["event"] == "vsl_recorded" for r in led_rows), "vsl_recorded row written")
        check(derive(load_job(j["key"], jobs), led_rows) == "recorded", "derive recorded")
        check(derive(j, led_rows + [L.build_row("vsl_sent", client="~0221223000000000001", file="x.mp4")]) == "attached", "derive attached")
        check(derive(j, led_rows + [L.build_row("client_reply", client="~0221223000000000001")]) == "replied", "derive replied")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"selftest: {n} checks passed")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", choices=["scan", "stage", "preflight", "take-done", "status", "tick"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--ledger")
    ap.add_argument("--rooms")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--no-fix", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--transcript")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.cmd:
        print(__doc__)
        return 2
    rows = read_ledger(a.ledger)
    if a.cmd == "scan":
        for j in scan(rows, rooms=a.rooms):
            print("job", j["key"], j["slug"], "BLOCKED: " + j["blocked"] if j["blocked"] else "queued")
        return 0
    if a.cmd == "tick":
        made, res = tick(rooms=a.rooms, rows=rows)
        print(f"{len(made)} new, {len(res)} staged/attempted")
        for k, ok, d in res:
            print(("OK  " if ok else "FAIL"), k, d)
        return 0 if all(ok for _, ok, _ in res) else 1
    if a.cmd == "status":
        st = status_rows(rows=rows)
        if a.json:
            print(json.dumps(st, indent=1))
        for s in st:
            print(f"{s['status']:9} {s['key']} {s['slug']}" + (f"  [{s['blocked']}]" if s["blocked"] else "")
                  + (f"  staged in {s['staged_in_min']} min" if s["staged_in_min"] is not None else ""))
        return 0
    job = (next_queued() if a.next or not a.job else load_job(a.job))
    if a.cmd == "preflight":
        rep = preflight(slug=job["slug"] if job else "", script=(Path(job["package"]) / "script.md") if job and job.get("package") else None,
                        fix=not a.no_fix)
        print(render_report(rep))
        print(json.dumps(rep))
        return 0 if rep["pass"] else 1
    if not job:
        print("no such job / nothing queued")
        return 2
    if a.cmd == "stage":
        ok, d = stage(job)
        print(("STAGED " if ok else "REFUSED ") + d)
        return 0 if ok else 1
    if a.cmd == "take-done":
        if not (a.file and a.transcript):
            print("take-done needs --file MP4 --transcript T")
            return 2
        ok, d, _ = take_done(job, a.file, a.transcript)
        print(("OK " if ok else "REFUSED ") + d)
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
