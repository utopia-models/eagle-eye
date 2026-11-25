#!/usr/bin/env python3
"""oneshot_delay.py: where every minute after READY went (Tyler 2026-11-22 6:55 AM ET). Each minute between READY and the take is exactly one of
  RECORDING        a recording is running (events recording_started .. recording_stopped)
  REVISION         the build was not good enough: a `oneshot revise` request is open (opened .. closed); his words are the reason
  WAITING ON TYLER the build is good, no revision open, he is not recording
When two overlap, RECORDING wins over REVISION wins over WAITING, so every minute has one tag. Build time ends at READY and is never extended by
a revision (this module reads t.ready and never writes it).

  oneshot_delay.py status [JOB]          the segments and minutes per job
  oneshot_delay.py week [--days N]       revisions per job (the quality KPI, goal 0), minutes by tag, and the gate that would have caught each
  oneshot_delay.py gate JOB REV N|none   record which gate should have caught revision REV (none = no gate exists yet: a new gate to build)
  oneshot_delay.py --self-test
Events come from the Eagle/Vizier side: `oneshot_auto.py event JOB recording_started|recording_stopped [--ts ISO]`; revisions are written by
oneshot_revise.py (opened = the request started, closed = it finished). The pure functions take a job dict and a time, nothing outward.
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TAGS = ("recording", "revision", "waiting")          # precedence, highest first
COLOUR = {"recording": "red", "revision": "amber", "waiting": "slate"}
PLAIN = {"recording": "Recording", "revision": "Revision", "waiting": "Waiting on Tyler"}
DEFAULT_GATE = {"diagram": 2, "script": 3, "app": 1}  # the gate that would normally catch a bad artifact; a person confirms or says none


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if s else None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def intervals(job, end):
    """-> {tag: [(start, end)]} clipped to [ready, end]. An open revision or recording runs to `end`."""
    ready = parse(job["t"].get("ready"))
    out = {"recording": [], "revision": []}
    if not ready:
        return out
    ev = sorted(job.get("events", []), key=lambda e: e["at"])
    start = None
    for e in ev:
        if e["kind"] == "recording_started" and start is None:
            start = parse(e["at"])
        elif e["kind"] == "recording_stopped" and start is not None:
            out["recording"].append((start, parse(e["at"])))
            start = None
    if start is not None:
        out["recording"].append((start, end))
    for r in job.get("revisions", []):
        if r.get("test"):   # a proof or test run is not a build-quality complaint: no minutes, no KPI
            continue
        a = parse(r.get("opened") or r.get("started"))
        b = parse(r.get("closed") or r.get("finished")) or end
        if a:
            out["revision"].append((a, b))
    return {k: [(max(a, ready), min(b, end)) for a, b in v if min(b, end) > max(a, ready)] for k, v in out.items()}


def attribute(job, now=None):
    """-> {"from", "to", "segments": [{tag, from, to, minutes}], "minutes": {tag: m}, "revisions": n, "revision_list": [...]}.
    A sweep over every boundary; each span takes the highest-precedence tag active in it."""
    ready = parse(job["t"].get("ready"))
    if not ready:
        return {"from": None, "to": None, "segments": [], "minutes": dict.fromkeys(TAGS, 0.0), "revisions": 0, "revision_list": []}
    end = parse(job["t"].get("recorded")) or now or dt.datetime.now(dt.timezone.utc)
    iv = intervals(job, end)
    cuts = sorted({ready, end} | {t for v in iv.values() for ab in v for t in ab})
    segs = []
    for a, b in zip(cuts, cuts[1:]):
        mid = a + (b - a) / 2
        tag = next((t for t in ("recording", "revision") if any(x <= mid < y for x, y in iv[t])), "waiting")
        if segs and segs[-1]["tag"] == tag:
            segs[-1]["to"] = iso(b)
        else:
            segs.append({"tag": tag, "from": iso(a), "to": iso(b)})
    mins = dict.fromkeys(TAGS, 0.0)
    for s in segs:
        s["minutes"] = round((parse(s["to"]) - parse(s["from"])).total_seconds() / 60, 2)
        s["colour"] = COLOUR[s["tag"]]
        mins[s["tag"]] = round(mins[s["tag"]] + s["minutes"], 2)
    revs = [{"rev": r.get("rev"), "reason": r.get("words"), "artifact": r.get("artifact"), "gate": r.get("gate_should_have_caught", DEFAULT_GATE.get(r.get("artifact"))),
             "gate_confirmed": "gate_should_have_caught" in r, "minutes": r.get("minutes"), "ok": r.get("ok")} for r in job.get("revisions", []) if not r.get("test")]
    return {"from": iso(ready), "to": iso(end), "segments": segs, "minutes": mins, "revisions": len(revs), "revision_list": revs,
            "tz_note": "stamps are UTC; the feed formats them in the display zone"}


def weekly(jobs, now=None, days=7):
    """The quality KPI: revisions per job (goal 0), minutes by tag, and every revision with the gate that would have caught it."""
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=days)
    rows, tot = [], dict.fromkeys(TAGS, 0.0)
    for j in jobs:
        r = parse(j["t"].get("ready"))
        if not r or r < since:
            continue
        a = attribute(j, now)
        rows.append({"slug": j["slug"], "revisions": a["revisions"], "minutes": a["minutes"], "revision_list": a["revision_list"]})
        for k in TAGS:
            tot[k] = round(tot[k] + a["minutes"][k], 2)
    allrev = [dict(x, slug=r["slug"]) for r in rows for x in r["revision_list"]]
    need = {}
    for x in allrev:
        key = "none (no gate exists yet)" if x["gate"] in (None, "none") else f"gate {x['gate']}" + ("" if x["gate_confirmed"] else " (suggested, unconfirmed)")
        need.setdefault(key, []).append(f"{x['slug']} rev {x['rev']}: {x['reason']}")
    return {"days": days, "jobs": len(rows), "revisions_total": len(allrev), "revisions_per_job": round(len(allrev) / len(rows), 2) if rows else 0.0,
            "goal": 0, "minutes": tot, "per_job": rows, "gates_to_feed_back": need}


def plain(a):
    m = a["minutes"]
    return (f"recording {m['recording']} min | revision {m['revision']} min | waiting on Tyler {m['waiting']} min | revisions: {a['revisions']}")


def selftest():
    def T(h, m, s=0):
        return f"2026-11-22T{h:02d}:{m:02d}:{s:02d}Z"
    job = {"slug": "x", "t": {"ready": T(12, 0), "recorded": T(12, 50)},
           "events": [{"at": T(12, 20), "kind": "recording_started"}, {"at": T(12, 40), "kind": "recording_stopped"}],
           "revisions": [{"rev": 1, "words": "make the diagram bigger", "artifact": "diagram", "opened": T(12, 10), "closed": T(12, 25), "minutes": 1.8, "ok": True},
                         {"rev": 2, "words": "ahead of ready", "artifact": "script", "opened": T(11, 40), "closed": T(11, 50), "ok": True}]}
    a = attribute(job)
    m = a["minutes"]
    ok = [[(s["tag"], s["minutes"]) for s in a["segments"]] == [("waiting", 10.0), ("revision", 10.0), ("recording", 20.0), ("waiting", 10.0)],   # recording beats the overlapping revision
          m == {"recording": 20.0, "revision": 10.0, "waiting": 20.0}, abs(sum(m.values()) - 50) < 0.01,   # every minute exactly one tag
          a["revisions"] == 2, a["revision_list"][0]["gate"] == 2 and a["revision_list"][0]["reason"] == "make the diagram bigger",
          a["segments"][1]["colour"] == "amber" and a["segments"][2]["colour"] == "red" and a["segments"][0]["colour"] == "slate"]
    # an open revision and an open recording run to now; a revision before READY adds no minutes
    now = parse(T(13, 0))
    openj = {"slug": "y", "t": {"ready": T(12, 0)}, "events": [{"at": T(12, 30), "kind": "recording_started"}],
             "revisions": [{"rev": 1, "words": "w", "artifact": "app", "opened": T(12, 5)}]}
    b = attribute(openj, now)
    ok += [b["minutes"] == {"recording": 30.0, "revision": 25.0, "waiting": 5.0}, b["to"] == T(13, 0)]
    ok += [attribute({"slug": "z", "t": {}}, now)["segments"] == []]                      # no READY, nothing to attribute
    j3 = dict(job, t=dict(job["t"]))
    before = dict(j3["t"])
    attribute(j3)
    ok += [j3["t"] == before]                                                              # build time (t.ready) is never touched
    w = weekly([job, openj], now, 7)
    ok += [w["jobs"] == 2 and w["revisions_total"] == 3 and w["revisions_per_job"] == 1.5 and w["goal"] == 0,
           any("gate 2 (suggested, unconfirmed)" in k for k in w["gates_to_feed_back"])]
    tj = dict(job, revisions=job["revisions"] + [{"rev": 9, "words": "proof run", "artifact": "app", "opened": T(12, 30), "closed": T(12, 35), "test": True}])
    ta = attribute(tj)
    ok += [ta["revisions"] == 2 and ta["minutes"] == a["minutes"]]                       # a test revision adds neither a count nor minutes
    job["revisions"][0]["gate_should_have_caught"] = "none"
    w2 = weekly([job], now, 7)
    ok += [any(k.startswith("none") for k in w2["gates_to_feed_back"])]                   # 'no gate exists' is a new gate to build
    print("self-test", "PASS" if all(ok) else f"FAIL {[i for i, v in enumerate(ok) if not v]}")
    return 0 if all(ok) else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    import oneshot_auto as A
    if argv[:1] == ["status"]:
        for j in A.all_jobs():
            if argv[1:2] and j["slug"] != argv[1]:
                continue
            a = attribute(j)
            print(f"{j['slug']}: {plain(a)}")
            for s in a["segments"]:
                print(f"   {PLAIN[s['tag']]:<18} {A.fmt_tz(s['from'])} -> {A.fmt_tz(s['to'])}  {s['minutes']} min")
        return 0
    if argv[:1] == ["week"]:
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
        w = weekly(A.all_jobs(), None, days)
        (A.STATE).mkdir(parents=True, exist_ok=True)
        (A.STATE / "weekly-report.json").write_text(json.dumps(w, indent=1) + "\n")
        A.PKG_ROOT.mkdir(parents=True, exist_ok=True)
        (A.PKG_ROOT / "weekly-report.json").write_text(json.dumps(w, indent=1) + "\n")
        print(json.dumps(w, indent=1))
        return 0
    if argv[:1] == ["gate"] and len(argv) == 4:
        slug, rev, g = argv[1], int(argv[2]), argv[3]
        j = A.load_job(slug)
        rec = next((r for r in j.get("revisions", []) if r.get("rev") == rev), None)
        if rec is None:
            print(f"no revision {rev} on {slug}")
            return 2
        rec["gate_should_have_caught"] = "none" if g == "none" else int(g)
        A.save_job(j)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
