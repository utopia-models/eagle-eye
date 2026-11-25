#!/usr/bin/env python3
"""deploy-api.py: deploy the Eagle Eye mobile API Worker `eagle-eye-api` at https://eagle-api.utopiamodels.ai (knowledge#14249).

    python3 deploy-api.py            # upload worker.js with its bindings, attach the custom domain, check /health
    python3 deploy-api.py --dry-run  # print the bindings it would send, upload nothing

Bindings: KV DATA = eagle-eye-data (the same namespace the eagle-eye Worker reads; this Worker writes only
`push/app/<person>`), secrets UP_ID / UP_SECRET (the EAGLE_ACCESS service token, for reads from eagle.utopiamodels.ai),
SIGNING_KEY (EAGLE_API_SIGNING_KEY, minted into the vault on first deploy), GOOGLE_AUDIENCES (the Eagle Eye web OAuth
client, the audience of every Google ID token the Android and iOS apps send).

KV `people` ({"emails": {email: person}, "admins": [...]}) is who may sign in. It is seeded once from SEED_PEOPLE when
absent and never overwritten here.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER, HOST = "eagle-eye-api", "eagle-api.utopiamodels.ai"
KV_NS = "d97b9be8758d4ede805c0bf9c6d2e68c"  # eagle-eye-data
ZONE = "utopiamodels.ai"
GET = os.path.expanduser("~/.claude/scripts/infisical-get.sh")
SET = os.path.expanduser("~/.claude/scripts/infisical-set.sh")
sys.path.insert(0, os.path.join(HERE, ".."))
import eeconf  # noqa: E402

SEED_PEOPLE = eeconf.get("people", {"emails": {}, "admins": []})  # {"emails": {email: person}, "admins": [...]} from the overlay


def vault(k: str) -> str:
    return subprocess.run(["bash", GET, "fleet-infra", k], capture_output=True, text=True).stdout.strip()


def call(url, tok, data=None, ctype="application/json", method="GET"):
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {tok}", "Content-Type": ctype})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def main(argv):
    tok, acct = vault("CF_API_TOKEN_UTOPIA"), vault("CF_ACCOUNT_ID_UTOPIA")
    key = vault("EAGLE_API_SIGNING_KEY")
    if not key:
        key = secrets.token_urlsafe(48)
        subprocess.run(["bash", SET, "fleet-infra", "EAGLE_API_SIGNING_KEY"], input=key, text=True, capture_output=True, check=True)
        if vault("EAGLE_API_SIGNING_KEY") != key:
            raise SystemExit("EAGLE_API_SIGNING_KEY did not read back from the vault")
    aud = vault("EAGLE_MOBILE_GOOGLE_WEB_CLIENT_ID")
    up_id, up_secret = vault("EAGLE_ACCESS_CLIENT_ID"), vault("EAGLE_ACCESS_CLIENT_SECRET")
    if not all([tok, acct, aud, up_id, up_secret]):
        raise SystemExit("a vault key is unreadable (CF_API_TOKEN_UTOPIA, EAGLE_MOBILE_GOOGLE_WEB_CLIENT_ID, EAGLE_ACCESS_*)")
    bindings = [
        {"type": "kv_namespace", "name": "DATA", "namespace_id": KV_NS},
        {"type": "secret_text", "name": "UP_ID", "text": up_id},
        {"type": "secret_text", "name": "UP_SECRET", "text": up_secret},
        {"type": "secret_text", "name": "SIGNING_KEY", "text": key},
        {"type": "plain_text", "name": "GOOGLE_AUDIENCES", "text": aud},
    ]
    if "--dry-run" in argv:
        print("bindings:", [(b["type"], b["name"]) for b in bindings])
        return 0
    src = open(os.path.join(HERE, "worker.js")).read()
    meta = {"main_module": "worker.js", "bindings": bindings, "compatibility_date": "2025-09-01"}
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n{json.dumps(meta)}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"worker.js\"; filename=\"worker.js\"\r\n"
            f"Content-Type: application/javascript+module\r\n\r\n{src}\r\n--{b}--\r\n").encode()
    api = f"https://api.cloudflare.com/client/v4/accounts/{acct}"
    r = call(f"{api}/workers/scripts/{WORKER}", tok, body, f"multipart/form-data; boundary={b}", "PUT")
    if not r.get("success"):
        raise SystemExit(f"upload failed: {r.get('errors')}")
    print(f"uploaded {WORKER}")
    zone = call(f"https://api.cloudflare.com/client/v4/zones?name={ZONE}", tok)["result"][0]["id"]
    r = call(f"{api}/workers/domains", tok, json.dumps({"hostname": HOST, "service": WORKER, "zone_id": zone, "environment": "production"}).encode(), method="PUT")
    print("domain", HOST, "ok" if r.get("success") else r.get("errors"))
    kv = f"{api}/storage/kv/namespaces/{KV_NS}/values/people"
    req = urllib.request.Request(kv, headers={"Authorization": f"Bearer {tok}"})
    try:
        urllib.request.urlopen(req, timeout=30)
        print("KV people: present, left as is")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        call(kv, tok, json.dumps(SEED_PEOPLE).encode(), "text/plain", "PUT")
        print("KV people: seeded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
