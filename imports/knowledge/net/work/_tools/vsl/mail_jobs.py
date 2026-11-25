#!/usr/bin/env python3
"""mail_jobs.py: Upwork's own job-alert mail as a source of one-shot jobs (Architect 16665, 2026-11-23: the feed lags the mail by 10+ minutes and misses jobs).

The matcher (mail_watch) turns each Upwork "New job alert" mail into a fleetmail line on thread `upwork-package`:
  Job matched [cat] TITLE... | Hourly: $12.00 - $30.00 · Est. time: ... | Payment verified · 4.99 stars · $20K spent · United States | upwork.com/jobs/~ID | mail 37s ago. WRITE THE PACKAGE ...
This module reads those lines (never upwork.com): parse_match turns one into {job, title, pay, client, category, mail_at}; fetch_matches reads the thread.
The mail does NOT carry the post body: the job waits at state `needs_description` until a person reads the post on the desk and the text lands in
hunts/upwork/<slug>/post.md (oneshot_auto.promote_described then queues the build). No script touches upwork.com."""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone

MATCH = re.compile(r"^Job matched \[(?P<cat>[^\]]+)\]\s*(?P<title>.+?)\s*\|\s*(?P<pay>[^|]+?)\s*\|\s*(?P<client>[^|]+?)\s*\|\s*upwork\.com/jobs/(?P<job>~\d+)\s*\|\s*mail (?P<ago>\d+)s ago", re.S)
FLEETMAIL = "/usr/local/bin/fleetmail"


def parse_match(body, sent_at):
    """-> dict or None. mail_at = the time the mail reached us (sent_at minus the 'mail Ns ago' the matcher printed), ISO UTC with Z."""
    m = MATCH.match((body or "").strip())
    if not m:
        return None
    try:
        t = datetime.fromisoformat(sent_at.replace("Z", "+00:00")).astimezone(timezone.utc) - timedelta(seconds=int(m["ago"]))
    except (ValueError, TypeError, AttributeError):
        return None
    title = re.sub(r"\.\.\.$", "", m["title"].strip()).strip()
    return {"job": m["job"], "title": title, "pay": m["pay"].strip(), "client": m["client"].strip(), "category": m["cat"].strip(),
            "mail_at": t.strftime("%Y-%m-%dT%H:%M:%SZ")}


def fetch_matches(thread="upwork-package", runner=None):
    """Every parsed job-match line on the thread, newest first. A failure returns [] (the next tick tries again)."""
    try:
        r = (runner or subprocess.run)([FLEETMAIL, "thread", thread], capture_output=True, text=True, timeout=40)
        msgs = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        import sys
        print(f"mail_jobs.fetch_matches FAILED ({type(e).__name__}: {str(e)[:160]}): no intake this tick", file=sys.stderr)
        return []
    out = [p for p in (parse_match(m.get("body", ""), m.get("sent_at", "")) for m in msgs if m.get("sender") == "upwork") if p]
    return sorted(out, key=lambda p: p["mail_at"], reverse=True)
