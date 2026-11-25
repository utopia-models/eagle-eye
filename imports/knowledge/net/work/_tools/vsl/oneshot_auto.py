#!/usr/bin/env python3
"""oneshot_auto.py: a NEW Upwork hunt row starts its one-shot build by itself (Tyler 2026-11-22 6:45 AM ET: "event-driven, no one asks").

  oneshot_auto.py tick [--feed FILE] [--no-spawn]   scan the Eagle Eye feed for Upwork rows with no job record, make one per new row, start
                                                    the build of the NEWEST queued job when none is running (max_concurrent_builds)
  oneshot_auto.py run JOB                           build one job now (foreground; `tick` starts this in the background)
  oneshot_auto.py status [--json]                   one row per job: stages, the running clock, the slowest stage, the SLA, times in ET
  oneshot_auto.py pick KEY|DIGITS full|intro [--by voice]   Tyler/Eagle's FULL or INTRO pick for one job (knowledge#18050); pull-picks drains the page's buttons
  oneshot_auto.py sync-sends [LEDGER]               stamp vsl_sent / text_proposal from the upwork ledger (also runs every tick)
  oneshot_auto.py mark JOB STAGE [--ts ISO]         set recorded | text_proposal | vsl_sent (from the Eagle/Upwork events)
  oneshot_auto.py event JOB recording_started|recording_stopped [--ts ISO]   the recording events the delay attribution reads
  oneshot_auto.py session PKG_DIR...   write session.json: the back-to-back run in order (tabs, action scripts, readiness) for Eagle/Vizier
  oneshot_auto.py feed                              write stages-feed.json (what Eagle Eye reads: six ticks, clock, slowest stage, ET)
  oneshot_auto.py serve [--every 20]               the hunt trigger as a SERVICE (systemd Restart=always): tick every N s forever; a failed tick is logged
                                                    with its real error and the loop goes on; heartbeat in $ONESHOT_AUTO_DIR/serve.json
  oneshot_auto.py live [--max-age 90]              liveness: prints the heartbeat age; exit 1 when the service is not ticking
  oneshot_auto.py timeline JOB...                  targeted_at / package_valid_at / staged_on_laptop_at and the minutes between (Tyler's 10-min target)
  oneshot_auto.py eagle-backfill                   push the built/blocked fact of every ready/blocked job to Eagle Eye (idempotent; knowledge#17557)
  oneshot_auto.py regen PKG_DIR                     rewrite ONE package's scripts in place with the current contract (idempotent; refuses a package already recorded or sent)
  oneshot_auto.py --self-test

A job is a JSON file in $ONESHOT_AUTO_DIR (default ~/.claude/state/net/oneshot-auto/jobs/<slug>.json): the feed row, `t` = the ISO time each
stage finished, `state` (queued, building, ready, blocked), `blocked_by` (a named reason, never a plausible fill). Stages and budgets come from
net/work/vsl/oneshot-auto.yaml; the display zone is that file's ONE `display_tz`. The build is: author (a headless Claude worker writes the
MVP config, the diagram model and the script source from the post, to the formats in oneshot-auto-examples/), then deterministic steps: the
app (oneshot-deploy), the diagram (animate.py + ra_publish), the scripts (gen_scripts.py), the gates (gates.py). READY only from a passing
gates.json. Hard stops: a post with too little text, or a role and not a build, is `skipped` with its reason.
Every outward step is a function you can replace in tests. Nothing here touches upwork.com: the feed is Eagle Eye's own.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[3]
sys.path.insert(0, str(HERE))
CFG_FILE = KNOW / "net/work/vsl/oneshot-auto.yaml"
EXAMPLES = KNOW / "net/work/vsl/oneshot-auto-examples"
PROMPT = KNOW / "net/work/vsl/oneshot-auto-prompt.md"
PROMPT_TERMINAL = KNOW / "net/work/vsl/oneshot-auto-prompt-terminal.md"
PROMPT_COPY = KNOW / "net/work/vsl/oneshot-auto-prompt-copy.md"
TERMINAL_TPL = KNOW / "net/work/_tools/oneshot-mvp/terminal/index.html"
STATE = Path(os.environ.get("ONESHOT_AUTO_DIR") or Path.home() / ".claude/state/net/oneshot-auto")
PKG_ROOT = Path(os.environ.get("ONESHOT_PKG_ROOT") or Path.home() / "oneshot/packages")
KIT = KNOW / "_infra/diagram-kit"
sys.path.insert(0, str(KNOW / "net/work/vsl/package"))
sys.path.insert(0, str(KNOW / "net/work/_tools/upwork"))
import screening   # knowledge#18203: the hunt step owns every screening question
import arch4   # ARCH 4 (knowledge#17280): metering, load guard, worktree
METER_DB = Path(os.environ.get("VSL_STATUS_DB") or Path.home() / ".claude/state/net/vsl-status.db")
WORKTREES = Path(os.environ.get("ONESHOT_WORKTREES") or Path.home() / "oneshot/worktrees")
MVP_TOOLS = KNOW / "net/work/_tools/oneshot-mvp"


def cfg():
    return yaml.safe_load(CFG_FILE.read_text())


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if s else None


def fmt_tz(s, c=None):
    """An ISO UTC stamp in the ONE configured display zone, with its label: '2026-11-22 06:51 ET'."""
    c = c or cfg()
    z = ZoneInfo(c["display_tz"])
    t = parse(s).astimezone(z)
    return f"{t:%Y-%m-%d %H:%M} {c.get('display_tz_label') or t.tzname()}"


def slugify(title, job):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:34].strip("-")
    return f"up-{base}-{re.sub(r'[^0-9]', '', job)[-4:]}"


TERMINAL_WORDS = r"\b(etl|pipelines?|spark|databricks|airflow|dbt|kafka|terraform|kubernetes|k8s|docker|devops|cli|scripts?|scraper|scraping|cron|batch|backend|api|sql|warehouse|data engineer|data engineering)\b"
APP_WORDS = r"\b(dashboard|crm|inbox|calendar|approvals?|briefing|assistant|chief of staff|workflow|portal|admin|front-?end|react|ux|saas|marketplace|booking|e-?commerce|website|mobile|chatbot)\b"


def choose_mvp_type(text):
    """The one-shot router: a CLI/batch/data-infrastructure post gets a terminal demo; a post about people using screens gets a web app, which is
    always a COPY of a real application (Tyler 2026-11-22 7:33 AM ET), never a custom design. Terminal only when it clearly leads (at least two
    terminal words and more of them than app words); the default is the copied app."""
    t = len(re.findall(TERMINAL_WORDS, text, re.I))
    a = len(re.findall(APP_WORDS, text, re.I))
    return "terminal" if t >= 2 and t > a else "copy"


def jobs_dir():
    d = STATE / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_job(slug):
    return json.loads((jobs_dir() / f"{slug}.json").read_text())


def save_job(j):
    """Atomic: write beside, then rename. A reader (another tick, a regen script, the feed) never sees a half-written file (2026-11-24: one empty job file
    raised JSONDecodeError in all_jobs() inside tick() and held the whole scan for hours)."""
    dst = jobs_dir() / f"{j['slug']}.json"
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(j, indent=1) + "\n")
    os.replace(tmp, dst)


BAD_JOBS = []   # job files skipped as unreadable this pass (name, why): shown by `live`/serve.json, never fatal


def all_jobs():
    out = []; BAD_JOBS.clear()
    for p in sorted(jobs_dir().glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, ValueError) as e:       # empty / half-written / corrupt: skip it, say so, keep scanning
            BAD_JOBS.append((p.name, str(e)[:80]))
    return out


# ---------------------------------------------------------------- arrival
def fetch_feed(url, tries=3):
    """The feed answers 502/timeout now and then (Eagle Eye restarts): retry with a short backoff before the tick gives up."""
    last = None
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=60).read())
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e; time.sleep(2 * (i + 1))
    raise last


def feed_rows(feed):
    items = feed if isinstance(feed, list) else feed.get("items", [])
    return [i for i in items if i.get("huntType") == "upwork" and (i.get("details") or {}).get("job")]


LIBRARY = HERE.parents[1] / "vsl" / "library"   # net/work/vsl/library (chief, knowledge#17012): prebuilt apps, diagrams and script skeletons


def library_pick(title, text):
    """Stage 1 of the library path (Tyler 12:5x ET): the closest prebuilt app, diagram and script for a job, by pick.py. Recorded on the job; the
    builder still copies the app itself until each library app has its build recipe wired. Never raises: a failure leaves the job on the old path."""
    try:
        sys.path.insert(0, str(LIBRARY))
        import pick as P
        r = P.pick(title, text or "")
        return {k: r[k] for k in ("category", "app", "diagram", "script", "fresh_copy_needed") if k in r}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:120]}


def intake(row, c):
    """-> (job record, None) or (None, skip reason). A row becomes a job once; the reason it did not is the answer."""
    d = row["details"]
    title = row.get("signal") or d.get("title") or ""
    text = "\n\n".join([title, d.get("desc") or "", "Skills: " + ", ".join(d.get("skills") or []), "Budget: " + str(d.get("comp") or "")])
    slug0 = slugify(title, d["job"])
    post = Path(d["package"]) / "post.md" if d.get("package") else Path(c.get("hunts_dir", "/nonexistent")) / slug0 / "post.md"
    if post and post.is_file():   # the intake already saved the whole post text: the worker reads that, not the feed excerpt
        text = post.read_text()
        if len(d.get("desc") or "") < c["min_post_chars"] and len(text) > c["min_post_chars"]:
            d = dict(d, desc=text)
    for pat in c["skip_title"]:
        if re.search(pat, title):
            return None, f"a role, not a build ({title[:40]})"
    import post_integrity   # knowledge#17487: never build or author from a truncated post (9263's 521-char text)
    whole = post.read_text() if post and post.is_file() else (d.get("desc") or "")
    bad = post_integrity.post_complete(whole)
    if bad:
        return None, PENDING_POST + ": " + "; ".join(bad)
    if len(d.get("desc") or "") < c["min_post_chars"] and not (d.get("skills") or []):
        return None, "post text too short and no stack named"
    slug = slugify(title, d["job"])
    return {"slug": slug, "mvp_type": choose_mvp_type(text), "library": library_pick(title, text), "job": d["job"], "title": title, "text": text, "link": d.get("link"), "state": "queued",
            "posted_at": row.get("signalAt", "").replace(".000Z", "Z") or None, "t": {}, "created": iso()}, None


PENDING_POST = "post integrity"   # the skip reason that means "the whole post has not been read yet", never a final answer


def scan(rows, c=None):
    c = c or cfg()
    seen = {j["job"] for j in all_jobs()}
    skipped = json.loads((STATE / "skipped.json").read_text()) if (STATE / "skipped.json").is_file() else {}
    new = []
    # knowledge#18251: "the post is not here YET" is not a verdict. The description desk reads a post 1-2 min after its alert, the feed row
    # arrives first with no text, and a permanent skip here starved every Upwork row since 2026-11-23 (the Go backend row was skipped "post is 0
    # chars" at 11:32Z, its description landed ok at 11:33Z). Forget those skips so each tick re-evaluates them.
    for k in [k for k, v in skipped.items() if str(v).startswith(PENDING_POST)]:
        skipped.pop(k)
    for r in rows:
        job = r["details"]["job"]
        if job in seen or job in skipped:
            continue
        j, why = intake(r, c)
        if j is None and why.startswith(PENDING_POST):
            d = r["details"]
            title = r.get("signal") or d.get("title") or ""
            j = {"slug": slugify(title, d["job"]), "mvp_type": None, "job": d["job"], "title": title, "text": "", "link": d.get("link"),
                 "state": "needs_description", "source": "feed", "posted_at": r.get("signalAt", "").replace(".000Z", "Z") or None, "t": {}, "created": iso()}
            why = None
        if j is None:
            skipped[job] = why
            continue
        pk = read_picks().get(job)
        if pk:
            j.update(take_type=pk["take"], picked_by=pk["by"], picked_at=pk["at"])
        j["t"]["posted"] = j["posted_at"]
        j["t"]["detected"] = iso()
        if j["posted_at"] and minutes(j["posted_at"], j["t"]["detected"]) > 90:
            j["backlog"] = True   # posted long before we looked (a staged test, or the feed was down): the SLA clock starts at detection
        save_job(j)
        new.append(j)
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "skipped.json").write_text(json.dumps(skipped, indent=1) + "\n")
    return new


# ---------------------------------------------------------------- the build
def render_prompt(j, work):
    """Explicit placeholder replacement: the template holds literal braces (`do: {tab: 1, ...}`), so str.format would fail on it."""
    p = {"terminal": PROMPT_TERMINAL, "copy": PROMPT_COPY}.get(j.get("mvp_type"), PROMPT).read_text()
    import script_rules   # the rules and the sources are generated from the contract, never hand-copied (knowledge#17827)
    for k, v in (("{RULES}", script_rules.prompt_rules()), ("{SOURCES}", script_rules.sources_text()), ("{JOB_TEXT}", j["text"]), ("{SLUG}", j["slug"]), ("{EXAMPLES}", str(EXAMPLES)), ("WORKDIR", str(work))):
        p = p.replace(k, v)
    if j.get("_repair"):   # knowledge#18233/#18574: the script gate refused the first draft; the worker gets the exact refusal and fixes only that
        p += ("\n\nYOUR PREVIOUS DRAFT WAS REFUSED by the script gate with this exact message:\n" + j["_repair"] + "\n\nFix ONLY script-source.yaml in " + str(work)
              + " so every refused row passes. Keep every other file as it is. A result row needs a REAL source from the post (source: {post: '<quote>'} or "
              "{artifact: '<file>'}): never invent one; if the post has no support for a row, drop or reword that row. Do not weaken or skip any rule. Where the message gives numbers (words, range, grade, seconds), hit them exactly: e.g. 'app section is 43 words, beat range 50-80' means rewrite that section to 50-80 words from the post's own facts.")
    return p


def author_worker(j, work, c):
    """The LLM step: a headless Claude worker writes config.json, architecture.yaml and script-source.yaml into `work`."""
    prompt = render_prompt(j, work)
    r = subprocess.run(["claude", "-p", prompt, "--model", c["author"]["model"], "--output-format", "json", "--permission-mode", "acceptEdits",
                        "--allowedTools", "Read", "Write", "--add-dir", str(work), str(EXAMPLES)],
                       capture_output=True, text=True, timeout=c["author"]["timeout_s"], cwd=str(work))
    j.setdefault("tokens", {})["authored"] = arch4.parse_usage(r.stdout)   # metered per stage; 0 when the CLI reported none
    if r.returncode:
        raise RuntimeError(f"author worker failed: {(r.stderr or r.stdout)[-200:]}")


def check_authored(work, slug, mvp_type="app"):
    """-> reasons. The three files exist, parse and carry the slug (a terminal job has terminal.json in place of config.json)."""
    why = []
    if mvp_type == "copy":   # the app already exists (copied); the worker wrote the diagram model and the script source against it
        for f in ("architecture.yaml", "script-source.yaml", "copied_from.json"):
            if not (work / f).is_file():
                why.append(f"{f} was not written")
        for f in ("architecture.yaml", "script-source.yaml"):
            try:
                yaml.safe_load((work / f).read_text())
            except (OSError, yaml.YAMLError) as e:
                why.append(f"{f} problem: {e}")
        return why
    if mvp_type == "terminal":
        if not (work / "terminal.json").is_file():
            return ["terminal.json was not written"] + [f"{f} was not written" for f in ("architecture.yaml", "script-source.yaml") if not (work / f).is_file()]
        try:
            tj = json.loads((work / "terminal.json").read_text())
            cmds = tj.get("commands") or []
            if not 4 <= len(cmds) <= 8 or any(not (x.get("cmd") and x.get("out") and x.get("label")) for x in cmds):
                why.append("terminal.json needs 4 to 8 commands, each with label, cmd and out")
        except ValueError as e:
            why.append(f"terminal.json does not parse: {e}")
        for f in ("architecture.yaml", "script-source.yaml"):
            try:
                yaml.safe_load((work / f).read_text())
            except (OSError, yaml.YAMLError) as e:
                why.append(f"{f} problem: {e}")
        return why
    for f in ("config.json", "architecture.yaml", "script-source.yaml"):
        if not (work / f).is_file():
            why.append(f"{f} was not written")
    if why:
        return why
    try:
        c = json.loads((work / "config.json").read_text())
        if c.get("slug") != f"{slug}-mvp":
            why.append(f"config.json slug is {c.get('slug')!r}, want {slug}-mvp")
        for k in ("kpis", "workflow", "queue", "ask", "log", "pages"):
            if k not in c:
                why.append(f"config.json has no {k}")
    except ValueError as e:
        why.append(f"config.json does not parse: {e}")
    for f in ("architecture.yaml", "script-source.yaml"):
        try:
            yaml.safe_load((work / f).read_text())
        except yaml.YAMLError as e:
            why.append(f"{f} does not parse: {e}")
    return why


def build_copy(j, work):
    """The copied app: pick (3 candidates), fork, adapt content only, build, publish at <slug>-mvp, write copied_from.json. No fallback to a custom
    design: a failure here blocks the job with its reason."""
    import oneshot_copy
    doc = oneshot_copy.copy_app(j["slug"], j["text"], work, publish_slug=f"{j['slug']}-mvp", model=cfg()["author"]["model"])
    j["copied_from"] = {"picked": doc["picked"], "license": doc["license"], "palette": doc["palette"]["decision"]}
    return True


def build_terminal(j, work):
    """The terminal MVP: the static player page + terminal.json published at <slug>-mvp. No pre-review (gate 1 clicks it)."""
    pub = work / "terminal-pub"
    shutil.rmtree(pub, ignore_errors=True)
    pub.mkdir()
    shutil.copy(TERMINAL_TPL, pub / "index.html")
    shutil.copy(work / "terminal.json", pub / "terminal.json")
    r = subprocess.run([sys.executable, str(MVP_TOOLS / "ra_publish.py"), str(pub), f"{j['slug']}-mvp", "--no-build"], capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f"terminal publish failed: {r.stdout[-200:]}{r.stderr[-200:]}")
    return True


def build_app(j, work):
    post = {"post_id": f"{j['slug']}-mvp", "title": j["title"], "text": j["text"]}
    (work / "post.json").write_text(json.dumps(post))
    r = subprocess.run([str(MVP_TOOLS / "oneshot-deploy"), str(work / "post.json"), "--config", str(work / "config.json"), "--target", "ra",
                        "--out", str(work / "build")], capture_output=True, text=True, timeout=1500)
    if r.returncode and "PRE-REVIEW FAIL" not in r.stdout:
        raise RuntimeError(f"app build failed: {r.stdout[-300:]}")
    return r.returncode == 0 or "PRE-REVIEW CRASH" in r.stdout   # a click-timeout crash under load is retried by the caller


def prereview(slug, work):
    url = f"https://ra.tail4016d7.ts.net:8450/hunts/{slug}-mvp/mvp/"
    r = subprocess.run(["node", str(MVP_TOOLS / "prereview.cjs"), url, str(work / "shots"), str(work / "build/mvp/dist"), "final"],
                       capture_output=True, text=True, timeout=900)
    return "PRE-REVIEW PASS" in r.stdout


ARCHDIAGRAM = Path(os.environ.get("ARCHDIAGRAM_SKILL") or "/srv/fleet-plugins/current/plugins/fleet-doctrine/skills/architecture-diagram") / "archdiagram.py"


def diagram_problems(arch_yaml):
    """-> the renderer's own failure text ('' = it lays the model out cleanly: no edge crossing in some layout). The renderer exits non-zero on
    a crossing it cannot remove, and the page builder would crash on that; the worker gets the exact message instead."""
    import tempfile
    r = subprocess.run([sys.executable, str(ARCHDIAGRAM), str(arch_yaml), "--out", str(Path(tempfile.mkdtemp()) / "x.html"), "--wall"], capture_output=True, text=True, timeout=300)
    if r.returncode == 0:
        return ""
    keep = [l for l in (r.stderr + r.stdout).splitlines() if (l.startswith("archdiagram:") or l.startswith("  ")) and "wrote" not in l]   # the headline and its indented reasons
    return "\n".join(keep)[:800] or (r.stderr or r.stdout)[-300:]


def fix_diagram_worker(work, problem, c):
    prompt = (f"The diagram model {work}/architecture.yaml does not lay out cleanly. The renderer said:\n{problem}\n\nEdit ONLY that file so it renders with no edge crossing: "
              "reorder nodes within a column, move a node one column to the left or right, or merge two boxes, keeping 8 to 12 boxes, the client's own stack named, every edge on a "
              "declared path and every edge node id existing. Do not touch any other file. When written, stop.")
    r = subprocess.run(["claude", "-p", prompt, "--model", c["author"]["model"], "--permission-mode", "acceptEdits", "--allowedTools", "Read", "Write", "Edit",
                        "--add-dir", str(work)], capture_output=True, text=True, timeout=300, cwd=str(work))
    if r.returncode:
        raise RuntimeError(f"diagram fix worker failed: {(r.stderr or r.stdout)[-200:]}")


def build_diagram(j, work):
    for attempt in range(3):   # the renderer decides when the model is clean; the worker gets its exact message, twice at most
        problem = diagram_problems(work / "architecture.yaml")
        if not problem:
            break
        if attempt == 2:
            raise RuntimeError("the diagram does not lay out cleanly after two fixes: " + problem.replace("\n", " | ")[:300])
        fix_diagram_worker(work, problem, cfg())
    out = work / "diagram"
    out.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(KIT / "animate.py"), str(work / "architecture.yaml"), "--out", str(out)], capture_output=True, text=True, timeout=600)
    if not (out / "architecture.html").is_file():
        raise RuntimeError("the diagram page was not generated")
    pub = work / "diagram-pub"
    shutil.rmtree(pub, ignore_errors=True)
    pub.mkdir()
    html = (out / "architecture.html").read_text().replace('<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="noindex">', 1)
    (pub / "index.html").write_text(html)
    shutil.copy(out / "beats.json", pub / "beats.json")
    r = subprocess.run([sys.executable, str(MVP_TOOLS / "ra_publish.py"), str(pub), f"{j['slug']}-diagram", "--no-build"], capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f"diagram publish failed: {r.stdout[-200:]}{r.stderr[-200:]}")


def scripts_and_gates(j, pkg, rewriter=None):
    import gen_scripts
    import gates
    import upwork_rules
    # The writer's first draft goes through the same rewrite loop the later script check uses (up to MAX_PASSES on the REWRITABLE rules)
    # BEFORE generate() refuses: a fresh build blocked on its first draft for E3/E4/E8/E10 with no rewrite at all (5027 and 0587 on Ra,
    # 2026-11-24 21:27Z, fm:21662). A crashed rewriter is not fatal here; generate() below still refuses with the real rule.
    try:
        post = Path(pkg) / "post.md"
        rw = rewriter or upwork_rules.claude_rewriter(post.read_text() if post.is_file() else j.get("text", ""),
                                                       cfg().get("author", {}).get("model", "sonnet"))
        upwork_rules.rewrite_loop(pkg, rw)
    except Exception as e:  # noqa: BLE001
        print(f"scripts_and_gates: rewrite loop did not run: {str(e)[:160]}", file=sys.stderr)
    gen_scripts.generate(pkg, upwork=True)   # E1-E5 (knowledge#17592): refuses, writes nothing, when a rule is missing
    return gates.run_package(pkg)


def auto_fix_script(j, pkg, doc, c, steps):
    """One scripted fix when only the script gates fail (a banned word, a long row): the revise loop edits script-source.yaml with the gate's own
    reason as the words, then every gate runs again. Marked a test revision: it is the system correcting its own draft before READY, not a complaint
    about build quality, so it is neither counted in the revisions KPI nor does it extend build time."""
    failing = [g for g in doc.get("blocking", []) if g["id"] != 9]   # gate 9 (readiness) fails only because another gate did
    if not failing or any(g["id"] not in (3, 4) for g in failing) or steps.get("gates"):
        return doc
    import oneshot_revise
    words = "Fix every one of these script gate failures and change nothing else: " + " | ".join(f"{g['name']}: {r}" for g in failing for r in g["why"])
    rec = (steps.get("revise") or oneshot_revise.revise)(j["slug"], words, "script", None, c=c, test=True)
    if not rec.get("ok"):
        return doc
    import gates
    return gates.run_package(pkg)


def hunt_screening(j, c):
    """The hunt step's screening.json for this job (hunts_dir/<slug>/screening.json, written by the desk read of the apply form), copied into the package.
    -> [] when complete or screening is not required, else the problems. Never a skip: an incomplete one keeps the job unbuilt and says why."""
    if not c.get("screening_required"):
        return []
    pkg = PKG_ROOT / j["slug"]
    src = Path(c["hunts_dir"]) / j["slug"] / "screening.json"
    if src.is_file():
        pkg.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, pkg / "screening.json")
    return screening.problems(pkg)


def full_post(j, pkg):
    """The whole post, never the job record's feed snippet (~250 chars): the package's post.md, then the intake's hunts_dir copy, then the record's text.
    The reviewer and writer were handed the snippet, so 2046's reviewer judged rows against a truncated post and flagged real details as invented (knowledge#18069)."""
    hp = Path(cfg().get("hunts_dir", "/nonexistent")) / j.get("slug", Path(pkg).name) / "post.md"
    for p in (Path(pkg) / "post.md", hp):
        try:
            if p.is_file() and p.read_text().strip():
                return p.read_text()
        except OSError:   # an unreadable copy is no copy: the next source, never a crash
            continue
    return j.get("text") or ""


def script_check_loop(j, pkg, c, steps=None):
    """DETERMINISTIC script check first (no LLM): upwork_rules (the contract-generated E rules) then script_authoring.check_package, both on the written files.
    Then the copy-reviewer, which is REQUIRED (contract script.reviewer): a crash, a timeout or an unparseable reply is a named failure that BLOCKS READY,
    never a silent pass (knowledge#17827). This runs on every build pass and on every tick's re-check of a ready job, whatever stages are stamped."""
    import script_authoring
    import upwork_rules
    post = full_post(j, pkg)
    imax = None
    try:
        import gates
        imax = gates.contract()["intro"]["max_words"]
    except Exception:  # noqa: BLE001
        pass
    rw = (steps or {}).get("rewrite") or upwork_rules.claude_rewriter(post, c.get("author", {}).get("model", "sonnet"))
    try:
        ufails, passes = upwork_rules.rewrite_loop(pkg, rw)   # #17942: E4/E6/E10 are rewritten (up to 3 passes), not blocked
    except Exception as e:  # noqa: BLE001  a crashed rewriter is a named failure, never a silent pass
        ufails, passes = upwork_rules.check(pkg) or [{"rule": "rewrite", "row": None, "why": f"rewriter did not run: {str(e)[:100]}"}], 0
    fails = [{"file": "script-source.yaml", "row": x["row"], "why": f"{x['rule']}: {x['why']}" + (f" (still failing after {passes} rewrite passes)" if passes else "")} for x in ufails]
    if not ufails and (Path(pkg) / "script-source.yaml").is_file():
        try:
            import gen_scripts
            gen_scripts.generate(pkg, upwork=True)   # a rewritten (or hook-stripped) source re-renders before check_package reads the takes
        except Exception:  # noqa: BLE001  check_package still runs on what is on disk and names what fails
            pass
    fails += script_authoring.check_package(pkg, post, intro_max_words=imax)
    if not fails:
        rc = c.get("reviewer", {})
        rv = (steps or {}).get("review") or (lambda p, t: script_authoring.review(p, t, rc.get("model", "sonnet"), rc.get("timeout_s", 150)))
        # fm:19397: the reviewer's findings on body rows go back to the writer (up to MAX_PASSES), they no longer block on the first read
        for rpass in range(upwork_rules.MAX_PASSES + 1):
            try:
                fails = rv(pkg, post)
            except Exception as e:  # noqa: BLE001  the reviewer being down is a named non-pass, never a fill
                fails = [{"file": "entire-script.md", "row": None, "why": f"reviewer did not run: {str(e)[:100]}"}]
                break
            if not fails or rpass == upwork_rules.MAX_PASSES:
                break
            rw(pkg, [{"rule": "REVIEW", "row": x.get("row"), "why": x.get("why", "")} for x in fails])
            passes += 1
            ufails, more = upwork_rules.rewrite_loop(pkg, rw)   # the rewrite must still pass every deterministic rule
            passes += more
            if ufails:
                fails = [{"file": "script-source.yaml", "row": x["row"], "why": f"{x['rule']}: {x['why']} (after a reviewer rewrite)"} for x in ufails]
                if rpass == upwork_rules.MAX_PASSES - 1 or not all(x["rule"] in upwork_rules.REWRITABLE for x in ufails):
                    break
                continue   # a rewritable miss: the next pass hands the writer both the rules' and the reviewer's rows
            import gen_scripts
            gen_scripts.generate(pkg, upwork=True)   # the reviewer and check_package read the rendered take files
            fails = script_authoring.check_package(pkg, post, intro_max_words=imax)
            if fails:
                break
    doc = {"pass": not fails, "loops": passes, "failing_rows": fails}
    (Path(pkg) / "script-check.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def gates_advisory(c):
    """knowledge#18249 (Tyler ~13:30Z 2026-11-24: "Cut every gate that blocks a send"): with autosend.gates_block_ready false a failing gate, rehearsal,
    script_check or screening is recorded on the job (`advisories`) and the job still reaches READY and sends. Default True keeps the old behaviour for tests."""
    return not ((c or {}).get("autosend") or {}).get("gates_block_ready", True)


def advise(j, stage, why):
    j.setdefault("advisories", [])
    j["advisories"] = [a for a in j["advisories"] if a.get("stage") != stage] + [{"stage": stage, "why": str(why)[:300], "at": iso()}]


def recheck_ready(j, c=None, steps=None):
    """A READY job is graded again against the rules as they are NOW: stage stamps from an older build must not outlive a rule (package 4462 stayed
    `ready` while upwork_rules refused it, because a resumed run skips every stamped stage). Deterministic rules only (no LLM per tick).
    Demotes to blocked and clears the stamps so the next build pass re-runs gates and the script check. -> True when demoted."""
    import upwork_rules
    pkg = PKG_ROOT / j["slug"]
    if j.get("state") != "ready" or not (pkg / "script-source.yaml").is_file():
        return False
    fails = upwork_rules.check(pkg)
    if not fails:
        return False
    if gates_advisory(c):
        advise(j, "script_check", f"{fails[0]['rule']}: {fails[0]['why']}")
        save_job(j)
        return False
    j["state"] = "blocked"
    j["blocked_by"] = f"script_check: {fails[0]['rule']}: {fails[0]['why']}"
    for k in ("ready", "scripts_gates"):
        j["t"].pop(k, None)
    j["script_check"] = {"pass": False, "loops": 0, "failing_rows": [{"file": "script-source.yaml", "row": x["row"], "why": f"{x['rule']}: {x['why']}"} for x in fails][:6]}
    record_attempt(j, "script_check", j["blocked_by"])
    save_job(j)
    return True


def regen(pkg, steps=None, c=None):
    """Regenerate one package's scripts in place against TODAY's contract (knowledge#17827, fm:18791). Idempotent: a package that already passes upwork_rules
    with current take files is left byte-identical. REFUSES a package whose job is recorded, text_proposal-stamped or vsl_sent (a take or a send exists:
    rewriting words under it would lie). The writer pass edits only the rows the rules name; every take file is then regenerated and the script check runs.
    -> {"slug", "action": noop|regenerated|refused, "why"|"failing_rows"}"""
    import gen_scripts
    import script_authoring
    import upwork_rules
    steps = steps or {}
    pkg = Path(pkg)
    slug = pkg.name
    if not (pkg / "script-source.yaml").is_file():
        return {"slug": slug, "action": "refused", "why": "script-source.yaml missing"}
    try:
        j = load_job(slug)
    except FileNotFoundError:
        j = {"slug": slug, "text": (pkg / "post.md").read_text() if (pkg / "post.md").is_file() else "", "t": {}}
    done = [k for k in ("recorded", "text_proposal", "vsl_sent") if (j.get("t") or {}).get(k)]
    if done:
        return {"slug": slug, "action": "refused", "why": f"already {'/'.join(done)}: a take or a send exists, never rewrite under it"}
    fails = upwork_rules.check(pkg)
    files = [pkg / f for f in ("intro-script.md", "entire-script.md", "action-script.json")]
    if not fails and all(f.is_file() for f in files):
        # passing rules is not enough: the take files must be what today's renderer makes of the source (1339 kept a 53-word
        # intro row after the row split landed, because regen stopped here, 2026-11-24)
        upwork_rules.fill_file(pkg)
        src0 = gen_scripts.load_source(pkg / "script-source.yaml")
        if all((pkg / n).read_text() == gen_scripts.render(src0, t) for n, t in (("intro-script.md", "intro"), ("entire-script.md", "entire"))) \
                and not upwork_rules.check(pkg):
            return {"slug": slug, "action": "noop", "why": "already passes today's rules"}
        fails = upwork_rules.check(pkg)
        if not fails:
            gen_scripts.generate(pkg, upwork=True)
            return {"slug": slug, "action": "regenerated", "why": "take files re-rendered"}
    # the real post first: the package's post.md, then the intake's hunts_dir copy; the job record's `text` is only the feed
    # snippet (~250 chars), and writing from it left every E1/E8 blank generic (0062 regen, 2026-11-24, nova)
    hp = Path(cfg().get("hunts_dir", "/nonexistent")) / slug / "post.md"
    post = next((p.read_text() for p in (pkg / "post.md", hp) if p.is_file()), "") or j.get("text") or ""
    import s7_hook
    import yaml
    model = (c or cfg()).get("reviewer", {}).get("model", "sonnet")
    triple, s7_done = None, False

    def fill_s7():
        """The S7 hook is code, not prose (knowledge#17941): the model supplies a validated triple, the contract template does the rest."""
        nonlocal triple, s7_done
        if triple is None:
            triple, _why = s7_hook.author(post, steps.get("triple") or (lambda p: script_authoring._claude(p, model, pkg)))
        if triple:
            sy = pkg / "script-source.yaml"
            line = s7_hook.fill(triple)
            sy.write_text(yaml.safe_dump(s7_hook.apply(yaml.safe_load(sy.read_text()), line, len(s7_hook.rows_for(line)) if s7_done else None), sort_keys=False, allow_unicode=True))
            s7_done = True

    if any(x["rule"] == "E1" for x in fails):
        fill_s7()
        fails = upwork_rules.check(pkg)
    for _ in range(max(script_authoring.MAX_LOOPS, upwork_rules.MAX_PASSES)):   # the build path's 3 rewrite passes (#17961), not 2
        if not fails:
            break
        failing = [{"file": "script-source.yaml", "row": x["row"], "why": f"{x['rule']}: {x['why']}"} for x in fails]
        (steps.get("write") or (lambda p, t, f: script_authoring.write(p, t, f, model)))(pkg, post, failing)
        if triple:
            fill_s7()   # the writer may not break the fixed sentence: re-apply the validated triple after every pass
        fails = upwork_rules.check(pkg)
        if any(x["rule"] == "E1" for x in fails) and not triple:
            fill_s7()
            fails = upwork_rules.check(pkg)
    if fails:
        return {"slug": slug, "action": "refused", "why": "still failing after the writer pass", "failing_rows": [{"row": x["row"], "why": f"{x['rule']}: {x['why']}"} for x in fails][:8]}
    gen_scripts.generate(pkg, upwork=True)
    return {"slug": slug, "action": "regenerated"}


def first_error_line(err):
    """The first real error line of an attempt: the first non-empty line that is not a traceback frame or a bare marker."""
    for l in str(err).splitlines():
        l = l.strip()
        if l and not l.startswith(("Traceback", "File ", "^")):
            return l[:200]
    return str(err).strip()[:200] or "(no message)"


def record_attempt(j, stage, err):
    """Every failed attempt lands in j['attempts'] with its first real error line, so the record can be audited (the Architect counted 8, the record held 1)."""
    j.setdefault("attempts", []).append({"at": iso(), "stage": stage, "build_started": (j.get("t") or {}).get("build_started"), "error": first_error_line(err)})


def rehearsal_check(j, pkg, c):
    """The laptop rehearsal is driven by the staged-take runner on Eagle's box (never from a build: it would put work on Tyler's screen).
    The command in ONESHOT_REHEARSAL_DRIVER takes the package dir and prints `<recording> <session-log>`; absent, the result is a named non-pass."""
    sys.path.insert(0, str(KNOW / "net/work/vsl/takeflow"))
    import rehearsal
    cmd = os.environ.get("ONESHOT_REHEARSAL_DRIVER")

    def drive(p):
        if not cmd:
            return None
        r = subprocess.run([cmd, str(p)], capture_output=True, text=True, timeout=600)
        parts = r.stdout.split()
        return (parts[0], parts[1]) if r.returncode == 0 and len(parts) >= 2 else None
    return rehearsal.run(pkg, drive=drive)


REPAIR_MAX = 2   # author re-runs after a script-gate refusal, then the job blocks with the last message
REPAIRABLE = re.compile(r"\bE(?:0|1|3|4|6|7|8|9|10|11)\b")   # every upwork_rules.enforce rule an author fixes by rewriting; E-input (post.md missing) is not one


def repairable(msg):
    """True when the refusal is a wording/row problem the author can fix (E0 intro, E3 source, E4 grade/length, E8). An absent input is not."""
    m = str(msg or "")
    return bool(REPAIRABLE.search(m)) and "post.md missing" not in m and "input:" not in m


def author_repair(j, pkg, c, steps, msg):
    """Re-run the author step with the exact refusal text; the gates stay as strict as ever (the caller re-checks). Recorded in j['attempts']."""
    j["_repair"] = msg
    try:
        (steps.get("author") or (lambda j, w, c: author_worker(j, w, c)))(j, pkg, c)
    finally:
        j.pop("_repair", None)
    bad = check_authored(pkg, j["slug"], j.get("mvp_type", "copy"))
    if bad:
        raise RuntimeError("authored files rejected: " + "; ".join(bad))
    record_attempt(j, "author_repair", msg)
    save_job(j)


def with_author_repair(j, pkg, c, steps, run, msg_of):
    """Run a script-gate step; on a fixable refusal (raised upwork_rules.Refused, or msg_of(result) non-empty) feed it to the author and retry, at most
    REPAIR_MAX times. After that the last refusal is raised / returned unchanged, so the job blocks with the real last message."""
    import upwork_rules
    n = 0
    while True:
        err = None
        try:
            res = run()
            msg = msg_of(res)
        except upwork_rules.Refused as e:
            res, err, msg = None, e, str(e)
        if not msg or n >= REPAIR_MAX or not repairable(msg):
            if err:
                raise err
            return res
        n += 1
        author_repair(j, pkg, c, steps, msg)


STEPS = ["authored", "app", "diagram", "scripts_gates"]


def deliver_canonical(slug, pkg, c=None, public=None, hunts=None):
    """Put a finished package where Eagle and the take read it (hunts/upwork/<slug>: mvp, demo/architecture, copied_from.md, scripts, tabs.txt), then
    rename the tabs (tab_titles.py: '<Product> App' and 'Architecture', Tyler 2026-11-22 1:1x PM ET). Best effort: a folder owned by another user is
    reported in the result, never raised, so a build is not blocked by a permission it cannot fix."""
    import gates
    import acceptance
    c = c or cfg()
    public = Path(public) if public else gates.RA_PUBLIC
    dest = Path(hunts or c["hunts_dir"]) / slug
    out = {"dest": str(dest), "errors": []}
    try:
        src = public / f"{slug}-mvp" / "mvp"
        if not (src / "index.html").is_file():
            out["errors"].append(f"no built app at {src}")
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(dest / "mvp", ignore_errors=True)
            shutil.copytree(src, dest / "mvp")
        dia = pkg / "diagram"
        if dia.is_dir():
            (dest / "demo" / "architecture").mkdir(parents=True, exist_ok=True)
            for f in dia.iterdir():
                if f.is_file():
                    shutil.copy(f, dest / "demo" / "architecture" / f.name)
        md = acceptance.copied_md(pkg)
        if md:
            (pkg / "copied_from.md").write_text(md)
            (dest / "copied_from.md").write_text(md)
        for f in ("intro-script.md", "entire-script.md", "action-script.json"):
            if (pkg / f).is_file():
                shutil.copy(pkg / f, dest / f)
        base = "https://ra.tail4016d7.ts.net:8450/hunts"
        (dest / "tabs.txt").write_text(f"{base}/{slug}-mvp/mvp/\n{base}/{slug}-diagram/mvp/\n")     # the URLs ra_publish really serves (<slug>-mvp, <slug>-diagram); the old paths 404ed and every tab opened an error page
        sys.path.insert(0, str(HERE.parents[1] / "vsl" / "takeflow"))
        import tab_titles
        tab_titles.main([str(dest)])
        # the tabs open the PUBLISHED copies (tabs.txt), not the hunts copy: give them the same short titles (a 'Shadcn Admin' tab reached Tyler 11-22)
        import re as _re
        m = _re.search(r"<title>(.*?)</title>", (dest / "mvp" / "index.html").read_text(errors="replace"), _re.S | _re.I) if (dest / "mvp" / "index.html").is_file() else None
        for f, new in ((public / f"{slug}-mvp" / "mvp" / "index.html", m.group(1).strip() if m else None), (public / f"{slug}-diagram" / "mvp" / "index.html", "Architecture")):
            if new:
                note = tab_titles.set_title(f, new, False)
                if note and "NOT WRITABLE" in note:
                    out["errors"].append(note[:160])
    except Exception as e:  # noqa: BLE001
        out["errors"].append(str(e)[:160])
    return out


def meter_stage(j, stage):
    """Tokens and minutes for the stage that just finished -> the stage_meter table beside the status table. Never fails a build."""
    order = [k for k in ("build_started", "authored", "app", "diagram", "scripts_gates", "ready") if k in j["t"]]
    prev = order[order.index(stage) - 1] if stage in order and order.index(stage) else None
    mins = minutes(j["t"].get(prev), j["t"][stage]) if prev else None
    try:
        METER_DB.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(METER_DB)
        arch4.record_stage(db, j["slug"], stage, (j.get("tokens") or {}).get(stage), mins)
        db.close()
    except Exception as e:
        print(f"meter failed: {e}", file=sys.stderr)


def push_eagle(j):
    """knowledge#17557: tell Eagle Eye the job is built (or blocked, with its gate) the moment its state is set. Only the real state dir
    (or EAGLE_EMIT=1) pushes, so tests never reach Eagle Eye; never raises."""
    try:
        if os.environ.get("EAGLE_EMIT") != "1" and STATE != Path.home() / ".claude/state/net/oneshot-auto":
            return "skipped"
        sys.path.insert(0, str(HERE.parent / "upwork"))
        import eagle_emit
        r = eagle_emit.emit_job(j)
        if r.startswith("failed"):
            print(f"eagle emit {j.get('slug')}: {r}", file=sys.stderr)
        return r
    except Exception as e:  # noqa: BLE001
        return f"failed:{type(e).__name__}"


def run_job(slug, steps=None, c=None):
    try:
        return _run_job(slug, steps, c)
    finally:
        push_eagle(load_job(slug))   # whichever way the build ended, ready/blocked reaches the board


def _run_job(slug, steps=None, c=None):
    """Build one job end to end, stamping each stage the moment it finishes. `steps` replaces the outward functions in tests."""
    c = c or cfg()
    steps = steps or {}
    j = load_job(slug)
    j["state"] = "building"
    j["t"]["build_started"] = iso()   # the whole-build clock reap_stale reads (build_timeout_s)
    pkg = PKG_ROOT / slug
    pkg.mkdir(parents=True, exist_ok=True)
    if j.get("text") and not (pkg / "post.md").is_file():
        (pkg / "post.md").write_text(j["text"])   # upwork_rules and check_package read the package's own post.md (knowledge#17917)

    def stamp(stage):
        j["t"][stage] = iso()
        save_job(j)
        meter_stage(j, stage)

    try:
        save_job(j)
        def do_authored():
            (steps.get("author") or (lambda j, w, c: author_worker(j, w, c)))(j, pkg, c)
            bad = check_authored(pkg, slug, j.get("mvp_type", "copy"))
            if bad:
                raise RuntimeError("authored files rejected: " + "; ".join(bad))
            stamp("authored")

        def do_app():
            kind = j.get("mvp_type", "copy")
            fn = steps.get("app") or {"terminal": build_terminal, "copy": build_copy}.get(kind, build_app)
            ok = fn(j, pkg)
            if not ok:
                j["prereview_rebuilds"] = j.get("prereview_rebuilds", 0) + 1   # #16636: a pre-review failure is rebuilt before Horus; the count shows on the job
                save_job(j)
                ok = (steps.get("prereview") or (lambda s, w: prereview(s, w)))(slug, pkg)   # one retry of the pre-review alone (load timeouts)
            if not ok:
                raise RuntimeError("the app failed its pre-review twice")
            stamp("app")
        # a copied app is built first: the script is then written against the app as it was actually adapted
        order = [("app", do_app), ("authored", do_authored)] if j.get("mvp_type", "copy") == "copy" else [("authored", do_authored), ("app", do_app)]
        for name, fn in order:
            if name not in j["t"]:
                fn()
        if "diagram" not in j["t"]:
            (steps.get("diagram") or build_diagram)(j, pkg)
            stamp("diagram")
        if "scripts_gates" not in j["t"]:
            doc = with_author_repair(j, pkg, c, steps, lambda: (steps.get("gates") or scripts_and_gates)(j, pkg), lambda d: "")
            doc = auto_fix_script(j, pkg, doc, c, steps)
            j["gates"] = [{"id": g["id"], "name": g["name"], "status": g["status"], "why": g["why"][:2]} for g in doc["gates"]]
            if not doc["ready"] and gates_advisory(c):
                advise(j, "scripts_gates", "; ".join(f"gate {g['id']} {g['name']}: {g['why'][0]}" for g in doc.get("blocking", [])) or "gates not passing")
            elif not doc["ready"]:
                j["blocked_by"] = "; ".join(f"gate {g['id']} {g['name']}: {g['why'][0]}" for g in doc.get("blocking", [])) or "gates not passing"
                j["state"] = "blocked"
                record_attempt(j, "scripts_gates", j["blocked_by"])
                stamp("scripts_gates")
                return j
            stamp("scripts_gates")
        if c.get("rehearsal", {}).get("required", True):
            rh = (steps.get("rehearsal") or rehearsal_check)(j, pkg, c)   # writes rehearsal.json; Ready only when it passes
            if not rh["pass"] and gates_advisory(c):
                advise(j, "rehearsal", rh.get("pending") or f"row {(rh.get('failing_row') or {}).get('row')}")
            elif not rh["pass"]:
                fr = rh.get("failing_row") or {}
                j["blocked_by"] = "rehearsal: " + (rh.get("pending") or f"row {fr.get('row')}: {fr.get('say')}")
                j["state"] = "blocked"
                save_job(j)
                return j
        sc = with_author_repair(j, pkg, c, steps, lambda: (steps.get("script_check") or (lambda j, p, c: script_check_loop(j, p, c, steps)))(j, pkg, c),
                                lambda d: "" if d["pass"] else "; ".join(str(x.get("why")) for x in d.get("failing_rows", [])))   # deterministic; a failing script blocks READY
        j["script_check"] = {"pass": bool(sc["pass"]), "loops": sc.get("loops", 0), "failing_rows": sc.get("failing_rows", [])[:6]}
        if not sc["pass"] and gates_advisory(c):
            fr = (sc.get("failing_rows") or [{}])[0]
            advise(j, "script_check", f"{fr.get('file')}: {fr.get('why')}")
        elif not sc["pass"]:
            fr = (sc.get("failing_rows") or [{}])[0]
            j["blocked_by"] = f"script_check: {fr.get('file')}: {fr.get('why')}"
            j["state"] = "blocked"
            record_attempt(j, "script_check", j["blocked_by"])
            save_job(j)
            return j
        sp = hunt_screening(j, c)
        if sp and gates_advisory(c):
            advise(j, "screening", sp[0])
        elif sp:
            j["blocked_by"] = "screening: " + sp[0]
            j["state"] = "blocked"
            save_job(j)
            return j
        j["delivery"] = (steps.get("deliver") or deliver_canonical)(slug, pkg, c)   # canonical folders and short tab titles; never blocks READY
        j["state"] = "ready"
        j.pop("blocked_by", None)
        stamp("ready")
        save_job(j)
    except Exception as e:   # a named reason, never a plausible fill
        import traceback
        tb = traceback.extract_tb(e.__traceback__)[-1]
        j["state"] = "blocked"
        j["blocked_by"] = f"{type(e).__name__}: {str(e)[:200]} (at {Path(tb.filename).name}:{tb.lineno} in {tb.name})"
        record_attempt(j, next((k for k in STEPS + ["ready"] if k not in j["t"]), "ready"), e)   # a bare KeyError 'say' named nothing (GHL 4047, 04:59Z)
        (STATE / f"{j['slug']}.traceback").write_text(traceback.format_exc())
        save_job(j)
    return j


SEND_BAR_MIN = 60   # #16636: fresh post -> submitted proposal, the number the stamps are graded against


def minutes(a, b):
    return round((parse(b) - parse(a)).total_seconds() / 60, 1) if a and b else None


def durations(j):
    """Minutes spent in each build stage, in order: from the previous stamp (detected for the first)."""
    prev, out = j["t"].get("detected"), {}
    for s in sorted((x for x in ("authored", "app", "diagram", "scripts_gates") if j["t"].get(x)), key=lambda x: j["t"][x]):   # in the order they happened
        out[s] = minutes(prev, j["t"][s])
        prev = j["t"][s]
    return out


def screening_rows(j):
    """Eagle Eye shows each job's screening questions + answers on its row (knowledge#18203). [] when the hunt step has not read the form."""
    f = PKG_ROOT / j["slug"] / "screening.json"
    try:
        return [{"q": r["question"], "a": r["answer"], "status": r.get("status")} for r in json.loads(f.read_text())["questions"]]
    except (OSError, ValueError, KeyError):
        return []


def feed_state(j):
    """A job whose intro VSL already went out reads `sent`, not the stale `blocked` an earlier grade left on the record (knowledge#18771: 3307)."""
    return "sent" if j["state"] == "blocked" and (j.get("t") or {}).get("vsl_sent") else j["state"]


def row(j, c, at=None):
    at = at or iso()
    t = j["t"]
    start = t.get("detected") if j.get("backlog") else (t.get("posted") or t.get("detected"))
    end = t.get("vsl_sent") or at
    elapsed = minutes(start, end)
    dur = durations(j)
    slowest = max(dur.items(), key=lambda kv: kv[1])[0] if dur else None
    sla = c["sla"]["arrival_to_vsl_sent_min"]
    ready_in = minutes(start, t.get("ready"))
    return {"slug": j["slug"], "job": j.get("job"), "send_hold": j.get("send_hold"), "title": j["title"], "state": feed_state(j), "blocked_by": None if feed_state(j) == "sent" else j.get("blocked_by"), "screening": screening_rows(j),
            "ticks": {name: {"done": bool(t.get(stage)), "at": fmt_tz(t[stage], c) if t.get(stage) else None} for name, stage in c["export_stages"].items()},
            "elapsed_min": elapsed, "sla_min": sla, "sla_state": "done" if t.get("vsl_sent") else ("over" if elapsed and elapsed > sla else "running"),
            "ready_in_min": ready_in, "ready_budget_min": c["sla"]["arrival_to_ready_min"],
            "stage_min": dur, "stage_budget_min": c["stage_budget_min"], "slowest_stage": slowest,
            # #16636: the 60-minute bar and the rebuild count ride the published feed row, read from the stamps (never typed in)
            "bar_min": SEND_BAR_MIN, "prereview_rebuilds": j.get("prereview_rebuilds", 0),
            "detected_to_sent_min": minutes(t.get("detected"), t.get("proposal_sent") or t.get("vsl_sent")),
            "within_bar": None if not (t.get("proposal_sent") or t.get("vsl_sent")) else minutes(t.get("detected"), t.get("proposal_sent") or t.get("vsl_sent")) <= SEND_BAR_MIN,
            "over_budget": [s for s, m in dur.items() if m and m > c["stage_budget_min"].get(s, 1e9)],
            "gates": j.get("gates", []), "delay": delay_block(j, c, at), "autosend": autosend_block(j, c, at), "tz": c["display_tz"], "updated": fmt_tz(at, c)}


def autosend_block(j, c, at):
    """The Eagle Eye countdown ("Intro sends in mm:ss") + the FULL VSL button's state, from autosend.status (knowledge#17826)."""
    import autosend
    mode = read_full_mode()
    return dict(autosend.status(j, parse(at), mode, c), fit=autosend.fit_tier(j, c), full_button=j.get("state") == "ready" and not j.get("claimed_at"))


def delay_block(j, c, at):
    """Where each minute after READY went: three coloured segments (recording, revision, waiting on Tyler) and the revision count (oneshot_delay.py)."""
    import oneshot_delay as D
    a = D.attribute(j, parse(at))
    return {"minutes": a["minutes"], "revisions": a["revisions"], "revision_list": a["revision_list"],
            "segments": [{"tag": s["tag"], "label": D.PLAIN[s["tag"]], "colour": s["colour"], "minutes": s["minutes"],
                          "from": fmt_tz(s["from"], c), "to": fmt_tz(s["to"], c)} for s in a["segments"]]}


def session_manifest(pkgs, c=None):
    """The back-to-back run as data (no LLM turn between takes): per package the take files, the two tabs (tab 1 app, tab 2 diagram, each with its
    reset state), the action script and whether its gates say READY. Eagle/Vizier switch by reading this file in order."""
    c = c or cfg()
    jobs = []
    for p in pkgs:
        p = Path(p)
        g = json.loads((p / "gates.json").read_text())
        jobs.append({"slug": g["slug"], "ready": bool(g["ready"]), "waiting_on": [x["name"] for x in g["gates"] if x["status"] == "pending"],
                     "intro_script": str(p / "intro-script.md"), "entire_script": str(p / "entire-script.md"),
                     "action_script": str(p / "action-script.json"), "tabs": json.loads((p / "tabs.json").read_text())})
    doc = {"generated": fmt_tz(iso(), c), "tz": c["display_tz"], "take_type": "intro", "order": jobs,
           "all_ready": all(j["ready"] for j in jobs)}
    PKG_ROOT.mkdir(parents=True, exist_ok=True)
    (PKG_ROOT / "session.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def feed_doc(c=None):
    c = c or cfg()
    rows = [row(j, c) for j in all_jobs()]
    return {"tz": c["display_tz"], "updated": fmt_tz(iso(), c), "jobs": rows}


def write_feed(c=None):
    doc = feed_doc(c)
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "stages-feed.json").write_text(json.dumps(doc, indent=1) + "\n")
    PKG_ROOT.mkdir(parents=True, exist_ok=True)
    (PKG_ROOT / "stages-feed.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def plain_status(doc):
    out = [f"updated {doc['updated']}"]
    for r in doc["jobs"]:
        ticks = " > ".join(f"{k}{'*' if v['done'] else ''}" for k, v in r["ticks"].items())
        out.append(f"{r['slug']}: {r['state'].upper()}  {ticks}")
        out.append(f"   clock {r['elapsed_min']} of {r['sla_min']} min ({r['sla_state']}), ready in {r['ready_in_min']} min (budget {r['ready_budget_min']}), slowest: {r['slowest_stage']} {r['stage_min']}")
        if r["blocked_by"]:
            out.append(f"   BLOCKED: {r['blocked_by']}")
    return "\n".join(out)


# ---------------------------------------------------------------- tick
MIN_MEM_MB = 3000   # measured: the 6495 vite rebuild was OOM-killed with 2031 MB available / 779 MB free on a 14.7 GB box (2026-11-23 09:37Z); a per-build peak is not measured yet, so this sits above the killed level


def mem_available_mb():
    """MemAvailable from /proc/meminfo in MB, or None when unreadable (then the guard does not block)."""
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        return None
    return None


def running_builds():
    return [j for j in all_jobs() if j["state"] == "building"]


def build_alive(slug):
    """True while a `oneshot_auto.py run <slug>` process exists."""
    r = subprocess.run(["pgrep", "-f", f"oneshot_auto.py run {slug}"], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def kill_build(slug):
    subprocess.run(["pkill", "-f", f"oneshot_auto.py run {slug}"], capture_output=True)


def reap_stale(alive=None, c=None, kill=None, at=None):
    """A job marked building whose process is gone holds a max_concurrent_builds slot forever (7091 sat 40 min, 2026-11-22): put it back to queued.
    A build still alive past build_timeout_s (whole build, 10 min, Architect 2026-11-22) is killed and marked blocked, so the next newest job starts."""
    alive = alive or build_alive
    kill = kill or kill_build
    limit = (c or cfg()).get("build_timeout_s", 600)
    t_now = at or now()
    reaped = []
    for j in running_builds():
        if not alive(j["slug"]):
            j["state"] = "queued"
            save_job(j)
            reaped.append(j["slug"])
            continue
        started = j["t"].get("build_started")
        if started and (t_now - parse(started)).total_seconds() > limit:
            kill(j["slug"])
            j["state"] = "blocked"
            j["blocked_by"] = f"build exceeded {limit // 60} min and was killed"
            record_attempt(j, next((k for k in STEPS if k not in j["t"]), "ready"), j["blocked_by"])
            save_job(j)
            push_eagle(j)
            reaped.append(j["slug"])
    return reaped


def scan_mail(c, matches=None):
    """Job-alert mail -> job records at state `needs_description` (Architect 16665). Deduped by Upwork job id against every job and every skipped job;
    a mail older than mail.max_age_min is skipped with its reason; a role (skip_title) is skipped. targeted = the mail time. No script touches upwork.com."""
    import mail_jobs
    mc = c.get("mail") or {}
    ms = matches if matches is not None else mail_jobs.fetch_matches(mc.get("thread", "upwork-package"))
    seen = {j["job"] for j in all_jobs()}
    skipped = json.loads((STATE / "skipped.json").read_text()) if (STATE / "skipped.json").is_file() else {}
    new = []
    for m in ms:
        job = m["job"]
        if job in seen or job in skipped:
            continue
        age = (now() - parse(m["mail_at"])).total_seconds() / 60
        if age > mc.get("max_age_min", 90):
            skipped[job] = f"mail {round(age)} min old (max {mc.get('max_age_min', 90)})"
            continue
        if any(re.search(p, m["title"]) for p in c["skip_title"]):
            skipped[job] = f"a role, not a build ({m['title'][:40]})"
            continue
        j = {"slug": slugify(m["title"], job), "mvp_type": None, "job": job, "title": m["title"], "text": "", "link": f"https://www.upwork.com/jobs/{job}",
             "state": "needs_description", "source": "mail", "pay": m["pay"], "client": m["client"], "category": m["category"],
             "posted_at": m["mail_at"], "t": {"posted": m["mail_at"], "targeted": m["mail_at"], "detected": iso()}, "created": iso()}
        save_job(j)
        seen.add(job)
        new.append(j)
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "skipped.json").write_text(json.dumps(skipped, indent=1) + "\n")
    return new


def feed_job_desc(c):
    """knowledge#17917: the job-description desk (job-desc.py) writes <job_desc_dir>/<job id>.json {job, link, title, desc, ok, read_at}. For every job that
    has no post.md yet and whose desk read is `ok` with at least min_post_chars of desc, write hunts_dir/<slug>/post.md = the title line + the desc VERBATIM and
    record post_source: job-desc. A job blocked ONLY on `post.md missing` goes back to queued (every other block reason is left alone); a queued job's text becomes
    the real post. An existing post.md is never overwritten. -> slugs fed."""
    ddir = Path(c.get("job_desc_dir", "/nonexistent"))
    if not ddir.is_dir():
        return []
    fed = []
    for j in all_jobs():
        st = j.get("state")
        only_missing = st == "blocked" and "post.md missing" in (j.get("blocked_by") or "")
        if st not in ("needs_description", "queued") and not only_missing:
            continue
        dest = Path(c["hunts_dir"]) / j["slug"] / "post.md"
        if not dest.is_file():
            jid = j.get("job") or ""
            src = next((f for f in (ddir / f"{jid}.json", ddir / f"{jid.lstrip('~')}.json", ddir / f"~{jid.lstrip('~')}.json") if f.is_file()), None)
            if not src:
                continue
            try:
                d = json.loads(src.read_text())
            except (OSError, ValueError):
                continue
            desc = d.get("desc") or ""
            if d.get("ok") is not True or len(desc) < c["min_post_chars"]:
                why = d.get("why") or f"desc shorter than {c['min_post_chars']} chars"     # never silent: the job says why it is stuck (2026-11-24 5765/0587)
                if (j.get("desc_failed") or {}).get("why") != why:
                    j["desc_failed"] = {"why": str(why)[:160], "read_at": d.get("read_at"), "seen_at": iso()}; save_job(j)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"{d.get('title') or j.get('title') or ''}\n\n{desc}\n")
            j["post_source"] = "job-desc"
        if not dest.is_file():
            continue
        if only_missing or (st == "queued" and j.get("post_source") == "job-desc"):
            j["text"] = dest.read_text()
        if only_missing:
            j["state"] = "queued"
            j.pop("blocked_by", None)
            for k in ("scripts_gates", "ready"):
                j["t"].pop(k, None)
        save_job(j)
        fed.append(j["slug"])
    return fed


def promote_described(c):
    """A needs_description job whose post text has been read by hand (hunts/upwork/<slug>/post.md, at least min_post_chars) becomes `queued`; the
    file time is description_at, so targeted -> description_at is measured. The text, the build type and the library pick are set here."""
    done = []
    for j in all_jobs():
        if j["state"] != "needs_description":
            continue
        p = Path(c.get("hunts_dir", "/nonexistent")) / j["slug"] / "post.md"
        if not p.is_file():
            continue
        text = p.read_text()
        if len(text) < c["min_post_chars"]:
            continue
        j["text"] = text
        j["t"]["description_at"] = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        j["mvp_type"] = choose_mvp_type(text)
        j["library"] = library_pick(j["title"], text)
        j["state"] = "queued"
        save_job(j)
        done.append(j["slug"])
    return done


def describe(slug, src, c=None):
    """Put the by-hand post text where the build reads it: hunts/upwork/<slug>/post.md (verbatim copy of src), then promote."""
    c = c or cfg()
    d = Path(c["hunts_dir"]) / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "post.md").write_text(Path(src).read_text())
    return promote_described(c)


READY_CAP = int(os.environ.get("ONESHOT_READY_CAP", "10"))


READY_WINDOW_H = float(os.environ.get("ONESHOT_READY_WINDOW_H", "6"))   # nova 18508 (was 12 h, Architect 18196): a package older than 6 h no longer counts toward the ready-unsent cap; fit jobs pass 50 proposals in 1-2 h


def ready_unsent(now=None):
    """Slugs of READY packages with no text_proposal / vsl_sent stamp whose job was posted within READY_WINDOW_H hours (0 = no window)."""
    now_t = now or globals()["now"]()
    out = []
    for j in all_jobs():
        if j.get("state") != "ready" or j["t"].get("text_proposal") or j["t"].get("vsl_sent"):
            continue
        p = j["t"].get("posted") or j.get("posted_at") or ""
        if READY_WINDOW_H and p:
            try:
                if (now_t - parse(p)).total_seconds() / 3600 > READY_WINDOW_H:
                    continue
            except (ValueError, TypeError):
                pass
        out.append(j["slug"])
    return out


def expire_stale(now_t=None):
    """A QUEUED or BLOCKED job posted more than READY_WINDOW_H hours ago is marked state "expired" instead of built: a package finished for a job past the window is stale
    before it exists (2026-11-24: 16 of 34 builds were for jobs already over 6 h old, ~2.5 h of builder time; nova 18612). Same setting as the cap window,
    ONESHOT_READY_WINDOW_H (0 = never expire). A job with no posted time is left alone. -> slugs expired."""
    if not READY_WINDOW_H:
        return []
    now_t = now_t or now()
    out = []
    for j in all_jobs():
        if j.get("state") not in ("queued", "blocked"):
            continue
        p = j["t"].get("posted") or j.get("posted_at") or ""
        try:
            age_h = (now_t - parse(p)).total_seconds() / 3600
        except (ValueError, TypeError):
            continue
        if age_h > READY_WINDOW_H:
            was = j["state"]
            j["state"] = "expired"
            j["expired"] = {"at": iso(), "was": was, "why": f"{was} job posted {age_h:.1f} h ago, past the {READY_WINDOW_H:g} h window (nova 18612)"}
            save_job(j)
            out.append(j["slug"])
    return out


def feed_alarm(c, rows, at=None, send=None):
    """knowledge#18532: the tick sees no new Upwork row for `feed_alarm_min` (default 60) while posts wait for a description -> ONE fleetmail to chief
    naming the dead component, per episode (re-sent only after the feed recovers). Measured 2026-11-24: every one of 154 jobs sat in needs_description
    with job_desc_dir absent, and no row had arrived since 16:34Z, while the tick printed an empty result for hours."""
    at = parse(at) if at else parse(iso())
    lim = float(c.get("feed_alarm_min", 60))
    rts = [r.get("foundAt") or r.get("signalAt") or "" for r in rows]
    newest = max([t.replace(".000Z", "Z") for t in rts if t] or [""])
    waiting = [j for j in all_jobs() if j.get("state") == "needs_description"]
    stamp = STATE / "feed-alarm.json"
    stale_rows = bool(newest) and minutes(newest, at.strftime("%Y-%m-%dT%H:%M:%SZ")) >= lim
    ddir = Path(c.get("job_desc_dir", "/nonexistent"))
    desc_dead = bool(waiting) and (not ddir.is_dir() or not any(ddir.glob("*.json")))
    dead = []
    if desc_dead:
        dead.append(f"job-desc reader (nothing in {ddir}; {len(waiting)} posts wait in needs_description)")
    if stale_rows:
        dead.append(f"hunt feed rows (newest row {newest}, limit {lim:g} min)")
    # knowledge#18574: name EACH intake source whose newest row is past the limit (measured 2026-11-24: the desk most-recent source sat 15 h dead
    # while the dev@ alert mail kept the all-rows newest fresh, so the aggregate check above never fired)
    by_src = {}
    for r in rows:
        s = (r.get("details") or {}).get("src")
        t = (r.get("foundAt") or r.get("signalAt") or "").replace(".000Z", "Z")
        if s and t:
            by_src[s] = max(by_src.get(s, ""), t)
    now_s = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in sorted(set(by_src) | set(c.get("feed_sources") or [])):
        n = by_src.get(s)
        if n is None:
            dead.append(f"intake source '{s}' (no row at all, limit {lim:g} min)")
        elif minutes(n, now_s) >= lim and not (stale_rows and n == newest):
            dead.append(f"intake source '{s}' (newest row {n}, limit {lim:g} min)")
    if not dead:
        stamp.unlink(missing_ok=True)
        return None
    if stamp.is_file():
        return None
    body = "oneshot-auto: no new Upwork build input for " + f"{lim:g}" + " min. Dead component: " + "; ".join(dead) + ". Nothing is built or sent until it is back. (knowledge#18532)"
    try:
        (send or (lambda b: subprocess.run(["fleetmail", "send", "chief", b, "--thread", "one-shot", "--ref", "18532"], check=True)))(body)
        STATE.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps({"at": iso(), "dead": dead}) + "\n")
    except Exception as e:
        print(f"feed alarm not sent: {e}", file=sys.stderr)
    return dead


def backlog_alarm(c, at=None, send=None):
    """knowledge#18593: ONE fleetmail to chief naming the component when (a) the job-desc reader's heartbeat (<job_desc_dir>/.reader-heartbeat, touched every loop)
    is older than backlog_alarm_min (default 15) while posts wait, or (b) more than backlog_max (default 20) jobs have sat in needs_description for that long.
    Per episode; the stamp clears when both are healthy. Private listings (desc_failed 'private listing') never count as waiting."""
    at = parse(at) if at else parse(iso())
    lim = float(c.get("backlog_alarm_min", 15)); mx = int(c.get("backlog_max", 20))
    waiting = [j for j in all_jobs() if j.get("state") == "needs_description" and "private listing" not in str((j.get("desc_failed") or {}).get("why", ""))]
    hb = Path(c.get("job_desc_dir", "/nonexistent")) / ".reader-heartbeat"
    over = STATE / "backlog-over-since.json"
    stamp = STATE / "backlog-alarm.json"
    dead = []
    if waiting:
        hb_age = (at.timestamp() - hb.stat().st_mtime) / 60 if hb.is_file() else None
        if hb_age is None or hb_age >= lim:
            dead.append("job-desc reader down (" + ("no heartbeat file" if hb_age is None else f"last heartbeat {hb_age:.0f} min ago") + f"; {len(waiting)} posts wait)")
    if len(waiting) > mx:
        STATE.mkdir(parents=True, exist_ok=True)
        if not over.is_file():
            over.write_text(json.dumps({"since": iso()}) + "\n")
        elif minutes(json.loads(over.read_text())["since"], iso(at)) >= lim:
            dead.append(f"needs_description backlog {len(waiting)} > {mx} for {lim:g} min")
    else:
        over.unlink(missing_ok=True)
    if not dead:
        stamp.unlink(missing_ok=True)
        return None
    if stamp.is_file():
        return None
    body = "oneshot-auto: " + "; ".join(dead) + ". Dead component: job-desc reader (job-desc-watch.service on novaserver, user upwork). (knowledge#18593)"
    try:
        (send or (lambda b: subprocess.run(["fleetmail", "send", "chief", b, "--thread", "one-shot", "--ref", "18593"], check=True)))(body)
        STATE.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps({"at": iso(), "dead": dead}) + "\n")
    except Exception as e:
        print(f"backlog alarm not sent: {e}", file=sys.stderr)
    return dead


def screening_holds(c):
    """knowledge#18574: every queued job held by a missing/incomplete screening.json, NAMED (serve.json + the Eagle Eye row via blocked_by), and the desk
    apply-form read REQUESTED once per job (state/screening-requests/<slug>.json, the desk reader's queue). -> [{slug, hold}]."""
    out = []
    for j in all_jobs():
        if j.get("state") != "queued":
            continue
        p = hunt_screening(j, c)
        if not p:
            if str(j.get("blocked_by") or "").startswith("screening hold"):
                j["blocked_by"] = None
                save_job(j)
            continue
        why = f"screening hold: {p[0]} (no screening.json from the desk apply-form read; read requested)"
        req = STATE / "screening-requests" / f"{j['slug']}.json"
        if not req.is_file():
            req.parent.mkdir(parents=True, exist_ok=True)
            req.write_text(json.dumps({"slug": j["slug"], "job": j.get("job"), "at": iso(), "want": str(Path(c.get("hunts_dir", "")) / j["slug"] / "screening.json")}) + "\n")
        if j.get("blocked_by") != why:
            j["blocked_by"] = why
            save_job(j)
        out.append({"slug": j["slug"], "hold": why})
    return out


def request_intro_renders(held):
    """knowledge#18574: a due intro held `mp4_missing` asks the vsl backend for its render ONCE (state/intro-requests/<slug>.json; the request is the trigger,
    deleted by nothing: the mp4 landing clears the hold). -> slugs newly requested."""
    out = []
    for slug, why in (held or {}).items():
        if why != "mp4_missing":
            continue
        req = STATE / "intro-requests" / f"{slug}.json"
        if not req.is_file():
            req.parent.mkdir(parents=True, exist_ok=True)
            req.write_text(json.dumps({"slug": slug, "at": iso(), "want": str(PKG_ROOT / slug / "intro.mp4")}) + "\n")
            out.append(slug)
    return out


def tick(feed=None, spawn=True, c=None):
    """Scan, start the NEWEST-posted queued job when no build runs (max_concurrent_builds), refresh the feed. Stateless per call."""
    c = c or cfg()
    rows = feed_rows(feed if feed is not None else fetch_feed(c["feed_url"]))
    pulled = pull_picks(c)
    new = scan(rows, c)
    new += scan_mail(c)
    sync_sends()
    feed_job_desc(c)
    promote_described(c)
    expire_stale()
    reap_stale()
    demoted = [j["slug"] for j in all_jobs() if recheck_ready(j, c)]   # a ready job that fails today's rules is not ready (knowledge#17827)
    started = None
    guard = arch4.allowed_builds(arch4.measure(str(Path.home())), cap=c["max_concurrent_builds"])
    mem_mb = mem_available_mb()
    guard["mem_available_mb"] = mem_mb
    if mem_mb is not None and mem_mb < MIN_MEM_MB:
        guard["allowed"], guard["why"] = 0, f"{mem_mb} MB memory available < {MIN_MEM_MB} (a build was OOM-killed at 2031 MB available, 2026-11-23 09:37Z); " + str(guard.get("why", ""))
    prebuilt = any((PKG_ROOT / j["slug"] / "app/dist/.prebuilt").is_file() for j in all_jobs() if j["state"] == "queued")
    if spawn and prebuilt and guard["allowed"] == 0 and mem_mb is not None and mem_mb < MIN_MEM_MB:
        guard["allowed"] = 1   # a job with a prebuilt dist (built elsewhere) skips vite, so the memory guard does not apply to it
    # PAUSE (Tyler card 2026-11-23 ~10:00 ET, Architect fleetmail 18028): no new build while READY_CAP packages are ready but
    # unsent (state ready, no text_proposal / vsl_sent stamp). MEASURED on Ra 2026-11-23 14:40Z: 110 jobs, 62 ready+unsent, 41
    # blocked, 7 queued -> the builder pauses now. ONESHOT_READY_CAP=0 turns the pause off.
    waiting = ready_unsent()
    if READY_CAP and len(waiting) >= READY_CAP:
        guard["allowed"], guard["why"] = 0, f"paused: {len(waiting)} packages ready but unsent (cap {READY_CAP}); " + str(guard.get("why", ""))
    if spawn and len(running_builds()) < guard["allowed"]:
        # NEWEST FIRST (Architect 2026-11-22): the job posted most recently starts first; a job with no posted time goes last
        q = sorted([j for j in all_jobs() if j["state"] == "queued"], key=lambda j: (bool(j.get("take_type")), j["t"].get("posted") or ""), reverse=True)   # a picked job (knowledge#18050) first, each group newest first
        q = [j for j in q if not hunt_screening(j, c)]   # no build or recording starts before screening.json answers every question (knowledge#18203)
        if mem_mb is not None and mem_mb < MIN_MEM_MB:   # low memory: only a prebuilt job (no vite) may start
            q = [j for j in q if (PKG_ROOT / j["slug"] / "app/dist/.prebuilt").is_file()]
        if q:
            started = q[0]["slug"]
            try:   # each worker gets its own detached worktree of origin/main as cwd; the hard 10-min cap is reap_stale
                wt = arch4.make_worktree(str(KNOW), started, str(WORKTREES))
            except Exception as e:
                print(f"worktree failed ({e}); worker runs in {KNOW}", file=sys.stderr)
                wt = str(KNOW)
            subprocess.Popen([sys.executable, str(HERE / "oneshot_auto.py"), "run", started], stdout=open(STATE / f"{started}.log", "w"),
                             stderr=subprocess.STDOUT, start_new_session=True, cwd=wt)
    due = due_intros(c)
    import intro_sender, intro_verify
    for slug in due:   # knowledge#18734: only a VERIFY pass sends. A file with no current verdict is verified here (frames + audio), never trusted.
        mp4 = PKG_ROOT / slug / "intro.mp4"
        if mp4.is_file() and intro_verify.verified(PKG_ROOT / slug, mp4)[1] in ("verify_missing", "verify_stale"):
            try:
                intro_verify.run(slug, PKG_ROOT)
            except Exception as e:   # an unreadable file is a failed verify, held and reported by the sender
                print(f"verify {slug} crashed: {e}", file=sys.stderr)
    sent = intro_sender.run(due, load_job, save_job, PKG_ROOT, STATE / "handed.json", iso()) if due else {"handed": [], "held": {}, "errors": {}}
    alarm = feed_alarm(c, rows)
    alarm = (alarm or []) + (backlog_alarm(c) or []) or None
    holds = screening_holds(c)
    intro_req = request_intro_renders(sent.get("held") or {})
    write_feed(c)
    return {"alarm": alarm, "screening_holds": holds, "intro_held": sent.get("held"), "intro_render_requested": intro_req, "new": [j["slug"] for j in new], "started": started, "picks": pulled, "due_intros": due, "intro_send": sent, "demoted": demoted, "guard": {k: guard.get(k) for k in ("allowed", "load1", "cores", "disk_free_gb", "mem_available_mb", "why")}}


# ---------------------------------------------------------------- triage picks (knowledge#18050)
KV_NS = "d97b9be8758d4ede805c0bf9c6d2e68c"   # eagle-eye-data; the page's FULL / INTRO buttons write KV `triage/<job key>` (handler-dev.js)


def picks_path():
    return STATE / "picks.json"


def read_picks():
    try:
        return json.loads(picks_path().read_text())
    except (OSError, ValueError):
        return {}


def job_keys():
    """Every job key we know of: job records, picks, and (best effort) the Upwork feed's triage rows, so 'full 1435' resolves."""
    return sorted({j["job"] for j in all_jobs() if j.get("job")} | set(read_picks()))


def set_pick(key, take, by="button", at=None):
    """Tyler or Eagle picks FULL or INTRO for one job (knowledge#18050). Written to picks.json AND onto the job record's `take_type`
    (a job with no record yet gets it stamped by scan()). A pick is the latest word: re-picking overwrites. `full` also stops the
    intro auto-send (autosend.status -> held) because a FULL job is Tyler's to record."""
    if take not in ("full", "intro"):
        raise ValueError("take must be full or intro")
    key = key if key.startswith("~") else "~" + key
    rec = {"take": take, "by": by, "at": at or iso()}
    picks = read_picks()
    picks[key] = rec
    STATE.mkdir(parents=True, exist_ok=True)
    picks_path().write_text(json.dumps(picks, indent=1) + "\n")
    stamped = []
    for j in all_jobs():
        if j.get("job") == key:
            j.update(take_type=take, picked_by=by, picked_at=rec["at"])
            save_job(j)
            stamped.append(j["slug"])
    return {"key": key, **rec, "records": stamped}


def pull_picks(c=None):
    """Drain the KV `triage/*` keys the page wrote (best effort; a failure is returned, never raised): apply each newer than what picks.json holds."""
    get = lambda k: subprocess.run(["cred", "get", "fleet-infra", k], capture_output=True, text=True).stdout.strip()  # noqa: E731
    try:
        tok, acct = get("CF_API_TOKEN_UTOPIA"), get("CF_ACCOUNT_ID_UTOPIA")
        if not tok or not acct:
            return {"error": "no CF credential"}
        base = f"https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces/{KV_NS}"
        h = {"Authorization": f"Bearer {tok}"}
        names = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/keys?prefix=triage/", headers=h), timeout=20).read())["result"]
        have, applied_ = read_picks(), []
        for n in names:
            v = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/values/" + urllib.parse.quote(n["name"], safe=""), headers=h), timeout=20).read())
            k = v.get("key")
            if k and v.get("take") in ("full", "intro") and (have.get(k) or {}).get("at", "") < v.get("at", ""):
                set_pick(k, v["take"], v.get("by", "button"), v.get("at"))
                applied_.append(k)
        return {"applied": applied_}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"[:200]}


def full_mode_path():
    return STATE / "full-mode.json"


def read_full_mode():
    try:
        return json.loads(full_mode_path().read_text())
    except (OSError, ValueError):
        return None


def claim_job(slug, voice=False, at=None, c=None):
    """Tyler claims a READY job for a FULL VSL (button or voice, asks 3122/3137): stops its intro timer; a voice claim also opens full mode (autosend.claim)."""
    import autosend
    c = c or cfg()
    j = load_job(slug)
    if j.get("state") != "ready":
        raise ValueError(f"{slug} is {j.get('state')}, only a ready job can be claimed")
    now_ = parse(at) if at else parse(iso())
    mode = autosend.claim(j, now_, voice=voice, mode=read_full_mode(), c=c)
    save_job(j)
    if voice and mode:
        full_mode_path().write_text(json.dumps(mode))
    # knowledge#18939: the claim IS the take-over, so the job's full-VSL script lands on Vizier's speaker script in the same call
    return {"slug": slug, "claim_by": j["claim_by"], "full_mode": mode, "status": autosend.status(j, now_, mode, c), "script": load_full_script(slug)}


VIZIER_PUT = Path(os.environ.get("VIZIER_PUT") or HERE.parent / "vizier" / "vizier-put.sh")


def load_full_script(slug, put=None):
    """knowledge#18939: write the job's full-VSL script (the package's entire-script.md, every row [Tyler]) onto Vizier's speaker script NOW,
    through vizier-put.sh (one atomic POST, ~45 ms measured on Ra). Stamps script_loaded_at / script_sha on the job record. Never raises:
    a missing script or a refused put comes back as {ok: False, why}, so a claim still stops the timer."""
    f = PKG_ROOT / slug / "entire-script.md"
    if not f.is_file() or not f.read_text().strip():
        return {"ok": False, "why": f"no {f.name} in the package yet (the writer has not finished); the claim stands, load it once the package is built"}
    t0 = time.time()
    try:
        r = (put or (lambda p: subprocess.run(["bash", str(VIZIER_PUT), str(p), "speaker-script"], capture_output=True, text=True, timeout=15)))(f)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "why": f"vizier-put did not run: {type(e).__name__}: {e}"[:200]}
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"sha=(\w+)", out)
    if r.returncode != 0 or not m:
        return {"ok": False, "why": ("vizier-put exit %d: %s" % (r.returncode, out.strip()[-160:]))}
    j = load_job(slug)
    j.update(script_loaded_at=iso(), script_sha=m.group(1))
    save_job(j)
    return {"ok": True, "sha": m.group(1), "ms": round((time.time() - t0) * 1000), "at": j["script_loaded_at"]}


def find_job(token):
    """A slug, or any trailing digits of the Upwork job id ('full 1435'), -> the one job record, or None."""
    jobs = all_jobs()
    hit = [j for j in jobs if j["slug"] == token]
    if not hit:
        d = re.sub(r"\D", "", str(token))
        hit = [j for j in jobs if d and re.sub(r"\D", "", j.get("job") or "").endswith(d)] if len(d) >= 4 else []
    return hit[0] if len(hit) == 1 else None


def take_over(token, take="full", voice=False, at=None, c=None):
    """Tyler's one tap (button or voice) on a hunt: FULL stops the intro countdown, claims the job when it is READY, and loads its full-VSL script into
    Vizier; INTRO puts it back on the auto-send clock. Works on a job that is not ready yet (the pick makes it build first; the claim lands
    once it is ready). -> hunt_state(slug) plus what each step did."""
    j = find_job(token)
    if not j:
        raise ValueError(f"{token!r} matches no single job")
    by = "voice" if voice else "button"
    out = {"pick": set_pick(j["job"], take, by, at) if j.get("job") else None}
    if take == "full":
        if load_job(j["slug"]).get("state") == "ready":
            out["claim"] = claim_job(j["slug"], voice=voice, at=at, c=c)   # also loads the script
        else:
            out["script"] = load_full_script(j["slug"])
    else:
        jj = load_job(j["slug"])
        for k in ("claimed_at", "claim_by"):
            jj.pop(k, None)
        save_job(jj)
    try:
        write_feed(c)   # the page's countdown reads this; the tap itself has already landed, so a feed error is reported, never raised
    except Exception as e:  # noqa: BLE001
        out["feed_error"] = f"{type(e).__name__}: {e}"[:160]
    return dict(hunt_state(j["slug"], at=at, c=c), did=out)


def hunt_state(token, at=None, c=None):
    """What the hunt page draws on one job: the autosend status, the pick and who made it, and whether Vizier holds its script."""
    import autosend
    c = c or cfg()
    j = find_job(token)
    if not j:
        return {"found": False}
    now_ = parse(at) if at else parse(iso())
    st = autosend.status(j, now_, read_full_mode(), c)
    return {"found": True, "slug": j["slug"], "job": j.get("job"), "take": j.get("take_type"), "by": j.get("picked_by") or j.get("claim_by"),
            "claim_by": j.get("claim_by"), "claimed_at": j.get("claimed_at"), "state": st["state"], "label": st["label"], "send_at": st["send_at"],
            "remaining_s": st["remaining_s"], "script_loaded_at": j.get("script_loaded_at"), "script_sha": j.get("script_sha")}


def due_intros(c=None, at=None):
    """Slugs whose intro should send this tick (ask 3124): ready, unclaimed past its fit delay, or claimed but not recorded in time. Decides only; the upwork desk sends and stamps vsl_sent."""
    import autosend
    c = c or cfg()
    return autosend.due_jobs(all_jobs(), read_full_mode(), parse(at) if at else parse(iso()), c)


def mark_stage(slug, stage, ts=None):
    """Stamp a human-side stage (recorded, text_proposal, vsl_sent) on the job record. The handler of those three stages in pipelines/upwork.yaml."""
    if stage not in ("recorded", "text_proposal", "vsl_sent"):
        raise ValueError("stage must be recorded, text_proposal or vsl_sent")
    j = load_job(slug)
    j["t"][stage] = ts or iso()
    save_job(j)
    return j


LEDGER = Path(os.environ.get("ONESHOT_LEDGER") or Path.home() / ".claude/state/net/upwork/ledger.jsonl")


def sync_sends(ledger=None):
    """Propagate the upwork ledger's sends to the job records (Eagle Eye showed "VSL proposal pending" for jobs already sent, 2026-11-24:
    3 of 160 jobs carried the vsl_sent stamp). A vsl_sent row stamps t.vsl_sent; a proposal_sent row with no vsl_sent for that job stamps
    t.text_proposal. Reuses mark_stage, only where the stamp is absent (idempotent), keeping the ledger's own ts. -> list of (slug, stage)."""
    p = Path(ledger or LEDGER)
    if not p.is_file():
        return []
    first = {}
    for line in p.read_text(errors="replace").splitlines():
        if '"vsl_sent"' not in line and '"proposal_sent"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        jid = str(r.get("job") or "").lstrip("~")
        if r.get("event") in ("vsl_sent", "proposal_sent") and jid and r.get("ts"):
            first.setdefault((jid, r["event"]), r["ts"])
    done = []
    for j in all_jobs():
        jid = str(j.get("job") or "").lstrip("~")
        stage = "vsl_sent" if (jid, "vsl_sent") in first else "text_proposal" if (jid, "proposal_sent") in first else None
        if stage and not (j.get("t") or {}).get(stage):
            mark_stage(j["slug"], stage, first[(jid, "vsl_sent" if stage == "vsl_sent" else "proposal_sent")])
            done.append((j["slug"], stage))
    return done


# The dispatch table (knowledge#17826): stage id -> the function that runs it. vsl/pipelines/upwork.yaml names the same functions;
# pipeline_spec.lint() fails when a handler here has no stage there, or a stage there has no handler here. `dispatch(stage, ...)` REFUSES an unregistered id.
STAGE_HANDLERS = {
    "detected": scan,
    "authored": author_worker,
    "app": build_copy,
    "diagram": build_diagram,
    "scripts_gates": scripts_and_gates,
    "ready": deliver_canonical,
    "recorded": mark_stage,
    "text_proposal": mark_stage,
    "vsl_sent": mark_stage,
}


def dispatch(stage, *a, **kw):
    fn = STAGE_HANDLERS.get(stage)
    if fn is None:
        raise KeyError(f"stage {stage!r} has no registered handler (vsl/pipelines/upwork.yaml and STAGE_HANDLERS must agree)")
    return fn(*a, **kw)


STAGED_STAMPS = Path(os.environ.get("VSL_STAGED_STAMPS", "/var/tmp/vsl-staged.jsonl"))   # render_queue --push appends {"slug","at"} per staged take


def heartbeat(**kw):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "serve.json").write_text(json.dumps({"at": iso(), "pid": os.getpid(), **kw}) + "\n")


SELF_UPDATE_EVERY_S = 300   # measured 2026-11-24: one `git fetch` + ff merge on ra is ~1 s; 5 min bounds how stale the builder can run


def self_update(repo=None, run=subprocess.run):
    """knowledge#18538 (Tyler, 3x: "why are one shots still not being built"): the builder on ra ran 652 commits behind main, so the merged #18251
    fix (a post not read yet waits instead of a permanent skip) never reached it and every row after 05:40Z was skipped. Fast-forward the clone
    the service runs from. -> 'updated' (caller re-execs), 'current', or a named reason it did not (dirty tree, diverged, fetch failed): never raises."""
    repo = str(repo or KNOW)
    def g(*a):
        return run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=120)
    try:
        if g("fetch", "-q", "origin", "main").returncode:
            return "fetch failed"
        if int(g("rev-list", "--count", "HEAD..origin/main").stdout.strip() or 0) == 0:
            return "current"
        if g("status", "--porcelain", "--untracked-files=no").stdout.strip():
            return "dirty tree: local edits block the fast-forward"
        return "updated" if g("merge", "--ff-only", "origin/main").returncode == 0 else "not a fast-forward"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:80]}"


def serve(every=20):
    """The trigger as a service: never exits on a bad tick (the error line is logged and the next tick runs). Liveness = `live`."""
    import time, traceback
    heartbeat(state="starting", every=every)
    last_update = 0.0
    while True:
        if time.time() - last_update >= SELF_UPDATE_EVERY_S:
            last_update = time.time()
            u = self_update()
            if u == "updated":
                heartbeat(state="starting", every=every, self_update=u)
                os.execv(sys.executable, [sys.executable, *sys.argv])   # run the code just merged
            if u != "current":
                print(f"self_update: {u}", flush=True)
        try:
            r = tick()
            heartbeat(state="ok", every=every, last=r)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            heartbeat(state="error", every=every, error=f"{type(e).__name__}: {str(e)[:200]}")
        time.sleep(every)


def live(max_age=90):
    try:
        d = json.loads((STATE / "serve.json").read_text())
        age = (now() - parse(d["at"])).total_seconds()
    except Exception as e:  # noqa: BLE001
        return {"live": False, "why": f"no heartbeat ({type(e).__name__})"}
    return {"live": age <= max_age and d.get("state") in ("ok", "starting"), "age_s": round(age), "state": d.get("state"), "error": d.get("error"), "last": d.get("last")}


def staged_at(slug):
    try:
        for l in STAGED_STAMPS.read_text().splitlines():
            r = json.loads(l)
            if r.get("slug") == slug:
                return r.get("at")
    except (OSError, ValueError):
        pass
    return None


def timeline(slug):
    """targeted_at = the job record exists (hunt row detected and targeted); package_valid_at = READY from a passing gates.json; staged_on_laptop_at = render_queue push."""
    j = load_job(slug); t = j.get("t", {})
    tg, pv, st = t.get("targeted") or t.get("detected"), t.get("ready"), staged_at(slug)
    ds = t.get("description_at")
    mins = lambda a, b: round((parse(b) - parse(a)).total_seconds() / 60, 1) if a and b else None
    return {"slug": slug, "state": j.get("state"), "targeted_at": tg, "description_at": ds, "package_valid_at": pv, "staged_on_laptop_at": st,
            "targeted_to_description_min": mins(tg, ds), "description_to_valid_min": mins(ds, pv), "targeted_to_valid_min": mins(tg, pv), "valid_to_staged_min": mins(pv, st), "targeted_to_staged_min": mins(tg, st),
            "under_10_min": (mins(tg, st) is not None and mins(tg, st) <= 10),
            # #16636: detection -> submitted against the 60-minute bar, read from the stamps, never typed in; None until sent
            "stage_min": durations(j), "prereview_rebuilds": j.get("prereview_rebuilds", 0),
            "detected_to_sent_min": mins(t.get("detected"), t.get("proposal_sent") or t.get("vsl_sent")), "bar_min": SEND_BAR_MIN,
            "within_bar": (None if not mins(t.get("detected"), t.get("proposal_sent") or t.get("vsl_sent")) else
                           mins(t.get("detected"), t.get("proposal_sent") or t.get("vsl_sent")) <= SEND_BAR_MIN)}


def selftest():
    import tempfile
    global STATE, PKG_ROOT, METER_DB
    METER_DB = Path(tempfile.mkdtemp()) / "m.db"
    STATE = Path(tempfile.mkdtemp())
    PKG_ROOT = Path(tempfile.mkdtemp())
    c = dict(cfg(), hunts_dir=tempfile.mkdtemp(), job_desc_dir=tempfile.mkdtemp(), screening_required=False)
    c["autosend"] = dict(c["autosend"], gates_block_ready=True)   # the blocking-path tests below; the advisory path has its own test at the end   # never the live builder-owned dirs
    _st, STATE = STATE, Path(tempfile.mkdtemp())   # the 60-minute bar checks get their own job dir so the counts below stay theirs
    save_job({"slug": "bar-1", "job": "~bar1", "title": "T", "state": "sent", "prereview_rebuilds": 1, "t": {"detected": "2026-11-22T12:00:00Z", "app": "2026-11-22T12:20:00Z", "proposal_sent": "2026-11-22T12:50:00Z"}})
    tl = timeline("bar-1")
    save_job({"slug": "bar-2", "job": "~bar2", "title": "T", "state": "sent", "t": {"detected": "2026-11-22T12:00:00Z", "vsl_sent": "2026-11-22T13:10:00Z"}})
    save_job({"slug": "bar-3", "job": "~bar3", "title": "T", "state": "building", "t": {"detected": "2026-11-22T12:00:00Z"}})
    bar_ok = [tl["detected_to_sent_min"] == 50.0 and tl["within_bar"] is True and tl["prereview_rebuilds"] == 1 and tl["stage_min"] == {"app": 20.0},
              timeline("bar-2")["within_bar"] is False, timeline("bar-3")["within_bar"] is None]
    STATE = _st
    ok = bar_ok + [fmt_tz("2026-11-22T11:51:00Z", c).endswith("ET") and fmt_tz("2026-11-22T11:51:00Z", c).startswith("2026-11-22 06:51"),
          slugify("Senior Data Engineer (Azure & Databricks)", "~022123695412240114119") == "up-senior-data-engineer-azure-databri-4119"]
    r1 = {"huntType": "upwork", "signal": "Python backend engineer", "signalAt": "2026-11-22T11:00:00.000Z",
          "details": {"job": "~0221000000000000009999", "desc": "We need help with our staff dashboard and the customer portal. " * 30, "skills": ["Python"], "comp": "hourly $30-$50", "link": "https://x"}}
    r2 = {"huntType": "upwork", "signal": "B2B Sales Closer", "details": {"job": "~0221000000000000008888", "desc": "y" * 300, "skills": []}}
    r3 = {"huntType": "upwork", "signal": "x", "details": {"job": "~0221000000000000007777", "desc": "short", "skills": []}}
    rcut = {"huntType": "upwork", "signal": "Cut post", "details": {"job": "~0221000000000000002121", "desc": "We operate a company and built Relay. The ass", "skills": ["Python"]}}   # 9263's truncated post: never built from (#17487), held as needs_description until the desk reads the whole post (#18251)
    new = scan(feed_rows([r1, r2, r3, rcut]), c)
    sk = json.loads((STATE / "skipped.json").read_text())
    ok += [[j["job"] for j in new] == ["~0221000000000000009999", "~0221000000000000007777", "~0221000000000000002121"], len(sk) == 1, new[2]["state"] == "needs_description", scan(feed_rows([r1, r2, r3, rcut]), c) == []]   # a row becomes a job once
    slug = new[0]["slug"]
    # canonical delivery on temp folders: app, diagram, copied_from.md, scripts, tabs.txt, short tab titles; a missing app is reported, not raised
    pub, hun, pk = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    (pub / "up-t-1-mvp" / "mvp").mkdir(parents=True)
    (pub / "up-t-1-diagram" / "mvp").mkdir(parents=True)
    (pub / "up-t-1-diagram" / "mvp" / "index.html").write_text("<html><head><title>Ticket Triage System: AWS</title></head></html>")
    (pub / "up-t-1-mvp" / "mvp" / "index.html").write_text("<html><head><title>Shadcn Admin</title></head></html>")
    (pk / "diagram").mkdir()
    (pk / "diagram" / "architecture.html").write_text("<html><head><title>Ticket Triage System: AWS</title></head><body><h1>Ticket Triage</h1></body></html>")
    (pk / "intro-script.md").write_text("## [Tyler] Intro\n")
    r = deliver_canonical("up-t-1", pk, c, public=pub, hunts=hun)
    d = hun / "up-t-1"
    ok += [r["errors"] == [], (d / "mvp" / "index.html").is_file(), (d / "demo" / "architecture" / "architecture.html").is_file(), (d / "intro-script.md").is_file(),
           (d / "tabs.txt").read_text().count("https://") == 2, "<title>Architecture</title>" in (d / "demo" / "architecture" / "architecture.html").read_text(),
           "<title>Ticket Triage App</title>" in (d / "mvp" / "index.html").read_text(),
           # the tabs open the PUBLISHED copies: short titles there too, and tab 2 is the page (-diagram/mvp/), never the folder listing (-diagram/)
           "<title>Ticket Triage App</title>" in (pub / "up-t-1-mvp" / "mvp" / "index.html").read_text(),
           "<title>Architecture</title>" in (pub / "up-t-1-diagram" / "mvp" / "index.html").read_text(),
           (d / "tabs.txt").read_text().splitlines()[1].endswith("up-t-1-diagram/mvp/")]
    ok += [deliver_canonical("up-none", pk, c, public=pub, hunts=hun)["errors"] != []]
    # newest first, and a dead build is put back to queued
    for sl, posted, st in (("old-1", "2026-11-21T10:00:00Z", "queued"), ("new-1", "2026-11-22T10:00:00Z", "queued"), ("none-1", None, "queued"), ("dead-1", "2026-11-22T09:00:00Z", "building")):
        save_job({"slug": sl, "state": st, "t": {"posted": posted, "detected": "2026-11-22T12:00:00Z"} if posted else {"detected": "2026-11-22T12:00:00Z"}})
    ok += [reap_stale(alive=lambda s: s != "dead-1") == ["dead-1"], load_job("dead-1")["state"] == "queued", reap_stale(alive=lambda s: False) == []]
    qs = sorted([j for j in all_jobs() if j["state"] == "queued" and j["slug"].endswith("-1")], key=lambda j: j["t"].get("posted") or "", reverse=True)
    ok += [[j["slug"] for j in qs] == ["new-1", "dead-1", "old-1", "none-1"]]
    # a live build past build_timeout_s is killed and blocked; one inside it is left alone
    save_job({"slug": "hung-1", "state": "building", "t": {"build_started": "2026-11-22T10:00:00Z"}})
    save_job({"slug": "fresh-1", "state": "building", "t": {"build_started": "2026-11-22T10:08:00Z"}})
    killed = []
    t10 = parse("2026-11-22T10:11:00Z")
    ok += [reap_stale(alive=lambda s: True, c=c, kill=killed.append, at=t10) == ["hung-1"], killed == ["hung-1"], load_job("hung-1")["state"] == "blocked",
           "10 min" in load_job("hung-1")["blocked_by"], load_job("fresh-1")["state"] == "building"]
    for sl in ("hung-1", "fresh-1"):
        (jobs_dir() / f"{sl}.json").unlink()
    for sl in ("old-1", "new-1", "none-1", "dead-1"):
        (jobs_dir() / f"{sl}.json").unlink()

    def author(j, w, c):
        (w / "config.json").write_text(json.dumps({"slug": f"{j['slug']}-mvp", "kpis": [], "workflow": {}, "queue": {}, "ask": {}, "log": [], "pages": {}}))
        (w / "architecture.yaml").write_text("title: x\n")
        (w / "script-source.yaml").write_text("slug: x\n")
        (w / "copied_from.json").write_text("{}")
    good = {"author": author, "app": lambda j, w: True, "diagram": lambda j, w: None,
            "gates": lambda j, w: {"gates": [{"id": 1, "name": "Real app", "status": "pass", "why": []}], "ready": True, "blocking": []},
             "deliver": lambda slug, pkg, c: {"dest": "test", "errors": []},
            "script_check": lambda j, w, c: {"pass": True, "loops": 0, "failing_rows": []}, "rehearsal": lambda j, w, c: {"pass": True, "checks": {}, "failing_row": None}}
    j = run_job(slug, good, c)
    ok += [j["state"] == "ready", all(k in j["t"] for k in ("authored", "app", "diagram", "scripts_gates", "ready")), "blocked_by" not in j]
    s2 = dict(good, gates=lambda j, w: {"gates": [{"id": 1, "name": "Real app", "status": "fail", "why": ["iframe"]}], "ready": False,
                                        "blocking": [{"id": 1, "name": "Real app", "why": ["iframe"]}]})
    r4 = dict(r1, signal="Another engineer", details=dict(r1["details"], job="~0221000000000000006666"))
    slug2 = scan(feed_rows([r4]), c)[0]["slug"]
    j2 = run_job(slug2, s2, c)
    ok += [j2["state"] == "blocked" and "gate 1 Real app: iframe" in j2["blocked_by"]]   # a failing gate stops READY and says why
    j2b = run_job(scan(feed_rows([dict(r1, signal="Short script", details=dict(r1["details"], job="~0221000000000000004444"))]), c)[0]["slug"],
                  dict(good, script_check=lambda j, w, c: {"pass": False, "failing_rows": [{"file": "entire-script.md", "row": None, "why": "49 words, floor 240"}]}), c)
    jb = load_job(j2b["slug"])
    ok += [j2b["state"] == "blocked" and "ready" not in j2b["t"] and "49 words" in j2b["blocked_by"] and jb["attempts"][0]["stage"] == "script_check"]   # a failing script_check BLOCKS READY and is an attempt
    ok += [load_job(j["slug"])["script_check"]["pass"] is True, "attempts" not in load_job(j["slug"]), load_job(j2["slug"])["attempts"][0]["error"].startswith("gate 1")]
    ok += [first_error_line("Traceback (most recent call last):\n  File \"x\", line 1\nValueError: boom") == "ValueError: boom"]
    j2c = run_job(scan(feed_rows([dict(r1, signal="No rehearsal", details=dict(r1["details"], job="~0221000000000000003333"))]), c)[0]["slug"],
                  dict(good, rehearsal=lambda j, w, c: {"pass": False, "failing_row": {"row": 3, "say": "no glide"}}), dict(c, rehearsal={"required": True}))   # the gate's own behaviour, whatever the live config says
    ok += [j2c["state"] == "blocked" and "rehearsal: row 3" in j2c["blocked_by"] and "ready" not in j2c["t"]]
    slug3 = scan(feed_rows([dict(r1, signal="Third engineer", details=dict(r1["details"], job="~0221000000000000005555"))]), c)[0]["slug"]
    j3 = run_job(slug3, dict(good, author=lambda j, w, c: None), c)
    ok += [j3["state"] == "blocked" and "was not written" in j3["blocked_by"]]            # an author worker that writes nothing is named, not filled
    ok += [choose_mvp_type("Senior Data Engineer: Spark, Databricks ETL pipelines and SQL warehouse") == "terminal",
           choose_mvp_type("AI chief of staff: inbox, calendar, approvals and a morning briefing dashboard") == "copy",
           choose_mvp_type("We need a React front-end with a booking portal and a Python API") == "copy",   # more app words than terminal words
           choose_mvp_type("a great engineer") == "copy"]
    # claim + due wiring (asks 3122, 3124): a voice claim stops the timer and opens full mode; an unclaimed job past its delay is due
    cj = load_job(j["slug"])
    cj["fit"] = "mid"; save_job(cj)
    t0 = parse(cj["t"]["ready"])
    at = lambda m: iso(t0 + dt.timedelta(minutes=m))
    ok += [j["slug"] not in due_intros(c, at(29)), j["slug"] in due_intros(c, at(30))]
    r = claim_job(j["slug"], voice=True, at=at(5), c=c)
    ok += [r["status"]["state"] == "claimed", read_full_mode() is not None, j["slug"] not in due_intros(c, at(34)), j["slug"] in due_intros(c, at(35))]
    try:
        claim_job("up-none", c=c); ok += [False]
    except (ValueError, OSError):
        ok += [True]
    pr = set_pick(j["job"], "full", "voice", at(40))
    ok += [pr["records"] == [j["slug"]], load_job(j["slug"])["take_type"] == "full", read_picks()[j["job"]]["by"] == "voice"]
    set_pick(j["job"], "intro", "button", at(41))
    ok += [load_job(j["slug"])["take_type"] == "intro"]
    try:
        set_pick(j["job"], "both"); ok += [False]
    except ValueError:
        ok += [True]
    # knowledge#18574: per-source intake alarm names the dead source; a held mp4 asks for its render once
    sent_msgs = []
    mk = lambda src, t: {"huntType": "upwork", "foundAt": t, "details": {"job": "~1", "src": src}}
    fa = feed_alarm(dict(c, feed_alarm_min=60), [mk("desk most-recent", "2026-11-24T05:38:56.000Z"), mk("dev@ mail", "2026-11-24T16:34:41.000Z")], at="2026-11-24T17:00:00Z", send=sent_msgs.append)
    ok += [bool(fa) and any("desk most-recent" in d for d in fa) and not any("dev@ mail" in d for d in fa), len(sent_msgs) == 1]
    (STATE / "feed-alarm.json").unlink(missing_ok=True)
    ok += [request_intro_renders({"x-intro-1": "mp4_missing", "y": "closed"}) == ["x-intro-1"], request_intro_renders({"x-intro-1": "mp4_missing"}) == []]
    (STATE / "intro-requests" / "x-intro-1.json").unlink(missing_ok=True)
    prt = render_prompt({"text": "T", "slug": "up-t-1", "mvp_type": "terminal"}, Path("/w"))
    ok += ["term-cmd-N" in prt and "terminal.json" in prt and "{SLUG}" not in prt]
    td = Path(tempfile.mkdtemp())
    ok += ["terminal.json was not written" in check_authored(td, "x", "terminal")]
    (td / "terminal.json").write_text(json.dumps({"commands": [{"label": "a", "cmd": "b", "out": ["c"]}] * 5}))
    (td / "architecture.yaml").write_text("a: 1\n")
    (td / "script-source.yaml").write_text("a: 1\n")
    ok += [check_authored(td, "x", "terminal") == []]
    (td / "terminal.json").write_text(json.dumps({"commands": [{"label": "a", "cmd": "b"}] * 5}))
    ok += [any("each with label, cmd and out" in r for r in check_authored(td, "x", "terminal"))]
    pr = render_prompt({"text": "T", "slug": "up-x-1"}, Path("/w"))
    ok += ["{tab: 1, click: <data-testid>}" in pr or "{tab: 1, click:" in pr, "{SLUG}" not in pr and "{JOB_TEXT}" not in pr and "WORKDIR" not in pr and "up-x-1-mvp" in pr]
    doc = write_feed(c)
    ok += [doc["tz"] == "America/New_York", doc["jobs"][0]["ticks"]["Posted"]["done"], [r for r in doc["jobs"] if r["slug"] == slug][0]["ticks"]["Ready"]["done"],
           all(r["updated"].endswith("ET") for r in doc["jobs"]), (STATE / "stages-feed.json").is_file(),
           all("delay" in r and set(r["delay"]["minutes"]) == {"recording", "revision", "waiting"} for r in doc["jobs"]),
           all(s["tag"] in ("waiting", "revision", "recording") for r in doc["jobs"] for s in r["delay"]["segments"])]
    # knowledge#18203: screening is decided at the HUNT step. No screening.json -> not startable and never READY; with every answer -> READY; the row carries it
    cs = dict(c, screening_required=True)
    sj = {"slug": "scr-1", "title": "T", "state": "queued", "t": {}}
    ok += [hunt_screening(sj, cs) != [], hunt_screening(sj, c) == []]
    (Path(cs["hunts_dir"]) / "scr-1").mkdir(parents=True)
    screening.write({"job": "1", "questions": ["Do you have a degree?", "What is your favourite colour?"]}, Path(cs["hunts_dir"]) / "scr-1")
    ok += ["unanswered" in hunt_screening(sj, cs)[0]]   # an unanswerable question holds the job for Eagle; it is never skipped
    d = json.loads((Path(cs["hunts_dir"]) / "scr-1" / "screening.json").read_text())
    d["questions"][1]["answer"] = "Blue."
    (Path(cs["hunts_dir"]) / "scr-1" / "screening.json").write_text(json.dumps(d))
    ok += [hunt_screening(sj, cs) == [], len(screening_rows(sj)) == 2]
    print("self-test", "PASS" if all(ok) else f"FAIL {[i for i, v in enumerate(ok) if not v]}")
    return 0 if all(ok) else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?")
    ap.add_argument("arg", nargs="*")
    ap.add_argument("--feed")
    ap.add_argument("--no-spawn", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ts")
    ap.add_argument("--by")
    a = ap.parse_args(argv)
    if a.cmd == "--self-test" or argv[:1] == ["--self-test"]:
        return selftest()
    if a.cmd == "tick":
        print(json.dumps(tick(json.loads(Path(a.feed).read_text()) if a.feed else None, spawn=not a.no_spawn)))
    elif a.cmd == "run":
        j = run_job(a.arg[0])
        write_feed()
        arch4.drop_worktree(str(KNOW), str(WORKTREES / a.arg[0]))   # the worker's worktree lives for one build
        print(j["state"], j.get("blocked_by", ""))
    elif a.cmd == "status":
        doc = write_feed()
        print(json.dumps(doc, indent=1) if a.json else plain_status(doc))
    elif a.cmd == "mark":
        slug, stage = a.arg
        try:
            dispatch(stage, slug, stage, a.ts) if stage in ("recorded", "text_proposal", "vsl_sent") else sys.exit("stage must be recorded, text_proposal or vsl_sent")
        except ValueError as e:
            sys.exit(str(e))
        write_feed()
    elif a.cmd == "sync-sends":
        print(json.dumps(sync_sends(a.arg[0] if a.arg else None)))
        write_feed()
    elif a.cmd == "event":
        slug, kind = a.arg
        if kind not in ("recording_started", "recording_stopped"):
            sys.exit("event must be recording_started or recording_stopped")
        j = load_job(slug)
        j.setdefault("events", []).append({"at": a.ts or iso(), "kind": kind})
        save_job(j)
        write_feed()
    elif a.cmd == "regen":
        r = regen(a.arg[0])
        print(json.dumps(r))
        return 0 if r["action"] != "refused" else 1
    elif a.cmd == "claim":   # claim <slug> [voice]
        print(json.dumps(claim_job(a.arg[0], voice=a.arg[1:] == ["voice"], at=a.ts)))
        write_feed()
    elif a.cmd == "pick":   # pick <job key | trailing digits> full|intro [--by voice|button]
        try:
            tok, take = a.arg[0], a.arg[1]
            sys.path.insert(0, str(HERE.parents[1] / "_tools/upwork"))
            import triage
            key = triage.resolve(tok, job_keys()) or (tok if re.fullmatch(r"~?0\d{17,}", tok) else None)
            if not key:
                sys.exit(f"pick: {tok!r} matches no single job (give more trailing digits)")
            print(json.dumps(set_pick(key, take, a.by or "button", a.ts)))
        except (ValueError, IndexError) as e:
            sys.exit(f"pick: {e}")
        write_feed()
    elif a.cmd == "take":   # take <slug | job digits> full|intro [--by voice]   (knowledge#18939: the hunt page's one tap)
        try:
            print(json.dumps(take_over(a.arg[0], a.arg[1] if len(a.arg) > 1 else "full", voice=a.by == "voice", at=a.ts)))
        except (ValueError, IndexError) as e:
            sys.exit(f"take: {e}")
    elif a.cmd == "state":
        print(json.dumps(hunt_state(a.arg[0])))
    elif a.cmd == "pull-picks":
        print(json.dumps(pull_picks()))
    elif a.cmd == "due":
        print(json.dumps(due_intros(at=a.ts)))
    elif a.cmd == "serve":
        serve(int(a.arg[0]) if a.arg else 20)
    elif a.cmd == "live":
        r = live(int(a.arg[0]) if a.arg else 90)
        print(json.dumps(r)); return 0 if r["live"] else 1
    elif a.cmd == "stuck":      # jobs waiting on a post text, with the reason and age: the alarm feed for "nothing retries them" (knowledge#21574)
        out = []
        for j in all_jobs():
            if j.get("state") == "needs_description" and "private listing" not in str((j.get("desc_failed") or {}).get("why", "")):     # a private listing can never be read: not an alarm
                ddir = Path(cfg().get("job_desc_dir", "/nonexistent")); jid = (j.get("job") or "").lstrip("~")
                f = next((x for x in (ddir / f"~{jid}.json", ddir / f"{jid}.json") if x.is_file()), None)
                out.append({"slug": j["slug"], "job": j.get("job"), "created": j.get("created"), "posted_at": j.get("posted_at"),
                            "why": "no description file" if not f else (j.get("desc_failed") or {}).get("why") or "description too short"})
        print(json.dumps({"stuck": out, "bad_job_files": BAD_JOBS}, indent=1))
    elif a.cmd == "describe":
        print(json.dumps({"queued": describe(a.arg[0], a.arg[1])}))
    elif a.cmd == "timeline":
        for slug in a.arg:
            print(json.dumps(timeline(slug)))
    elif a.cmd == "session":
        print(json.dumps(session_manifest(a.arg), indent=1))
    elif a.cmd == "feed":
        print(json.dumps(write_feed(), indent=1))
    elif a.cmd == "eagle-backfill":   # knowledge#17557: push every ready/blocked job's fact once (idempotent at the server)
        os.environ["EAGLE_EMIT"] = "1"
        out = {}
        for j in all_jobs():
            if j["state"] in ("ready", "blocked"):
                r = push_eagle(j)
                out[r] = out.get(r, 0) + 1
        print(json.dumps(out))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
