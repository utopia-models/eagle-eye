#!/usr/bin/env python3
"""vsl_lastwords.py: the last-words pre-step of the VSL/Upwork queue (Domain 8 item 8, Lanam lesson 2026-11-20).

Package state files drift (`net/work/vsl/<slug>/stage.json` said `recorded:false` after the VSL was sent and the client said
"no spec builds"). Before ANY plan or stage, read the client's own latest words (ledger `client_reply` rows, newest last) and
refuse when they say stop, already sent, or no build. `check()` is what vsl_jobs.stage() calls; it returns (ok, reason).
Never a fill: no words found means nothing to refuse on (the stage.json is then the only state, as before).
"""
import re

LOOKBACK_DAYS = 7
FIELDS = ("text", "body", "message", "quote", "note")
STOP = re.compile(
    r"(no|not|don.?t|do not|never|without)\W+(?:\w+\W+){0,3}?(spec|build|builds|demo)\b"
    r"|already\s+(been\s+)?(sent|received|watched|got|recorded)"
    r"|(vsl|video)\W+(?:\w+\W+){0,3}?already\s+(sent|received)"
    r"|not\s+interested|no\s+longer\s+(need|hiring|looking)|position\s+(is\s+)?filled|please\s+stop|stop\s+(sending|contacting)",
    re.I)


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def last_words(rows, key, client=None, now=None, days=LOOKBACK_DAYS):
    """The client's own client_reply texts for this job key / client, oldest first, within `days`."""
    import datetime as dt
    now = now or dt.datetime.now(dt.timezone.utc)
    keys = {str(key).lstrip("~"), _slug(key), _slug(client)} - {""}
    out = []
    for r in rows:
        if r.get("event") != "client_reply":
            continue
        ids = {_slug(r.get("client")), *re.findall(r"\d{12,}", str(r.get("job") or r.get("key") or ""))}
        if not ids & keys:
            continue
        try:
            t = dt.datetime.strptime(str(r.get("ts", ""))[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
            if (now - t).days > days:
                continue
        except ValueError:
            pass   # a row with no parseable ts is kept: older than we can prove is not a reason to drop the client's words
        txt = next((str(r[f]) for f in FIELDS if r.get(f)), "")
        if txt:
            out.append((str(r.get("ts", "")), txt))
    return [t for _, t in sorted(out)]


def check(rows, key, client=None, now=None):
    """-> (ok, reason). ok False when any of the client's last words in the window say stop / already sent / no build."""
    msgs = last_words(rows, key, client, now)
    for m in reversed(msgs[-3:]):
        hit = STOP.search(m)
        if hit:
            return False, f"last words refuse the plan: client said {m.strip()[:140]!r} (matched {hit.group(0)!r}); stage.json is not the truth, the client is"
    return True, f"{len(msgs)} client message(s) read, none refuse"
