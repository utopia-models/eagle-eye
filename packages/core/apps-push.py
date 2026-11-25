#!/usr/bin/env python3
"""apps-push.py: build the applications feed (apps_feed.py over feed.py) as horus on novaserver and PUT it into KV
eagle-eye-data key `apps`. See apps_feed.py. A failed build pushes nothing (the KV keeps the last good copy).

    python3 apps-push.py --print
    python3 apps-push.py --push [--loop 30]
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
NS = "d97b9be8758d4ede805c0bf9c6d2e68c"   # eagle-eye-data (push-kv.sh)
# defaults = push-kv.sh on Ra as horus (the same ssh refresh-data.py uses); from another account set EAGLE_NOVA_SSH=nova@100.71.25.43
# EAGLE_NOVA_RUN="sudo -u eagle bash -c 'cd ~ && python3 -'"
NOVA = os.environ.get("EAGLE_NOVA_SSH", "eagle@100.71.25.43")
RUN = os.environ.get("EAGLE_NOVA_RUN", "cd ~ && python3 -")


def source():
    feed = open(os.path.join(HERE, "feed.py")).read()
    feed = feed[:feed.rindex('if __name__ == "__main__":')]
    return feed + "\n" + open(os.path.join(HERE, "network_here.py")).read() + "\n" + \
        open(os.path.join(HERE, "apps_feed.py")).read() + \
        '\nprint(json.dumps(apps_feeds(), ensure_ascii=False, separators=(",", ":")))\n'


def build():
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", NOVA, RUN],
                       input=source().encode(), capture_output=True, timeout=120)
    out = r.stdout.decode().strip().splitlines()
    if r.returncode or not out:
        raise RuntimeError(f"rc={r.returncode} {r.stderr.decode()[-600:]}")
    d = json.loads(out[-1])
    assert isinstance(d.get("tyler", {}).get("apps"), list)
    return {k: json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in d.items()}, d


def cred(k):
    return subprocess.run(["bash", os.path.expanduser("~/.claude/scripts/infisical-get.sh"), "fleet-infra", k],
                          capture_output=True, text=True).stdout.strip()


def put(key, body, tok, acct):
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces/{NS}/values/{urllib.parse.quote(key, safe='')}",
                                 data=body.encode(), method="PUT", headers={"Authorization": f"Bearer {tok}"})
    return urllib.request.urlopen(req, timeout=30).status


def main(a):
    if "--print" in a:
        raw, d = build()
        for k, v in d.items():
            print(k, len(raw[k]), json.dumps(v["totals"]), json.dumps(v["sources"])[:300])
        return 0
    if "--push" not in a:
        print(__doc__)
        return 2
    tok = os.environ.get("CF_TOKEN") or cred("CF_API_TOKEN_UTOPIA")   # push-kv.sh passes its own token
    acct = os.environ.get("CF_ACCOUNT") or cred("CF_ACCOUNT_ID_UTOPIA")
    every = int(a[a.index("--loop") + 1]) if "--loop" in a else 0
    while True:
        try:
            raw, d = build()
            for k in raw:   # KV `apps` = Tyler (what the live preview reads), `apps/<person>` = each other person
                print(time.strftime("%FT%TZ", time.gmtime()), k, len(d[k]["apps"]), "apps", len(raw[k]), "bytes kv",
                      put("apps" if k == "tyler" else f"apps/{k}", raw[k], tok, acct), flush=True)
        except Exception as ex:  # noqa: BLE001
            print(time.strftime("%FT%TZ", time.gmtime()), "BUILD FAILED, nothing pushed:", str(ex)[-400:], file=sys.stderr, flush=True)
            if not every:
                return 1
        if not every:
            return 0
        time.sleep(every)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
