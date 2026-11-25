#!/usr/bin/env python3
"""feed.py — Eagle Eye's data.json, measured live from horus's stores on novaserver (knowledge#13151).

Runs AS horus ON novaserver, read-only on every store, stdlib only. Ra's refresh-data.py pipes this file over ssh
(`ssh eagle@novaserver python3 - < feed.py`) every 30 s and writes what it prints to ~/dev/eagle-eye/data.json,
which push-kv.sh puts in the `eagle-eye-data` KV (key `data`) behind https://eagle.utopiamodels.ai/data.json.

Output (one JSON object):
  hunts.<id>   = {sent, answered, window, what, source, status, reason?}  for upwork, cold_apps, linkedin,
                 cold_email, in_person. `sent`/`answered` are null when no store measures them (status "empty",
                 `reason` names the source and what is missing) — never a zero that was not counted.
  roosts.<id>  = {rows: [{name, hunt, stage, contracts, paid}], status, source, reason?}  for clients, network, social.
  clients      = the Upwork-marketplace client table pipeline.js renders ({name, contracts, paid}); paid_total.
  linkedin_sent, cold_email_sent, ... = flat copies of the hunt numbers, the keys pipelines.json flow[] reads.
  proposals_sent … paid_events = the marketplace keys the existing pages read, unchanged in meaning.
  candidate    = whose pipeline a block is (knowledge#13453): every hunt/roost above is Tyler's ("tyler"); the family
                 desks' apply ledgers (`apply.py --candidate <id>`) are `candidates.<id>` = {candidate, sent, sent_total,
                 last_24h, last_7d, status, source}, read from <apply root>/candidates/<id>/applications.db.
  cold_apps_feed = what refresh-data.py writes to cold-apps.json (KV key `cold-apps`): submitted, replies and
                 interviews over ONE base (net-funnel's 28-day window) plus the all-time submitted count.

    python3 feed.py               # print the feed (as horus on novaserver)
    python3 feed.py --self-test   # offline, fixtures in a tmpdir
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys

HOME = os.path.expanduser("~")
STATE = os.environ.get("EAGLE_STATE") or os.path.join(HOME, ".claude/state")
KB = os.environ.get("EAGLE_KB") or os.path.join(HOME, "dev/utopia-models/knowledge")
#: Tyler is the candidate of every hunt and roost; the family desks are listed under `candidates` (knowledge#13453).
TYLER = "tyler"
LINKEDIN = os.environ.get("NET_LINKEDIN_LEDGER") or "/home/sekhmet/.local/state/net-linkedin/ledger.jsonl"
#: the upwork agent's ledger, the ONE Upwork ledger since the 11-15 cutover (knowledge#13798); horus's own copy stopped at
#: 2026-11-15T18:51Z. horus reads it through `setfacl -m u:horus:x /home/upwork` (knowledge#14154; below that dir is o+r).
UPWORK = os.environ.get("EAGLE_UPWORK_LEDGER") or "/home/upwork/.claude/state/net/upwork/ledger.jsonl"
#: rahman's social store (YouTube/X/Instagram/TikTok inbox + channel metrics); horus reads it through an ACL (knowledge#13746)
RAHMAN = os.environ.get("EAGLE_RAHMAN") or "/home/rahman/.claude/state/rahman"
#: Tyler's own accounts: never counted as a person who came in
OWN_HANDLES = {"@tyleryouk1430", "@tyleryouk", "tyler youk", "@ahau", "@reflex", "@utopiamodels"}


def P(*a):
    return os.path.join(*a)


def probe(path):
    """'ok' | 'absent' | 'unreadable' — an unreadable store is never reported as an empty one."""
    try:
        os.stat(path)
        with open(path, "rb"):
            return "ok"
    except FileNotFoundError:
        return "absent"
    except PermissionError:
        return "unreadable"


def jl(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def js(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def mtime(path):
    try:
        return dt.datetime.fromtimestamp(os.stat(path).st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return None


def money(c):
    return f"${c / 100:,.0f}" if c % 100 == 0 else f"${c / 100:,.2f}"


def hunt(sent, answered, window, what, source, at=None, status="live", reason=None, **extra):
    h = {"sent": sent, "answered": answered, "window": window, "what": what, "source": source, "at": at,
         "status": status}
    if reason:
        h["reason"] = reason
    h.update(extra)
    return h


def empty_hunt(source, reason, **extra):
    return hunt(None, None, None, None, source, status="empty", reason=reason, **extra)


# ── hunts ────────────────────────────────────────────────────────────────────────────────────────────────────────
def upwork(ctx):
    path = UPWORK
    st = probe(path)
    if st != "ok":
        return empty_hunt(f"Upwork ledger {UPWORK}", f"ledger {st}")
    rows = list({json.dumps(r, sort_keys=True): r for r in jl(path)}.values())
    ctx["upwork_rows"] = rows
    sent = {(r.get("key") or r.get("job")) for r in rows if r.get("event") == "proposal_sent" and (r.get("key") or r.get("job"))}
    answered = {r.get("job") for r in rows if r.get("event") == "client_reply" and r.get("job") in sent}
    return hunt(len(sent), len(answered), "all time",
                "sent = distinct proposals submitted; answered = those a client wrote back on",
                f"Upwork ledger {UPWORK}", mtime(path),
                last_row=_newest(rows, ctx["now"]), last_action=_newest(rows, ctx["now"], ACTION_EVENTS))


# The rows a person's hand action on the seat writes (proposals.py, ledger.py, call_kit.py), as opposed to the mail
# watcher's triggers and the retired automation's research/scored/error rows. `last_action` is the freshness Eagle Eye
# shows for the Upwork hunt (knowledge#13160): a silent ledger reads as N min ago on the page, never as current.
ACTION_EVENTS = {"proposal_sent", "client_reply", "reply_sent", "vsl_sent", "message_sent", "call_booked", "call_held",
                 "offer", "contract_started", "hired", "milestone_submitted", "milestone_funded", "milestone_paid",
                 "payout", "viewed", "declined", "interview"}


def _row_time(r):
    v = r.get("ts") if r.get("ts") is not None else r.get("at")
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v, dt.timezone.utc)
    if isinstance(v, str):
        try:
            return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except ValueError:
            return None
    return None


def _newest(rows, now, events=None):
    """{ts, event, age_min} of the newest row (by its own time) whose event is in `events` (any, when None); None when
    no row carries a time."""
    best = None
    for r in rows:
        if events is not None and r.get("event") not in events:
            continue
        t = _row_time(r)
        if t and (best is None or t > best[0]):
            best = (t, r)
    if best is None:
        return None
    return {"ts": best[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "event": best[1].get("event"),
            "age_min": max(0, round((now - best[0]).total_seconds() / 60))}


def cold_apps(ctx):
    db = P(STATE, "sf/apply/applications.db")
    nf_path = P(STATE, "sf/funnel/net-funnel.json")
    st = probe(db)
    if st != "ok":
        return empty_hunt("apply store ~horus/.claude/state/sf/apply/applications.db", f"apply store {st}")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ok = "outcome in ('submitted','submitted_unconfirmed')"
    total = c.execute("select count(*) from applications where " + ok).fetchone()[0]
    try:  # recency from the same table; a store without the timestamp columns just omits them
        since = lambda d: c.execute("select count(*) from applications where " + ok  # noqa: E731
                                    + f" and coalesce(submitted_at,started_at)>datetime('now','-{d} day')").fetchone()[0]
        ctx["cold_recent"] = {"last_24h": since(1), "last_7d": since(7)}
    except sqlite3.Error:
        ctx["cold_recent"] = {}
    c.close()
    w = (((js(nf_path) or {}).get("jobFunnel") or {}).get("window")) or {}
    days = (((js(nf_path) or {}).get("jobFunnel") or {}).get("windowDays")) or 28
    if not isinstance(w.get("applied"), int) or not isinstance(w.get("replied"), int):
        return hunt(None, None, None, None, "net-funnel jobFunnel (~horus/.claude/state/sf/funnel/net-funnel.json)",
                    status="empty", reason="net-funnel has no jobFunnel window: sent and answered need the same base",
                    sent_total=total)
    ctx["cold_window"] = {"days": days, "interviews": (w.get("screened") or 0) + (w.get("interviewed") or 0)}
    return hunt(w["applied"], w["replied"], f"last {days} days",
                "sent = applications submitted; answered = a person or ATS answered (rejections included)",
                "net-funnel jobFunnel over applications.db + dev@ inbox", (js(nf_path) or {}).get("computedAt"),
                sent_total=total, sent_total_what="applications submitted, all time (applications.db)")


def linkedin(ctx):
    """The LinkedIn worker's lane ledger, plus the hand-sent log in net/work/outreach/linkedin-log.csv."""
    st = probe(LINKEDIN)
    log = P(KB, "net/work/outreach/linkedin-log.csv")
    rows = []
    if probe(log) == "ok":
        with open(log, newline="") as f:
            rows = [r for r in csv.DictReader(f)]
    ctx["linkedin_log"] = rows
    led = jl(LINKEDIN) if st == "ok" else []
    if st != "ok" and not rows:
        return empty_hunt(f"LinkedIn lane ledger {LINKEDIN}",
                          f"lane ledger {st} from horus; the LinkedIn worker has not written a row it can read")
    sent_log = sum(1 for r in rows if (r.get("status") or "").strip() in ("sent", "accepted", "replied"))
    ans_log = sum(1 for r in rows if (r.get("status") or "").strip() in ("accepted", "replied"))
    sent_led = len({json.dumps(r, sort_keys=True) for r in led if r.get("stage") == "invite_sent"})
    ans_led = len({r.get("recruiter") or r.get("thread") for r in led if r.get("stage") == "replied"})
    src = "net/work/outreach/linkedin-log.csv (hand-sent)" + (f" + lane ledger {LINKEDIN}" if st == "ok" else "")
    reason = None if st == "ok" else f"the lane ledger {LINKEDIN} is {st} from horus, so only the hand-sent log counts"
    return hunt(sent_log + sent_led, ans_log + ans_led, "all time",
                "sent = connection requests / messages sent; answered = accepted or replied",
                src, mtime(log), status="live" if st == "ok" else "partial", reason=reason)


def cold_email(ctx):
    """dev@ openers (horus's outreach store) + the cold-domain sequence and audience ledgers in the knowledge clone.
    SalesBlaster has no API: its sends land only through audience_c.py's ledger, counted when it exists."""
    em_path, rp_path = P(STATE, "sf/outreach/emails.jsonl"), P(STATE, "sf/outreach/replies.jsonl")
    emails, replies = jl(em_path), jl(rp_path)
    sent_threads = {r.get("gmail_thread_id") for r in emails
                    if r.get("direction") == "out" and r.get("status") == "sent" and r.get("kind") == "opener"
                    and r.get("gmail_thread_id")}
    ctx["cold_email_companies"] = {(r.get("company") or "").lower() for r in emails
                                   if r.get("direction") == "out" and r.get("status") == "sent"}
    ans_threads = {r.get("gmail_thread_id") for r in replies if r.get("gmail_thread_id") in sent_threads}
    led_sent, led_ans, ledgers = 0, 0, []
    for path in sorted(glob.glob(P(KB, "net/work/outreach/campaigns/*.jsonl"))) + \
            [p for p in (P(KB, "net/work/outreach/audience-b.jsonl"), P(KB, "net/work/outreach/audience-c.jsonl"))
             if os.path.exists(p)]:
        rows = jl(path)
        ledgers.append(os.path.relpath(path, KB))
        led_sent += sum(1 for r in rows if r.get("kind") == "send" and str(r.get("touch", "1")) in ("1", "None")
                        and not r.get("dry"))
        led_ans += len({r.get("gmail_thread_id") or r.get("email") for r in rows if r.get("kind") == "reply"})
    if probe(em_path) != "ok" and not ledgers:
        return empty_hunt("outreach store ~horus/.claude/state/sf/outreach/emails.jsonl", f"store {probe(em_path)}")
    return hunt(len(sent_threads) + led_sent, len(ans_threads) + led_ans, "all time",
                "sent = first-touch emails sent (one per thread); answered = threads a person replied in",
                "outreach store emails.jsonl + replies.jsonl; ledgers " + ", ".join(ledgers)
                + ("; SalesBlaster (no API) not recorded yet: audience-c.jsonl absent"
                   if not os.path.exists(P(KB, "net/work/outreach/audience-c.jsonl")) else ""),
                mtime(em_path))


def in_person(ctx):
    path = P(STATE, "sf/events.jsonl")
    ev = jl(path)
    attended = [r for r in ev if (r.get("status") or "") in ("attended", "went")]
    if not attended and ev:   # knowledge#13746: live = events found + events in the coming 7 days, until attendance is recorded
        today = ctx["now"].date()
        week = sum(1 for r in ev if (d := _t(r.get("date"))) and today <= d.date() <= today + dt.timedelta(days=7))
        return hunt(len(ev), week, "all time found · next 7 days",
                    "found = events found by the watchers; this week = found events dated in the next 7 days",
                    "events store ~horus/.claude/state/sf/events.jsonl", mtime(path), found=len(ev),
                    labels=["found", "this week"])
    if not attended:
        return empty_hunt("events store ~horus/.claude/state/sf/events.jsonl",
                          f"{len(ev)} events found, attendance not recorded (every row is status "
                          f"{'/'.join(sorted({r.get('status') or '?' for r in ev})) or 'none'}): nothing sent, nothing answered",
                          found=len(ev))
    return hunt(len(attended), None, "all time", "sent = events attended; answered is not recorded",
                "events store ~horus/.claude/state/sf/events.jsonl", mtime(path), found=len(ev))


HUNTS = {"upwork": upwork, "cold_apps": cold_apps, "linkedin": linkedin, "cold_email": cold_email, "in_person": in_person}


# ── roosts ───────────────────────────────────────────────────────────────────────────────────────────────────────
HUNT_OF_SOURCE = {"upwork": "upwork", "consulting": "personal_network", "direct": "personal_network"}


def clients_roost(ctx):
    path = P(KB, "_infra/occ-feeds/clients.json")
    feed = js(path)
    if not feed:
        return {"rows": [], "status": "empty", "source": "clients feed _infra/occ-feeds/clients.json",
                "reason": f"clients feed {probe(path)} or unparseable"}
    rows = []
    for c in feed.get("clients") or []:
        m = c.get("money") or {}
        paid = int(m.get("paidCents") or 0)
        pend = int(m.get("pendingCents") or 0) + int(m.get("fundedCents") or 0)
        rows.append({"name": c.get("name") or c.get("slug"), "hunt": HUNT_OF_SOURCE.get(c.get("source"), c.get("source")),
                     "stage": c.get("kind") or "client", "what": c.get("what"),
                     "contracts": 1 if c.get("kind") == "contract" else 0,
                     "paid": money(paid) + (f" · {money(pend)} pending/funded" if pend else ""),
                     "paid_cents": paid, "pending_cents": pend})
    for p in feed.get("prospects") or []:
        rows.append({"name": p.get("name"), "hunt": None, "stage": "prospect: " + (p.get("status") or "")[:80],
                     "what": p.get("what"), "contracts": 0, "paid": money(0), "paid_cents": 0, "pending_cents": 0})
    ctx["clients_feed"] = feed
    return {"rows": rows, "status": "live", "source": "clients feed _infra/occ-feeds/clients.json (CRM Deals)",
            "at": feed.get("computedAt")}


ACTIVE = {"interview": 0, "screen": 1, "assessment": 2, "offer": -1}


#: knowledge#14132: the network roster, everyone Tyler knows (tyler@ contacts + WhatsApp chats + LinkedIn), one row per person
#: with their channels. Built by net/work/_tools/outreach/roster.py (horus's network-roster.timer); PII, off git.
ROSTER = "sf/network/roster.json"
#: Tyler 2026-11-19: atlas owns the roster now; the feed reads ITS file (NET_NETWORK_STATE, the same dir env roster.py reads,
#: overrides). horus's own network-roster.timer is retired.
def roster_path():
    return os.path.join(os.environ.get("NET_NETWORK_STATE") or "/home/atlas/.claude/state/sf/network", "roster.json")


def roster_roost(ctx):
    """The roost once the roster exists: each person once, with every channel. Recruiters and hiring teams are companies,
    not Tyler's network (eagle-eye-hunts-audit 2026-11-15, Network Q1): they stay on the cold apps / cold email lanes."""
    path = roster_path()
    doc = js(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("people_rows"), list):
        return None
    seen = {}
    for p in doc["people_rows"]:
        seen[(p.get("name") or "").lower()] = seen.get((p.get("name") or "").lower(), 0) + 1

    def label(p):   # two people his phone calls "Mike" are two rows: the number's last 4 tell them apart
        n, ph = p.get("name"), re.sub(r"\D", "", ((p.get("phones") or [""])[0]).split("@")[0].split(":")[0])
        return f"{n} (…{ph[-4:]})" if seen.get((n or "").lower(), 0) > 1 and ph else n
    rows = [{"name": label(p), "hunt": "personal_network", "stage": " · ".join(p.get("channels") or []) or "no channel",
             "channels": p.get("channels") or [], "referral_ok": bool(p.get("referral_ok")),
             "contracts": 0, "paid": money(0), "kind": "network roster",
             "what": " · ".join(x for x in (p.get("title"), p.get("company")) if x) or None, "at": p.get("wa_last")}
            for p in doc["people_rows"] if p.get("name")]
    src = doc.get("sources") or {}
    gaps = [f"{k}: {v.get('reason') or v.get('status')}" for k, v in src.items() if k != "linkedin" and isinstance(v, dict) and v.get("status") != "live"]
    li = (src.get("linkedin") or {}).get("connections") or {}
    if li.get("status") and li.get("status") != "live":
        gaps.append("linkedin connections: " + (li.get("reason") or li["status"]))
    out = {"rows": rows, "status": "live" if not gaps else "partial", "at": doc.get("built_at"), "people": len(rows),
           "in_contacts": doc.get("in_contacts"),
           "channels": doc.get("channels"), "roster_sources": src,
           "source": f"network roster {ROSTER} (roster.py: tyler@ contacts + WhatsApp chats + LinkedIn, each person once)"}
    if gaps:
        out["reason"] = "; ".join(gaps)
    last = max((r for r in rows if r["at"]), key=lambda r: r["at"], default=None)
    if last:
        out["latest"] = {"ts": last["at"], "co": (last["name"] or "")[:60], "kind": "whatsapp", "what": "last 1:1 message"}
    if not rows:
        out.update(status="empty", reason="the roster holds no one: " + (out.get("reason") or "every source empty"))
    return out


def network_roost(ctx):
    r = roster_roost(ctx)
    if r is not None:
        return r
    rows = []
    pl = P(STATE, "sf/outreach/pipeline.jsonl")
    sent_cos = ctx.get("cold_email_companies") or set()
    for r in jl(pl):
        co = r.get("company") or r.get("key")
        hunt_id = "cold_email" if (r.get("key") or "").lower() in sent_cos or (co or "").lower() in sent_cos else "cold_apps"
        rows.append({"name": co, "hunt": hunt_id, "stage": r.get("stage"), "contracts": 0, "paid": money(0),
                     "kind": "recruiter / hiring team", "next": r.get("next_step") or None, "at": r.get("stage_at")})
    for r in ctx.get("linkedin_log") or []:
        if not (r.get("name") or "").strip():
            continue
        rows.append({"name": f"{r['name'].strip()} ({(r.get('company') or '').strip()})", "hunt": "linkedin",
                     "stage": f"{(r.get('channel') or '').strip()} {(r.get('status') or '').strip()}".strip(),
                     "contracts": 0, "paid": money(0), "kind": "LinkedIn contact", "at": r.get("date")})
    for path in sorted(glob.glob(P(KB, "net/work/outreach/personal-network/*.md"))):
        try:
            text = open(path).read()
        except OSError:
            continue
        head = re.search(r"^#\s+(.+?)(?:\s+—|$)", text, re.M)
        met = re.search(r"\*\*How met:\*\*\s*([^\n]+)", text)
        stg = re.search(r"\*\*Stage:\*\*\s*([^\n·]+)", text)
        rows.append({"name": head.group(1).strip() if head else os.path.basename(path)[:-3],
                     "hunt": "in_person" if met and "in-person" in met.group(1) else "personal_network",
                     "stage": stg.group(1).strip() if stg else "personal contact", "contracts": 0, "paid": money(0),
                     "kind": "personal network"})
    rows.sort(key=lambda r: (ACTIVE.get(r["stage"], 9), r["name"] or ""))
    if not rows:
        return {"rows": [], "status": "empty", "source": "pipeline.jsonl + linkedin-log.csv + personal-network/",
                "reason": "no network or recruiter rows in any source"}
    return {"rows": rows, "status": "live", "at": mtime(pl),
            "source": "horus's pipeline store sf/outreach/pipeline.jsonl (recruiters, hiring teams), "
                      "net/work/outreach/linkedin-log.csv, net/work/outreach/personal-network/"}


def _social_people():
    """rahman's inbox: one row per person who wrote in (DM, comment, live chat), newest first; Tyler's own handles out."""
    people = {}
    for r in jl(P(RAHMAN, "inbox.jsonl")):
        who = (r.get("author") or r.get("name") or "").strip()
        if not who or who.lower() in OWN_HANDLES or r.get("status") == "ignored":
            continue
        t = r.get("seen_at")
        at = dt.datetime.fromtimestamp(t, dt.timezone.utc) if isinstance(t, (int, float)) else None
        k = (r.get("platform"), who.lower())
        cur = people.get(k)
        if not cur or (at and (cur["_t"] is None or at > cur["_t"])):
            people[k] = {"name": who[:60], "hunt": "social", "stage": f"{r.get('platform') or ''} {r.get('kind') or ''}".strip(),
                         "contracts": 0, "paid": money(0), "kind": r.get("platform"), "what": (r.get("text") or "")[:100],
                         "at": _iso(at) if at else None, "_t": at}
    rows = sorted(people.values(), key=lambda x: x["_t"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
    for x in rows:
        x.pop("_t")
    return rows


def social_roost(ctx):
    rows = _social_people() if probe(P(RAHMAN, "inbox.jsonl")) == "ok" else []
    st = js(P(RAHMAN, "state.json")) or {}
    yt = st.get("yt_metrics") or {}
    ctx["social_rows"] = rows
    if rows:
        return {"rows": rows, "status": "live", "at": mtime(P(RAHMAN, "inbox.jsonl")),
                "source": "rahman's inbox ~rahman/.claude/state/rahman/inbox.jsonl (YouTube, X, Instagram, TikTok) + state.json yt_metrics",
                "youtube": {k: yt.get(k) for k in ("subscribers", "views", "videos", "at")} if yt else None}
    return {"rows": [], "status": "empty",
            "source": "rahman's YouTube/X stores (~rahman/.claude/state/rahman: inbox.jsonl, yt-comments.jsonl)",
            "reason": "no feed of people who came in from YouTube or X yet: rahman records posts and comments, "
                      "not who became a contact"}


#: knowledge#13870: the inbox router's public feed (atlas writes it every tick from its state: the lane/<agent> claims and
#: the replies the gateway sent). World-readable on purpose: this feed runs as horus. Absent = not tracked, never zero.
INBOX_FEED = os.environ.get("EAGLE_INBOX_FEED") or "/var/tmp/inbox-router/inbox.json"


def inbox_roost(ctx):
    """One row per human thread in the last 24 h across Tyler's two inboxes: who wrote, which lane agent owns it, answered
    or waiting, and how fast. The block's own numbers: in, answered, waiting, open, median first-reply minutes, per agent."""
    d = js(INBOX_FEED)
    if not isinstance(d, dict) or not isinstance(d.get("mailboxes"), dict):
        return {"rows": [], "status": "empty", "source": f"inbox router feed {INBOX_FEED}",
                "reason": f"inbox feed {probe(INBOX_FEED)} or unparseable: the router has not published yet"}
    rows, tot = [], {"in": 0, "answered": 0, "waiting": 0, "open": 0, "by_agent": {}}
    med = []
    for mbx, blk in d["mailboxes"].items():
        for k in ("in", "answered", "waiting", "open"):
            tot[k] += int(blk.get(k) or 0)
        for a, n in (blk.get("by_agent") or {}).items():
            tot["by_agent"][a] = tot["by_agent"].get(a, 0) + int(n or 0)
        if blk.get("median_first_reply_min") is not None:
            med.append(float(blk["median_first_reply_min"]))
        for r in blk.get("rows") or []:
            st = r.get("state") or ""
            stage = {"answered": "replied", "waiting": "waiting for 8 AM MT", "pending": "replying", "failed": "FAILED",
                     "capped": "daily cap", "claim-failed": "claim failed", "answered-elsewhere": "answered by Tyler"}.get(st, st)
            rows.append({"name": f"{r.get('from') or '?'}: {r.get('subject') or ''}"[:90], "hunt": "inbox",
                         "stage": stage + (f" in {r['latency_min']} min" if r.get("latency_min") is not None and st == "answered" else ""),
                         "contracts": 0, "paid": money(0), "kind": f"{mbx.split('@')[0]}@ -> {r.get('agent') or '?'} ({r.get('class') or '?'})",
                         "at": (dt.datetime.fromtimestamp(r["received_at"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                if r.get("received_at") else None), "late": st in ("pending", "failed", "claim-failed", "capped")})
    rows.sort(key=lambda r: (not r["late"], r.get("at") or ""), reverse=False)
    lv = d.get("liveness") or {}
    return {"rows": rows[:60], "status": "live" if rows else "empty", "at": d.get("at"),
            "source": f"the inbox router's feed {INBOX_FEED} (lane/<agent> labels + the gateway's sends, knowledge#13870)",
            "in_24h": tot["in"], "answered": tot["answered"], "waiting": tot["waiting"], "open": tot["open"],
            "by_agent": tot["by_agent"], "median_first_reply_min": (sum(med) / len(med)) if med else None,
            "oldest_unanswered_s": lv.get("oldest_unanswered_human_age_s"), "business_hours": lv.get("business_hours"),
            **({} if rows else {"reason": "no human thread in the last 24 h"})}


ROOSTS = {"clients": clients_roost, "network": network_roost, "social": social_roost, "inbox": inbox_roost}


SENT_SQL = "outcome in ('submitted','submitted_unconfirmed')"
CANDIDATE_SENT_SQL = ("select count(distinct coalesce(nullif(posting_url, ''), posting_id)) from applications "
                      "where outcome = 'submitted'")


# ── lane pages (knowledge#13617): /hunt/<id> and /roost/<id> read `lanes_feed` (KV `lanes`, /lanes.json) ────────────
# Per lane: every dated row of the last 7 days (the page shows the last 24 h and counts the 7), and the companies the
# lane touched, each joined across EVERY store (applications, emails, replies, VSLs, pipeline stage) and tagged with its
# target tier from the newest net/work/dream-list/dream-list-*.json. Nothing is estimated: a lane with no dated rows
# says which store it read.
EVENT_DAYS = 7
REPLY_STAGES = {"rejection", "screen", "assessment", "interview", "offer", "reply", "replied"}


_LEGAL = (r"(?:,?\s+(?:incorporated|inc|llc|l\.l\.c|ltd|limited|private limited|pvt|corp|corporation|co|company|"
          r"gmbh|plc|s\.?a|ag|bv|pty|lp|llp)\.?)+$")
_SUBJECT = re.compile(r"(?i)^(?:re:|fwd?:)|\b(?:your application|thank(?:s| you)|application (?:received|for|to)|"
                      r"interview|update on|regarding|we received|next steps|unfortunately)\b")
_INTEREST = re.compile(r"(?i)(?:interest in|applying (?:to|at|for a role at)|application (?:to|at|with)|joining|"
                       r"opportunit(?:y|ies) (?:at|with))\s+(?:the\s+)?([A-Z][\w&.' -]{1,60}?)[.!]?$")
_ALIAS_TAIL = ("technologies", "technology", "labs", "hq", "ai", "io", "inc", "app", "software", "systems", "group")


def _drop_org_code(s):
    """A Workday org-code prefix ("EPIC Epicor Software", "RPMS RoundPoint Mortgage Servicing") comes off; a real
    acronym that IS the name stays ("RVO Health", "IXL Learning", "GE Aviation", "CDW"). The leading all-caps token
    (3+ letters) is a code when it spells, in order, letters of the words after it starting at a word that begins with
    its own first letter: the capitals ("RPMS" = RoundPoint Mortgage Servicing, "GSS"), a word ("EPIC" in Epicor,
    "SAMC" in SitusAMC) or a run across words ("CHN" = Choice Hotels iNternational, "DIGITL" = Digital)
    (knowledge#13617, fleetmail #5011)."""
    parts = s.split(" ", 1)
    if len(parts) < 2 or not re.fullmatch(r"[A-Z]{3,8}", parts[0]):
        return s
    tok, rest = parts[0].lower(), parts[1]
    words = rest.split()
    for i, w in enumerate(words):
        if not w[:1].lower() == tok[0]:
            continue
        hay, k = "".join(words[i:]).lower(), 0
        for ch in hay:
            if k < len(tok) and ch == tok[k]:
                k += 1
        if k == len(tok):
            return rest
    return s


def _clean(name, loose=False, strip_code=True):
    """The company a raw store string names, readable, or None when the string is not a company (an email subject).
    Strips a leading ATS numeric code ("00100 LEIDOS, INC." → "LEIDOS"), legal suffixes and a trailing
    parenthetical ("F5, Inc. (United States)" → "F5"), and pulls the company out of a subject that names one
    ("Thank You for Your Interest in SkyePoint Decisions" → "SkyePoint Decisions")."""
    s = re.sub(r"\s+", " ", (name or "").strip().strip("\"'"))
    if not s:
        return None
    if loose:   # an Upwork client or job title is a name as written, never an ATS string or a mail subject
        return s
    if _SUBJECT.search(s):
        m = _INTEREST.search(s)
        if not m:
            return None
        s = m.group(1).strip()
    if s.islower() and " " not in s and "-" in s:                    # a slug: "instrumental-inc-" is two words
        s = re.sub(r"-+", " ", s).strip()
    s = re.sub(r"^[A-Z]_\d+\s+", "", s)                               # "C_087 "
    if re.search(r"_\d|\d_", s):                                    # "United States_641_Semi-Mo/Bi-Wk_USD": a pay code
        return None
    s = s.replace("_", " ")
    m = re.match(r"^(\S+?)(?:\s+|-(?=[A-Z]))(?=[A-Z])", s)            # an ATS entity code: "00100 ", "6090-", "1US0 ", "5PY "
    if strip_code and m and re.search(r"\d", m.group(1)) and (re.fullmatch(r"[\d-]+", m.group(1))
                                                             or len(re.findall(r"\d", m.group(1))) >= 2
                                                             or re.fullmatch(r"[0-9A-Z]{3,5}", m.group(1))):
        s = s[m.end():]
    if strip_code:
        s = _drop_org_code(s)
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s)                         # "(United States)", "(Employer-Payroll)"
    s = re.sub(r"[-–]\s*federal$", "", s, flags=re.I).strip(" ,.-")
    s = re.sub(r"(?i)[\s,–-]+(?:careers?(?: page| site)?|jobs(?: page)?)$", "", s).strip(" ,.-") or s
    before = s
    for _ in range(3):
        s = re.sub(_LEGAL, "", s, flags=re.I).strip(" ,.-&")
        s = re.sub(r"(?i)\s+(?:legal entity|ltda|limitada|sp\.?\s?z\.?\s?o\.?\s?o|n\.a|b\.v|"
                   r"usa?|u\.s\.?a?|united states|uk|s\.?l\.?u|s\.?r\.?l|canada|india|brasil|brazil|taiwan|hungary|germany|south africa|north america|"
                   r"taiwan branch|shared services|global business services|poland|australia|spain|portugal|france|italy|"
                   r"netherlands|ireland|sweden|israel|egypt|singapore|japan|korea|mexico|argentina|colombia|"
                   r"philippines|romania|bulgaria|deutschland|bengaluru|bangalore|hyderabad|pune|chennai|mumbai|"
                   r"london|dublin|toronto|cairo|dubai)\.?$", "", s).strip(" ,.-&")
    if len(s) < 2:
        s = before if len(before) >= 2 else (_clean(name, False, False) if strip_code else None)
        if not s:
            return None
    if len(s) < 2 or len(s.split()) > 6:
        return None
    if s.islower() or s.isupper():                                  # "capitalone", "LEIDOS": readable case
        s = s if (s.isupper() and " " not in s and len(s) <= 5) else " ".join(w.upper() if w.lower() in ("ai", "io", "hq") or (len(w) <= 3 and s.isupper()) else w.capitalize() for w in re.split(r"[-_ ]+", s) if w) \
            if not re.search(r"\.[a-z]{2,3}$", s) else s
    return s


# One canonical company key (knowledge#13617 round 4): rules, never per-company swaps. Words come off the END of a
# name while more than one is left — a legal form, a region (country / city / "united states"), a division or careers
# word — then the words are joined with no spaces or punctuation and a glued alias tail ("beaconai", "claylabs") is cut.
_TAIL_LEGAL = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "gmbh", "plc",
               "sa", "sas", "slu", "sl", "srl", "ag", "bv", "nv", "pty", "lp", "llp", "pvt", "private", "pbc", "holdings",
               "ltda", "limitada", "spzoo", "kk", "oy", "ab", "as", "aps", "com"}
_TAIL_REGION = {"us", "usa", "u", "s", "a", "uk", "united", "states", "kingdom", "america", "americas", "north", "south",
                "emea", "apac", "latam", "mena", "europe", "asia", "global", "worldwide",
                "canada", "india", "brasil", "brazil", "mexico", "argentina", "colombia", "chile", "poland", "spain",
                "portugal", "france", "germany", "deutschland", "italy", "netherlands", "belgium", "ireland", "sweden",
                "norway", "denmark", "finland", "switzerland", "austria", "hungary", "romania", "bulgaria", "czech",
                "ukraine", "israel", "egypt", "uae", "saudi", "arabia", "qatar", "turkey", "africa", "nigeria", "kenya",
                "australia", "zealand", "new", "japan", "korea", "china", "taiwan", "singapore", "malaysia", "philippines",
                "vietnam", "indonesia", "thailand", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai",
                "delhi", "noida", "gurgaon", "gurugram", "london", "dublin", "toronto", "vancouver", "montreal", "paris",
                "berlin", "munich", "warsaw", "krakow", "amsterdam", "madrid", "barcelona", "lisbon", "cairo", "dubai",
                "riyadh", "tokyo", "seoul", "sydney", "melbourne", "branch"}
_TAIL_DIVISION = {"graphics", "computing", "dev", "development", "personnel", "people", "operations", "operating",
                  "shared", "services", "solutions", "digital", "careers", "career", "page", "site", "jobs", "group",
                  "technologies", "technology", "labs", "lab", "hq", "ai", "io", "app", "software", "systems",
                  "consulting", "public", "sector", "federal"}
_TAIL_WORDS = _TAIL_LEGAL | _TAIL_REGION | _TAIL_DIVISION
_GLUED_TAIL = ("technologies", "labs", "inc", "llc", "hq", "ai")   # never "io": Syndio is not Synd
_PARENT = {"nytimes": "newyorktimes", "bah": "boozallenhamilton", "seqholdings": "sequence",  # a short form or ticker
           "jpmc": "jpmorganchase"}


def _norm(name, loose=False):
    """The join key: one company, one key. Case and accents folded, punctuation and spaces gone, and — for an ATS or
    mail company, not an Upwork client written by hand — legal forms, regions, division and careers words cut off
    the end, so "NVIDIA Graphics Bengaluru", "Nvidia Poland" and "Nvidia" are one key, as are "Beacon AI"/"Beaconai",
    "Clay Labs"/"Claylabs", "ATOMS Careers page"/"ATOMS", "Instrumental Inc"/"Instrumental", "rune"/"Rune
    Technologies" and "The Voleon Group"/"Voleon"."""
    import unicodedata  # noqa: PLC0415
    c = _clean(name, loose)
    if not c:
        return ""
    s = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\.(?:ai|io|com|co)$", "", s.replace("'s ", " "))
    s = re.sub(r"\b([a-z](?:\.[a-z])+)\.?(?![a-z])", lambda m: m.group(1).replace(".", ""), s)   # "s.l.u" -> "slu"
    words = re.sub(r"[^a-z0-9 ]", " ", s).split()
    if loose:   # a hand-written client or job title: only the alias tail comes off
        while len(words) > 1 and words[-1] in _ALIAS_TAIL:
            words.pop()
        return "".join(words)
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    while len(words) > 1 and words[-1] in _TAIL_WORDS:
        words.pop()
    s = "".join(words)
    for suf in _GLUED_TAIL:
        if s.endswith(suf) and len(s) >= len(suf) + 3:
            s = s[: -len(suf)]
            break
    return _PARENT.get(s, s)


def _better(a, b):
    """The more readable of two names for one company: mixed case and spaces beat a slug."""
    score = lambda n: (n != n.lower() and n != n.upper(), " " in n, -abs(len(n) - 14))  # noqa: E731
    return b if score(b) > score(a) else a


def _display(spell):
    """The name a company shows: its most common clean spelling across every store row; ties to the readable one."""
    flat = lambda n: re.sub(r"[^a-z0-9]", "", n.lower())  # noqa: E731
    spaced = {flat(n): n for n in spell if " " in n}
    folded = {}
    for n, k in spell.items():   # "Claylabs" is the slug of "Clay Labs": its sightings count for the spaced name
        m = n if " " in n else spaced.get(flat(n), n)
        folded[m] = folded.get(m, 0) + k
    words = lambda n: [w for w in re.sub(r"[^a-z0-9 ]", " ", n.lower()).split() if w != "the"]  # noqa: E731
    for n in sorted(folded, key=lambda n: -len(words(n))):   # "Fiserv Solutions" is "Fiserv" plus a tail: it counts
        wn = words(n)                                         # for the parent's spelling, never the other way round
        parent = next((m for m in folded if m != n and 0 < len(words(m)) < len(wn) and wn[:len(words(m))] == words(m)), None)
        if parent and set(wn[len(words(parent)):]) <= _TAIL_WORDS:
            k = folded.pop(n) + folded.pop(parent)
            pre = " ".join(n.split()[: len(parent.split())])   # "EverCommerce Solutions" keeps its inner capital
            if pre.lower() == parent.lower() and not pre.isupper() and sum(map(str.isupper, pre)) > sum(map(str.isupper, parent)):
                parent = pre
            folded[parent] = folded.get(parent, 0) + k
    spell, best = folded, None
    for n, k in spell.items():
        if best is None or k > spell[best] or (k == spell[best] and _better(best, n) == n):
            best = n
    return best or ""


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def _t(v):
    if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"\d{9,11}(\.\d+)?", v or "")):
        return dt.datetime.fromtimestamp(float(v), dt.timezone.utc)
    if isinstance(v, str) and v:
        v = v.strip().replace(" ", "T")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            v += "T12:00:00"
        try:
            t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
        except ValueError:
            return None
    return None


def dream_tiers():
    """{norm: {name, tier, why}} from the newest dream list; {} when none is readable."""
    files = sorted(glob.glob(P(KB, "net/work/dream-list/dream-list-*.json")))
    out = {}
    for c in (js(files[-1]) or []) if files else []:
        if isinstance(c, dict) and c.get("company") and c.get("tier") is not None:
            out[_norm(c["company"])] = {"name": c["company"], "tier": c["tier"], "why": (c.get("why_him") or "")[:160]}
    return out, (os.path.relpath(files[-1], KB) if files else None)


def upwork_once(rows):
    """The Upwork ledger without its doubles. A client message is logged up to three ways: the room watcher's verbatim
    row (`via`), a hand summary written a minute later, and Upwork's "X sent you a message" notification mail. One
    message is one row: an identical client+event+text row is dropped, a client_reply within 3 min of another
    client_reply from the same client is the same message (the verbatim row wins), and a bare notification within
    90 min of a real message from that client is that message's notice."""
    NOTICE = re.compile(r"(?i)sent you a message\s*·\s*view your message")
    out, last_text = [], {}
    msgs = sorted(((_row_time(r), r) for r in rows if r.get("event") == "client_reply" and _row_time(r)
                   and not NOTICE.search(r.get("preview") or "")), key=lambda x: x[0])
    by_client = {}
    for t, r in msgs:
        by_client.setdefault(_norm((r.get("client") or "").split(" ")[0], True), []).append(t)
    kept_reply = {}
    for r in sorted(rows, key=lambda r: _row_time(r) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)):
        e, t = r.get("event"), _row_time(r)
        cl = _norm((r.get("client") or "").split(" ")[0], True)
        text = re.sub(r"\s+", " ", (r.get("preview") or r.get("what") or r.get("note") or r.get("text") or "")).strip()
        if text and last_text.get((cl, e, text)):
            continue
        last_text[(cl, e, text)] = 1
        if e == "client_reply" and t and cl:
            if NOTICE.search(text):
                if any(abs((m - t).total_seconds()) <= 5400 for m in by_client.get(cl, [])):
                    continue
            else:
                prev = kept_reply.get(cl)
                if prev and (t - prev[0]).total_seconds() <= 180:
                    if r.get("via") and not prev[1].get("via"):   # the verbatim row replaces the summary
                        out[out.index(prev[1])] = r
                        kept_reply[cl] = (t, r)
                    continue
                kept_reply[cl] = (t, r)
        out.append(r)
    return out


def lanes_detail(ctx):
    now = ctx["now"]
    cut = now - dt.timedelta(days=EVENT_DAYS)
    tiers, tier_src = dream_tiers()
    cos = {}

    def co(name, loose=False):
        k = _norm(name, loose)
        if not k:
            return None
        if k not in cos:
            cos[k] = {"name": None, "spell": {}, "key": k, "apps": 0, "emails": 0, "replies": 0, "vsls": 0,
                      "proposals": 0, "stage": None, "last": None, "lanes": set()}
            if k in tiers:   # the dream list's spelling counts as one sighting, cleaned like any store's
                t = _clean(tiers[k]["name"]) or tiers[k]["name"]
                cos[k]["spell"][t] = 1
        n = _clean(name, loose)
        if n:
            cos[k]["spell"][n] = cos[k]["spell"].get(n, 0) + 1
        return cos[k]

    def touch(c, lane, t):
        if c is None:
            return
        c["lanes"].add(lane)
        if t and t <= now and (c["last"] is None or t > c["last"]):
            c["last"] = t

    lanes = {k: {"events": [], "source": ""} for k in ("upwork", "cold_apps", "linkedin", "cold_email", "in_person",
                                                        "clients", "network", "social")}

    newest = {}

    def ev(lane, t, name, kind, what="", loose=False):
        if t and t <= now and (lane not in newest or t > newest[lane][0]):   # knowledge#13746: the lane's latest activity
            newest[lane] = (t, _clean(name, loose) or "", kind, (what or "")[:120])
        if t and t >= cut:   # a future row (a booked interview) is kept and flagged `up`, the page lists it as next
            # `co` is the company's join key here; it becomes the merged company's display name at the end
            e = {"ts": _iso(t), "co": _norm(name, loose) or "", "raw": _clean(name, loose) or "", "kind": kind, "what": (what or "")[:120]}
            if t > now:
                e["up"] = 1
            lanes[lane]["events"].append(e)

    # applications (cold apps): one row per submitted application, company + role
    db = P(STATE, "sf/apply/applications.db")
    if probe(db) == "ok":
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            for name, role, ts in c.execute("select company, role, coalesce(submitted_at,started_at) from applications where "
                                            + SENT_SQL):
                t = _t(ts)
                x = co(name)
                if x:
                    x["apps"] += 1
                touch(x, "cold_apps", t)
                ev("cold_apps", t, name, "application", role)
        except sqlite3.Error:
            pass
        c.close()
    lanes["cold_apps"]["source"] = "applications.db (submitted) + pipeline.jsonl (replies, interviews)"
    # cold email: sent touches and replies
    seen = set()   # one message reaches several of Tyler's inboxes (dev@, main@): count it once, by Gmail message id

    def once(r):
        mid = r.get("gmail_message_id") or r.get("message_id")
        if not mid:
            return True
        if mid in seen:
            return False
        seen.add(mid)
        return True
    for r in jl(P(STATE, "sf/outreach/emails.jsonl")):
        if r.get("direction") != "out" or r.get("status") != "sent" or not once(r):
            continue
        t = _t(r.get("sent_at") or r.get("ts"))
        x = co(r.get("company"))
        if x:
            x["emails"] += 1
        touch(x, "cold_email", t)
        ev("cold_email", t, r.get("company"), "email " + (r.get("kind") or ""), (r.get("tier") or "") + (" · " + r["subject"] if r.get("subject") else ""))
    for r in jl(P(STATE, "sf/outreach/replies.jsonl")):
        if not once(r):
            continue
        t = _t(r.get("ts"))
        x = co(r.get("company"))
        if x:
            x["replies"] += 1
        touch(x, "cold_email", t)
        ev("cold_email", t, r.get("company"), "reply", (r.get("snippet") or "")[:100])
    lanes["cold_email"]["source"] = "emails.jsonl (sent) + replies.jsonl"
    # pipeline stage per company (rejection / screen / interview / offer): a reply to an application or an email
    for r in jl(P(STATE, "sf/outreach/pipeline.jsonl")):
        name = r.get("company") or r.get("key")
        x = co(name)
        t = _t(r.get("stage_at"))
        if x:
            x["stage"] = r.get("stage")
            x["replies"] += (r.get("stage") or "") in REPLY_STAGES   # a rejection, screen or interview IS the reply
        lane = "cold_email" if x and x["emails"] and not x["apps"] else "cold_apps"
        touch(x, lane, t)
        touch(x, "network", t)
        ev(lane, t, name, r.get("stage") or "stage", r.get("next_step") or "")
        ev("network", t, name, r.get("stage") or "stage", "recruiter / hiring team")
    lanes["network"]["source"] = "pipeline.jsonl (recruiters, hiring teams) + linkedin-log.csv"
    # LinkedIn hand-sent log
    for r in ctx.get("linkedin_log") or []:
        t = _t(r.get("date"))
        x = co(r.get("company"))
        touch(x, "linkedin", t)
        touch(x, "network", t)
        what = f"{(r.get('name') or '').strip()} · {(r.get('title') or '').strip()}".strip(" ·")
        ev("linkedin", t, r.get("company"), (r.get("channel") or "linkedin") + " " + (r.get("status") or ""), what)
        ev("network", t, r.get("company"), "linkedin " + (r.get("status") or ""), what)
    # referral asks sekhmet sent to people Tyler knows: the campaign ledger files them under co "Network" (no company, so
    # no Cold Apps panel shows them); each sent / answered ask is a Network event (knowledge#16117)
    camp_rows = jl(os.environ.get("NET_CAMPAIGN_LEDGER") or "/home/sekhmet/.local/state/net-campaigns/ledger.jsonl")
    who = {r.get("slug"): r.get("name") for r in camp_rows if r.get("type") == "person" and r.get("name")}
    for r in camp_rows:
        if r.get("type") == "step" and r.get("co") == "Network" and r.get("step") == "referral_ask" \
                and r.get("state") in ("sent", "replied"):
            ev("network", _t(r.get("at")), who.get(r.get("slug")) or r.get("slug"), "referral ask " + r["state"], "")
    lanes["linkedin"]["source"] = "linkedin-log.csv (hand-sent)"
    # Upwork: every hand action; a client is the company once it has a name
    up_rows = ctx.get("upwork_rows") or []
    titles = {(r.get("job") or r.get("key")): r.get("title") for r in up_rows if r.get("title") and (r.get("job") or r.get("key"))}
    feed_names = {_norm(c.get("name"), True): c.get("name") for c in (ctx.get("clients_feed") or {}).get("clients") or [] if c.get("name")}

    def client(n):   # "Mohamed Talat" in the ledger is "Mohamed" in the clients feed: one row, the feed's name
        if not n:
            return n
        return feed_names.get(_norm(n, True)) or feed_names.get(_norm(n.split()[0], True)) or n
    for r in upwork_once(up_rows):
        e = r.get("event")
        if e not in ACTION_EVENTS and e != "sent":
            continue
        t = _row_time(r)
        if r.get("client"):
            r = {**r, "client": client(r["client"])}
        job = r.get("job") or r.get("key")
        name = r.get("client") or r.get("title") or titles.get(job) or ("Upwork job" if job else "")
        x = co(name, loose=True)
        if x:
            x["vsls"] += e == "vsl_sent"
            x["proposals"] += e == "proposal_sent"
        touch(x, "upwork", t)
        ev("upwork", t, name, e, r.get("what") or r.get("note") or r.get("preview") or r.get("text") or "", loose=True)
        if r.get("client"):
            touch(x, "clients", t)
            ev("clients", t, name, e, r.get("what") or r.get("note") or r.get("preview") or "", loose=True)
    # knowledge#14154: every job read reaches the activity feed too (a job is not a company: no `co` row). An alert
    # mail's row counts at the mail's arrival, so a backfill written hours later does not pose as a fresh read.
    for r in up_rows:
        if r.get("event") != "job_read":
            continue
        mail = r.get("source") == "job_alert_mail"
        t = (_t(r.get("mail_at")) if mail else None) or _row_time(r)
        ev("upwork", t, r.get("title") or titles.get(r.get("job")) or "Upwork job", "job_read",
           " · ".join(x for x in (str(r.get("budget") or "").split(" · ")[0], "alert mail" if mail else "desk read") if x),
           loose=True)
    lanes["upwork"]["source"] = ("Upwork ledger (hand actions: proposals, replies, VSLs, contracts, milestones; "
                                 "job reads from the alert mail and the desk)")
    for c in (ctx.get("clients_feed") or {}).get("clients") or []:
        x = co(c.get("name"), loose=True)
        touch(x, "clients", _t(c.get("readAt")))
        for it in c.get("items") or []:
            ev("clients", _t(it.get("paidAt")), c.get("name"), "paid " + (it.get("label") or ""), money(int(it.get("amountCents") or 0)), loose=True)
    lanes["clients"]["source"] = "clients feed (CRM Deals) + Upwork ledger client rows"
    # in person: events found (the store records discovery, not attendance yet)
    for r in jl(P(STATE, "sf/events.jsonl")):
        t = _t(r.get("detected_at"))
        ev("in_person", t, r.get("host_company") or r.get("event_name"), "event " + (r.get("status") or "found"),
           f"{r.get('city') or ''} · {r.get('date') or ''}" + (f" · {r['event_name']}" if r.get("host_company") else ""), loose=True)
    lanes["in_person"]["source"] = "events store sf/events.jsonl (events found; attendance not recorded yet)"
    for r in ctx.get("social_rows") or []:
        ev("social", _t(r.get("at")), r["name"], r["stage"], r.get("what") or "")
    for r in jl(P(RAHMAN, "yt-comments.jsonl")):   # the comments rahman posted on other channels' videos
        ev("social", _t(r.get("ts")), r.get("handle") or "YouTube", "comment on " + (r.get("title") or "a video")[:60],
           r.get("text") or "", loose=True)
    lanes["social"]["source"] = "rahman's inbox.jsonl (people who wrote in) + yt-comments.jsonl (comments rahman posted)"

    for c in cos.values():   # display = the most common clean spelling; a tie goes to the more readable one
        c["name"] = _display(c.pop("spell"))
    for blk in lanes.values():
        for e in blk["events"]:
            k = e.pop("co")
            raw = e.pop("raw")
            e["co"] = (cos[k]["name"] if k in cos else raw)[:80]
    rows = {}
    for k, c in cos.items():
        t = tiers.get(k)
        rows[k] = {"name": c["name"], "tier": t["tier"] if t else None, "apps": c["apps"], "emails": c["emails"],
                   "replies": c["replies"], "vsls": c["vsls"], "proposals": c["proposals"], "stage": c["stage"],
                   "last": _iso(c["last"]), "lanes": sorted(c["lanes"])}
    for lane, blk in lanes.items():
        blk["events"].sort(key=lambda e: e["ts"], reverse=True)
        blk["events"] = blk["events"][:600]
        blk["companies"] = sorted((k for k, r in rows.items() if lane in r["lanes"]),
                                  key=lambda k: rows[k]["last"] or "", reverse=True)
    ctx["lane_latest"] = {k: {"ts": _iso(t), "co": (co or "")[:60], "kind": str(kind).replace("_", " "), "what": what}
                          for k, (t, co, kind, what) in newest.items()}
    return {"updated": _iso(now), "event_days": EVENT_DAYS, "companies": rows, "lanes": lanes,
            "tiers": [{"key": k, **v, "touched": k in rows} for k, v in sorted(tiers.items(), key=lambda kv: (kv[1]["tier"], kv[1]["name"]))],
            "tier_source": tier_src}


def candidate_ledgers(ctx):
    """{id: block} for every family desk whose apply ledger exists under the apply root's candidates/ (the root is
    `apply.py`'s SF_APPLY_DATA_ROOT, ~/.claude/state/sf/apply for horus). A store that will not open is reported as
    such, never as zero."""
    root = os.environ.get("EAGLE_CANDIDATES_ROOT") or P(STATE, "sf/apply/candidates")
    out = {}
    for db in sorted(glob.glob(P(root, "*", "applications.db"))):
        cid = os.path.basename(os.path.dirname(db))
        src = f"apply store {db}"
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                # knowledge#14302: a family desk's "sent" is CONFIRMED submits once per job URL, the number
                # candidate-apply.py status, milli-scout and claire-scout read (person_feed.CONFIRMED_SQL).
                sent = c.execute(CANDIDATE_SENT_SQL).fetchone()[0]
                total = c.execute("select count(*) from applications").fetchone()[0]
                since = lambda d: c.execute(CANDIDATE_SENT_SQL  # noqa: E731
                                            + f" and coalesce(submitted_at,started_at)>datetime('now','-{d} day')").fetchone()[0]
                recent = {"last_24h": since(1), "last_7d": since(7)}
            finally:
                c.close()
            out[cid] = {"candidate": cid, "sent": sent, "runs_total": total, **recent, "status": "live", "source": src,
                        "what": "sent = applications submitted in their name, all time; runs_total includes dry runs and holds"}
        except sqlite3.Error as ex:
            out[cid] = {"candidate": cid, "sent": None, "status": "empty", "source": src, "reason": f"store error: {ex}"[:160]}
    return out


def build(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    ctx, errors = {"now": now}, []
    hunts = {}
    for k, fn in HUNTS.items():
        try:
            hunts[k] = fn(ctx)
        except Exception as ex:  # noqa: BLE001 — one broken store never blanks the others
            hunts[k] = empty_hunt(k, f"error: {str(ex)[:160]}")
            errors.append(f"hunt {k}: {str(ex)[:160]}")
    roosts = {}
    for k, fn in ROOSTS.items():
        try:
            roosts[k] = fn(ctx)
        except Exception as ex:  # noqa: BLE001
            roosts[k] = {"rows": [], "status": "empty", "source": k, "reason": f"error: {str(ex)[:160]}"}
            errors.append(f"roost {k}: {str(ex)[:160]}")
    for blk in list(hunts.values()) + list(roosts.values()):
        blk.setdefault("candidate", TYLER)
    up = ctx.get("upwork_rows") or []
    vsl = [r for r in up if r.get("event") == "vsl_sent"]
    out = {
        # the marketplace keys the existing pages read (same meaning as refresh-data.py's first version)
        "proposals_sent": hunts["upwork"]["sent"] or 0, "proposals_answered": hunts["upwork"]["answered"] or 0,
        "videos_sent": len(vsl), "video_clients": len({r.get("client") for r in vsl}),
        "contracts": sum(1 for r in up if r.get("event") == "contract_started"),
        "paid_events": sum(1 for r in up if r.get("event") == "milestone_paid"),
        "hunts": hunts, "roosts": roosts,
        # knowledge#13453: whose pipeline this is. Every hunt and roost is Tyler's; the family desks are `candidates`.
        "candidate": TYLER, "candidates": {},
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "errors": errors,
    }
    # cold-apps.json (the cold-applications pipeline page): ONE base for sent → replies → interviews, the 28-day window
    ca, cw = hunts["cold_apps"], ctx.get("cold_window") or {}
    out["cold_apps_feed"] = {
        "applications_submitted": ca["sent"], "replies": ca["answered"], "interviews": cw.get("interviews"),
        "applications_submitted_total": ca.get("sent_total"), **(ctx.get("cold_recent") or {}),
        "updated": out["updated"],
        "status": f"live · last {cw['days']} days" if ca["status"] == "live" else f"empty · {ca.get('reason')}"}
    # flat keys for pipelines.json flow[] (pipeline.js reads data[key]); null stays null, never 0
    for k, h in hunts.items():
        out[f"{k}_sent"], out[f"{k}_answered"] = h["sent"], h["answered"]
    # the marketplace client table (pipeline.js renderClients: {name, contracts, paid} + paid_total)
    up_clients = [r for r in roosts["clients"]["rows"] if r.get("hunt") == "upwork"]
    out["clients"] = [{"name": r["name"], "contracts": r["contracts"], "paid": r["paid"]} for r in up_clients]
    out["paid_total"] = money(sum(r["paid_cents"] for r in up_clients))
    try:
        out["lanes_feed"] = lanes_detail(ctx)
    except Exception as ex:  # noqa: BLE001 — the lane pages never blank the home feed
        errors.append(f"lanes: {str(ex)[:160]}")
    # knowledge#17952 (ask 3202): the one-shot architecture diagrams, drawn from the pipelines registry feed, never copied here
    pf = js(P(KB, "_infra/occ-feeds/pipelines.json"))
    if pf and pf.get("pipelines"):
        out["pipelines_feed"] = pf
    else:
        errors.append("pipelines: _infra/occ-feeds/pipelines.json " + probe(P(KB, "_infra/occ-feeds/pipelines.json")))
    for k, blk in list(hunts.items()) + list(roosts.items()):   # knowledge#13746: every lane says what moved last
        if (ctx.get("lane_latest") or {}).get(k) and not blk.get("latest"):   # a roost's own latest wins (the roster's)
            blk["latest"] = ctx["lane_latest"][k]
    try:
        out["candidates"] = candidate_ledgers(ctx)
    except Exception as ex:  # noqa: BLE001 — the family desks never blank Tyler's feed
        errors.append(f"candidates: {str(ex)[:160]}")
    return out


def lanes_collisions(lanes):
    """{key: [names]} for every two company rows in a lanes feed (/lanes.json) that share one canonical key — empty
    when every company is one row. `--check-lanes <file>` runs it over the live feed."""
    g = {}
    for c in (lanes.get("companies") or {}).values():
        loose = not set(c.get("lanes") or ()) & {"cold_apps", "cold_email", "linkedin", "network"}
        g.setdefault(_norm(c.get("name"), loose), []).append(c.get("name"))
    return {k: sorted(v) for k, v in g.items() if k and len(v) > 1}


def _self_test():
    import tempfile  # noqa: PLC0415
    global STATE, KB, LINKEDIN, RAHMAN, UPWORK  # noqa: PLW0603
    t = tempfile.mkdtemp()
    STATE, KB, LINKEDIN = P(t, "state"), P(t, "kb"), P(t, "absent/ledger.jsonl")
    UPWORK = P(STATE, "net/upwork/ledger.jsonl")
    for d in ("net/upwork", "sf/apply", "sf/funnel", "sf/outreach"):
        os.makedirs(P(STATE, d))
    for d in ("_infra/occ-feeds", "net/work/outreach/campaigns", "net/work/outreach/personal-network"):
        os.makedirs(P(KB, d))

    def w(path, rows):
        with open(path, "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
    w(P(STATE, "net/upwork/ledger.jsonl"), [
        {"event": "proposal_sent", "job": "a"}, {"event": "proposal_sent", "key": "b"}, {"event": "proposal_sent", "job": "a"},
        {"event": "client_reply", "job": "a"}, {"event": "client_reply", "job": "zz"},
        {"event": "vsl_sent", "client": "M", "at": 1794600000.0}, {"event": "contract_started", "client": "M"},
        {"event": "milestone_paid", "ts": "2026-11-13T22:00:00Z"},
        {"event": "upwork_mail", "ts": "2026-11-13T23:30:00Z"},
        {"event": "job_read", "source": "job_alert_mail", "ts": "2026-11-13T23:00:00Z", "mail_at": "2026-11-13T21:00:00Z",
         "job": "~022", "title": "Stripe webhook backend", "budget": "Fixed: $500.00 · Est. time: 1 month"}])
    c = sqlite3.connect(P(STATE, "sf/apply/applications.db"))
    c.execute("create table applications (outcome text)")
    c.executemany("insert into applications values (?)", [("submitted",), ("submitted_unconfirmed",), ("failed",)])
    c.commit(); c.close()
    os.makedirs(P(STATE, "sf/apply/candidates/claire"))
    c = sqlite3.connect(P(STATE, "sf/apply/candidates/claire/applications.db"))
    c.execute("create table applications (posting_id text, posting_url text, outcome text, submitted_at text, started_at text)")
    # knowledge#14302: a retry row of the same job URL and an unconfirmed submit are not counted as sent.
    c.executemany("insert into applications values (?,?,?,?,?)", [
        ("p1", "https://jobs.lever.co/x/1", "submitted", None, "2000-01-01T00:00:00Z"),
        ("p1b", "https://jobs.lever.co/x/1", "submitted", None, "2000-01-01T00:00:00Z"),
        ("p2", "https://jobs.lever.co/x/2", "submitted_unconfirmed", None, "2000-01-01T00:00:00Z"),
        ("p3", "https://jobs.lever.co/x/3", "dry_run", None, None)])
    c.commit(); c.close()
    json.dump({"computedAt": "X", "jobFunnel": {"windowDays": 28, "window": {"applied": 5, "replied": 2}}},
              open(P(STATE, "sf/funnel/net-funnel.json"), "w"))
    w(P(STATE, "sf/outreach/emails.jsonl"), [
        {"direction": "out", "status": "sent", "kind": "opener", "gmail_thread_id": "t1", "company": "acme"},
        {"direction": "out", "status": "sent", "kind": "followup", "gmail_thread_id": "t1", "company": "acme"},
        {"direction": "out", "status": "dry-run", "kind": "opener", "gmail_thread_id": "t2", "company": "beta"},
        {"direction": "out", "status": "sent", "kind": "opener", "gmail_thread_id": "t3", "company": "gamma"}])
    w(P(STATE, "sf/outreach/replies.jsonl"), [{"gmail_thread_id": "t1"}, {"gmail_thread_id": "t9"}])
    w(P(STATE, "sf/outreach/pipeline.jsonl"), [{"key": "acme", "company": "Acme", "stage": "interview"},
                                               {"key": "delta", "company": "Delta", "stage": "rejection"}])
    w(P(KB, "net/work/outreach/campaigns/x.jsonl"), [{"kind": "send", "touch": 1}, {"kind": "send", "touch": 2}])
    os.makedirs(P(STATE, "sf/network"))
    json.dump({"computedAt": "C", "clients": [
        {"name": "M", "source": "upwork", "kind": "contract", "money": {"paidCents": 0, "pendingCents": 10000, "fundedCents": 10000}},
        {"name": "O", "source": "direct", "kind": "step", "money": {}}], "prospects": [{"name": "R", "status": "draft"}]},
        open(P(KB, "_infra/occ-feeds/clients.json"), "w"))
    json.dump({"schema": "pipelines/1", "pipelines": [{"id": "t", "title": "T", "stages": []}]}, open(P(KB, "_infra/occ-feeds/pipelines.json"), "w"))
    with open(P(KB, "net/work/outreach/linkedin-log.csv"), "w") as f:
        f.write("date,company,name,title,linkedin_url,channel,status,message,follow_up_due,notes,track\n"
                "2026-10-05,Urban,Tina B,CEO,,linkedin-connect,sent,a,,x,agency\n")
    with open(P(KB, "net/work/outreach/personal-network/p-x.md"), "w") as f:
        f.write("# Bo X — person brief\n- **How met:** in-person · 2026-10-30\n- **Stage:** first-touch · next 2026-11-03\n")
    RAHMAN = P(STATE, "rahman")
    os.makedirs(RAHMAN, exist_ok=True)
    w(P(RAHMAN, "inbox.jsonl"), [
        {"platform": "youtube", "kind": "chat", "author": "@fan", "text": "yo", "seen_at": 1794300000, "status": "for_tyler"},
        {"platform": "youtube", "kind": "chat", "author": "@fan", "text": "again", "seen_at": 1794400000, "status": "for_tyler"},
        {"platform": "youtube", "kind": "chat", "author": "@tyleryouk1430", "text": "me", "seen_at": 1794400000},
        {"platform": "instagram", "kind": "dm", "author": "spam", "text": "x", "seen_at": 1794400000, "status": "ignored"}])
    d = build(dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc))
    h = d["hunts"]
    assert (h["upwork"]["sent"], h["upwork"]["answered"]) == (2, 1), h["upwork"]
    # knowledge#13160: freshness from the rows' own times — the mail trigger is the newest row, the hand action is not
    assert h["upwork"]["last_row"] == {"ts": "2026-11-13T23:30:00Z", "event": "upwork_mail", "age_min": 30}, h["upwork"]
    assert h["upwork"]["last_action"] == {"ts": "2026-11-13T22:00:00Z", "event": "milestone_paid", "age_min": 120}, h["upwork"]
    assert (h["cold_apps"]["sent"], h["cold_apps"]["answered"], h["cold_apps"]["sent_total"]) == (5, 2, 2), h["cold_apps"]
    assert (h["cold_email"]["sent"], h["cold_email"]["answered"]) == (3, 1), h["cold_email"]  # t1, t3 + 1 ledger touch-1
    assert (h["linkedin"]["sent"], h["linkedin"]["status"]) == (1, "partial") and "absent" in h["linkedin"]["reason"], h["linkedin"]
    assert h["in_person"]["sent"] is None and h["in_person"]["status"] == "empty" and "events" in h["in_person"]["source"]
    assert d["in_person_sent"] is None and d["linkedin_sent"] == 1  # null stays null in the flat keys
    assert h["linkedin"]["latest"]["co"] == "Urban", h["linkedin"].get("latest")   # knowledge#13746: older than the window still shows
    assert (d["proposals_sent"], d["proposals_answered"], d["videos_sent"], d["contracts"], d["paid_events"]) == (2, 1, 1, 1, 1)
    cl = d["roosts"]["clients"]["rows"]
    assert [(r["name"], r["hunt"], r["contracts"]) for r in cl] == [("M", "upwork", 1), ("O", "personal_network", 0), ("R", None, 0)], cl
    assert d["clients"] == [{"name": "M", "contracts": 1, "paid": "$0 · $200 pending/funded"}] and d["paid_total"] == "$0", d["clients"]
    nw = d["roosts"]["network"]["rows"]
    assert nw[0]["name"] == "Acme" and nw[0]["hunt"] == "cold_email", nw
    assert any(r["hunt"] == "linkedin" for r in nw) and any(r["name"] == "Bo X" and r["hunt"] == "in_person" for r in nw), nw
    assert {"name", "hunt", "stage", "contracts", "paid"} <= set(nw[-1]), nw[-1]
    # knowledge#14132: once the roster exists the roost is the roster: each person once, with every channel, counted
    json.dump({"built_at": "B", "channels": {"text": 1}, "sources": {"phone": {"status": "live"}, "linkedin": {
        "status": "partial", "connections": {"status": "absent", "reason": "no export"}}},
        "people_rows": [{"name": "Ann Lee", "channels": ["text", "whatsapp", "email"], "company": "Decagon"},
                        {"name": "Bo X", "channels": ["whatsapp"], "wa_last": "2026-11-12T01:00:00Z"},
                        {"name": "Mike", "channels": ["text"], "phones": ["+15551110001"]},
                        {"name": "Mike", "channels": ["text"], "phones": ["15552220002@s.whatsapp.example"]}]}, open(P(STATE, ROSTER), "w"))
    os.environ["NET_NETWORK_STATE"] = os.path.dirname(P(STATE, ROSTER))
    rn = build(dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc))["roosts"]["network"]
    assert {r["name"] for r in rn["rows"]} >= {"Mike (…0001)", "Mike (…0002)"}, rn["rows"]
    assert rn["people"] == len(rn["rows"]) == 4 and rn["status"] == "partial" and "no export" in rn["reason"], rn
    assert rn["rows"][0]["stage"] == "text · whatsapp · email" and rn["rows"][0]["what"] == "Decagon", rn["rows"][0]
    assert not any(r["kind"] == "recruiter / hiring team" for r in rn["rows"]), rn
    assert rn["latest"] == {"ts": "2026-11-12T01:00:00Z", "co": "Bo X", "kind": "whatsapp", "what": "last 1:1 message"}, rn
    os.remove(P(STATE, ROSTER))
    os.environ.pop("NET_NETWORK_STATE")
    so = d["roosts"]["social"]   # knowledge#13746: one row per person who wrote in, Tyler's own handle and ignored out
    assert so["status"] == "live" and [r["name"] for r in so["rows"]] == ["@fan"] and so["rows"][0]["what"] == "again", so
    assert so["latest"]["co"].lower().lstrip("@") == "fan", so.get("latest")
    caf = d["cold_apps_feed"]
    assert (caf["applications_submitted"], caf["replies"], caf["interviews"], caf["applications_submitted_total"]) == (5, 2, 0, 2), caf
    assert caf["status"] == "live · last 28 days", caf
    assert not d["errors"], d["errors"]
    # knowledge#13617: the lane pages' feed: companies joined across stores, Upwork clients named, every lane present
    assert d["pipelines_feed"]["pipelines"][0]["id"] == "t"   # knowledge#17952
    lf = d["lanes_feed"]
    assert set(lf["lanes"]) == {"upwork", "cold_apps", "linkedin", "cold_email", "in_person", "clients", "network", "social"}
    # knowledge#14154: a job read is on the Upwork activity feed at its alert mail's time, and is not a company
    jr = [e for e in lf["lanes"]["upwork"]["events"] if e["kind"] == "job_read"]
    assert jr == [{"ts": "2026-11-13T21:00:00Z", "kind": "job_read", "what": "Fixed: $500.00 · alert mail",
                   "co": "Stripe webhook backend"}], jr
    assert not any("stripe" in k for k in lf["companies"]), list(lf["companies"])
    assert lf["companies"]["acme"]["emails"] == 2 and lf["companies"]["acme"]["stage"] == "interview", lf["companies"]["acme"]
    assert lf["companies"]["acme"]["replies"] == 1 and "cold_email" in lf["companies"]["acme"]["lanes"], lf["companies"]["acme"]
    assert "m" in lf["companies"] and lf["companies"]["m"]["vsls"] == 1, lf["companies"].get("m")
    # knowledge#13617 round 3: company names normalised before grouping, doubled messages counted once
    for raw, want in (("00100 LEIDOS, INC.", "Leidos"), ("205 F5, Inc. (United States)", "F5"), ("C_087 Acme Ltd", "Acme"),
                      ("Thank You for Your Interest in SkyePoint Decisions", "SkyePoint Decisions"), ("Your application", None),
                      ("capitalone", "Capitalone"), ("retell-ai", "Retell AI")):
        assert _clean(raw) == want, (raw, _clean(raw), want)
    assert _norm("rune") == _norm("Rune Technologies") == "rune" and _norm("mistral.ai") == _norm("Mistral")
    assert _better("rune", "Rune Technologies") == "Rune Technologies"
    # knowledge#13617 round 4: ONE canonical key by rule — glued/spaced, legal forms, careers labels, regions and
    # division words all fold into the parent; display is the most common clean spelling
    for group in (("Beacon AI", "Beaconai"), ("Clay Labs", "Claylabs"), ("ATOMS", "ATOMS Careers page", "ATOMS jobs"),
                  ("Nvidia", "NVIDIA Graphics Bengaluru", "Nvidia Poland", "NVIDIA Canada Dev",
                   "NVIDIA Computing Spain, S.L.U"), ("CrowdStrike", "CrowdStrike Australia"), ("SpaceX", "SpaceXAI"),
                  ("Instrumental", "Instrumental Inc", "Instrumental, LLC"), ("Voleon", "The Voleon Group"),
                  ("Capital One", "capitalone"), ("Bose", "Bose Corporation, U.S.A"), ("Hitachi", "Hitachi Global"),
                  ("ASML", "ASML People Operations"), ("Fiserv", "Fiserv Solutions"), ("Acme", "Acme Ltd", "Acme Corp")):
        keys = {_norm(n) for n in group}
        assert len(keys) == 1, (group, keys)
    for apart in (("Syndio", "Synd"), ("ATOM Technologies", "ATOMS"), ("Applied", "Applied Materials"),
                  ("Echo", "Echo Neurotechnologies")):
        assert _norm(apart[0]) != _norm(apart[1]), apart
    assert _clean("Instrumental Inc") == "Instrumental" and _clean("ATOMS Careers page") == "ATOMS", _clean("ATOMS Careers page")
    assert _norm("Ōura") == "oura" and _display({"Nvidia": 36, "NVIDIA Graphics Bengaluru": 1, "Nvidia Poland": 1}) == "Nvidia"
    assert _display({"Fiserv Solutions": 5, "Fiserv": 1}) == "Fiserv" and _display({"The Voleon Group": 3, "Voleon": 1}) == "Voleon"
    assert _clean("Booz Allen Hamilton United States") == "Booz Allen Hamilton"
    assert _clean("SS&C Technologies Poland") == "SS&C Technologies" and _clean("CrowdStrike Australia") == "CrowdStrike"
    assert _display({"EverCommerce Solutions": 4, "Evercommerce": 1}) == "EverCommerce"
    assert _display({"Claylabs": 3, "Clay Labs": 2}) == "Clay Labs" and _display({"Beaconai": 4, "Beacon AI": 3}) == "Beacon AI"
    assert _clean("instrumental-inc-") == "Instrumental" and _clean("retell-ai") == "Retell AI"
    for raw, want in (("EPIC Epicor Software", "Epicor Software"), ("CHN Choice Hotels International Services",
                      "Choice Hotels International"), ("DIGITL Fox Digital & Technology Group", "Fox Digital & Technology Group"),
                      ("SAMC SitusAMC Holdings", "SitusAMC"), ("GSS Geisinger System Services", "Geisinger System"),
                      ("RPMS RoundPoint Mortgage Servicing", "RoundPoint Mortgage Servicing"),
                      ("RVO Health", "RVO Health"), ("IXL Learning", "IXL Learning"), ("GE Aviation", "GE Aviation"),
                      ("CDW", "CDW")):   # Workday org codes off, real acronyms kept (fleetmail #5011)
        assert _drop_org_code(raw).split(" ")[0] == want.split(" ")[0], (raw, _drop_org_code(raw), want)
    assert not lanes_collisions({"companies": {"a": {"name": "Beacon AI", "lanes": ["cold_apps"]},
                                               "b": {"name": "Beacon Biosignals", "lanes": ["cold_apps"]}}})
    assert lanes_collisions({"companies": {"a": {"name": "Beacon AI", "lanes": ["cold_apps"]},
                                           "b": {"name": "Beaconai", "lanes": ["cold_email"]}}}) == {"beacon": ["Beacon AI", "Beaconai"]}
    up = upwork_once([
        {"ts": "2026-11-12T22:24:42Z", "event": "client_reply", "client": "Mo T", "preview": "Hi, ready", "via": "w"},
        {"ts": "2026-11-12T23:22:01Z", "event": "client_reply", "client": "Mo T", "preview": "Hi, ready", "via": "w"},
        {"ts": "2026-11-12T21:42:22Z", "event": "client_reply", "client": "Mo T", "preview": "Hi, server made", "via": "w"},
        {"ts": "2026-11-12T21:42:50Z", "event": "client_reply", "client": "Mo T", "preview": "server made (summary)"},
        {"ts": "2026-11-12T21:12:22Z", "event": "client_reply", "client": "Mo T",
         "preview": "Mo T. sent you a message · View your message and send a reply."},
        {"ts": "2026-11-12T04:17:08Z", "event": "client_reply", "client": "Mo T",
         "preview": "Mo T. sent you a message · View your message and send a reply."}])
    assert [r["ts"][11:16] for r in up] == ["04:17", "21:42", "22:24"], up   # a lone notice is that message's only record
    # knowledge#13453: every block names its candidate; the family desks come from their own ledgers, never Tyler's
    assert d["candidate"] == "tyler" and all(b["candidate"] == "tyler" for b in list(h.values()) + list(d["roosts"].values()))
    cc = d["candidates"]
    assert set(cc) == {"claire"} and (cc["claire"]["candidate"], cc["claire"]["sent"], cc["claire"]["runs_total"],
                                      cc["claire"]["last_7d"]) == ("claire", 1, 4, 0), cc
    # no store at all: every hunt is an honest empty, never a zero
    STATE, KB, UPWORK = P(t, "none"), P(t, "none"), P(t, "none/net/upwork/ledger.jsonl")
    e = build()
    assert all(e["hunts"][k]["sent"] is None and e["hunts"][k]["reason"] for k in HUNTS), e["hunts"]
    assert e["roosts"]["clients"]["status"] == "empty" and e["roosts"]["network"]["status"] == "empty"
    assert e["candidates"] == {}, e["candidates"]
    print("eagle-eye feed self-test: ok")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--check-lanes" in sys.argv:   # knowledge#13617: no two company rows of a live lanes feed share a key
        bad = lanes_collisions(json.load(open(sys.argv[sys.argv.index("--check-lanes") + 1])))
        print(json.dumps(bad, ensure_ascii=False) if bad else "lanes: every company is one row")
        sys.exit(1 if bad else 0)
    print(json.dumps(build(), ensure_ascii=False))
