#!/usr/bin/env python3
"""refresh-data.py (Ra, ~horus/dev/eagle-eye) — runs feed.py on novaserver as horus (read-only on every store) and
writes data.json, cold-apps.json and lanes.json beside itself, atomically. A failed measurement leaves the last good files in
place and exits non-zero, so push-kv.sh never pushes a half-written or empty feed. Source of truth for this file:
utopia-models/eagle-eye packages/core/ (knowledge#13151); the unit runs it from the checkout.

    python3 refresh-data.py [data.json] [cold-apps.json] [lanes.json]
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("EE_DATA", "/srv/eagle-eye/data")   # runtime data, never in the checkout
NOVA = os.environ.get("EAGLE_NOVA", "eagle@100.71.25.43")
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "data.json")
COLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT, "cold-apps.json")
LANES = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "lanes.json")   # the /hunt/ and /roost/ pages (knowledge#13617)


def write(path, obj):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


with open(os.path.join(HERE, "feed.py"), "rb") as f:
    src = f.read()
r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", NOVA, "cd ~ && python3 -"],
                   input=src, capture_output=True, timeout=90)
try:
    d = json.loads(r.stdout.decode().strip().splitlines()[-1])
    assert isinstance(d.get("hunts"), dict) and isinstance(d.get("roosts"), dict)
except Exception as ex:  # noqa: BLE001
    sys.exit(f"refresh-data: feed failed (rc={r.returncode}): {ex}; stderr: {r.stderr.decode()[-400:]}")
cold = d.pop("cold_apps_feed", None)
lanes = d.pop("lanes_feed", None)
pipes = d.pop("pipelines_feed", None)   # knowledge#17952: the one-shot diagrams (KV `pipelines`)
write(DATA, d)
if cold:
    write(COLD, cold)
if lanes:
    write(LANES, lanes)
if pipes:
    write(os.path.join(OUT, "pipelines.json"), pipes)
print(json.dumps({k: [h["sent"], h["answered"]] for k, h in d["hunts"].items()}))
