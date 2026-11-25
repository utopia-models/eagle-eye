#!/usr/bin/env python3
"""oneshot_copy.py: the MVP is a COPY of a real application (Tyler 2026-11-22 7:33 AM ET: "no custom-designed UI from scratch, ever").

  oneshot_copy.py probe APP_ID                    clone, install and build a catalog app as a static page; prints the result to put in the catalog
  oneshot_copy.py build JOB_SLUG WORK_DIR [--publish-slug S] [--text-file F]    pick -> fork -> adapt -> build -> publish -> provenance
  oneshot_copy.py check WORK_DIR                  verify copied_from.json against the catalog (what gate 11 runs)
  oneshot_copy.py --self-test

The steps: PICK (a worker names 3 catalog candidates with a line each, the pick, and a real reference architecture for the diagram), FORK
(a cached clone of the verified app, copied, installed), ADAPT (a worker rewrites ONLY the catalog's content_files so every screen speaks the
client's domain, and decides once, in one line, whether to re-skin with the Utopia palette or keep the copied one; the code refuses any other
file change), BUILD (router basepath patched, vite build under /hunts/<slug>-mvp/mvp/, noindex injected, published), PROVENANCE
(copied_from.json: url, license, commit, candidates, pick, palette, diagram source). Gate 11 re-checks the provenance live.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[3]
sys.path.insert(0, str(HERE))
CATALOG = KNOW / "net/work/vsl/reference-apps.yaml"
PICK_PROMPT = KNOW / "net/work/vsl/oneshot-copy-pick-prompt.md"
ADAPT_PROMPT = KNOW / "net/work/vsl/oneshot-copy-adapt-prompt.md"
CACHE = Path(os.environ.get("ONESHOT_REFS_CACHE") or Path.home() / ".cache/oneshot-refs")
RA_BASE = "https://ra.tail4016d7.ts.net:8450/hunts"
SKIP_DIRS = {"node_modules", "dist", ".git"}
# Fleet infra pass 2026-11-23 (F6): builds run on novaserver, never on Ra. Ra (14.7 GB, voice + desk) OOM-killed a vite
# build at 2031 MB available (09:37Z) and sat in a swap storm (load 80, 10 GB swap); novaserver has ~12 GB available.
# The app's source goes to novaserver, `pnpm install` + `vite build` run there (nice 10), and dist comes back with the
# dist/.prebuilt marker this file and oneshot_auto.py already honour. ONESHOT_BUILD_HOST="" builds here (the old path);
# a remote failure falls back to a local build with the reason logged, so a job is never lost to the network.
BUILD_HOST = os.environ.get("ONESHOT_BUILD_HOST", "upwork@100.71.25.43")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]


def build_remote(dest, base):
    """pnpm install + vite build of `dest` on BUILD_HOST; dist/ comes back with dist/.prebuilt. Returns (code, out)."""
    if not BUILD_HOST:
        return 1, "no build host"
    rdir = f"/var/tmp/oneshot-build/{Path(dest).parent.name}-{Path(dest).name}-{os.getpid()}"
    code, out = sh(["rsync", "-a", "--delete", "--exclude", "node_modules", "--exclude", "dist", "--exclude", ".git",
                    "-e", " ".join(SSH), "--rsync-path", f"mkdir -p {rdir} && rsync", f"{dest}/", f"{BUILD_HOST}:{rdir}/"], timeout=300)
    if code:
        return code, "rsync to build host: " + out
    pn = "npx -y pnpm@10"   # the same pnpm Ra used (no pnpm on Ra's PATH), so the lockfile installs exactly as before
    code, out = sh([*SSH, BUILD_HOST, f"cd {rdir} && nice -n 10 {pn} install --frozen-lockfile --store-dir ~/.cache/oneshot-refs/pnpm-store "
                    f"&& nice -n 10 {pn} exec vite build --base {base}/"], timeout=900)
    if not code:
        shutil.rmtree(Path(dest) / "dist", ignore_errors=True)
        code, o2 = sh(["rsync", "-a", "-e", " ".join(SSH), f"{BUILD_HOST}:{rdir}/dist/", f"{dest}/dist/"], timeout=300)
        out = out if not code else "rsync dist back: " + o2
        if not code:
            (Path(dest) / "dist/.prebuilt").write_text(f"built on {BUILD_HOST}\n")
    sh([*SSH, BUILD_HOST, f"rm -rf {rdir}"], timeout=60)
    return code, out


def catalog():
    return yaml.safe_load(CATALOG.read_text())


def get_app(cat, app_id):
    return next((a for a in cat["apps"] if a["id"] == app_id), None)


def sh(cmd, cwd=None, timeout=900):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)[-400:]


def pnpm():
    """pnpm as installed, else through npx (pinned major): the reference apps ship pnpm lockfiles, so their dependencies install exactly as locked."""
    return ["pnpm"] if shutil.which("pnpm") else ["npx", "-y", "pnpm@10"]


def tree_hashes(root):
    out = {}
    for p in Path(root).rglob("*"):
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(root).parts)):
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------------------------- provenance
def pick_reasons(pick, cat):
    why = []
    ids = [c.get("id") for c in pick.get("candidates", [])]
    known = {a["id"] for a in cat["apps"]}
    if len(ids) != 3 or len(set(ids)) != 3:
        why.append("the pick needs exactly 3 distinct candidates")
    why += [f"candidate {i} is not in the catalog" for i in ids if i not in known]
    if any(not c.get("why") for c in pick.get("candidates", [])):
        why.append("every candidate needs its one-line why")
    app = get_app(cat, pick.get("picked"))
    if pick.get("picked") not in ids:
        why.append("the picked app is not one of the 3 candidates")
    elif app and not (app.get("verified_build") or {}).get("ok"):
        why.append(f"{app['id']} has not passed a build probe (verified_build.ok), so it cannot be picked")
    if not pick.get("why"):
        why.append("the pick has no why")
    ds = pick.get("diagram_source") or {}
    hosts = [d["host"] for d in cat["diagram_sources"]]
    if not (ds.get("name") and ds.get("url") and any(h in ds["url"] for h in hosts)):
        why.append(f"diagram_source needs a name and a url on one of {hosts}")
    return why


def live_license(repo):
    """The license SPDX id the GitHub API reports now, or None when it cannot be read (then the catalog's recorded value stands, marked stale)."""
    code, out = sh(["gh", "api", f"repos/{repo}", "--jq", "[(.license.spdx_id // \"none\"), (.archived|tostring)] | join(\" \")"], timeout=60)
    if code or not out.strip():
        return None
    spdx, archived = (out.strip().split() + ["false"])[:2]
    return spdx, archived == "true"


def reachable(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (oneshot-copy)"})
        return urllib.request.urlopen(req, timeout=30).status == 200
    except Exception:
        return False


def provenance_reasons(doc, cat, live=True, url_check=None):
    """-> reasons the copied_from.json fails (gate 11): known catalog app, permissive license (read live), 3 candidates, palette decision, a real diagram source."""
    why = pick_reasons({k: doc.get(k) for k in ("candidates", "picked", "why", "diagram_source")} | {"candidates": doc.get("candidates", [])}, cat)
    app = get_app(cat, doc.get("picked"))
    if not app:
        return why + ["copied_from names an app that is not in the catalog"]
    if doc.get("url") != app["url"]:
        why.append("copied_from.url is not the catalog app's url")
    lic = app["license"]
    if live:
        got = live_license(app["repo"])
        if got:
            lic, archived = got
            if archived:
                why.append(f"{app['repo']} is archived")
        elif doc.get("license") != app["license"]:
            why.append("license could not be read live and copied_from disagrees with the catalog")
    if lic not in cat["license_allowlist"]:
        why.append(f"license {lic} is not in the allowlist {cat['license_allowlist']}")
    p = doc.get("palette") or {}
    if p.get("decision") not in ("keep", "utopia") or not p.get("why"):
        why.append("palette needs a decision (keep or utopia) and a one-line why")
    if not doc.get("commit"):
        why.append("copied_from has no commit")
    ds = (doc.get("diagram_source") or {}).get("url")
    if ds and not (url_check or reachable)(ds):
        why.append(f"the diagram source {ds} does not open")
    return why


# ---------------------------------------------------------------- the steps
def render(path, repl):
    p = Path(path).read_text()
    for k, v in repl.items():
        p = p.replace(k, v)
    return p


def worker(prompt, cwd, add_dirs, model, tools, timeout=600):
    r = subprocess.run(["claude", "-p", prompt, "--model", model, "--permission-mode", "acceptEdits", "--allowedTools", *tools,
                        "--add-dir", *map(str, add_dirs)], capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
    if r.returncode:
        raise RuntimeError(f"worker failed: {(r.stderr or r.stdout)[-200:]}")


def pick_step(job_text, work, model):
    out = Path(work) / "pick.json"
    prompt = render(PICK_PROMPT, {"{JOB_TEXT}": job_text, "{CATALOG}": str(CATALOG), "{OUT}": str(out), "{DIAGRAM_SOURCES_NOTE}": "diagram_sources in the same file."})
    worker(prompt, work, [work, CATALOG.parent], model, ["Read", "Write"], 300)
    return json.loads(out.read_text())


def fork_step(app, dest):
    """A cached shallow clone, copied (no .git), dependencies installed from a shared store."""
    CACHE.mkdir(parents=True, exist_ok=True)
    clone = CACHE / app["id"]
    if not clone.is_dir():
        code, out = sh(["git", "clone", "--depth", "1", app["url"] + ".git", str(clone)], timeout=300)
        if code:
            raise RuntimeError(f"clone failed: {out}")
    commit = sh(["git", "rev-parse", "--short", "HEAD"], cwd=clone)[1].strip()
    dest = Path(dest)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(clone, dest, ignore=shutil.ignore_patterns(".git", "node_modules", "dist"))
    if BUILD_HOST:   # F6: dependencies are installed where the build runs (novaserver); build_step installs here only on fallback
        return commit
    code, out = sh([*pnpm(), "install", "--frozen-lockfile", "--store-dir", str(CACHE / "pnpm-store")], cwd=dest, timeout=900)
    if code:
        raise RuntimeError(f"install failed: {out}")
    return commit


EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}")
LEFTOVER_SKIP = ("test", "auth", "clerk", "assets", "routeTree", "sign-in", "sign-up", "forgot", "otp")


def leftovers(dest):
    """Template leftovers in the shipped source that would show on a page: email addresses, phone numbers, faker data (never contact details on a
    client-facing demo: Upwork User Agreement 7.2 covers pages and videos too). -> up to 8 'file: what' lines."""
    out = []
    for p in sorted((Path(dest) / "src").rglob("*")):
        rel = str(p.relative_to(dest))
        if not p.is_file() or p.suffix not in (".ts", ".tsx", ".json") or any(s in rel for s in LEFTOVER_SKIP):
            continue
        t = p.read_text(errors="ignore")
        for what, rx in (("an email address", EMAIL), ("a phone number", PHONE)):
            m = rx.search(t)
            if m:
                out.append(f"{rel}: {what} ({m.group(0)})")
        if "faker" in t:
            out.append(f"{rel}: faker-generated data")
    return out[:8]


def adapt_step(job_text, app, dest, work, model):
    before = tree_hashes(dest)
    pal = Path(work) / "palette.json"
    prompt = render(ADAPT_PROMPT, {"{JOB_TEXT}": job_text, "{REPO}": app["repo"], "{LICENSE}": app["license"], "{APP}": str(dest), "{THEME_FILE}": app["theme_file"],
                                   "{CONTENT_FILES}": "\n".join(f"- {f}" for f in app["content_files"]), "{PALETTE_OUT}": str(pal)})
    worker(prompt, dest, [dest, work], model, ["Read", "Write", "Edit"], 900)
    left = leftovers(dest)
    if left:   # one more pass with the exact list; the code, not the worker, decides when the content is clean
        worker(prompt + "\n\nYour first pass left template leftovers in the source. Remove every one (no email addresses or phone numbers anywhere, no faker; replace with this client's domain content, or drop the column or field):\n" + "\n".join(left),
               dest, [dest, work], model, ["Read", "Write", "Edit"], 600)
        left = leftovers(dest)
    if left:
        raise RuntimeError("template leftovers remain after the second pass: " + "; ".join(left))
    after = tree_hashes(dest)
    changed = sorted(f for f in set(before) | set(after) if before.get(f) != after.get(f))
    palette = json.loads(pal.read_text())
    allowed = set(app["content_files"]) | ({app["theme_file"]} if palette.get("decision") == "utopia" else set())
    bad = [f for f in changed if f not in allowed]
    if bad:
        raise RuntimeError(f"the adapt step changed files outside the content list: {bad}")
    if not [f for f in changed if f in app["content_files"]]:
        raise RuntimeError("the adapt step changed no content file (the app would still say the template's words)")
    if palette.get("decision") not in ("keep", "utopia") or not palette.get("why"):
        raise RuntimeError("palette.json needs a decision (keep or utopia) and a one-line why")
    return {"changed": changed, "palette": palette}


def build_step(app, dest, publish_slug):
    base = f"/hunts/{publish_slug}/mvp"
    if app.get("router") == "tanstack":
        main = Path(dest) / "src/main.tsx"
        t = main.read_text()
        if "basepath" not in t:
            t2 = re.sub(r"createRouter\(\{", f"createRouter({{\n  basepath: '{base}',", t, count=1)
            if t2 == t:
                raise RuntimeError("could not set the router basepath in src/main.tsx")
            main.write_text(t2)
    if (Path(dest) / "dist/.prebuilt").is_file() and (Path(dest) / "dist/index.html").is_file():
        code, out = 0, "prebuilt dist (built on another host, marker dist/.prebuilt): vite not run here"
    else:
        code, out = build_remote(dest, base)
        if code and BUILD_HOST:
            print(f"oneshot_copy: build on {BUILD_HOST} failed, building here instead: {str(out)[-200:]}", file=sys.stderr)
            if not (Path(dest) / "node_modules").exists():
                c2, o2 = sh([*pnpm(), "install", "--frozen-lockfile", "--store-dir", str(CACHE / "pnpm-store")], cwd=dest, timeout=900)
                if c2:
                    raise RuntimeError(f"install failed: {o2}")
            code, out = sh([*pnpm(), "exec", "vite", "build", "--base", base + "/"], cwd=dest, timeout=600)
    if code or not (Path(dest) / "dist/index.html").is_file():
        hits = [ln.strip()[:160] for ln in str(out).splitlines() if re.search(r"error TS\d+|Error:|error during build", ln)][:3]
        raise RuntimeError("build failed: " + (" | ".join(hits) if hits else str(out)[-300:]))   # the first real error lines, not a stack tail (6495: a TS1003 was hidden)
    idx = Path(dest) / "dist/index.html"
    h = idx.read_text()
    if "noindex" not in h:
        idx.write_text(h.replace("<head>", '<head><meta name="robots" content="noindex">', 1))
    code, out = sh([sys.executable, str(HERE.parent / "oneshot-mvp/ra_publish.py"), str(Path(dest) / "dist"), publish_slug, "--no-build"], timeout=300)
    if code:
        raise RuntimeError(f"publish failed: {out}")
    return f"{RA_BASE}/{publish_slug}/mvp/"


def copy_app(slug, job_text, work, publish_slug=None, model="sonnet", steps=None):
    """pick -> fork -> adapt -> build -> provenance. `steps` replaces the outward functions in tests. -> the copied_from record."""
    steps = steps or {}
    cat = catalog()
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    pick = (steps.get("pick") or pick_step)(job_text, work, model)
    bad = pick_reasons(pick, cat)
    if bad:
        raise RuntimeError("pick rejected: " + "; ".join(bad))
    app = get_app(cat, pick["picked"])
    dest = work / "app"
    commit = (steps.get("fork") or fork_step)(app, dest)
    adapted = (steps.get("adapt") or adapt_step)(job_text, app, dest, work, model)
    url = (steps.get("build") or build_step)(app, dest, publish_slug or f"{slug}-mvp")
    doc = {"url": app["url"], "repo": app["repo"], "license": app["license"], "commit": commit, "checked": str(app["checked"]),
           "candidates": pick["candidates"], "picked": pick["picked"], "why": pick["why"], "palette": adapted["palette"],
           "diagram_source": pick["diagram_source"], "content_files_changed": adapted["changed"], "built_url": url}
    (work / "copied_from.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def probe(app_id):
    cat = catalog()
    app = get_app(cat, app_id)
    if not app:
        return {"error": f"{app_id} is not in the catalog"}
    import tempfile, time
    d = Path(tempfile.mkdtemp()) / "app"
    res = {"id": app_id}
    try:
        t = time.time()
        res["commit"] = fork_step(app, d)
        res["install_s"] = round(time.time() - t)
        t = time.time()
        code, out = build_remote(d, "") if BUILD_HOST else sh([*pnpm(), "exec", "vite", "build"], cwd=d, timeout=600)
        res["build_s"] = round(time.time() - t)
        res["ok"] = code == 0 and (d / "dist/index.html").is_file()
        if not res["ok"]:
            res["note"] = out[-200:]
    except Exception as e:
        res.update(ok=False, note=str(e)[:200])
    return res


def selftest():
    import tempfile
    cat = catalog()
    ok = [get_app(cat, "shadcn-admin")["verified_build"]["ok"] is True, all(a["license"] in cat["license_allowlist"] for a in cat["apps"]),
          not any(a["license"] in ("AGPL-3.0", "NOASSERTION") for a in cat["apps"])]
    good = {"candidates": [{"id": "shadcn-admin", "why": "tasks and approvals"}, {"id": "refine", "why": "back office"}, {"id": "react-admin", "why": "crud"}],
            "picked": "shadcn-admin", "why": "closest", "diagram_source": {"name": "Azure Architecture Center", "url": "https://learn.microsoft.com/azure/architecture/", "why": "x"}}
    ok += [pick_reasons(good, cat) == []]
    ok += [any("exactly 3" in r for r in pick_reasons(dict(good, candidates=good["candidates"][:2]), cat)),
           any("not in the catalog" in r for r in pick_reasons(dict(good, candidates=[{"id": "nope", "why": "x"}] + good["candidates"][1:]), cat)),
           any("build probe" in r for r in pick_reasons(dict(good, picked="refine"), cat)),
           any("not one of the 3" in r for r in pick_reasons(dict(good, picked="tailadmin-react"), cat)),
           any("diagram_source" in r for r in pick_reasons(dict(good, diagram_source={"name": "n", "url": "https://example.com/x"}), cat))]
    doc = dict(good, url="https://github.com/satnaing/shadcn-admin", license="MIT", commit="e16c87f", palette={"decision": "keep", "why": "its look is stronger"})
    ok += [provenance_reasons(doc, cat, live=False, url_check=lambda u: True) == [],
           any("palette" in r for r in provenance_reasons(dict(doc, palette={"decision": "maybe"}), cat, live=False, url_check=lambda u: True)),
           any("does not open" in r for r in provenance_reasons(doc, cat, live=False, url_check=lambda u: False)),
           any("no commit" in r for r in provenance_reasons(dict(doc, commit=""), cat, live=False, url_check=lambda u: True)),
           any("not the catalog" in r or "not the catalog app" in r for r in provenance_reasons(dict(doc, url="https://github.com/x/y"), cat, live=False, url_check=lambda u: True))]
    # the orchestration with injected steps: a clean run writes copied_from.json; a bad pick, a stray file change and a no-content change are refused
    w = Path(tempfile.mkdtemp())
    steps = {"pick": lambda t, w, m: good, "fork": lambda a, d: "abc1234",
             "adapt": lambda t, a, d, w, m: {"changed": a["content_files"][:2], "palette": {"decision": "keep", "why": "its look is stronger"}},
             "build": lambda a, d, s: f"{RA_BASE}/{s}/mvp/"}
    d1 = copy_app("up-x-1111", "job text", w, steps=steps)
    ok += [d1["built_url"].endswith("/up-x-1111-mvp/mvp/"), (w / "copied_from.json").is_file(), d1["commit"] == "abc1234", d1["palette"]["decision"] == "keep"]
    try:
        copy_app("up-x-1111", "t", tempfile.mkdtemp(), steps=dict(steps, pick=lambda t, w, m: dict(good, picked="refine")))
        ok += [False]
    except RuntimeError as e:
        ok += ["pick rejected" in str(e)]
    # adapt_step's file guard, against a real temp tree with a fake worker
    app = dict(get_app(cat, "shadcn-admin"))
    tree = Path(tempfile.mkdtemp())
    for f in app["content_files"] + ["src/other.ts", app["theme_file"]]:
        (tree / f).parent.mkdir(parents=True, exist_ok=True)
        (tree / f).write_text("x")
    wk = Path(tempfile.mkdtemp())

    def fake(edit, decision="keep"):
        def w(prompt, cwd, add, model, tools, timeout=600):
            for f in edit:
                (tree / f).write_text("changed")
            (wk / "palette.json").write_text(json.dumps({"decision": decision, "why": "because"}))
        return w
    global worker
    real = worker
    try:
        worker = fake([app["content_files"][0]])
        ok += [adapt_step("t", app, tree, wk, "m")["changed"] == [app["content_files"][0]]]
        worker = fake(["src/other.ts"])
        try:
            adapt_step("t", app, tree, wk, "m")
            ok += [False]
        except RuntimeError as e:
            ok += ["outside the content list" in str(e)]
        for f in tree.rglob("*.ts"):
            f.write_text("x")
        worker = fake([app["theme_file"]], "keep")           # a theme change with decision keep is refused
        try:
            adapt_step("t", app, tree, wk, "m")
            ok += [False]
        except RuntimeError as e:
            ok += ["outside the content list" in str(e) or "changed no content" in str(e)]
        (tree / app["theme_file"]).write_text("x")
        worker = fake([app["theme_file"], app["content_files"][1]], "utopia")   # a theme change with decision utopia, plus content, is allowed
        ok += [set(adapt_step("t", app, tree, wk, "m")["changed"]) == {app["theme_file"], app["content_files"][1]}]
    finally:
        worker = real
    print("self-test", "PASS" if all(ok) else f"FAIL {[i for i, v in enumerate(ok) if not v]}")
    return 0 if all(ok) else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    if argv[:1] == ["probe"] and len(argv) == 2:
        print(json.dumps(probe(argv[1]), indent=1))
        return 0
    if argv[:1] == ["check"] and len(argv) == 2:
        doc = json.loads((Path(argv[1]) / "copied_from.json").read_text())
        why = provenance_reasons(doc, catalog())
        print("PASS" if not why else "FAIL\n  " + "\n  ".join(why))
        return 1 if why else 0
    if argv[:1] == ["build"] and len(argv) >= 3:
        slug, work = argv[1], argv[2]
        pub = argv[argv.index("--publish-slug") + 1] if "--publish-slug" in argv else None
        text = Path(argv[argv.index("--text-file") + 1]).read_text() if "--text-file" in argv else ""
        print(json.dumps(copy_app(slug, text, work, pub), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
