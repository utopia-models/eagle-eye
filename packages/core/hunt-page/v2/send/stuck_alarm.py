#!/usr/bin/env python3
"""Stuck-row alarm (knowledge#18576): reads the one feed path (/api/feed timelines[*].stuck, budgets in src/stuck.ts) and
fleetmails the Architect (thread eagle-stuck) when a hunt row sits in one stage past its budget. Silent when nothing is stuck;
re-sends only rows not already named in the last mail (state file), so a stuck row alarms once, not every run."""
import json, os, subprocess, sys, urllib.request
from pathlib import Path

FEED = os.environ.get("EAGLE_FEED", "http://100.127.249.81:8798/api/feed?workspace=tyler")
STATE = Path(os.environ.get("EAGLE_STUCK_STATE", str(Path.home() / ".local/state/eagle-stuck.json")))


def stuck_rows(feed):
    return {i: t["stuck"] for i, t in (feed.get("timelines") or {}).items() if t.get("stuck")}


def main(argv=None):
    with urllib.request.urlopen(FEED, timeout=30) as r:
        feed = json.loads(r.read())
    rows = stuck_rows(feed)
    first = not STATE.exists()
    seen = set(json.loads(STATE.read_text())) if not first else set()
    if first:   # seed run: the backlog is one summary line, never one mail per row (224 of 307 rows were stuck when this shipped)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(sorted(rows)))
        print(json.dumps({"stuck": len(rows), "new": 0, "seeded": True}))
        if rows and "--no-mail" not in (argv or sys.argv[1:]):
            subprocess.run(["fleetmail", "send", "agent", f"Eagle Eye stuck alarm armed: {len(rows)} rows already past budget (seeded, not listed); only rows that newly stick will alarm.", "--thread", "eagle-stuck"], timeout=60)
        return 0
    new = {i: s for i, s in rows.items() if i not in seen}
    print(json.dumps({"stuck": len(rows), "new": len(new)}))
    if new and "--no-mail" not in (argv or sys.argv[1:]):
        lines = [f"Eagle Eye: {len(new)} hunt row(s) past their stage budget ({len(rows)} stuck in all)."]
        lines += [f"- {i}: {s['hours']} h at {s['stage']} (budget {s['budget_h']} h), waiting for {s['waiting_for']}" for i, s in list(new.items())[:25]]
        subprocess.run(["fleetmail", "send", "agent", "\n".join(lines), "--thread", "eagle-stuck"], timeout=60)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(rows)))   # rows that cleared drop out, so a row that sticks again alarms again
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
