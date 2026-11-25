#!/usr/bin/env python3
"""deploy-preview.py: the Eagle Eye PREVIEW Worker `eagle-dev` on dev.eagle.utopiamodels.ai (same Access as eagle).

Copies every asset of the LIVE `eagle-eye` Worker, applies the preview changes, and uploads it as `eagle-dev` with the
same KV binding. Production (`eagle-eye`) is never touched; it changes only when Tyler picks (then deploy-worker.py).

Preview changes (v1 of the applications section, 2026-11-15):
  * /apps.html (apps.html) served at /hunt/cold_apps, /lane/cold-applications and /applications; /apps.json from KV `apps`
  * /data.json overlays `hunts_24h` (apps_feed.py): every hunt card reads the last 24 hours, all-time kept as *_all
  * desk links: the tailnet base http://novaserver.tail4016d7.ts.net:8796 becomes relative (/go/*, /view/*, /desk/*),
    proxied by the Worker to desks.utopiamodels.ai (desk-view through the novaserver tunnel, Access service token)
  * the jobs agent is labelled sekhmet (Tyler, 2026-11-17, knowledge#14846; was horus)

    python3 deploy-preview.py [--dry-run]
    python3 deploy-preview.py --prod      # the same build onto production `eagle-eye` (only on Tyler's pick)
"""
import importlib.util, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("dw", os.path.join(HERE, "deploy-worker.py"))
dw = importlib.util.module_from_spec(spec); spec.loader.exec_module(dw)
NAME, HOST = "eagle-dev", "dev.eagle.utopiamodels.ai"
TAIL = "http://novaserver.tail4016d7.ts.net:8796"


def rewrite(body):
    body = body.replace(TAIL + "/", "/").replace(TAIL, "/")
    body = re.sub(r'("agent"\s*:\s*")jobs(")', r"\1sekhmet\2", body)
    # lanes.yaml gives cold-email and in-person to jobs (knowledge#13798); the live DOORS block still says horus
    body = re.sub(r'("(?:cold_email|in_person)"\s*:\s*\{\s*"agent"\s*:\s*")horus(")', r"\1sekhmet\2", body)
    body = body.replace("<b>jobs</b>", "<b>sekhmet</b>").replace("Worked by jobs", "Worked by sekhmet")
    return body


def main(a):
    tok, acct = dw.creds()
    handler, assets, types, settings = dw.live(tok, acct)
    assets = {k: rewrite(v) for k, v in assets.items()}
    assets["/apps.html"] = open(os.path.join(HERE, "apps.html")).read()
    types["/apps.html"] = "text/html"
    left = [k for k, v in assets.items() if "tail4016d7" in v]
    src = dw.build(open(os.path.join(HERE, "handler-dev.js")).read().strip(), assets, types)
    get = lambda k: os.popen(f"bash ~/.claude/scripts/infisical-get.sh fleet-infra {k}").read().strip()  # noqa: E731
    binds = [b for b in settings.get("bindings") or [] if b.get("type") == "kv_namespace"] + \
        [{"type": "secret_text", "name": "DESK_ID", "text": get("EAGLE_ACCESS_CLIENT_ID")},
         {"type": "secret_text", "name": "DESK_SECRET", "text": get("EAGLE_ACCESS_CLIENT_SECRET")}]
    print(f"{len(assets)} assets, {len(src)} chars, tailnet links left in: {left or 'none'}")
    if "--dry-run" in a:
        return 0
    if "--prod" in a:   # promote to eagle.utopiamodels.ai (Tyler's pick); its route is the Worker's own custom domain
        etag = dw.upload(tok, acct, src, {**settings, "bindings": binds})
        print("PROMOTED eagle-eye", etag)
        return 0
    dw.API = dw.API.rsplit("/", 1)[0] + "/" + NAME
    print("uploaded", dw.upload(tok, acct, src, {**settings, "bindings": binds}))
    # 2026-11-22: eagle.utopiamodels.ai serves Eagle Eye v2 on Ra (tunnel ra-demos) and dev.eagle 302s there (Worker
    # eagle-dev-redirect). Re-attaching dev.eagle to this old preview Worker is the rollback, done by
    # ~/dev/utopia-models/eagle-eye-v2/deploy/rollback-eagle-hostname.sh, never as a side effect of a preview upload.
    if "--legacy-rollback" not in a:
        print("domain", HOST, "left as is (Eagle Eye v2 owns it; rollback = eagle-eye-v2/deploy/rollback-eagle-hostname.sh)")
        return 0
    zone = json.loads(dw.call("https://api.cloudflare.com/client/v4/zones?name=utopiamodels.ai", tok))["result"][0]["id"]
    body = json.dumps({"hostname": HOST, "service": NAME, "zone_id": zone, "environment": "production"}).encode()
    r = json.loads(dw.call(f"https://api.cloudflare.com/client/v4/accounts/{acct}/workers/domains", tok, body, "application/json", "PUT"))
    print("domain", HOST, r.get("success"), r.get("errors") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
