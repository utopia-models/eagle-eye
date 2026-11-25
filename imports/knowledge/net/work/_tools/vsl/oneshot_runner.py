#!/usr/bin/env python3
"""oneshot_runner.py: Upwork niche post -> MVP + speaker script + Eagle script + D2 diagram, in parallel -> Horus -> Eagle queue
(knowledge#16515, Tyler 2026-11-19 04:15 MT; plan #16481). Stateless per call: `tick` advances every run one state, so a run survives
restarts and nothing is resident.

  oneshot_runner.py signal  POSTS.json [--day D] [--top 5]     score posts vs the niche (OCC-style ops apps), start a run per top post
  oneshot_runner.py start   POST.json                          one run: intake (verbatim post + client stats + root problem) first
  oneshot_runner.py tick    [--id ID]                          intake -> building -> in_review -> (pass: queued | fail: rebuild w/ notes)
  oneshot_runner.py verdict ID pass|fail [--notes TEXT]        Horus's answer (it writes review.json; this is the same write)
  oneshot_runner.py report                                     rewrite _infra/occ-feeds/one-shots.json (the OCC One-Shots section, #16493)
  oneshot_runner.py --selftest

States (run.json `state`, stored because the clock and rebuild count are facts, not derivations): intake, building, in_review, queued,
failed (build could not finish: named reason, never a plausible fill). Run folder: net/work/upwork/one-shot/runs/<post-id>/.
Hard stops: a post with no text has no run; an MVP with no preview URL is NOT ready (the deployer is injected; none configured = the
run says so and stays in building). One lock per run (flock), a quota-aware master pick (lowest weekly utilisation among the masters).
Horus rubric (#16481): matches the post's criteria and root problem; MVP boots and its demo moments work; speaker script under 2:30
ending on the one ask; Eagle cues name real screens; diagram readable.
"""
import argparse
import concurrent.futures as cf
import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vsl-demo"))
sys.path.insert(0, str(HERE.parent / "vsl-viewer"))

RUNS = Path(os.environ.get("ONESHOT_RUNS_DIR") or KNOW / "net/work/upwork/one-shot/runs")
FEED = Path(os.environ.get("ONESHOT_FEED") or KNOW / "_infra/occ-feeds/one-shots.json")
USAGE = Path(os.environ.get("ONESHOT_USAGE_DIR") or KNOW / "_infra/occ-feeds/usage")
MASTERS = ("win", "cloud", "dust")   # Tyler 2026-11-24: nova is NOT part of the one-shot -> VSL chain (agent vsl owns it end to end); this only labels a run with the least-used master
MAX_REBUILDS = 3
BUILD_TIMEOUT_S = int(os.environ.get("ONESHOT_BUILD_TIMEOUT_S") or 600)   # Tyler 2026-11-22 (#17023): a build that hangs is failed after 10 min   # the four build stages only; the advisory script review runs after READY under its own review_timeout_s (oneshot-auto.yaml, #17413)
SLOTS = int(os.environ.get("ONESHOT_SLOTS") or 3)                          # parallel builds per tick; the newest runs take the slots first
SLA_MIN = 90
NICHE = {  # OCC-style ops apps (Tyler 04:12): AI ops, command centers, observability, monitoring
    "command center": 4, "ops dashboard": 4, "operations dashboard": 4, "observability": 3, "monitoring": 3, "dashboard": 2,
    "ai ops": 4, "aiops": 4, "ai agent": 2, "agents": 1, "automation": 1, "workflow": 1, "internal tool": 2, "crm": 1,
    "alerting": 2, "logs": 1, "metrics": 1, "audit": 1, "orchestration": 2, "n8n": 1, "grafana": 2,
    # software engineering, data, devops (Tyler 4:01 AM, widened hunt): weight 1-2 so they rank but never outrank an ops/AI fit
    "full-stack": 1, "backend": 1, "api": 1, "web app": 1, "microservice": 1, "data pipeline": 2, "etl": 1, "data warehouse": 1, "devops": 1, "kubernetes": 1, "terraform": 1,
}
PLACEHOLDER_STATS = {"rating", "spent", "hires", "location", "member_since"}


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if s else None


def post_id(post):
    return re.sub(r"[^a-z0-9]+", "-", str(post.get("id") or post.get("job_key") or "").lower()).strip("-")


# ------------------------------------------------------------------ 1. signal
def score(post):
    """Niche score of one post: weighted keyword hits in title + text. 0 = not in niche."""
    low = f"{post.get('title', '')} {post.get('text', '')}".lower()
    return sum(w * min(3, len(re.findall(r"(?<![\w])" + re.escape(k), low))) for k, w in NICHE.items())


def top_posts(posts, n=5, minimum=4):
    ranked = sorted(((score(p), p) for p in posts if post_id(p)), key=lambda t: -t[0])
    return [dict(p, niche_score=s) for s, p in ranked[:n] if s >= minimum]


# ------------------------------------------------------------------ 2. intake
def is_hourly(post):
    low = f"{post.get('pay', '')} {post.get('text', '')}".lower()
    return bool(re.search(r"hourly|/hr|per hour", low))


def root_problem(post, llm=None):
    """One short note: the root problem under the post. Model call (VSL_LLM_CMD, default `claude -p`); no model = a hard stop."""
    prompt = ("In 2-3 plain sentences, state the ROOT problem behind this Upwork post (what hurts, not what they asked for). "
              "Use only facts in the post.\n\n" + post["text"])
    if llm:
        return llm(prompt)
    cmd = os.environ.get("VSL_LLM_CMD", "claude -p").split()
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300)
    if r.returncode or not r.stdout.strip():
        raise SystemExit("root-problem note: model call failed: " + r.stderr[:200])
    return r.stdout.strip()


def intake(post, llm=None, runs=None, when=None):
    """Verbatim post + client stats + root-problem note, BEFORE any build (the Adam run lost hours without them)."""
    if not post_id(post) or not str(post.get("text", "")).strip():
        raise SystemExit("post has no id or no text: nothing to ground a run in (hard stop, no fill)")
    d = Path(runs or RUNS) / post_id(post)
    d.mkdir(parents=True, exist_ok=True)
    (d / "post.md").write_text(f"# {post.get('title', '')}\n\n{post['text']}\n")
    stats = {k: post.get(k) for k in ("client", "rating", "spent", "hires", "location", "member_since", "pay", "url") if post.get(k)}
    (d / "client.json").write_text(json.dumps(stats, indent=1) + "\n")
    (d / "root-problem.md").write_text(root_problem(post, llm) + "\n")
    hourly = is_hourly(post)
    run = {"id": post_id(post), "title": post.get("title"), "state": "building", "hourly": hourly, "niche_score": post.get("niche_score"),
           "signal_at": post.get("signal_at") or iso(when), "intake_at": iso(when), "rebuilds": 0, "master": None, "ready_at": None,
           "verdict": None, "funnel": {"sent": 0, "reply": 0, "call": 0, "contract": 0, "usd": 0}}
    save(d, run)
    return d, run


def build_source(d, run):
    """The text the pipeline treats as 'the only facts about the client': the post, the ask, and Horus's notes on a rebuild."""
    text = (d / "post.md").read_text()
    if run["hourly"]:
        text += "\nClosing ask: a fixed-price first milestone, defined by the post's own first deliverable (hourly retainer follows).\n"
    for n in sorted(d.glob("horus-notes-*.md")):
        text += f"\nHorus's notes from the last review (fix these): {n.read_text().strip()}\n"
    p = d / "source.txt"
    p.write_text(text)
    return p


# ------------------------------------------------------------------ 3. parallel build
def d2_from_spec(spec):
    nodes = spec.get("nodes", [])
    ids = {n.get("id", n["label"]): re.sub(r"\W+", "_", n["label"]).strip("_") or f"n{i}" for i, n in enumerate(nodes)}
    out = ["direction: right"] + [f'{ids[n.get("id", n["label"])]}: "{n["label"]}"' for n in nodes]
    edges = spec.get("edges") or [{"from": a, "to": b} for a, b in zip(spec.get("order", []), spec.get("order", [])[1:])]
    for e in edges:
        a, b = ids.get(e.get("from") or e.get("source")), ids.get(e.get("to") or e.get("target"))
        if a and b:
            out.append(f"{a} -> {b}")
    return "\n".join(out) + "\n"


def build_scripts(d, src, pipeline=None):
    """Speaker script, Eagle script (+ qc.json) from the pipeline; the D2 diagram from its diagram spec."""
    if pipeline is None:
        import vsl_pipeline
        pipeline = vsl_pipeline.run
    doc = pipeline("upwork-job", str(src), None, d / "pkg", d.name)
    spec = json.loads((d / "pkg/diagram.spec.json").read_text())
    (d / "diagram.d2").write_text(d2_from_spec(spec))
    for a, b in (("script.md", "speaker-script.md"), ("horus-script.md", "eagle-script.md")):
        if (d / "pkg" / a).is_file():
            (d / b).write_text((d / "pkg" / a).read_text())
    return {"pass": bool(doc.get("pass")), "findings": (doc.get("gate_findings") or []) + (doc.get("cue_problems") or [])}


def build_mvp(d, src, deployer=None, demo_checker=None):
    """Ops Command Center scaffold (mvp_router) -> noindex preview. No deployer or no URL back = not ready, said plainly.
    The preview and the package's demo page must not be the architecture diagram (demo_check.py, Tyler 2026-11-22 6:20 AM): an iframe or
    redirect to architecture.html, or a screenshot within 12 bits of the diagram's, fails the package. An injected deployer (a dry run or a
    test) skips the check unless a demo_checker is injected too."""
    import mvp_router
    plan = mvp_router.scaffold(src.read_text(), d.name, d / "mvp")
    url = (deployer or cmd_deployer)(d / "mvp", d.name)
    plan["deploy"].update(deployed=bool(url), url=url or plan["deploy"]["url"], noindex=True)
    (d / "mvp/mvp.plan.json").write_text(json.dumps(plan, indent=1) + "\n")
    findings = [] if url else ["no preview URL: the MVP is scaffolded but not deployed (no deployer configured)"]
    if url and (deployer is None or demo_checker):
        findings += demo_findings(url, d.name, demo_checker)
    return {"pass": bool(url) and not findings, "preview": url, "stack": plan["stack"], "findings": findings}


def demo_findings(preview_url, slug, checker=None):
    """-> findings: the preview page and the job's own demo/index.html (when it exists) must each be a real page, not the diagram."""
    import demo_check
    base = preview_url.split(f"/{slug}/")[0]
    arch = f"{base}/{slug}/demo/architecture/architecture.html"
    urls = [preview_url]
    try:
        demo_check.fetch(f"{base}/{slug}/demo/index.html")
        urls.append(f"{base}/{slug}/demo/index.html")
    except Exception:   # a job with no demo page yet has only the MVP to check
        pass
    out = []
    for u in urls:
        r = (checker or demo_check.check)(u, arch)
        out += [f"{u}: {x}" for x in r.get("reasons", [])]
    return out


def cmd_deployer(mvp_dir, slug):
    """ONESHOT_DEPLOY_CMD `<cmd> DIR SLUG` must print the noindex preview URL on its last line; unset = ra_publish.py where
    Ra's public dir is writable, else no deploy (not ready)."""
    cmd = os.environ.get("ONESHOT_DEPLOY_CMD")
    if not cmd:  # on Ra (nova dark = no Cloudflare token) the default is Ra's eagle-eye-spike: /hunts/<slug>/mvp/
        sys.path.insert(0, str(HERE.parent / "oneshot-mvp"))
        import ra_publish
        if not ra_publish.available():
            return None
        cmd = f"{sys.executable} {HERE.parent / 'oneshot-mvp' / 'ra_publish.py'}"
    r = subprocess.run(cmd.split() + [str(mvp_dir), slug], capture_output=True, text=True, timeout=1800)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    return last if r.returncode == 0 and last.startswith("https://") else None


def pick_master(usage=None):
    """Quota-aware: the master with the lowest weekly utilisation; unreadable feed = last, never a guess of zero."""
    best = None
    for m in MASTERS:
        try:
            u = json.loads((Path(usage or USAGE) / f"{m}.json").read_text())["utilization"]["seven_day"]["utilization"]
        except (OSError, KeyError, TypeError, ValueError):
            u = 101
        if best is None or u < best[0]:
            best = (u, m)
    return best[1]


def run_gates(d, gater=None):
    """-> {"pass", "findings", "ready"}: every active gate of gates.py must pass; a crash fails the package, never passes it."""
    try:
        import gates
        doc = (gater or gates.run_package)(d)
    except (Exception, SystemExit) as e:
        return {"pass": False, "findings": [f"gates crashed: {e}"], "ready": False}
    blocking = [f"gate {g['id']} {g['name']}: {g['why'][0]}" for g in doc.get("blocking", [])]
    return {"pass": not blocking, "findings": blocking, "ready": bool(doc.get("ready"))}


LEDGER_LIMIT_S = 600   # #18869 / #18762: detection -> finished MP4 in 10 minutes or less


@contextlib.contextmanager
def stage(run, name):
    """Stage wall-time ledger (#18869 item 5): the pipeline itself records `run["stages"][name] = {start, s}` for every stage it runs, so the
    10-minute claim is read from the run, never estimated. Re-entered stages (a rebuild) add up."""
    t0 = time.monotonic()
    st = run.setdefault("stages", {}).setdefault(name, {"start": iso(), "s": 0.0})
    try:
        yield
    finally:
        st["s"] = round(st["s"] + time.monotonic() - t0, 1)
        st["end"] = iso()


def ledger(run):
    """-> {stages: {name: s}, detect_to_mp4_s, limit_s, within_limit}. detect_to_mp4 = signal_at -> `mp4_at` (the finished MP4), else None."""
    a, b = parse(run.get("signal_at")), parse(run.get("mp4_at"))
    tot = round((b - a).total_seconds(), 1) if a and b else None
    return {"stages": {k: v["s"] for k, v in (run.get("stages") or {}).items()}, "detect_to_mp4_s": tot, "limit_s": LEDGER_LIMIT_S,
            "within_limit": None if tot is None else tot <= LEDGER_LIMIT_S}


def build(d, run, pipeline=None, deployer=None, demo_checker=None, gater=None):
    with stage(run, "build_source"):
        src = build_source(d, run)
    def timed(name, fn, *a):
        with stage(run, name):
            return fn(*a)
    with cf.ThreadPoolExecutor(2) as ex:
        fs = {"scripts": ex.submit(timed, "scripts", build_scripts, d, src, pipeline), "mvp": ex.submit(timed, "mvp", build_mvp, d, src, deployer, demo_checker)}
        res = {}
        for k, f in fs.items():
            try:
                res[k] = f.result()
            except (Exception, SystemExit) as e:  # a failed part is named, never swallowed
                res[k] = {"pass": False, "findings": [f"{k} build crashed: {e}"]}
    if gater or (d / "script-source.yaml").is_file():   # one-shot v2: a package with a script source must pass every active gate (gates.py)
        with stage(run, "gates"):
            res["gates"] = run_gates(d, gater)
    run["build"] = res
    ok = all(r["pass"] for r in res.values())
    run["state"] = "in_review" if ok else "building"
    if not ok:   # #16636: an automated pre-review failure is rebuilt before Horus sees it, and the count shows on the run
        run["prereview_rebuilds"] = run.get("prereview_rebuilds", 0) + 1
    run["built_at"] = iso() if ok else None
    return ok


# ------------------------------------------------------------------ 4. review / 5. queue
def hand_to_horus(d, run, send=None):
    body = (f"One-shot {run['id']} ready for review (rebuild {run['rebuilds']}). Folder: {d.relative_to(KNOW) if d.is_relative_to(KNOW) else d}. "
            f"Rubric #16481. Answer: oneshot_runner.py verdict {run['id']} pass|fail --notes '...'")
    (send or (lambda b: subprocess.run(["fleetmail", "send", "horus", b, "--thread", "one-shot", "--ref", "16515"], check=True)))(body)
    run["sent_to_horus_at"] = iso()


def verdict(d, run, v, notes="", when=None):
    (d / "review.json").write_text(json.dumps({"verdict": v, "notes": notes, "at": iso(when)}) + "\n")
    run["verdict"] = v
    if v == "pass":
        run["state"] = "pass"
    else:
        run["rebuilds"] += 1
        (d / f"horus-notes-{run['rebuilds']}.md").write_text(notes + "\n")
        run["state"] = "building" if run["rebuilds"] <= MAX_REBUILDS else "failed"
        run["failed_reason"] = None if run["state"] == "building" else f"{MAX_REBUILDS} rebuilds, still failing Horus: {notes[:200]}"
        run["sent_to_horus_at"] = None


def queue(d, run, loader=None):
    """On pass: both scripts onto Eagle's/Vizier's queue (Ra prompter), the same loader vsl_jobs uses."""
    if loader is None:
        import vsl_jobs
        loader = vsl_jobs.load_prompter
    ok1, w1 = loader(d.name, d / "speaker-script.md")
    ok2, w2 = loader(d.name + "-horus-script", d / "eagle-script.md")
    if not (ok1 and ok2):
        run["queue_error"] = f"{w1}; {w2}"
        return False
    run.update(state="queued", ready_at=iso(), queue_error=None)
    return True


# ------------------------------------------------------------------ state machine
def save(d, run):
    (d / "run.json").write_text(json.dumps(run, indent=1) + "\n")


def tick_run(d, pipeline=None, deployer=None, send=None, loader=None):
    with open(d / ".lock", "w") as lk:   # one lock per run: two ticks never build the same folder
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return "locked"
        run = json.loads((d / "run.json").read_text())
        if run["state"] == "building":
            run["master"] = run.get("master") or pick_master()
            build(d, run, pipeline, deployer)
        if run["state"] == "in_review" and not run.get("sent_to_horus_at"):
            hand_to_horus(d, run, send)
        rv = d / "review.json"
        if run["state"] == "in_review" and rv.is_file() and run.get("sent_to_horus_at"):
            j = json.loads(rv.read_text())
            if j["at"] >= run["sent_to_horus_at"]:
                verdict(d, run, j["verdict"], j.get("notes", ""))
                rv.unlink()
                if run["state"] == "building":   # a fail is rebuilt with Horus's notes in the same tick, nobody asks
                    build(d, run, pipeline, deployer)
                    if run["state"] == "in_review":
                        hand_to_horus(d, run, send)
        if run["state"] == "pass":
            queue(d, run, loader)
        save(d, run)
        return run["state"]


def pending(runs=None):
    """Runs that still need a tick, NEWEST signal first (a stale job never starves a fresh one)."""
    out = []
    for f in Path(runs or RUNS).glob("*/run.json"):
        r = json.loads(f.read_text())
        if r["state"] not in ("queued", "failed"):
            out.append((r.get("signal_at") or "", f.parent))
    return [d for _, d in sorted(out, key=lambda t: t[0], reverse=True)]


def fail_run(d, reason):
    run = json.loads((d / "run.json").read_text())
    run.update(state="failed", failed_reason=reason)
    save(d, run)


def tick_isolated(d, timeout=None, argv=None):
    """One run's tick in its own process, killed at the timeout: a hung build is marked failed, the next newest builds."""
    cmd = argv or [sys.executable, str(Path(__file__).resolve()), "tick", "--one", str(d)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout or BUILD_TIMEOUT_S)
        return (r.stdout.strip().splitlines() or ["?"])[-1] if r.returncode == 0 else "crashed"
    except subprocess.TimeoutExpired:
        fail_run(d, f"build exceeded {timeout or BUILD_TIMEOUT_S}s and was killed")
        return "failed"


def tick_all(runs=None, slots=None, timeout=None, argv_for=None):
    ds = pending(runs)
    with cf.ThreadPoolExecutor(slots or SLOTS) as ex:   # submitted newest-first = started newest-first
        res = list(ex.map(lambda d: (d.name, tick_isolated(d, timeout, argv_for(d) if argv_for else None)), ds))
    return res


def report(runs=None, feed=None):
    rows, funnel = [], {"sent": 0, "reply": 0, "call": 0, "contract": 0, "usd": 0}
    for f in sorted(Path(runs or RUNS).glob("*/run.json")):
        r = json.loads(f.read_text())
        mins = None
        if r.get("ready_at"):
            mins = round((parse(r["ready_at"]) - parse(r["signal_at"])).total_seconds() / 60)
        rows.append({"id": r["id"], "title": r.get("title"), "state": r["state"], "signal_to_ready_min": mins,
                     "within_sla": None if mins is None else mins <= SLA_MIN, "horus_verdict": r.get("verdict"),
                     "rebuilds": r["rebuilds"], "prereview_rebuilds": r.get("prereview_rebuilds", 0), "master": r.get("master"), "failed_reason": r.get("failed_reason")})
        for k in funnel:
            funnel[k] += r["funnel"].get(k, 0)
    doc = {"generated_at": iso(), "sla_min": SLA_MIN, "runs": rows, "funnel": funnel,
           "rebuilds_total": sum(r["rebuilds"] for r in rows), "failed": sum(r["state"] == "failed" for r in rows)}
    Path(feed or FEED).parent.mkdir(parents=True, exist_ok=True)
    Path(feed or FEED).write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def _selftest():
    import tempfile
    t = Path(tempfile.mkdtemp())
    os.environ["ONESHOT_RA_PUBLIC"] = str(t / "no-ra-here")   # the "no deployer" case below must not publish on Ra
    os.environ.pop("ONESHOT_DEPLOY_CMD", None)
    post = {"id": "~0123", "title": "AI ops command center", "text": "We need an ops dashboard with monitoring and alerting for our AI agents. Hourly.",
            "client": "Acme", "rating": "4.9"}
    assert score(post) >= 4 and score({"id": "x", "title": "logo", "text": "design a logo"}) == 0
    runs = t / "runs"
    d, run = intake(post, llm=lambda p: "Ops are blind to agent failures.", runs=runs)
    assert (d / "post.md").read_text().count("alerting") and run["hourly"]
    calls = []

    def pipe(variant, job, target, out, slug):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "script.md").write_text("speaker " + Path(job).read_text()[-40:])
        (out / "horus-script.md").write_text("eagle")
        (out / "diagram.spec.json").write_text(json.dumps({"nodes": [{"id": "a", "label": "Agent"}, {"id": "b", "label": "Ops UI"}], "order": ["a", "b"]}))
        return {"pass": True}
    dep = lambda mvp, slug: f"https://{slug}.preview.example"
    ld = lambda slug, p: (calls.append(slug) or True, "ok")
    sent = []
    assert tick_run(d, pipe, dep, sent.append, ld) == "in_review" and len(sent) == 1
    assert "Agent -> Ops_UI" in (d / "diagram.d2").read_text()
    # fail path: Horus writes review.json after the handoff, the runner rebuilds with the notes, without anyone asking
    (d / "review.json").write_text(json.dumps({"verdict": "fail", "notes": "fix screens", "at": iso()}))
    assert tick_run(d, pipe, dep, sent.append, ld) == "in_review" and json.loads((d / "run.json").read_text())["rebuilds"] == 1
    assert "fix screens" in (d / "source.txt").read_text() and len(sent) == 2
    (d / "review.json").write_text(json.dumps({"verdict": "pass", "notes": "", "at": iso()}))
    assert tick_run(d, pipe, dep, sent.append, ld) == "queued" and calls[-2:] == ["0123", "0123-horus-script"]
    rep = report(runs, t / "feed.json")
    assert rep["runs"][0]["rebuilds"] == 1 and rep["runs"][0]["within_sla"] is True
    # no deployer (and no writable Ra public dir): not ready, said plainly
    d2, _ = intake(dict(post, id="~9"), llm=lambda p: "x", runs=runs)
    assert tick_run(d2, pipe, None, sent.append, ld) == "building"
    assert "no preview URL" in json.loads((d2 / "run.json").read_text())["build"]["mvp"]["findings"][0]
    assert json.loads((d2 / "run.json").read_text())["prereview_rebuilds"] == 1
    # newest first + hung build killed at the timeout + next newest still builds
    r2 = t / "r2"
    for i, (rid, at) in enumerate((("old", "2026-11-22T01:00:00Z"), ("hang", "2026-11-22T03:00:00Z"), ("new", "2026-11-22T02:00:00Z"))):
        (r2 / rid).mkdir(parents=True)
        save(r2 / rid, {"id": rid, "state": "building", "signal_at": at, "rebuilds": 0, "funnel": {}})
    assert [x.name for x in pending(r2)] == ["hang", "new", "old"]
    argv = lambda d: [sys.executable, "-c", "import time;time.sleep(30)"] if d.name == "hang" else [sys.executable, "-c", "print('in_review')"]
    out = dict(tick_all(r2, slots=2, timeout=2, argv_for=argv))
    assert out == {"hang": "failed", "new": "in_review", "old": "in_review"}, out
    assert "exceeded 2s" in json.loads((r2 / "hang/run.json").read_text())["failed_reason"]
    print("selftest OK")


def main(argv):
    if argv and argv[0] == "--selftest":
        return _selftest() or 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signal"); s.add_argument("posts"); s.add_argument("--top", type=int, default=5)
    s = sub.add_parser("start"); s.add_argument("post")
    s = sub.add_parser("tick"); s.add_argument("--id"); s.add_argument("--one")
    s = sub.add_parser("verdict"); s.add_argument("id"); s.add_argument("v", choices=["pass", "fail"]); s.add_argument("--notes", default="")
    s = sub.add_parser("ledger", help="stage wall-time ledger of one run; --mp4-done stamps the finished-MP4 time (#18869)"); s.add_argument("id"); s.add_argument("--mp4-done", action="store_true"); s.add_argument("--render-s", type=float)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd in ("signal", "start"):
        posts = json.loads(Path(a.posts if a.cmd == "signal" else a.post).read_text())
        posts = posts if isinstance(posts, list) else [posts]
        for p in (top_posts(posts, a.top) if a.cmd == "signal" else posts):
            d, _ = intake(p)
            print("run", d)
    elif a.cmd == "tick" and a.one:
        print(tick_run(Path(a.one)))
    elif a.cmd == "tick":
        if a.id:
            for d in sorted(RUNS.glob(a.id)):
                if (d / "run.json").is_file() and json.loads((d / "run.json").read_text())["state"] not in ("queued", "failed"):
                    print(d.name, tick_isolated(d))
        else:
            for name, st in tick_all():
                print(name, st)
        report()
    elif a.cmd == "ledger":
        d = RUNS / a.id
        run = json.loads((d / "run.json").read_text())
        if a.render_s is not None:
            run.setdefault("stages", {})["render"] = {"start": iso(), "s": a.render_s, "end": iso()}
        if a.mp4_done:
            run["mp4_at"] = iso()
        save(d, run)
        print(json.dumps(ledger(run), indent=1))
    elif a.cmd == "verdict":
        d = RUNS / a.id
        (d / "review.json").write_text(json.dumps({"verdict": a.v, "notes": a.notes, "at": iso()}) + "\n")
        print("recorded", a.id, a.v)
    else:
        print(json.dumps(report(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
