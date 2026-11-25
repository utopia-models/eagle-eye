#!/usr/bin/env python3
"""vsl_pool.py: fully isolated parallel VSL jobs (knowledge#18932). Each job owns, and shares nothing else with any other job:
  dir        $VSL_JOBS_ROOT/<slug>/            (default /var/tmp/vsl-jobs, group vsl, setgid, umask 002)
  display    its own Xvfb 1920x1080x24 on :N   (N derived from the slug, probed free, recorded in env.json)
  profile    <dir>/chrome-profile cloned from the template (VSL_CHROME_TEMPLATE; Utopia favicons, no account login)
  ports      a 20-port block <dir>-private by slug (demo host, CDP, ...), probed free by bind(), recorded in env.json
  seat       <dir>/.seat (post_take FIFO queue pointed at the job's own dir: nothing to queue behind)
  processes  Xvfb + the post_take chain (whisper/ffmpeg children) run in the job's own systemd unit / process group

  vsl_pool.py prepare SLUG     create dir, profile, display and ports; print env.json
  vsl_pool.py run SLUG --take FILE [--feedback]   prepare + Xvfb + post_take.run under that env; always tears Xvfb down
  vsl_pool.py place            where the next job goes: ra (free RAM allows) or overflow (VSL_OVERFLOW_HOST); print one JSON line
  vsl_pool.py start SLUG --take FILE   place, then `systemctl start vsl-job@SLUG` (vsl.slice: MemoryMax, CPUQuota) locally or over ssh on overflow
  vsl_pool.py --self-test

Concurrency is OBSERVED, never waited on: the ledger gets `concurrency` (other live jobs at start); a job never blocks on another job or agent."""
import hashlib, json, os, shutil, signal, socket, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("VSL_JOBS_ROOT") or "/var/tmp/vsl-jobs")
TEMPLATE = Path(os.environ.get("VSL_CHROME_TEMPLATE") or "/var/lib/vsl/chrome-template")
PER_JOB_MB = int(os.environ.get("VSL_JOB_MB", "3500"))      # = MemoryMax in vsl-job@.service (measured: Chrome ~1.2G + whisper large-v3-turbo int8 ~2G + ffmpeg)
RESERVE_MB = int(os.environ.get("VSL_RESERVE_MB", "1500"))
MAX_LOCAL = int(os.environ.get("VSL_MAX_LOCAL", "3"))
OVERFLOW = os.environ.get("VSL_OVERFLOW_HOST", "nova@novaserver")
DISPLAY_BASE, PORT_BASE, PORT_BLOCK = 100, 30000, 20


def avail_mb():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"):
            return int(l.split()[1]) // 1024
    return 0


def live_jobs():
    out = []
    if ROOT.is_dir():
        for p in ROOT.glob("*/job.pid"):
            try:
                os.kill(int(p.read_text()), 0); out.append(p.parent.name)
            except (OSError, ValueError):
                pass
    return out


def place():
    """Free RAM decides (VSL_JOB_MB per job + a reserve), capped at MAX_LOCAL; otherwise the overflow host."""
    n, free = len(live_jobs()), avail_mb()
    fits = free - RESERVE_MB >= PER_JOB_MB
    return {"host": "local" if (n < MAX_LOCAL and fits) else "overflow", "live": n, "avail_mb": free, "per_job_mb": PER_JOB_MB}


def _h(slug):
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16)


def _port_free(p):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p)); return True
    except OSError:
        return False
    finally:
        s.close()


def _display_free(n):
    return not Path(f"/tmp/.X11-unix/X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists()


def allocate(slug):
    """Slug-derived, probed free: two different slugs can collide only on the hash, and then probing moves the later one on. No shared registry."""
    h = _h(slug)
    disp = next(DISPLAY_BASE + (h + i) % 800 for i in range(800) if _display_free(DISPLAY_BASE + (h + i) % 800))
    for i in range(1000):
        base = PORT_BASE + ((h >> 16) + i) % 1000 * PORT_BLOCK
        if all(_port_free(base + k) for k in range(PORT_BLOCK)):
            return disp, base
    raise RuntimeError("no free port block")


def prepare(slug):
    os.umask(0o002)
    d = ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o2775)
    except OSError:
        pass
    prof = d / "chrome-profile"
    if prof.exists():
        shutil.rmtree(prof)
    if TEMPLATE.is_dir():
        shutil.copytree(TEMPLATE, prof, symlinks=True)
    else:
        prof.mkdir()          # no template on this box: an empty profile, still private to the job
    for lock in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (prof / lock).unlink(missing_ok=True)
    disp, base = allocate(slug)
    env = {"slug": slug, "dir": str(d), "display": f":{disp}", "chrome_profile": str(prof), "port_base": base,
           "demo_port": base, "cdp_port": base + 1, "seat_dir": str(d / ".seat"), "screen": "1920x1080x24"}
    (d / "env.json").write_text(json.dumps(env, indent=1))
    return env


def job_environ(env):
    return dict(os.environ, VSL_ROOT=str(ROOT), VSL_SEAT_DIR=env["seat_dir"], DISPLAY=env["display"],
                CHROME_PROFILE=env["chrome_profile"], DEMO_PORT=str(env["demo_port"]), CDP_PORT=str(env["cdp_port"]),
                TMPDIR=str(Path(env["dir"]) / "tmp"))


def run(slug, take, feedback=False):
    env = prepare(slug)
    d = Path(env["dir"])
    (d / "tmp").mkdir(exist_ok=True)
    (d / "job.pid").write_text(str(os.getpid()))
    others = [j for j in live_jobs() if j != slug]
    xv = subprocess.Popen(["Xvfb", env["display"], "-screen", "0", env["screen"], "-nolisten", "tcp"], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True) if shutil.which("Xvfb") else None
    try:
        cmd = [sys.executable, str(HERE / "post_take.py"), "run", slug, "--take", str(take)] + (["--feedback"] if feedback else [])
        rc = subprocess.run(cmd, env=job_environ(env)).returncode
        lp = d / "ledger.json"
        if lp.exists():
            L = json.loads(lp.read_text())
            L["concurrency"] = {"others_live_at_start": others, "count": len(others) + 1, "display": env["display"], "port_base": env["port_base"]}
            lp.write_text(json.dumps(L, indent=1))
        return rc
    finally:
        if xv:
            try:
                os.killpg(xv.pid, signal.SIGTERM)
            except OSError:
                pass
        (d / "job.pid").unlink(missing_ok=True)


def start(slug, take, feedback=False):
    p = place()
    unit = f"vsl-job@{slug}.service"
    args = f"{take}" + (" --feedback" if feedback else "")
    if p["host"] == "local":
        (ROOT / slug).mkdir(parents=True, exist_ok=True)
        (ROOT / slug / "take.arg").write_text(args)
        r = subprocess.run(["systemctl", "--user", "start", "--no-block", unit])
    else:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", OVERFLOW, f"mkdir -p {ROOT}/{slug} && printf %s {args!r} > {ROOT}/{slug}/take.arg && systemctl --user start --no-block {unit}"])
    print(json.dumps(p | {"unit": unit, "rc": r.returncode}))
    return r.returncode


def self_test():
    global ROOT
    import threading
    ROOT = Path(tempfile.mkdtemp(prefix="vsl-pool-test-"))
    slugs = ["alpha", "bravo", "charlie"]
    envs = {s: prepare(s) for s in slugs}
    for k in ("dir", "display", "chrome_profile", "port_base", "seat_dir"):
        assert len({e[k] for e in envs.values()}) == 3, k
    assert all(Path(e["chrome_profile"]).is_dir() for e in envs.values())
    # three jobs at once through the real post_take chain with trivial stage commands: each finishes, none waits on another
    take = ROOT / "t.mkv"; take.write_text("x")
    for s in slugs:
        (ROOT / s / "stages.json").write_text(json.dumps({"fetch": f"cp {take} {ROOT}/{s}/take.mkv", "align": "sleep 1", "compose": "sleep 1", "encode": "sleep 1", "deliver": f"touch {ROOT}/{s}/final.mp4"}))
    rcs = {}
    ths = [threading.Thread(target=lambda s=s: rcs.__setitem__(s, subprocess.run([sys.executable, __file__, "run", s, "--take", str(take)], env=dict(os.environ, VSL_JOBS_ROOT=str(ROOT))).returncode)) for s in slugs]
    t0 = time.time(); [t.start() for t in ths]; [t.join() for t in ths]; wall = time.time() - t0
    assert rcs == {s: 0 for s in slugs}, rcs
    for s in slugs:
        c = json.loads((ROOT / s / "clock.json").read_text()); L = json.loads((ROOT / s / "ledger.json").read_text())
        assert c["within_budget"] and c["wait_s"] == 0 and all(x["waited_on"] is None for x in L["stages"]), (s, c)
        assert (ROOT / s / "final.mp4").exists() and "concurrency" in L
    assert wall < 4 * 1 + 3 + 6, wall      # serial would be >= 12 s of stage sleeps; parallel ~4 s
    assert place()["host"] in ("local", "overflow")
    shutil.rmtree(ROOT)
    print(f"vsl_pool self-test ok (3 parallel jobs, wall {wall:.1f}s)")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--self-test"]:
        sys.exit(self_test())
    if a[:1] == ["prepare"] and len(a) == 2:
        print(json.dumps(prepare(a[1]), indent=1)); sys.exit(0)
    if a[:1] == ["run"] and "--take" in a:
        sys.exit(run(a[1], a[a.index("--take") + 1], "--feedback" in a))
    if a[:1] == ["start"] and "--take" in a:
        sys.exit(start(a[1], a[a.index("--take") + 1], "--feedback" in a))
    if a == ["place"]:
        print(json.dumps(place())); sys.exit(0)
    print(__doc__); sys.exit(2)
