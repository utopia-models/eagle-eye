#!/usr/bin/env python3
"""csv_feed.py: the reference pipeline adapter. A ledger CSV in, an Eagle Eye feed (docs/FEED.md) out.

Plug in your own pipeline by writing ONE row per application or status change to a CSV, in time order:

    ts,lane,org,role,status
    2026-11-02 10:00,job_boards,Northwind,Backend engineer,applied
    2026-11-05 16:20,job_boards,Northwind,Backend engineer,interview

    python3 adapters/csv_feed.py ledger.csv > data.json      # then point config.js `feed` at data.json
    python3 adapters/csv_feed.py --self-test

An application is (lane, org, role); its funnel is every status it ever reached. Statuses (any others are ignored):
found, applied, replied, screen, interview, offer, signed, rejected. `rejected` counts as a reply.
Any other adapter works the same way: produce this JSON from your CRM, ATS, inbox or spreadsheet.
"""
import csv
import datetime as dt
import json
import sys

ORDER = ["found", "applied", "replied", "screen", "interview", "offer", "signed"]
STAGES = {"applied": "applied", "replied": "replied", "screen": "screens", "interview": "interviews",
          "offer": "offers", "signed": "signed"}


def reached(seen):
    """the funnel stages one application reached: a later stage implies every earlier one past `found`"""
    if "rejected" in seen:
        seen = seen | {"replied"}
    top = max((ORDER.index(s) for s in seen if s in ORDER), default=-1)
    return {s for s in ORDER[1:top + 1]}


def feed(rows):
    apps = {}
    for r in rows:
        k = (r["lane"].strip(), r["org"].strip().lower(), r["role"].strip().lower())
        a = apps.setdefault(k, {"seen": set(), "ts": "", "last": ""})
        a["seen"].add(r["status"].strip().lower())
        a["ts"], a["last"] = r["ts"].strip(), r["status"].strip().lower()
    out = {s: 0 for s in STAGES.values()}
    hunts = {}
    for (lane, _, _), a in apps.items():
        got = reached(a["seen"])
        h = hunts.setdefault(lane, {"sent": 0, "answered": 0, "status": "live", "source": "csv ledger", "_ts": ""})
        h["sent"] += "applied" in got
        h["answered"] += "replied" in got
        for s in got:
            if s in STAGES:
                out[STAGES[s]] += 1
        if a["ts"] > h["_ts"]:
            h["_ts"], h["last_action"] = a["ts"], {"ts": a["ts"].replace(" ", "T") + ":00Z", "event": a["last"]}
    for h in hunts.values():
        h.pop("_ts")
    out["hunts"] = hunts
    out["roosts"] = {}
    out["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def self_test():
    rows = [dict(zip(["ts", "lane", "org", "role", "status"], x.split(","))) for x in [
        "2026-11-01 10:00,job_boards,A,eng,applied", "2026-11-03 10:00,job_boards,A,eng,interview",
        "2026-11-01 10:00,job_boards,B,eng,applied", "2026-11-02 10:00,job_boards,B,eng,rejected",
        "2026-11-01 10:00,referrals,C,eng,found"]]
    f = feed(rows)
    jb = f["hunts"]["job_boards"]
    want = [(jb["sent"], 2), (jb["answered"], 2), (f["interviews"], 1), (f["applied"], 2),
            (f["hunts"]["referrals"]["sent"], 0), (jb["last_action"]["event"], "interview")]
    bad = [(g, w) for g, w in want if g != w]
    print("self-test", "PASS" if not bad else f"FAIL {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], newline="") as f:
        print(json.dumps(feed(list(csv.DictReader(f))), indent=1))
