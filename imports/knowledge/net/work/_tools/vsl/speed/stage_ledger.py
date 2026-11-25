#!/usr/bin/env python3
"""stage_ledger.py: per-stage work/wait wall-time ledger of one-shot VSL runs (knowledge#18876, 1/3 of the 100x speed plan).

  stage_ledger.py JOB [JOB...] [--json] [--feed URL] [--state-dir D] [--vsl-root D] [--mail-json F]

JOB is the 4-digit job suffix the slug carries (3307, 5027). Sources, each read live and each named in the output; a source this box cannot
read prints `unreadable` and its stages stay `no data` (never guessed):
  jobrec  oneshot-auto job record `t` stamps (detected, build_started, authored, app, diagram, scripts_gates, ready, vsl_sent) in
          $ONESHOT_AUTO_DIR or ~/.claude/state/net/oneshot-auto/jobs/<slug>.json  (Ra, user upwork)
  feed    the Eagle Eye hunt feed (oneshot-auto.yaml feed_url): signalAt (posted), foundAt, ready_at, firstSentAt
  mtime   file mtimes under --vsl-root (default /srv/vsl/*/) and /var/tmp/eagle-send whose name carries the job: raw take, final MP4
  mail    `fleetmail inbox --all --json` bodies that name the job (handoff messages)
A stage is the gap between two consecutive STAMPED events. KIND says whether the gap is WORK (a machine or person doing the step) or WAIT
(a handoff, a queue, an idle clock); the split follows the event pair, so a gap spanning an unstamped event is reported as one gap.
"""
from __future__ import annotations
import argparse, datetime as dt, glob, json, os, subprocess, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOW = HERE.parents[4]
# (event, kind of the gap that ENDS at this event, what the gap is)
CHAIN = [
    ("posted",        None,   "client posts the job"),
    ("found",         "wait", "post -> in Eagle Eye feed (intake lag)"),
    ("build_started", "wait", "found -> build picked up (queue)"),
    ("authored",      "work", "post read + app/script authoring (claude worker)"),
    ("app",           "work", "app build + pre-review"),
    ("diagram",       "work", "architecture diagram build + publish"),
    ("scripts_gates", "work", "script draft, rewrite loop, gates"),
    ("ready",         "work", "package marked READY"),
    ("raw_take",      "wait", "READY -> Tyler records the take (wait on Tyler)"),
    ("final_mp4",     "work", "TTS/orb render/composite/mux to MP4"),
    ("vsl_sent",      "wait", "MP4 -> proposal sent (review/upload/send handoff)"),
]


def P(s):
    if not s:
        return None
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def feed_cfg():
    import yaml
    return yaml.safe_load((KNOW / "net/work/vsl/oneshot-auto.yaml").read_text())["feed_url"]


def from_feed(job, url, ev, src):
    try:
        items = json.loads(urllib.request.urlopen(url, timeout=60).read())["items"]
    except Exception as e:  # noqa: BLE001
        src["feed"] = f"unreadable ({type(e).__name__})"
        return
    for i in items:
        if i.get("huntType") == "upwork" and str((i.get("details") or {}).get("job", "")).endswith(job):
            for k, f in (("posted", "signalAt"), ("found", "foundAt"), ("vsl_sent", "firstSentAt")):
                if i.get(f):
                    ev.setdefault(k, (P(i[f]), "feed " + f))
            if i["details"].get("ready_at"):
                ev.setdefault("ready", (P(i["details"]["ready_at"]), "feed details.ready_at"))
            src["feed"] = f"ok ({i['signal'][:50]})"
            return
    src["feed"] = "ok, job not in feed"


def from_jobrec(job, state_dir, ev, src):
    d = Path(state_dir or os.environ.get("ONESHOT_AUTO_DIR") or Path.home() / ".claude/state/net/oneshot-auto") / "jobs"
    try:
        files = sorted(d.glob(f"*-{job}.json"))
    except OSError as e:
        src["jobrec"] = f"unreadable ({e.strerror})"
        return
    if not files:
        src["jobrec"] = f"unreadable or absent: {d}"
        return
    t = json.loads(files[0].read_text()).get("t", {})
    for k in ("posted", "detected", "build_started", "authored", "app", "diagram", "scripts_gates", "ready", "vsl_sent"):
        if t.get(k):
            ev["found" if k == "detected" else k] = (P(t[k]), f"jobrec t.{k}")
    src["jobrec"] = f"ok ({files[0].name})"


def from_mtime(job, root, ev, src):
    pats = [f"{root}/*/*{job}*", f"{root}/*{job}*", f"/var/tmp/eagle-send/*{job}*", f"/var/tmp/eagle-send/*/*{job}*"]
    hits = sorted({p for g in pats for p in glob.glob(g)})
    src["mtime"] = f"{len(hits)} file(s) named {job}" if hits else f"no file named {job} under {root} or /var/tmp/eagle-send"
    for p in hits:
        m = dt.datetime.fromtimestamp(os.stat(p).st_mtime, dt.timezone.utc)
        n = os.path.basename(p).lower()
        if n.endswith((".mkv", ".mov")) and "raw" in n:
            ev.setdefault("raw_take", (m, "mtime " + p))
        elif n.endswith(".mp4") and "final" in n:
            ev.setdefault("final_mp4", (m, "mtime " + p))


def mail(job, mail_json, src):
    try:
        raw = open(mail_json).read() if mail_json else subprocess.run(["fleetmail", "inbox", "--all", "--json"], capture_output=True, text=True, timeout=90).stdout
        rows = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        src["mail"] = f"unreadable ({type(e).__name__})"
        return []
    hit = [r for r in rows if job in r.get("body", "")]
    src["mail"] = f"{len(hit)} message(s) name {job}"
    return [(r["id"], r["sender"], r["sent_at"], r["body"][:140].replace("\n", " ")) for r in hit]


def ledger(job, a):
    ev, src = {}, {}
    from_jobrec(job, a.state_dir, ev, src)
    from_feed(job, a.feed or feed_cfg(), ev, src)
    from_mtime(job, a.vsl_root, ev, src)
    msgs = mail(job, a.mail_json, src)
    rows, prev, skipped = [], None, 0
    for name, kind, what in CHAIN:
        t = ev.get(name)
        row = {"event": name, "at": iso(t[0]) if t else None, "source": t[1] if t else "no data", "kind": kind, "what": what}
        if t and prev:
            gap = max(0, round((t[0] - prev[1]).total_seconds()))
            if skipped:   # the gap spans unstamped events: its work/wait split is unknown, never assigned to the end event's kind
                row.update(seconds=gap, from_event=prev[0], kind="span (unstamped events inside)", work_s=0, wait_s=0, span_s=gap)
            else:
                row.update(seconds=gap, from_event=prev[0], work_s=gap if kind == "work" else 0, wait_s=gap if kind == "wait" else 0)
        if t:
            prev, skipped = (name, t[0]), 0
        elif prev:
            skipped += 1
        rows.append(row)
    tot = [r for r in rows if "seconds" in r]
    return {"job": job, "sources": src, "rows": rows, "mail": msgs,
            "work_s": sum(r["work_s"] for r in tot), "wait_s": sum(r["wait_s"] for r in tot),
            "span_s": sum(r.get("span_s", 0) for r in tot)}


def md(L):
    o = [f"### Job {L['job']}", "", "Sources: " + "; ".join(f"**{k}** {v}" for k, v in L["sources"].items()), "",
         "| event | at (UTC) | gap from previous stamped event | kind | work s | wait s | source |", "|---|---|---|---|---|---|---|"]
    for r in L["rows"]:
        gap = f"{r['seconds']} s from {r['from_event']}" if "seconds" in r else ("no data" if not r["at"] else "-")
        o.append(f"| {r['event']}: {r['what']} | {r['at'] or 'no data'} | {gap} | {r['kind'] or '-'} | {r.get('work_s', '')} | {r.get('wait_s', '')} | {r['source']} |")
    o += ["", f"Stamped work **{L['work_s']} s**, stamped wait **{L['wait_s']} s**, unsplit span **{L['span_s']} s**.", ""]
    o += [f"- fleetmail #{m[0]} {m[1]} {m[2][:19]}: {m[3]}" for m in L["mail"]]
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--feed")
    ap.add_argument("--state-dir")
    ap.add_argument("--vsl-root", default="/srv/vsl")
    ap.add_argument("--mail-json")
    a = ap.parse_args()
    out = [ledger(j, a) for j in a.jobs]
    print(json.dumps(out, indent=1) if a.json else "\n\n".join(md(L) for L in out))


if __name__ == "__main__":
    main()
