#!/usr/bin/env python3
"""upwork_feed.py: the Upwork lane's live feed for Eagle Eye (knowledge#14038).

Runs as the `upwork` user on Nova (the lane's agent owns its stores, knowledge#13798), from `upwork-eagle-feed.timer`
every 5 min. Reads, read-only:
  * jobs       - the ledger's `job_read` rows of the last 3 days: mail_watch.py writes one per dev@ Upwork "New job
                 alert" mail within a minute (knowledge#14154), and the upwork agent one per job it reads on its desk:
                 title, link, budget line, client line, posted = the mail's arrival time, readAt = the newest read
  * intake     - when jobs last arrived and by which path: Upwork's alert mail is capped at 5 a day, all in the
                 evening (MT), so the desk's own reads are the only intake for the rest of the day
  * proposals  - proposals.db (the upwork agent's sends) + every `proposal_sent` row of the ledger, one row per job,
                 status from proposals.db's stage columns and the ledger's `hired` / `client_reply` rows on that job
  * contracts  - ledger rows that name a contract (`message_sent`, `client_reply`, `milestone_*`, `hired`), grouped by
                 client; Mohamed Talat's contract 113036261 is the one live today
  * applied    - what /hunt/upwork shows (knowledge#14455): every job with a sent proposal, newest send first, with the
                 proposal text, bid, Connects, the job post as read, the client's stage dates, the VSL (attached /
                 recorded), the Polymarket-type demo (its vsl_pick slug, built = https://<slug>.utopiamodels.ai is 200)
                 and the next action (`next_action()`: VSL first, then the demo, then the client's stage); the
                 letter's thesis in three lines (`thesis`: what the client wants, what we show him, the price;
                 letter_lint.py) and the lint verdict on the text sent (`lint`: [] = PASS) (knowledge#14741)
  * replies    - `client_reply` + `upwork_mail` (mail_watch.py) rows: the home badge counts the ones newer than the
                 viewer's last visit to /hunt/upwork
and writes one JSON object (schema `upwork/1`) to KV key `upwork` of namespace eagle-eye-data (the eagle-eye Worker
serves it at /upwork.json). A failed read pushes nothing, so the KV keeps the last good copy; every run logs one line.

    upwork_feed.py            # measure + PUT to KV
    upwork_feed.py --stdout   # measure, print, push nothing
"""
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = Path(os.environ.get("EAGLE_KB") or os.path.expanduser("~/dev/utopia-models/knowledge"))
sys.path.insert(0, str(KB / "net/work/_tools/upwork"))
import letter_lint  # noqa: E402  (net/work/_tools/upwork, stdlib only)
import triage  # noqa: E402  (knowledge#18050: newest-first triage rows + the 7-day no-reply drop)
H = Path.home()
STORE = H / ".claude/state/net/upwork"
LEDGER, DB = STORE / "ledger.jsonl", STORE / "proposals.db"
BOX = "the dev@ inbox"   # a label only: the address itself stays out of the tracked file and the public feed
NS = "d97b9be8758d4ede805c0bf9c6d2e68c"   # eagle-eye-data (push-kv.sh)


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_of(r):
    if r.get("ts"):
        try:
            return dt.datetime.fromisoformat(str(r["ts"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return float(r.get("at") or 0)


def key_of(s):
    m = re.search(r"~?(0[0-9]{17,})", str(s or ""))
    return "~" + m.group(1) if m else None


def read_t(r):
    """When the lane learned of a job: an alert mail's arrival (mail_watch.py writes it within the minute; a backfill
    written hours later still counts at the mail's time), else the hand read's own row time."""
    return ts_of({"ts": r["mail_at"]}) if r.get("source") == "job_alert_mail" and r.get("mail_at") else r["_t"]


def private_keys(rows):
    """Jobs the upwork agent marked `job_private` (invited freelancers only): not listed, not matched."""
    return {key_of(r.get("job")) for r in rows if r.get("event") == "job_private" and r.get("job")}


def jobs(rows, now, window_days=3):
    """The last 3 days of jobs, from the ledger's `job_read` rows (knowledge#14154): mail_watch.py writes one per Upwork
    job alert mail within a minute, and a hand read on the desk (ledger.py add job_read) adds the fit. One per job,
    newest read first; `postedAt` is when the alert mail landed (or the hand read, for a job with no alert), `readAt`
    the job's newest read, `via` which paths read it ("alert mail", "desk")."""
    by = {}
    private = private_keys(rows)
    for r in rows:
        if r.get("event") != "job_read":
            continue
        k = key_of(r.get("job") or r.get("url")) or r.get("gmail_id")
        if not k or k in private:
            continue
        at = r.get("mail_at") or iso(r["_t"])
        d = by.setdefault(k, {"title": "", "url": None, "postedAt": at, "readAt": iso(read_t(r)), "budget": "", "client": "",
                              "key": key_of(k), "via": []})
        d["postedAt"] = min(d["postedAt"], at)
        d["readAt"] = max(d["readAt"], iso(read_t(r)))
        via = "alert mail" if r.get("source") == "job_alert_mail" else "desk"
        if via not in d["via"]:
            d["via"].append(via)
        for f, src in (("title", "title"), ("url", "url"), ("budget", "budget"), ("client", "client_line")):
            if r.get(src):
                d[f] = r[src]
        if r.get("fit") is not None:
            d["fit"] = r["fit"]
        if not d["url"] and d["key"]:
            d["url"] = f"https://www.upwork.com/jobs/{d['key']}"
    st = job_stages(rows)
    for k, rs in st.items():   # a job with a demo or a take but no read row (it was read before the 3-day window) still shows
        if k not in by and k not in private:
            at = iso(max(r["_t"] for r in rs))
            by[k] = {"title": "", "url": f"https://www.upwork.com/jobs/{k}", "postedAt": at, "readAt": at, "budget": "",
                     "client": "", "key": k, "via": ["ledger"]}
    for k, d in by.items():
        d["stages"] = stage_rows(st.get(key_of(k), []))
    out = [j for j in by.values() if window_days is None or ts_of({"ts": j["readAt"]}) > now - window_days * 86400]
    return sorted(out, key=lambda j: j["readAt"], reverse=True)


STAGE_EVENTS = ("demo_ready", "vsl_recorded", "vsl_sent", "proposal_sent", "client_reply")


def job_stages(rows):
    """job key -> that job's stage events (demo_ready, vsl_recorded, vsl_sent, proposal_sent, client_reply), oldest first."""
    by = {}
    for r in rows:
        if r.get("event") in STAGE_EVENTS:
            k = key_of(r.get("job") or r.get("key") or r.get("link"))
            if k:
                by.setdefault(k, []).append(r)
    return by


def stage_rows(rs):
    """One job's pipeline as rows: DEMO READY (demo_ready) -> VSL (vsl_recorded) -> SENT (vsl_sent / proposal_sent) ->
    STATUS ('in conversation' when the client replied, else 'none'). `at` is the newest matching row's time, None when
    the stage has not happened; `done` is `at is not None`. DEMO READY also carries the demo `url`, VSL the take `file`."""
    def last(*events):
        m = [r for r in rs if r.get("event") in events]
        return max(m, key=lambda r: r["_t"]) if m else None
    out = []
    for name, evs in (("DEMO READY", ("demo_ready",)), ("VSL", ("vsl_recorded",)), ("SENT", ("vsl_sent", "proposal_sent"))):
        r = last(*evs)
        row = {"stage": name, "done": r is not None, "at": iso(r["_t"]) if r else None}
        if r and name == "DEMO READY" and r.get("url"):
            row["url"] = r["url"]
        if r and name == "VSL" and r.get("file"):
            row["file"] = r["file"]
        out.append(row)
    r = last("client_reply")
    out.append({"stage": "STATUS", "done": r is not None, "at": iso(r["_t"]) if r else None,
                "value": "in conversation" if r else "none"})
    return out


def pipeline(rs, a):
    """The four stages for one applied job (Tyler 2026-11-17, fleetmail 8493/8494): DEMO READY -> VSL -> SENT -> STATUS
    (in conversation | none). stage_rows() reads the ledger's stage events; the store's own facts fill what the ledger
    has not said (a live demo page, a recorded take, the sent proposal). Tyler's rule: a proposal counts as SENT only
    when its VSL exists, so `noVsl` is True on a sent job with no recorded or attached VSL; the page flags it."""
    st = stage_rows(rs)
    d, v = a.get("demo") or {}, a.get("vsl") or {}
    if d.get("live") and not st[0]["done"]:
        st[0].update(done=True, at=d.get("picked"))
    if d.get("url") and st[0]["done"]:
        st[0]["url"] = d["url"]
    if (v.get("recorded") or v.get("attached")) and not st[1]["done"]:
        st[1].update(done=True, at=v.get("at"))
    if v.get("file") and st[1]["done"]:
        st[1]["file"] = v["file"]
    sent = bool(a.get("sentAt"))
    if sent and not st[2]["done"]:
        st[2].update(done=True, at=a["sentAt"])
    if (a.get("stages") or {}).get("replied") and not st[3]["done"]:
        st[3].update(done=True, at=a["stages"]["replied"], value="in conversation")
    return {"stages": st, "noVsl": sent and not st[1]["done"],
            "demoOwner": None if st[0]["done"] else "upwork"}


# The STATUS of a job, one or two words, Tyler's pipeline vocabulary (4:53 PM). Edit the words HERE only; the page shows what the feed says.
STATUS_WORDS = {"demo": "Awaiting Demo", "vsl": "Awaiting VSL", "drafting": "Proposal Drafting", "sent": "Awaiting Reply",
                "engaged": "In Conversation", "won": "Won", "lost": "Lost", "passed": "Passed"}


def status_word(demo, vsl, sent=False, stages=None, passed=False, **_):
    """no demo -> Awaiting Demo -> Awaiting VSL -> Proposal Drafting (VSL recorded, proposal not sent) -> Awaiting Reply
    (sent) -> In Conversation (client replied, the Upwork agent answers) -> Won | Lost; Passed = we dropped it."""
    st = stages or {}
    k = ("won" if st.get("hired") else "lost" if st.get("declined") else "engaged" if st.get("replied") or st.get("interview") or st.get("call")
         else "sent" if sent else "passed" if passed else "drafting" if vsl else "vsl" if demo else "demo")
    return STATUS_WORDS[k]


def matches(rows, props, limit=10):
    """The matches Tyler reviews (coordinator, 2026-11-17): jobs the lane picked a demo for (vsl_pick / demo_ready rows),
    not yet sent, newest first, at most `limit`. Per job: title, why it fits, the demo it needs, who owns that demo
    ('UNASSIGNED' when no row names one: the owner rides in a row's `who`, the state in its `note`) and the status."""
    sent = {p["key"] for p in props if p.get("sentAt")} | private_keys(rows)
    by = {}
    for r in rows:
        k = key_of(r.get("job") or r.get("key") or r.get("link") or r.get("url"))
        if k and k not in sent:
            by.setdefault(k, []).append(r)
    out = []
    for k, rs in by.items():
        picks = [r for r in rs if r.get("event") in ("vsl_pick", "demo_ready", "vsl_recorded")]
        if not picks:
            continue
        last = lambda *ev: next((r for r in reversed(rs) if r.get("event") in ev), {})  # noqa: E731
        pick, ready, rec = last("vsl_pick"), last("demo_ready"), last("vsl_recorded")
        read, scored = last("job_read"), last("scored")
        slug = ready.get("slug") or pick.get("slug")
        owner = next((r["who"] for r in reversed(picks) if r.get("who")), None) or "UNASSIGNED"
        note = next((r["note"] for r in reversed(picks) if r.get("note")), "")
        status = "VSL recorded" if rec else "demo ready, VSL pending" if ready else (note or "demo building")
        posted = pick.get("posted_at") or read.get("posted_at") or scored.get("published") or read.get("mail_at")   # the real posted_at first, the alert-mail time is only a proxy
        why = scored.get("reasons") or pick.get("why") or pick.get("reason") or []
        out.append({"key": k, "title": read.get("title") or scored.get("title") or pick.get("title") or "",
                    "url": f"https://www.upwork.com/jobs/{k}", "why": why if isinstance(why, list) else [why],
                    "vslScript": any(r.get("event") == "vsl_script" for r in rs), "runsheet": f"net/work/vsl/{slug}/runsheet.md" if slug else None,
                    "demo": {"slug": slug, "url": ready.get("url") or (f"https://{slug}.{DEMO_DOMAIN}/" if slug else None),
                             "ready": bool(ready)},
                    "postedAt": posted if not isinstance(posted, (int, float)) else iso(posted),
                    "owner": owner, "note": note, "status": status, "vsl": bool(rec),
                    "statusWord": status_word(bool(ready), bool(rec), scripted=any(r.get("event") == "vsl_script" for r in rs), passed=any(r.get("event") in ("passed", "skipped") for r in rs)), "at": iso(max(r["_t"] for r in picks))})
    return sorted(out, key=lambda m: m["at"], reverse=True)[:limit]


def intake(rows, now):
    """How jobs reach the lane, so a quiet list reads as what it is (knowledge#14154). Upwork mails at most 5 job alerts
    a day, all between ~00:00 and ~06:30 UTC (measured over 2026-11-07..16: exactly 5 every day); every other hour of
    the day a job reaches the ledger only when the upwork agent reads one on its desk (`ledger.py add job_read`)."""
    reads = [r for r in rows if r.get("event") == "job_read"]
    mail = [r for r in reads if r.get("source") == "job_alert_mail"]
    desk = [r for r in reads if r.get("source") != "job_alert_mail"]
    newest = lambda rs: iso(max(read_t(r) for r in rs)) if rs else None  # noqa: E731
    within = lambda rs, s: sum(1 for r in rs if read_t(r) > now - s)  # noqa: E731
    return {"lastRead": newest(reads), "lastAlertMail": newest(mail), "lastDeskRead": newest(desk),
            "read1h": within(reads, 3600), "read24h": within(reads, 86400), "desk24h": within(desk, 86400),
            "alertCap": "Upwork mails at most 5 job alerts a day, all between about 5 PM and 11:30 PM MT"}


def ledger():
    rows = []
    with open(LEDGER) as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            r["_t"] = ts_of(r)
            rows.append(r)
    return sorted(rows, key=lambda r: r["_t"])


def proposals(rows):
    by = {}
    for r in rows:
        if r.get("event") != "proposal_sent":
            continue
        k = key_of(r.get("job") or r.get("key") or r.get("link"))
        if not k:
            continue
        bid = r.get("bid_usd") or (r.get("bid") or [None, None])[1]
        by[k] = {"key": k, "title": r.get("title") or "", "url": f"https://www.upwork.com/jobs/{k}",
                 "sentAt": iso(r["_t"]), "bid": bid, "connects": r.get("connects")}
    if DB.exists():
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        for p in db.execute("select * from proposals"):
            k = key_of(p["job_key"] or p["job_url"])
            if not k:
                continue
            d = by.setdefault(k, {"key": k, "url": p["job_url"] or f"https://www.upwork.com/jobs/{k}"})
            d.update({"title": p["title"] or d.get("title", ""), "sentAt": p["sent_at"] or d.get("sentAt"),
                      "bid": p["bid_usd"] if p["bid_usd"] is not None else d.get("bid"),
                      "connects": p["connects"] if p["connects"] is not None else d.get("connects")})
            for st, col in (("hired", "hired_at"), ("declined", "declined_at"), ("call", "call_at"),
                            ("interview", "interview_at"), ("replied", "replied_at"), ("viewed", "viewed_at")):
                if p[col]:
                    d.setdefault("_st", []).append((st, p[col]))
    rank = {"hired": 6, "declined": 5, "call": 4, "interview": 3, "replied": 2, "viewed": 1}
    for r in rows:   # the ledger's own stage rows on a proposal's job
        k = key_of(r.get("job") or r.get("key"))
        if k in by and r.get("event") in ("hired", "client_reply"):
            by[k].setdefault("_st", []).append(("hired" if r["event"] == "hired" else "replied", iso(r["_t"])))
    out = []
    for d in by.values():
        st = max(d.pop("_st", []), key=lambda s: rank[s[0]], default=("sent", d.get("sentAt")))
        d["status"], d["statusAt"] = st
        out.append(d)
    return sorted(out, key=lambda d: d.get("sentAt") or "", reverse=True)


def contracts(rows, props):
    title = {p["key"]: p["title"] for p in props}
    by = {}
    for r in rows:
        if not (r.get("contract") or r.get("event") == "hired"):
            continue
        name = r.get("client") or ""
        if r.get("event") == "hired" and not name:
            name = next((x.get("client") for x in rows if x.get("job") == r.get("job") and x.get("client")), "")
        if not name:
            continue
        c = by.setdefault(name, {"client": name, "ids": [], "status": "active", "milestones": {}})
        if r.get("contract") and r["contract"] not in c["ids"]:
            c["ids"].append(r["contract"])
        ev = r.get("event")
        if ev == "hired":
            c["since"] = iso(r["_t"]); c["title"] = title.get(key_of(r.get("job")), c.get("title", ""))
            c["url"] = f"https://www.upwork.com/jobs/{key_of(r.get('job'))}"
        elif ev == "client_reply":
            c["lastReply"] = {"ts": iso(r["_t"]), "what": r.get("note") or r.get("preview") or ""}
        elif ev in ("message_sent", "sent", "vsl_sent", "reply_sent"):
            c["lastSent"] = {"ts": iso(r["_t"]), "what": r.get("note") or r.get("what") or ""}
        elif ev and ev.startswith("milestone_") and r.get("milestone"):
            c["milestones"][str(r["milestone"])] = {"n": r["milestone"], "amount": r.get("amount"),
                                                     "state": ev.split("_", 1)[1], "ts": iso(r["_t"])}
        elif ev in ("contract_ended", "contract_closed"):
            c["status"] = "ended"
    out = []
    for c in by.values():
        c["milestones"] = sorted(c["milestones"].values(), key=lambda m: m["n"])
        c["id"] = max(c["ids"], key=len) if c["ids"] else None   # the contract id Upwork shows (113036261), not a milestone's
        c["paid"] = sum(m["amount"] or 0 for m in c["milestones"] if m["state"] == "paid")
        out.append(c)
    return sorted(out, key=lambda c: (c["status"] != "active", -(ts_of({"ts": (c.get("lastReply") or {}).get("ts")}) or 0)))


def replies(rows):
    out = []
    for r in rows:
        if r.get("event") == "client_reply":
            out.append({"ts": iso(r["_t"]), "client": r.get("client") or "", "what": r.get("note") or r.get("preview") or ""})
        elif r.get("event") == "upwork_mail" and not str(r.get("subject", "")).startswith("[DRILL"):
            out.append({"ts": iso(r["_t"]), "client": re.sub(r"\s+sent you a message$", "", r.get("subject", "")), "what": "", "mail": True})
    said = [ts_of(x) for x in out if not x.get("mail")]   # a mail alert for a reply the agent already logged is one reply
    out = [x for x in out if not x.get("mail") or all(abs(ts_of(x) - t) > 1800 for t in said)]
    return sorted(out, key=lambda x: x["ts"], reverse=True)[:40]


def who(name):
    """One client however a row spells them: the ledger's "Mohamed Talat" and the mail subject's "Mohamed T." -> mohamed t."""
    w = re.findall(r"[a-z]+", str(name or "").lower())
    return " ".join([w[0]] + [w[1][0]] if len(w) > 1 else w)


OUTBOX = Path("/srv/upwork-vsl/outbox")   # a custom take, <job-key>--<slug>.mp4 (vsl_cadence.py `attach`)
DEMO_DOMAIN = "utopiamodels.ai"            # a demo is https://<slug>.utopiamodels.ai (vsl_cadence.py demo_url)
FOLLOW_D = 5
# Upwork's proposal edit window: a sent proposal takes an edited-in VSL for 6 h, or until the client views it, the
# earlier of the two (vsl_cadence.py EDIT_WINDOW, knowledge#14125). Past it the video waits for the client's reply
# (knowledge#14748: the feed kept saying "attach the recorded VSL" hours after the edit had closed).
EDIT_WINDOW_S = 6 * 3600
TZ_CACHE = H / ".local/state/upwork-vsl/tz.json"   # Tyler's calendar zone, cached by vsl_cadence.py tz_live()


def tyler_tz():
    """Tyler's zone for a clock time he reads: vsl_cadence.py's cache of his calendar zone, else Mountain."""
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(json.loads(TZ_CACHE.read_text())["tz"])
    except Exception:  # noqa: BLE001
        return ZoneInfo("America/Denver")


EAGLE_EYE_TZ = "America/New_York"   # Tyler 2026-11-22 (ask 2179): "could we use EST for Eagle Eye", so every Eagle Eye clock reads Eastern


def clock(t, tz=None):
    """A clock time the way he says it: 11:08 PM ET (never 06:08Z). Eastern by default; an explicit zone drops the label."""
    from zoneinfo import ZoneInfo
    if tz is not None:
        return dt.datetime.fromtimestamp(t, tz).strftime("%-I:%M %p")
    return dt.datetime.fromtimestamp(t, ZoneInfo(EAGLE_EYE_TZ)).strftime("%-I:%M %p") + " ET"


def demo_live(slug, cache={}):
    """https://<slug>.utopiamodels.ai answers 200: the demo is built (vsl_cadence.py probe, minus the noindex check)."""
    if slug not in cache:
        try:
            req = urllib.request.Request(f"https://{slug}.{DEMO_DOMAIN}/", headers={"User-Agent": "eagle-upwork-feed"})
            cache[slug] = urllib.request.urlopen(req, timeout=8).status == 200
        except Exception:  # noqa: BLE001
            cache[slug] = False
    return cache[slug]


def letter(r, p):
    """The proposal text as sent: the ledger row's own `proposal` (the auto sends), else the store's letter file."""
    if (r or {}).get("proposal"):
        return str(r["proposal"]), "ledger proposal_sent row"
    f = (p or {}).get("letter_file") or (r or {}).get("letter_file")
    if f:
        try:
            return Path(f).read_text(errors="replace").strip(), Path(f).name
        except OSError:
            return None, f"{Path(f).name} (not readable)"
    return None, None


def next_action(a, now):
    """What to do next on one sent proposal (knowledge#14455): apply first, then a VSL edited into the proposal, then a
    Polymarket-type demo; past that, the client's own stage decides."""
    st, v, d = a["status"], a["vsl"], a["demo"]
    if st == "declined":
        return "none: declined"
    if st == "hired":
        c = a.get("contract") or {}
        f = next((m for m in c.get("milestones", []) if m["state"] == "funded"), None)
        return f"deliver M{f['n']}, then ask for the release" if f else "deliver, then invoice"
    if st in ("interview", "call"):
        return f"prep for the {st}"
    if st == "replied":
        return "reply to the client" + ("" if v["attached"] else " with a VSL")
    if not v["attached"]:
        sent = ts_of({"ts": a["sentAt"]}) if a.get("sentAt") else None
        closes = sent + EDIT_WINDOW_S if sent else None
        viewed = (a.get("stages") or {}).get("viewed")
        if (closes and now >= closes) or viewed:   # past the edit window: the video goes with the reply to the client
            if v["recorded"] or (a.get("_generic") and v["verdict"] != "RECORD_CUSTOM"):
                return "VSL ready; posts in the room when the client replies"
            kind = "custom" if v["verdict"] == "RECORD_CUSTOM" else "generic"
            return f"record the {kind} VSL; it posts in the room when the client replies"
        by = f" · edit window closes {clock(closes)}" if closes else ""
        if v["recorded"]:
            return "edit the proposal: attach the recorded VSL" + by
        if v["verdict"] == "RECORD_CUSTOM":
            return "record the custom VSL, then edit it into the proposal" + by
        return ("edit the proposal: attach the generic VSL" if a.get("_generic") else
                "record the generic VSL, then edit it into the proposal") + by
    if d["slug"] and not d["live"]:
        return f"finish the demo ({d['slug']})"
    if not d["live"]:
        return "build a Polymarket-type demo"
    sent = ts_of({"ts": a["sentAt"]}) if a.get("sentAt") else now
    if now - sent >= FOLLOW_D * 86400:
        return "follow up"
    return "wait for a reply · follow up " + dt.datetime.fromtimestamp(sent + FOLLOW_D * 86400, dt.timezone.utc).strftime("%b %-d")


def applied(rows, props, cons, now):
    """Every job with a sent proposal, newest send first, with all the store holds on it (knowledge#14455): the
    proposal text, bid, Connects, the job post as read (title, link, budget, client line, fit score and why), the
    client's stage dates, the VSL (attached = arm E/F or a video_sent/vsl_sent row; recorded = a take in the outbox)
    and the demo (the job's vsl_pick / page slug, built = its page answers 200), and the next action."""
    k_of = lambda r: key_of(r.get("job") or r.get("key") or r.get("link") or r.get("url"))  # noqa: E731
    by, client_job = {}, {}
    for r in rows:
        if r.get("client") and k_of(r):
            client_job[who(r["client"])] = k_of(r)
    for r in rows:   # a row that names only the client (the hand vsl_sent row) lands on that client's job
        k = k_of(r) or (client_job.get(who(r.get("client"))) if r.get("client") else None)
        if k:
            by.setdefault(k, []).append(r)
    store = {}
    if DB.exists():
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        store = {key_of(p["job_key"] or p["job_url"]): dict(p) for p in db.execute("select * from proposals")}
    takes = {}
    try:
        for f in OUTBOX.glob("*/*.mp4"):
            takes.setdefault(key_of(f.name.split("--")[0]), f.name)
    except OSError:
        pass
    try:   # the generic proposal video, once recorded (/srv/upwork-vsl/generic, vsl_cadence.py)
        generic = any(OUTBOX.parent.joinpath("generic").glob("*.mp4"))
    except OSError:
        generic = False
    con = {key_of(c.get("url")): c for c in cons if c.get("url")}
    out = []
    for p in props:
        k = p["key"]
        rs, sp = by.get(k, []), store.get(k) or {}
        sent_row = next((r for r in reversed(rs) if r.get("event") == "proposal_sent"), {})
        text, src = letter(sent_row, sp)
        read = [r for r in rs if r.get("event") == "job_read"]
        scored = next((r for r in reversed(rs) if r.get("event") == "scored"), {})
        job = {"budget": "", "client": "", "fit": None, "score": scored.get("score"), "why": scored.get("reasons") or [],
               "posted": None, "competition": sent_row.get("proposals_when_sent") or sp.get("proposals_when_sent")}
        for r in read:
            job["budget"] = r.get("budget") or job["budget"]
            job["client"] = r.get("client_line") or job["client"]
            job["fit"] = r.get("fit") if r.get("fit") is not None else job["fit"]
            if r.get("proposals") and not job["competition"]:
                job["competition"] = r["proposals"]
        job["budget"] = job["budget"] or scored.get("budget") or ""
        if not job["client"]:
            job["client"] = next((re.sub(r"^\+\d+ client \((.*)\)$", r"\1", w) for w in job["why"] if "client (" in str(w)), "")
        posted = sent_row.get("posted_at") or sp.get("posted_at") or scored.get("published")
        if isinstance(posted, (int, float)):
            posted = iso(posted)
        job["posted"] = posted or next((r.get("mail_at") for r in read if r.get("mail_at")), None)
        vrows = [r for r in rs if r.get("event") in ("video_sent", "vsl_sent")]
        kinds = {"E": "generic", "F": "custom"}
        vsl = {"attached": bool(vrows or sp.get("arm") in kinds or sp.get("vsl_id")),
               "kind": kinds.get(sp.get("arm")) or (kinds.get(vrows[-1].get("arm")) if vrows else None),
               "at": iso(vrows[-1]["_t"]) if vrows else None, "file": (vrows[-1].get("file") if vrows else None) or takes.get(k),
               "recorded": bool(takes.get(k) or vrows), "verdict": sp.get("vsl_verdict")}
        pick = next((r for r in reversed(rs) if r.get("event") == "vsl_pick" and r.get("slug")), {})
        slug = sp.get("page_slug") or pick.get("slug")
        demo = {"slug": slug, "url": f"https://{slug}.{DEMO_DOMAIN}/" if slug else None,
                "live": bool(slug) and demo_live(slug), "picked": iso(pick["_t"]) if pick else None, "big": bool(pick.get("big"))}
        stages = {s: sp.get(f"{s}_at") for s in ("viewed", "replied", "interview", "call", "hired", "declined") if sp.get(f"{s}_at")}
        for r in rs:
            if r.get("event") == "client_reply":
                stages.setdefault("replied", iso(r["_t"]))
            elif r.get("event") == "hired":
                stages.setdefault("hired", iso(r["_t"]))
        a = {"key": k, "title": p.get("title") or "", "url": p.get("url"), "sentAt": p.get("sentAt"), "bid": p.get("bid"),
             "bidType": (sent_row.get("bid") or [None])[0] if isinstance(sent_row.get("bid"), list) else None,
             "connects": p.get("connects"), "boost": sp.get("boost_connects") or sent_row.get("boost_connects"),
             "arm": sp.get("arm") or sent_row.get("arm"), "status": p.get("status"), "statusAt": p.get("statusAt"),
             "stages": stages, "proposal": text, "proposalSrc": src,
             "thesis": letter_lint.thesis(text) if text else None, "lint": letter_lint.lint(text) if text else None,
             "answers": [x for x in (sent_row.get("answers") or []) if x] if isinstance(sent_row.get("answers"), list) else [],
             "proposalId": sp.get("proposal_id") or sent_row.get("proposal_id"),
             "minSincePost": sp.get("min_since_post") or sent_row.get("min_since_post"),
             "job": job, "vsl": vsl, "demo": demo, "contract": con.get(k)}
        a["pipeline"] = pipeline(rs, a)
        a["statusWord"] = status_word(True, True, True, stages)
        a["_generic"] = generic
        a["next"] = next_action(a, now)
        del a["_generic"]
        out.append(a)
    return sorted(out, key=lambda a: a.get("sentAt") or "", reverse=True)


def measure():
    rows = ledger()
    props = proposals(rows)
    now = time.time()
    day = [p for p in props if p.get("sentAt") and ts_of({"ts": p["sentAt"]}) > now - 86400]
    reps = replies(rows)
    cons = contracts(rows, props)
    wrote = {who(x["client"]) or x["ts"] for x in reps if ts_of(x) > now - 86400}   # clients who wrote, not their messages
    app = applied(rows, props, cons, now)
    drop = set(triage.no_reply(app, now))
    for a in app:
        a["noReply"] = a["key"] in drop   # sent >= 7 d, the client never wrote: off the active views, kept under 'No reply'
    sent_keys = {p["key"] for p in props if p.get("sentAt")}
    return {"schema": "upwork/1", "computedAt": iso(now),
            "source": {"jobs": f"ledger job_read rows ({BOX} Upwork job alert mail, mail_watch.py)", "ledger": str(LEDGER),
                       "proposals": str(DB)},
            "jobs": jobs(rows, now), "intake": intake(rows, now), "proposals": props, "contracts": cons, "replies": reps,
            "applied": app, "triage": triage.triage_rows(jobs(rows, now, None), sent_keys, {}, now, autosend_blocks()),
            "funnel": {"sent": len(app), "noReply": len(drop), "active": len(app) - len(drop)}, "matches": matches(rows, props),
            "h24": {"sent": len(day), "answered": len(wrote)}}


def autosend_blocks():
    """{job id digits: autosend block} from the builder's stages-feed.json (oneshot_auto.py feed): the countdown Eagle Eye shows on a READY job (knowledge#18249)."""
    p = os.environ.get("ONESHOT_STAGES_FEED") or os.path.join(os.environ.get("ONESHOT_AUTO_DIR") or os.path.expanduser("~/.claude/state/net/oneshot-auto"), "stages-feed.json")
    try:
        jobs_ = json.load(open(p)).get("jobs", [])
    except (OSError, ValueError):
        return {}
    # #19257: the 60-minute bar rides the same block (Tyler views one-shots in Eagle Eye, not the OCC); every field is read from the job stamps
    bar = lambda r: {k: r.get(k) for k in ("bar_min", "detected_to_sent_min", "within_bar", "prereview_rebuilds", "stage_min")}  # noqa: E731
    return {re.sub(r"\D", "", str(r["job"])): dict(r["autosend"], hold=r.get("send_hold"), **bar(r)) for r in jobs_ if r.get("job") and r.get("autosend")}


def kv_put(body):
    get = lambda k: subprocess.run(["cred", "get", "fleet-infra", k], capture_output=True, text=True).stdout.strip()  # noqa: E731
    tok, acct = get("CF_API_TOKEN_UTOPIA"), get("CF_ACCOUNT_ID_UTOPIA")
    if not tok or not acct:
        raise SystemExit("upwork_feed: CF token or account id missing from cred")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces/{NS}/values/upwork"
    req = urllib.request.Request(url, data=body, method="PUT", headers={"Authorization": f"Bearer {tok}"})
    return urllib.request.urlopen(req, timeout=30).status


def main():
    try:
        d = measure()
    except Exception as e:  # noqa: BLE001
        print(f"upwork_feed: MEASURE FAILED, nothing pushed: {e!r}"[:400], file=sys.stderr)
        return 1
    body = json.dumps(d, ensure_ascii=False).encode()
    if "--stdout" in sys.argv:
        print(body.decode())
        return 0
    print(f"{d['computedAt']} jobs={len(d['jobs'])} proposals={len(d['proposals'])} contracts={len(d['contracts'])} "
          f"replies={len(d['replies'])} applied={len(d['applied'])} kv={kv_put(body)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
