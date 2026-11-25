#!/usr/bin/env python3
"""desc_loop.py: the stuck-description loop (knowledge#21574; Architect/nova 21594). One pass (a novaserver systemd user timer runs it every 5 min):
  1 ask Ra's builder which jobs wait on a post text (oneshot_auto.py stuck, read-only on upwork's state)
  2 read ONE of them in vsl's own headful Chrome on Ra (desc_reader.py: logged-out, public listings only, never the Upwork seat) -> /var/tmp/vsl-descriptions/<~id>.json;
    when the builder's desc dir is writable for vsl, copy it there so the next tick queues the job
  3 alarm: a job stuck > ALARM_MIN with no readable description is mailed once to chief + upwork with the reason (private/closed listings say so)
One load per pass keeps the 4-9 minute spacing Upwork asked for."""
import json, os, subprocess, sys, time
from pathlib import Path
RA = "vsl@100.127.249.81"; STATE = Path.home() / ".claude/state/desc-loop"; STATE.mkdir(parents=True, exist_ok=True)
ALARM_MIN = 15
def ra(cmd, t=180):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", RA, cmd], capture_output=True, text=True, timeout=t)
seen = json.loads((STATE / "seen.json").read_text()) if (STATE / "seen.json").exists() else {}
r = ra("ONESHOT_AUTO_DIR=/home/upwork/.claude/state/net/oneshot-auto python3 /home/upwork/oneshot/kb-v2/net/work/_tools/vsl/oneshot_auto.py --no-spawn stuck")
try:
    stuck = json.loads(r.stdout)["stuck"]
except Exception:
    print("stuck call failed:", r.stderr[-200:]); sys.exit(1)
now = time.time(); alarms = []; did_read = False
for j in stuck:
    jid = j["job"]; rec = seen.setdefault(jid, {"first": now, "tries": 0, "ok": False})
    if rec.get("ok") or rec.get("private"):
        pass
    elif now - rec.get("last", 0) > 240 and not did_read:
        out = ra(f"cd ~/render && PLAYWRIGHT_BROWSERS_PATH=$HOME/render/pw timeout 120 xvfb-run -a ./venv/bin/python desc_reader.py {jid.lstrip('~')} 2>&1 | tail -1", 200).stdout
        rec["last"] = now; rec["tries"] += 1; did_read = True       # ONE page load per pass (timer = 5 min)
        try:
            res = json.loads(out.split("}", 1)[0] + "}")
            rec["ok"] = bool(res.get("ok")); rec["why"] = res.get("why")
            rec["private"] = bool(res.get("why") and "private" in res["why"])
            if rec["ok"]:   # hand it to the builder when its dir takes our write
                ra(f"cp '/var/tmp/vsl-descriptions/{jid}.json' '/var/tmp/upwork-descriptions/{jid}.json' 2>&1")
        except Exception:
            rec["why"] = out[-120:]
    if not rec.get("ok") and (now - rec["first"]) / 60 > ALARM_MIN and not rec.get("alarmed"):
        alarms.append(f"{j['slug']} ({jid}): {rec.get('why') or j.get('why')}"); rec["alarmed"] = True
(STATE / "seen.json").write_text(json.dumps(seen, indent=1))
if alarms:
    msg = "vsl desc-loop: jobs stuck in needs_description > %d min with no readable post:\n- %s\n(private/closed listings can never be read: skip them; others: read by hand or tell me)" % (ALARM_MIN, "\n- ".join(alarms))
    for who, th in (("chief", "vsl-speed"), ("upwork", "vsl-handoff")):
        subprocess.run(["fleetmail", "send", who, msg, "--thread", th], capture_output=True)
print(time.strftime("%H:%MZ", time.gmtime()), "stuck", len(stuck), "alarms", len(alarms))
