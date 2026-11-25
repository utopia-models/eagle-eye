#!/usr/bin/env python3
"""deploy-worker.py: put changed page files into the deployed `eagle-eye` Worker (eagle.utopiamodels.ai) (knowledge#13174).

The Worker is one module: `const A={path: body}` (the page files), `const T={path: content-type}`, and a fetch handler
that serves A and answers /data.json from KV `data` (namespace eagle-eye-data, filled by push-kv.sh). This tool reads
the LIVE script, swaps in only the files you name, keeps every other asset, the handler and the KV binding as they
are, and uploads it. So a deploy never rolls back what horus shipped from ~horus/dev/eagle-eye.

    python3 deploy-worker.py /home-v2c.js=path/to/home-v2c.js [/x.html=path ...]   # deploy
    python3 deploy-worker.py --dry-run /home-v2c.js=path/to/home-v2c.js             # build + print, no upload
    python3 deploy-worker.py --list                                                 # the live asset paths + sizes
    python3 deploy-worker.py --handler person/handler.js [/x=path ...]              # also replace the fetch handler
    python3 deploy-worker.py --remove /p/claire [/x ...]                             # drop assets nothing serves
    python3 deploy-worker.py --pwa                                                   # the installable app's files (pwa/)

The handler in git (person/handler.js, knowledge#13617) adds `/p/<person>` (page `/p/<person>`, feed KV `p/<person>`,
UI `/p/eagle-eye.js` = the open-source build); pass it whenever the live handler lacks the /p/ route.

Always check after: `python3 net/work/_tools/eagle_hunts.py --live` (the PIPES list matches lanes.yaml).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.request
import uuid

WORKER = "eagle-eye"
API = "https://api.cloudflare.com/client/v4/accounts/{acct}/workers/scripts/" + WORKER
CT = {".js": "text/javascript", ".html": "text/html", ".json": "application/json", ".css": "text/css",
      ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".png": "image/png"}


def creds():
    get = os.path.expanduser("~/.claude/scripts/infisical-get.sh")
    rd = lambda k: subprocess.run(["bash", get, "fleet-infra", k], capture_output=True, text=True).stdout.strip()  # noqa: E731
    tok, acct = rd("CF_API_TOKEN_UTOPIA"), rd("CF_ACCOUNT_ID_UTOPIA")
    if not tok or not acct:
        raise SystemExit("CF_API_TOKEN_UTOPIA / CF_ACCOUNT_ID_UTOPIA unreadable from Infisical")
    return tok, acct


def call(url, tok, data=None, ctype=None, method="GET"):
    h = {"Authorization": f"Bearer {tok}"}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=60).read()


def live(tok, acct):
    """-> (script source, assets A, types T, bindings) of the deployed Worker."""
    raw = call(API.format(acct=acct), tok).decode()
    i, j, k = raw.find("const A="), raw.find("};\nconst T="), raw.find("export default")
    if min(i, j, k) < 0:
        raise SystemExit("deployed Worker has no `const A={...};\\nconst T={...};` + export default: shape changed")
    a = json.loads(raw[i + 8:j + 1])
    t_end = raw.find("};\n", j + 3)
    t = json.loads(raw[j + 11:t_end + 1])  # past "};\nconst T="
    handler = raw[k:raw.rfind("}") + 1]
    settings = json.loads(call(API.format(acct=acct) + "/settings", tok))["result"]
    return handler, a, t, settings


def build(handler, a, t):
    return f"const A={json.dumps(a)};\nconst T={json.dumps(t)};\n{handler}\n"


def upload(tok, acct, src, settings):
    # knowledge#13870: the settings API returns a `secret_text` binding (DESK_SECRET) WITHOUT its text, and a PUT that
    # re-sends it is refused (10021 "invalid or missing text property"). Secrets are kept by type, never re-sent.
    kept = [b for b in (settings.get("bindings") or []) if b.get("type") != "secret_text"]
    meta = {"main_module": "worker.js", "bindings": kept, "keep_bindings": ["secret_text"],
            "compatibility_date": settings.get("compatibility_date") or "2025-01-01",
            "compatibility_flags": settings.get("compatibility_flags") or []}
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n"
            f"{json.dumps(meta)}\r\n--{b}\r\nContent-Disposition: form-data; name=\"worker.js\"; filename=\"worker.js\"\r\n"
            f"Content-Type: application/javascript+module\r\n\r\n{src}\r\n--{b}--\r\n").encode()
    r = json.loads(call(API.format(acct=acct), tok, body, f"multipart/form-data; boundary={b}", "PUT"))
    if not r.get("success"):
        raise SystemExit(f"upload failed: {r.get('errors')}")
    return r["result"].get("etag") or r["result"].get("id")


# The home page's own files (and pwa.js, loaded on every page). A deploy that changes any of them first runs
# phone-check.mjs (knowledge#14223) on the live page with them swapped in; a failing check stops the deploy (knowledge#14243).
GATED = ("/home-v2.js", "/who.js", "/upwork-badge.js", "/pwa.js")
HERE = os.path.dirname(os.path.abspath(__file__))


def phone_check(specs):
    """Run phone-check.mjs with the gated files swapped in; SystemExit unless it prints PASS."""
    swaps = [x for x in specs if x.partition("=")[0] in GATED]
    if not swaps:
        return
    audit = os.path.normpath(os.path.join(HERE, "../../../../_infra/scripts/site-audit"))
    env = dict(os.environ)
    if not env.get("PLAYWRIGHT_DIR") and not os.path.isdir(os.path.join(audit, "node_modules", "playwright")):
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=audit, check=True, capture_output=True)
    if not env.get("CF_ACCESS_CLIENT_ID"):
        get = os.path.expanduser("~/.claude/scripts/infisical-get.sh")
        rd = lambda k: subprocess.run(["bash", get, "fleet-infra", k, "prod"], capture_output=True, text=True).stdout.strip()  # noqa: E731
        env["CF_ACCESS_CLIENT_ID"], env["CF_ACCESS_CLIENT_SECRET"] = rd("EAGLE_ACCESS_CLIENT_ID"), rd("EAGLE_ACCESS_CLIENT_SECRET")
    cmd = ["node", os.path.join(HERE, "phone-check.mjs")]
    for x in swaps:
        path, _, local = x.partition("=")
        cmd += ["--asset", f"{path}={os.path.abspath(local)}"]
    print(f"phone-check: {' '.join(x.partition('=')[0] for x in swaps)} ...", flush=True)
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=900)
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0 or not out.endswith("PASS"):
        raise SystemExit(f"phone-check FAILED, nothing deployed:\n{out[-3000:]}")
    print("phone-check: PASS")


def main(argv):
    dry = "--dry-run" in argv
    argv = [x for x in argv if x != "--dry-run"]
    new_handler = None
    if "--handler" in argv:
        i = argv.index("--handler")
        new_handler = open(argv[i + 1]).read().strip()
        del argv[i:i + 2]
        if not new_handler.startswith("export default"):
            raise SystemExit("--handler file must start with `export default`")
    gone = []
    while "--remove" in argv:   # knowledge#14303: subtraction, an asset the handler no longer serves
        i = argv.index("--remove")
        gone.append(argv[i + 1])
        del argv[i:i + 2]
    if "--pwa" in argv:   # knowledge#14243: manifest, service worker, pwa.js, icons, favicon from pwa/
        argv.remove("--pwa")
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pwa")
        argv += [f"/{n}={d}/{n}" for n in ("manifest.webmanifest", "sw.js", "pwa.js", "favicon.svg", "logo-mark.svg", "logo-mark-light.svg", "logo-lockup.svg", "logo-wordmark.svg")]
        argv += [f"/icons/{n}={d}/icons/{n}" for n in sorted(os.listdir(os.path.join(d, "icons")))]
        argv.append(f"/favicon.ico={d}/icons/favicon-48.png")
    if (not argv and not new_handler and not gone) or (argv and argv[0] in ("-h", "--help")):
        print(__doc__)
        return 0
    tok, acct = creds()
    handler, a, t, settings = live(tok, acct)
    if new_handler:
        handler = new_handler
    if argv and argv[0] == "--list":
        for p, body in a.items():
            print(f"{p}\t{len(body)}\t{t.get(p)}")
        return 0
    for spec in argv:
        path, _, local = spec.partition("=")
        if not path.startswith("/") or not local:
            raise SystemExit(f"bad argument {spec!r}: want /asset/path=local/file")
        # a PNG is stored base64 under content-type image/png; the handler's serve() decodes it (knowledge#14243)
        body = base64.b64encode(open(local, "rb").read()).decode() if local.endswith(".png") else open(local).read()
        print(f"{path}: {len(a.get(path, ''))} -> {len(body)} chars{' (new)' if path not in a else ''}")
        a[path] = body
        t.setdefault(path, CT.get(os.path.splitext(path)[1]) or CT.get(os.path.splitext(local)[1], "text/plain"))
        if local.endswith(".png"):
            t[path] = "image/png"
        if path == "/home-v2c.html":
            a["/"] = body  # "/" serves the same document
    for path in gone:
        print(f"{path}: removed ({len(a.pop(path, ''))} chars)")
        t.pop(path, None)
    src = build(handler, a, t)
    if not dry:
        phone_check(argv)
    if dry:
        print(f"dry run: {len(src)} chars, bindings {[x.get('name') for x in settings.get('bindings') or []]}")
        return 0
    print(f"deployed {WORKER}: {upload(tok, acct, src, settings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
