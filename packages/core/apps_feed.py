#!/usr/bin/env python3
"""apps_feed.py: the applications section of Eagle Eye (cold apps + each application's campaign), KV key `apps`.

Spec: fleet-memory agent/feedback_cold_apps_view_spec.md (Tyler 2026-11-15) and
net/work/specs/cold-apps-system-2026-11-15.md section 3.7. Every row is read from a store; nothing is invented, and a
store that is missing is named in `sources` with its status.

How it runs: this file is APPENDED to feed.py's source (without feed.py's __main__ block) and piped to python3 as
horus on novaserver, the same way refresh-data.py runs feed.py, so it reuses feed.py's readers (_norm, _clean,
dream_tiers, jl, probe ...). Output: one JSON object on stdout.

    python3 apps-push.py --print             # build once, print the totals (from any box with nova ssh)
    python3 apps-push.py --push [--loop 30]  # build and PUT it into KV eagle-eye-data key `apps` (every N s with --loop)

Read by: the Eagle Eye Worker's `/apps.json` (preview: eagle-dev on dev.eagle.utopiamodels.ai), and its `/data.json`
overlays `hunts_24h` so every hunt card reads the last 24 hours (Tyler 2026-11-15: "everything else is in clients and
network").
"""
# ── appended part: everything below runs after feed.py's definitions ──────────────────────────────────────────────
APPS_DETAIL_N = 300        # at least this many newest submitted applications carry their full record (the drawer)
APPS_DETAIL_DAYS = 14      # ...and every one inside this window does. Was 300 alone: 627 were sent in the 7 days to
                           # 2026-11-16, so 327 of last week's opened with an empty "More details" (knowledge#14258)
NOT_CAPTURED = "not captured"
SLA_S = 300                # Tyler's SLA: apply within 5 minutes of posting
_TZ = {"UTC": 0, "GMT": 0, "Z": 0, "EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7}

#: the campaign ledger sekhmet writes (net/work/_tools/campaigns/campaign.py) and the steps every campaign runs (data)
CAMPAIGNS = os.environ.get("NET_CAMPAIGN_LEDGER") or "/home/sekhmet/.local/state/net-campaigns/ledger.jsonl"
CAMPAIGN_STEPS = "net/work/outreach/campaign-steps.json"


#: the referral asks sekhmet has written (referral.py queue). knowledge#14599 showed each with Approve / Edit and held it
#: until Tyler approved; knowledge#14694 deleted that approval: every applied job's panel shows each queued text, which
#: the drain sends as it is.
REF_QUEUE = os.environ.get("NET_REFERRAL_QUEUE") or "/home/sekhmet/.local/state/net-campaigns/referral-queue.jsonl"


def pending_copy(rows, queue=None):
    """-> {company key: [{campaign, posting, channel, to, name, relationship, text, state, at}]}: every v3 referral
    ask in the queue with no referral_ask step yet (sent, skipped or failed for good), newest per person. `state` is
    `queued`: the text shown is the one that leaves, with no approval."""
    done = {((r.get("slug") or "") or (r.get("name") or "").lower()) for r in rows
            if r.get("type") == "step" and r.get("step") == "referral_ask" and r.get("state") in ("sent", "skipped", "replied")}
    latest = {}
    try:
        with open(queue or REF_QUEUE) as f:
            for line in f:
                try:
                    q = json.loads(line)
                except ValueError:
                    continue
                if q.get("v") != 3 or not q.get("campaign"):
                    continue   # pre-#14599 rows never send
                who = q.get("slug") or (q.get("name") or "").lower()
                if who and who not in done:
                    latest[(q["campaign"], who)] = q
    except OSError:
        return {}
    out = {}
    for (cid, who), q in latest.items():
        ch = q.get("channel") or "linkedin"
        to = f"linkedin:{q['slug']}" if ch == "linkedin" and q.get("slug") else (q.get("name") or "").lower()
        out.setdefault(_norm(q.get("co")), []).append({
            "campaign": cid, "posting": q.get("posting_id") or "", "role": q.get("role") or "", "channel": ch,
            "to": to, "name": q.get("name") or "", "relationship": q.get("relationship") or "",
            "text": q.get("text") or "", "state": "queued", "at": q.get("at") or ""})
    for v in out.values():
        v.sort(key=lambda x: x["name"])
    return out


def all_copy(rows, queue=None):
    """-> [{campaign, co, posting, role, channel, to, name, relationship, text, state, at}], newest first: EVERY v3
    referral text sekhmet wrote, sent ones included (`state` = the referral_ask step's state, else `queued`). Tyler,
    2026-11-17 (knowledge#14672): "I just want to see the copy of everything". Read-only; nobody approves it."""
    steps = {((r.get("slug") or "") or (r.get("name") or "").lower()): r.get("state") for r in rows
             if r.get("type") == "step" and r.get("step") == "referral_ask"}
    latest = {}
    try:
        with open(queue or REF_QUEUE) as f:
            for line in f:
                try:
                    q = json.loads(line)
                except ValueError:
                    continue
                if q.get("v") != 3 or not q.get("campaign"):
                    continue
                who = q.get("slug") or (q.get("name") or "").lower()
                if who:
                    latest[(q["campaign"], who)] = q
    except OSError:
        return []
    out = []
    for (cid, who), q in latest.items():
        ch = q.get("channel") or "linkedin"
        out.append({"campaign": cid, "co": q.get("co") or "", "posting": q.get("posting_id") or "", "role": q.get("role") or "",
                    "channel": ch, "to": f"linkedin:{q['slug']}" if ch == "linkedin" and q.get("slug") else (q.get("name") or "").lower(),
                    "name": q.get("name") or "", "relationship": q.get("relationship") or "", "text": q.get("text") or "",
                    "state": steps.get(who) or "queued", "at": q.get("at") or ""})
    out.sort(key=lambda x: x["at"], reverse=True)
    return out


def camp_ledger(candidate):
    """Tyler's campaign ledger, or another person's own (campaign.py --person; knowledge#14300)."""
    return CAMPAIGNS if candidate == TYLER else os.path.join(os.path.dirname(CAMPAIGNS), candidate, "ledger.jsonl")


#: sekhmet's clone (sekhmet; jobs-repo-refresh.timer keeps it on main every 5 min) holds the steps the campaigns run on;
#: horus's own clone is often on another run's branch, so it is only the fallback (knowledge#14340)
CAMPAIGN_STEPS_LIVE = os.environ.get("NET_CAMPAIGN_STEPS") or "/home/sekhmet/dev/utopia-models/knowledge/" + CAMPAIGN_STEPS


def camp_steps_for(candidate):
    """campaign-steps.json `steps` for Tyler; `people.<candidate>.steps` for anyone else ([] when they have none)."""
    d = None
    for path in (CAMPAIGN_STEPS_LIVE, P(KB, CAMPAIGN_STEPS)):
        try:
            d = json.load(open(path))
            break
        except (OSError, ValueError):
            continue
    if d is None:
        return []
    if candidate == TYLER:
        return d.get("steps") or []
    return ((d.get("people") or {}).get(candidate) or {}).get("steps") or []

ROLE_TYPES = [   # first match wins; the label is what the role filter shows
    ("Forward deployed", r"forward[- ]deployed|\bfde\b|solutions? engineer|customer engineer|deployment"),
    ("AI / ML", r"\bai\b|\bml\b|machine learning|\bllm|applied scien|research engineer|genai|agent|nlp|inference|model"),
    ("Platform / infra", r"platform|infra|sre|site reliab|devops|cloud|kubernetes|reliability|systems engineer|network"),
    ("Data", r"\bdata\b|analytics|etl|warehouse"),
    ("Security", r"secur|appsec|detection|threat"),
    ("Frontend", r"front[- ]?end|\bui\b|web engineer|react"),
    ("Mobile", r"mobile|ios|android"),
    ("Full-stack", r"full[- ]?stack"),
    ("Backend", r"back[- ]?end|api|server|distributed"),
    ("Software (general)", r"software|engineer|developer|swe|programmer"),
]


def role_type(role):
    r = (role or "").lower()
    for label, rx in ROLE_TYPES:
        if re.search(rx, r):
            return label
    return "Other"


def posted_time(v):
    """-> (utc datetime | None, date_only bool). Formats seen: ISO with zone, ISO date only, Workday's
    `2026-11-13T00:00:00` (a date with no time), and `Sep 13, 2026 11:29 AM MDT`."""
    if not v or not isinstance(v, str):
        return None, False
    s = v.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(T00:00:00(\.0+)?)?", s):
        return _t(s[:10]), True
    m = re.fullmatch(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) (\d{1,2}):(\d{2}) ([AP]M)(?: ([A-Z]{1,4}))?", s)
    if m:
        mon, d, y, hh, mm, ap, tz = m.groups()
        try:
            t = dt.datetime.strptime(f"{mon} {d} {y} {hh}:{mm} {ap}", "%b %d %Y %I:%M %p")
        except ValueError:
            return None, False
        off = _TZ.get(tz or "UTC")
        if off is None:
            return None, False
        return (t - dt.timedelta(hours=off)).replace(tzinfo=dt.timezone.utc), False
    t = _t(s)
    return t, False


def _person_files():
    """Tyler's own network people at companies: net/work/outreach/personal-network/*.md -> [{name, company, role, file, last}]."""
    out = []
    for f in sorted(glob.glob(P(KB, "net/work/outreach/personal-network/*.md"))):
        try:
            txt = open(f).read()
        except OSError:
            continue
        head = (txt.splitlines() or [""])[0].lstrip("# ").strip()
        name, company, role = head, None, None
        m = re.match(r"(.+?)\s+[—-]\s+(.+?)(?:\s*\(.*\))?$", head)
        if m:
            name, company = m.group(1).strip(), m.group(2).strip()
        m = re.search(r"\*\*Company / role:\*\*\s*([^\n·]+)(?:·\s*([^\n]+))?", txt)
        if m:
            company = re.sub(r"\s*\(.*?\)", "", m.group(1)).strip()
            role = (m.group(2) or "").strip() or None
        name = re.sub(r"\s+person brief.*$", "", name)
        dates = re.findall(r"\*\*(\d{4}-\d{2}-\d{2})", txt)
        out.append({"name": name[:60], "company": company, "role": role, "file": os.path.relpath(f, KB),
                    "last": max(dates) if dates else None,
                    "asked": bool(re.search(r"(?i)refer|referral|put (me|my name) in|submit (me|my)", txt))})
    return out


# ── THE UNIFORM APPLICATION RECORD (knowledge#14258) ─────────────────────────────────────────────────────────────────
# Every submit path (apply.py's Greenhouse/Lever/Gem playwright driver, the Ashby/Workable x-input driver, and the
# guest-form drivers for Workday, Oracle, SmartRecruiters, Robert Half) writes its own run record. The drawer shows
# ONE shape for all of them, read from the store, with "not captured" wherever a path did not keep a thing:
#   answers   every form question with the exact answer the form was left holding ([question, answer]); a private
#             one (contact, EEO, `pii` in the store) shows its question with its answer masked, never dropped
#   resume    the resume version id that was attached     cover      the cover letter / essay text, else None
#   evidence  confirmation screenshot + the page words that confirmed it (+ the employer's email id when recorded)
#   times     posted · started · submitted · finished · post→apply seconds
#   req       {"missing": [labels], "how": what decided it} — the required questions left unanswered, from the
#             form's own required marks; the panel shows it ONLY when something is missing
# `fields_seen` / `fields_filled` stay in the run record for debugging and never reach the page: "seen" counts every
# control the bot scanned (hidden proxies, duplicates, optional and EEO controls), so "15 of 55" read as 40 skipped.
PRIVATE = "private · stored, not shown"


def app_record(rec, resume, posted, date_only, at, tta):
    shots = rec.get("screenshots") or {}
    conf_shot = (shots.get("confirmation") or {}).get("name") if isinstance(shots.get("confirmation"), dict) else None
    filled_shot = (shots.get("filled") or {}).get("name") if isinstance(shots.get("filled"), dict) else None
    email = rec.get("confirmation_email_id") or rec.get("gmail_id")
    essays = {k: str(v) for k, v in (rec.get("essays_submitted") or {}).items() if v}
    cover = next((v for k, v in essays.items() if re.search(r"(?i)cover", k)), None)
    att = rec.get("resume_attached") or {}
    return {"driver": rec.get("driver"), "identity": rec.get("identity_email"),
            "confirmed_by": (rec.get("confirmed_by") or "")[:120], "employment": rec.get("employment_type"),
            "role_class": rec.get("role_class"), "answers": [],
            "resume": att.get("version_id") or (resume or {}).get("v") or (rec.get("resume_receipt") or {}).get("name")
            or NOT_CAPTURED,
            "cover": cover[:1500] if cover else None,
            "evidence": {"screenshot": conf_shot or (f"{filled_shot} (filled form; no confirmation shot)" if filled_shot
                                                    else NOT_CAPTURED),
                         "page": (rec.get("confirmed_by") or "")[:160] or NOT_CAPTURED,
                         "email": email or NOT_CAPTURED},
            "times": {"posted": _iso(posted) if posted else NOT_CAPTURED, "date_only": bool(date_only),
                      "started": rec.get("started_at") or NOT_CAPTURED,
                      "submitted": rec.get("submitted_at") or _iso(at) or NOT_CAPTURED,
                      "finished": rec.get("finished_at") or NOT_CAPTURED, "tta": tta},
            "req": {"missing": [], "how": NOT_CAPTURED}}


def _blank(v):
    return v is None or str(v).strip() in ("", "N/A", "None", "[]")


def add_questions(f, rows, rec):
    """Fill f["answers"] (and f["req"]) from the store's field_answers rows + the run record's own per-field list.

    One entry per question, in form order; a question the run answered twice (a guess, then a last-resort pick)
    keeps the answer the form was LEFT holding. The resume upload is the `resume` field, not a question."""
    raw = rec.get("field_answers") or []
    seen, out, req_flags, missing = {}, [], 0, []
    for ord_, label, grp, kind, final, intended, how, pii in rows:
        q = (label or "").strip()
        if not q or re.fullmatch(r"(?i)g-recaptcha-response|attach|resume(/cv)?|cv", q) or kind == "file":
            continue
        entry = raw[ord_] if ord_ < len(raw) and isinstance(raw[ord_], dict) else {}
        val = final if not _blank(final) else None
        req = entry.get("required")
        if req is not None:
            req_flags += 1
        key = q.lower()
        ans = PRIVATE if (pii and val is not None) else (str(val)[:400] if val is not None else
                                                         ("left blank (required)" if req else "left blank"))
        if key in seen:
            i = seen[key]
            if val is not None:
                out[i] = [q[:300], ans, bool(req)]
            continue
        seen[key] = len(out)
        out.append([q[:300], ans, bool(req)])
    f["answers"] = [[q, a] for q, a, _ in out]
    if req_flags:
        missing = [q for q, a, r in out if r and a.startswith("left blank")]
        f["req"] = {"missing": missing, "how": "the form's required marks, per question"}
    elif "required_empty" in rec:   # apply.py drivers before per-field marks: the pre-click required check
        missing = list(rec.get("required_empty") or []) + [u.get("label") for u in rec.get("unsatisfied_required") or []
                                                           if isinstance(u, dict) and u.get("label")]
        f["req"] = {"missing": missing, "how": "the pre-click required check (every required control filled)"}
    elif raw and all(isinstance(x, dict) and "action" in x for x in raw):   # guest-form drivers: a required
        # question with no answer is a `block`, and a block never clicks Submit
        missing = [x.get("label") for x in raw if x.get("action") == "block"]
        f["req"] = {"missing": missing, "how": "the driver's ledger (a required question with no answer blocks Submit)"}


#: whose applications: tyler = horus's own store; anyone else = the family desk's ledger (feed.py candidate_ledgers)
PEOPLE = ("tyler", "osman", "claire")


def apps_feed(now=None, candidate=TYLER):
    now = now or dt.datetime.now(dt.timezone.utc)
    me = candidate == TYLER   # the outreach stores, tier list and network are Tyler's; another person's campaign is empty until theirs exist
    day = now - dt.timedelta(hours=24)
    sources = {}
    tiers, tier_src = dream_tiers() if me else ({}, None)
    sources["tiers"] = tier_src or ("no dream list" if me else f"no tier list for {candidate} yet")
    db = P(STATE, "sf/apply/applications.db") if me else P(STATE, "sf/apply/candidates", candidate, "applications.db")
    sources["applications"] = f"applications.db ({probe(db)})"
    apps, resumes, fields, recs = [], {}, {}, {}
    if probe(db) == "ok":
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for sha, vid, url, first in c.execute("select sha256, version_id, snapshot_url, first_seen_at from resume_versions"):
            # knowledge#14839: only an http(s) link is a link; a candidate store once held a filesystem path here and
            # Eagle Eye rendered it as an href that 404'd. A path is shown as "not linked" instead.
            resumes[sha] = {"v": vid, "url": url if (url or "").startswith(("http://", "https://")) else None, "first": first}
        rows = c.execute("select posting_id, company, role, source, posting_url, ats, outcome, started_at, submitted_at,"
                         " resume_sha256, resume_variant, record_json from applications where " + SENT_SQL
                         + " order by coalesce(submitted_at, started_at) desc").fetchall()
        reach = {}   # posting_id -> work-location tag (Tyler lives in Egypt from 2026-01-04; knowledge#6560)
        if c.execute("select 1 from sqlite_master where name='posting_residency'").fetchone():
            for pid_, res_, con_ in c.execute("select posting_id, residency, contract from posting_residency"):
                reach[pid_] = "contract" if con_ else {"worldwide": "global-remote", "us_resident": "us-remote-only"}.get(res_, "unknown")
        for i, (pid, co_, role, src, url, ats, outcome, started, submitted, rsha, rvar, rj) in enumerate(rows):
            try:
                rec = json.loads(rj or "{}")
            except ValueError:
                rec = {}
            at = _t(submitted or started)
            pt, date_only = posted_time(rec.get("posted_date"))
            tta = int((at - pt).total_seconds()) if (at and pt and not date_only and at >= pt) else None
            a = {"id": pid, "co": (_clean(co_) or co_ or "")[:80], "k": _norm(co_) or "", "role": (role or "")[:140],
                 "rt": role_type(role), "ats": ats or "", "src": src or "", "url": url or "", "out": outcome,
                 "at": _iso(at), "posted": _iso(pt), "tta": tta, "rv": rvar or "", "r": (resumes.get(rsha) or {}).get("v"),
                 "loc": (rec.get("location") or "")[:60], "lvl": rec.get("level") or "", "wk": reach.get(pid, "unknown")}
            if date_only:
                a["pd"] = 1   # the ATS gives the posting date only, so time-to-apply cannot be measured under a day
            if i < APPS_DETAIL_N or (at and at >= now - dt.timedelta(days=APPS_DETAIL_DAYS)):
                a["d"] = 1
                fields[pid] = app_record(rec, resumes.get(rsha), pt, date_only, at, tta)
                recs[pid] = rec
            apps.append(a)
        if fields:
            qs = ",".join("?" * len(fields))
            rows_by = {}
            for r in c.execute(f"select app_id, ord, label, grp, kind, final_value, intended_value, match_type, pii "
                               f"from field_answers where app_id in ({qs}) order by app_id, ord", list(fields)):
                rows_by.setdefault(r[0], []).append(r[1:])
            for app_id, f in fields.items():
                add_questions(f, rows_by.get(app_id, []), recs[app_id])
        interviews = [dict(zip(("company", "role", "posting_id", "start", "status", "stage", "outcome"), r))
                      for r in c.execute("select company, role, posting_id, start_utc, status, stage, outcome from interviews")]
        touch_sends = _sends(c)
        booked = _interviews_booked(db)
        c.close()
    else:
        interviews, touch_sends, booked = [], [], {"weeks": {}, "stale_scheduled": []}
    # companies: the join key across applications, cold email, LinkedIn and Tyler's network
    cos = {}

    def co(name):
        k = _norm(name)
        if not k:
            return None
        if k not in cos:
            t = tiers.get(k)
            cos[k] = {"name": (_clean(t["name"]) if t else None) or _clean(name) or name, "tier": t["tier"] if t else None,
                      "apps": 0, "a24": 0, "roles": {}, "emails": [], "replies": [], "li": [], "people": [],
                      "contacts": 0, "stage": None, "stage_at": None, "last": None}
        return cos[k]
    for a in apps:
        x = co(a["co"])
        if not x:
            continue
        x["apps"] += 1
        x["a24"] += bool(a["at"] and a["at"] >= _iso(day))
        x["roles"][a["rt"]] = x["roles"].get(a["rt"], 0) + 1
        x["last"] = max(x["last"] or "", a["at"] or "") or None
        if a["url"] and len(x.setdefault("urls", [])) < 3 and a["url"] not in x["urls"]:
            x["urls"].append(a["url"])
    if not me:   # every store below is Tyler's own outreach
        none = "/nonexistent"
        em_path = rp_path = pipe_path = li = contacts_path = none
    else:
        em_path, rp_path = P(STATE, "sf/outreach/emails.jsonl"), P(STATE, "sf/outreach/replies.jsonl")
        pipe_path, li = P(STATE, "sf/outreach/pipeline.jsonl"), P(KB, "net/work/outreach/linkedin-log.csv")
        contacts_path = P(KB, "net/work/outreach/contacts.jsonl")
    sources["cold_email"] = f"emails.jsonl ({probe(em_path)}) + replies.jsonl ({probe(rp_path)}); SalesBlaster: " + \
        ("audience-c.jsonl" if os.path.exists(P(KB, "net/work/outreach/audience-c.jsonl")) else "not recorded yet (no export)")
    seen = set()
    for r in jl(em_path):
        if r.get("direction") != "out" or r.get("status") != "sent":
            continue
        x = co(r.get("company"))
        if x is None:
            continue
        x["emails"].append({"at": _iso(_t(r.get("sent_at") or r.get("ts"))), "to": r.get("to_email") or "",
                            "kind": r.get("kind") or "", "touch": r.get("touch") or "", "subject": (r.get("subject") or "")[:140],
                            "from": r.get("identity") or ""})
    inbound = []
    for r in jl(rp_path):
        mid = r.get("gmail_message_id")
        if mid and mid in seen:
            continue
        seen.add(mid)
        x = co(r.get("company"))
        rep = {"at": _iso(_t(r.get("ts"))), "from": r.get("from_email") or "", "snippet": (r.get("snippet") or "")[:220]}
        if x is not None:
            x["replies"].append(rep)
        inbound.append({**rep, "co": x["name"] if x else (r.get("company") or ""), "k": _norm(r.get("company")) or ""})
    if not me:   # knowledge#14304: the person's own mailbox, answered by their agent (milli-scout/person_inbox.py)
        for r in jl(P("/var/tmp/person-inbox", candidate + ".jsonl")):
            if not r.get("company"):
                continue
            x = co(r.get("company"))
            rep = {"at": r.get("at") or "", "from": "", "snippet": (r.get("snippet") or "")[:220],
                   "class": r.get("class") or "", "action": r.get("action") or "", "minutes": r.get("minutes")}
            if x is not None:
                x["replies"].append(rep)
            inbound.append({**rep, "co": x["name"] if x else r["company"], "k": _norm(r["company"]) or ""})
    for r in jl(pipe_path):
        x = co(r.get("company") or r.get("key"))
        if x is None:
            continue
        sa = _iso(_t(r.get("stage_at")))
        if x["stage_at"] is None or (sa or "") >= x["stage_at"]:
            x["stage"], x["stage_at"] = r.get("stage"), sa
    sources["stages"] = "pipeline.jsonl (ATS / recruiter answers per company)"
    if probe(li) == "ok":
        with open(li, newline="") as f:
            for r in csv.DictReader(f):
                x = co(r.get("company"))
                if x is not None:
                    x["li"].append({"at": r.get("date"), "name": r.get("name"), "title": r.get("title"),
                                    "channel": r.get("channel"), "status": r.get("status")})
    cl = camp_ledger(candidate)
    camp_rows = jl(cl) if probe(cl) == "ok" else []
    camp_slugs = {r.get("slug") for r in camp_rows if r.get("type") == "person"}
    camp_names = {(r.get("name") or "").lower(): r.get("co") for r in camp_rows if r.get("type") == "person"}
    li_unjoined = 0
    if me and probe(LINKEDIN) == "ok":   # the LinkedIn lane ledger: every row is its company's touch
        led = jl(LINKEDIN)
        who = {**camp_names, **{(r.get("recruiter") or "").lower(): r.get("company") for r in led if r.get("company")}}
        for r in led:
            if r.get("stage") in ("checkpoint", "resumed"):
                continue
            m = re.search(r"linkedin\.com/in/([^/?#]+)", r.get("thread_url") or "")
            if m and m.group(1) in camp_slugs:
                continue   # a campaign send: its step row already shows it
            cname = r.get("company") or who.get((r.get("recruiter") or "").lower())
            x = co(cname) if cname else None
            if x is None:
                li_unjoined += 1
                continue
            x["li"].append({"at": _iso(_t(r.get("ts"))), "name": r.get("recruiter"), "title": r.get("role") or "",
                            "channel": "linkedin", "status": (r.get("stage") or "").replace("_", " ")})
    sources["linkedin"] = f"linkedin-log.csv ({probe(li)}); lane ledger {probe(LINKEDIN)}" + \
        (f" ({li_unjoined} rows name no company)" if li_unjoined else "")
    if me:   # the cold-domain sequences and audience ledgers (the old Cold Email lane): each send is its company's touch
        for path in sorted(glob.glob(P(KB, "net/work/outreach/campaigns/*.jsonl"))):
            meta = js(path[:-1]) or {}
            cname = meta.get("company") or os.path.basename(path)[:-6]
            for r in jl(path):
                x = co(r.get("company") or cname)
                if x is not None and r.get("kind") == "send" and not r.get("dry"):
                    x["emails"].append({"at": _iso(_t(r.get("ts"))), "to": r.get("email") or "", "kind": "sequence",
                                        "touch": r.get("touch") or "", "subject": (r.get("subject") or "")[:140],
                                        "from": r.get("from") or "", "name": r.get("name") or ""})
                elif x is not None and r.get("kind") == "reply":
                    x["replies"].append({"at": _iso(_t(r.get("ts"))), "from": r.get("email") or "",
                                         "snippet": (r.get("snippet") or "")[:220]})
        for path in (P(KB, "net/work/outreach/audience-b.jsonl"), P(KB, "net/work/outreach/audience-c.jsonl")):
            rows = jl(path)
            sends = {r.get("id"): r for r in rows if r.get("kind") == "send" and r.get("id")}
            for r in rows:
                if r.get("proof") or r.get("dry"):
                    continue   # a proof send to Tyler's own address is not a company's touch
                base = r if r.get("company") else sends.get(r.get("send_id")) or {}
                x = co(base.get("company")) if base.get("company") and not base.get("proof") else None
                if x is None:
                    continue
                if r.get("kind") == "send":
                    x["emails"].append({"at": _iso(_t(r.get("ts"))), "to": r.get("email") or "", "kind": "audience",
                                        "touch": r.get("touch") or "", "subject": (r.get("subject") or "")[:140],
                                        "from": r.get("sender") or "", "name": r.get("name") or ""})
                elif r.get("kind") in ("reply", "bounce"):
                    x["replies"].append({"at": _iso(_t(r.get("ts"))), "from": r.get("from") or r.get("email") or base.get("email") or "",
                                         "snippet": ("Bounced: " if r["kind"] == "bounce" else "") + (r.get("snippet") or r.get("reason") or "")[:220]})
    for p in (_person_files() if me else []):
        x = co(p["company"]) if p["company"] else None
        if x is not None:
            x["people"].append(p)
    for p in (((js(P(STATE, ROSTER)) or {}).get("people_rows") or []) if me else []):
        if p.get("in_contacts") and p.get("referral_ok") and p.get("company"):
            x = cos.get(_norm(p["company"]))   # only companies already in the campaign join
            if x is not None:
                x.setdefault("referrers", []).append({"name": (p.get("name") or "")[:60], "title": (p.get("title") or "")[:80]})
    sources["referrers"] = f"{ROSTER} people_rows with in_contacts + referral_ok (Tyler's phone contacts)"
    sources["network"] = "net/work/outreach/personal-network/*.md (people Tyler knows); referral asks are not logged as rows yet"
    for r in jl(contacts_path):
        k = _norm(r.get("company"))
        if k in cos:
            cos[k]["contacts"] += 1
    # traction (outputs): who answered, interviews, inbound, and the campaign that drove each one
    def via(k, at=None):
        x = cos.get(k) or {}
        ems = [e for e in x.get("emails") or [] if e["at"] and (at is None or e["at"] <= at)]
        parts = []
        if x.get("apps"):
            parts.append("application")
        if ems:
            parts.append(f"cold email ({len(ems)})")
        if x.get("li"):
            parts.append("LinkedIn")
        if x.get("people"):
            parts.append("network")
        return " + ".join(parts) or "inbound (no campaign)"
    responded = sorted(({"co": x["name"], "k": k, "stage": x["stage"], "at": x["stage_at"], "via": via(k, x["stage_at"]),
                         "tier": x["tier"]} for k, x in cos.items() if x["stage"]), key=lambda r: r["at"] or "", reverse=True)
    ivs = []
    for v in interviews:
        k = _norm(v["company"])
        ivs.append({**v, "co": (cos.get(k) or {}).get("name") or v["company"], "k": k or "", "via": via(k, v["start"])})
    ivs.sort(key=lambda r: r["start"] or "", reverse=True)
    inbound.sort(key=lambda r: r["at"] or "", reverse=True)
    for r in inbound:
        r["via"] = via(r["k"], r["at"])
    # the last 24 hours (Tyler 2026-11-15: hunts show 24 h output, never all-time totals)
    a24 = [a for a in apps if a["at"] and a["at"] >= _iso(day)]
    t24 = sorted(a["tta"] for a in a24 if a["tta"] is not None)
    totals = {"applied_24h": len(a24), "under_sla_24h": sum(1 for x in t24 if x <= SLA_S), "timed_24h": len(t24),
              "median_tta_24h": t24[len(t24) // 2] if t24 else None,
              "answers_24h": sum(1 for r in responded if (r["at"] or "") >= _iso(day)) + sum(1 for r in inbound if (r["at"] or "") >= _iso(day)),
              "interviews_next": sum(1 for v in ivs if (v["start"] or "") >= _iso(now) and v["status"] not in ("cancelled",)),
              "applied_all": len(apps), "interviews_booked_week": _week_booked(booked, now), "interviews_booked_weeks": booked["weeks"],
              "interviews_stale_scheduled": len(booked["stale_scheduled"]), "sends_total": len(touch_sends)}
    # YOUR NETWORK HERE (network_here.py): who Tyler knows at each company he applied to, and the LinkedIn lookup queue
    if me:
        try:
            for k, x in cos.items():
                if x["apps"]:
                    n = network_at(x["name"], *x.get("urls", []), now=now)
                    if n.get("wn") or n.get("kn"):
                        x["net"] = {f: n[f] for f in ("works", "wn", "knows", "kn")}
            write_queue([(x["name"], k, x["last"], x.get("urls", [])) for k, x in cos.items() if x["apps"]])
            sources["network_here"] = network_index()[1]
        except Exception as e:  # noqa: BLE001  the panel section degrades to "No one yet", never the whole feed
            sources["network_here"] = f"failed: {type(e).__name__}: {str(e)[:160]}"
    camp_steps = camp_steps_for(candidate)
    sources["campaigns"] = (f"campaign ledger {cl} ({probe(cl)}, {len(camp_rows)} rows) + {CAMPAIGN_STEPS}"
                            if camp_steps else f"no campaign steps for {candidate} yet")
    by_co = {}
    for a in apps:
        by_co.setdefault(a["k"], []).append(a)
    camp_by_k = {}
    for r in camp_rows:
        k = _norm(r.get("co"))
        if k:
            camp_by_k.setdefault(k, []).append(r)
    copy_by_k = pending_copy(camp_rows) if candidate == TYLER else {}
    sources["pending_copy"] = f"{REF_QUEUE} v3 rows ({probe(REF_QUEUE)})"
    out_cos = {}
    for k, x in cos.items():
        if camp_steps and x["apps"]:
            x["campaign"] = campaign(by_co.get(k) or [], camp_by_k.get(k) or [], camp_steps, x, now)
            x["campaign"]["copy"] = copy_by_k.get(k) or []
        x.pop("urls", None)
        if not (x["apps"] or x["emails"] or x["people"] or x["li"] or x["tier"] is not None or x["stage"]):
            continue
        out_cos[k] = {**x, "roles": sorted(x["roles"].items(), key=lambda kv: -kv[1]), "emails": _dedupe(sorted(x["emails"], key=lambda e: e["at"] or "")),
                      "replies": sorted(x["replies"], key=lambda r: r["at"] or "")}
    tier_rows = [{"k": k, "name": v["name"], "tier": v["tier"], "why": v["why"]} for k, v in
                 sorted(tiers.items(), key=lambda kv: (kv[1]["tier"], kv[1]["name"]))]
    return {"updated": _iso(now), "sla_s": SLA_S, "totals": totals, "apps": apps, "fields": fields, "resumes": resumes,
            "companies": out_cos, "tiers": tier_rows, "traction": {"responded": responded[:80], "interviews": ivs, "inbound": inbound[:60]}, "sends": touch_sends,
            "copy": all_copy(camp_rows) if candidate == TYLER else [],
            "hunts_24h": hunts_24h(now) if me else {}, "sources": sources, "campaign_steps": camp_steps, "detail_n": APPS_DETAIL_N, "candidate": candidate}


SENDS_CAP = 300   # newest sent touches carried in the feed; the sends tab shows each one's text (knowledge#16088)
BOOKED_SCRIPT = "_infra/scripts/sekhmet/interviews-booked.py"   # sekhmet's counter (knowledge#15298); used, never copied


def _sends(c):
    """Every sent campaign touch, newest first, with the text that went out: [{at, co, job, person, to, subject, body,
    body_sha, transport, message_id, channel, posting}]. A store older than schema 8 has no body column -> []."""
    cols = {r[1] for r in c.execute("pragma table_info(touches)")}
    if "body" not in cols:
        return []
    out = []
    for r in c.execute("select sent_at, coalesce(target_company, company_key), target_job, to_name, to_addr, subject, body, body_sha, "
                       "transport, message_id, channel, posting_id from touches where status='sent' "
                       "order by sent_at desc, id desc limit ?", (SENDS_CAP,)):
        out.append(dict(zip(("at", "co", "job", "person", "to", "subject", "body", "body_sha", "transport", "message_id", "channel", "posting"), r)))
    return out


def _interviews_booked(db):
    """sekhmet's interviews-booked.py --json over this store: {weeks: {ISO week: {booked, ...}}, stale_scheduled: [...]}."""
    import subprocess
    try:
        r = subprocess.run([sys.executable, P(KB, BOOKED_SCRIPT), "--weeks", "8", "--json"], capture_output=True, text=True, timeout=30,
                           env={**os.environ, "NET_APPLICATIONS_DB": str(db)})
        return json.loads(r.stdout) if r.returncode == 0 else {"weeks": {}, "stale_scheduled": []}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"weeks": {}, "stale_scheduled": []}


def _week_booked(booked, now):
    """Interviews booked (non-cancelled rows) in `now`'s ISO week; 0 when the week has none."""
    y, w, _ = now.isocalendar()
    return (booked["weeks"].get(f"{y}-W{w:02d}") or {}).get("booked", 0)


def _dedupe(emails):
    """One row per email: the same send can sit in emails.jsonl and a sequence ledger."""
    out, seen = [], set()
    for e in emails:
        key = (e.get("to") or "").lower(), (e.get("subject") or "").lower(), (e.get("at") or "")[:16]
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def job_template(role):
    """The job post's role type and its template's state (net/work/_tools/jobs/sekhmet_guard.py, knowledge#14619):
    {role_type, label, s: ready | no template, file, steps}. Nothing sends for this job while s = no template; nobody
    approves a template (knowledge#14694)."""
    try:
        sys.path.insert(0, os.path.join(KB, "net/work/_tools/jobs"))
        import sekhmet_guard  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001  the drawer degrades to "template state unknown", never the whole feed
        return {"role_type": "", "s": f"unknown ({type(e).__name__})"}
    rt = sekhmet_guard.role_type(role)
    t = sekhmet_guard.template(rt) or {}
    ok = sekhmet_guard.approved(rt)
    return {"role_type": rt, "label": t.get("label") or rt, "s": "ready" if ok else "no template",
            "file": f"net/work/outreach/role-templates/{rt}.json", "steps": t.get("steps") or {}}


def campaign(apps_here, rows, steps_cfg, x, now):
    """One company's campaign, derived on every read from the campaign ledger + the steps file (nothing stored twice):
    {people: [{slug, name, title, kind, why, steps: {id: {s, at, text?, why?}}}], skipped, vsl: [{posting, role, url}],
    size, hold_until, company_steps: {id: {s, ...}}, last}. A step's state: the newest `step` row for it, else
    `waiting` text for a channel that is not live, else held (`after` not reached, or a startup's first touch waiting
    up to `hold_max_h` for its VSL), else planned."""
    people, skip, size, vsl, stepped = {}, {}, None, {}, {}
    for r in sorted(rows, key=lambda r: r.get("at") or ""):
        t = r.get("type")
        if t == "person" and r.get("slug"):
            people[r["slug"]] = {"slug": r["slug"], "name": r.get("name") or "", "title": r.get("title") or "",
                                 "kind": r.get("kind") or "", "why": r.get("why") or "", "src": r.get("src") or "",
                                 **{k: r[k] for k in ("email", "email_check", "li") if r.get(k)}}
        elif t == "skip" and r.get("slug"):
            skip[r["slug"]] = r.get("why") or ""
        elif t == "company":
            size = r.get("size")
        elif t == "vsl" and r.get("posting"):
            vsl[r["posting"]] = r.get("url")
        elif t == "step" and r.get("step"):
            stepped[(r.get("slug") or "", r["step"])] = {"s": r.get("state"), "at": r.get("at"),
                                                         **({"text": r["text"]} if r.get("text") else {}),
                                                         **({"subject": r["subject"]} if r.get("subject") else {}),
                                                         **({"to": r["to"]} if r.get("to") else {}),
                                                         **({"via": r["channel"]} if r.get("channel") else {}),
                                                         **({"why": r["why"]} if r.get("why") else {})}
    newest = sorted(apps_here, key=lambda a: a["at"] or "", reverse=True)
    slots, seen_p = [], set()
    for a in newest:   # one VSL slot per job post, every post
        if a["id"] not in seen_p:
            seen_p.add(a["id"])
            slots.append({"posting": a["id"], **({"url": vsl[a["id"]]} if vsl.get(a["id"]) else {})})   # role: apps[]
    has_vsl = any(s.get("url") for s in slots)
    jobs = {a["id"]: job_template(a.get("role") or "") for a in newest}   # knowledge#14619: one campaign per job post
    first_app = _t(min((a["at"] for a in apps_here if a["at"]), default=None))
    hold_until = None

    def state(slug, st, per):
        got = stepped.get((slug, st["id"]))
        if got and got.get("s") == "ready" and not st.get("live", True):
            return {**got, "s": "written · " + (st.get("waiting") or "waiting")}
        if got:
            return got
        if st.get("only_if") == "network" and not x.get("referrers"):
            return {"s": "none"}   # nobody from Tyler's phone contacts at the company
        if not st.get("live", True):
            return {"s": st.get("waiting") or "waiting"}
        aft = st.get("after")
        if aft and (per.get(aft[0]) or {}).get("s") not in (aft[1], "replied"):
            return {"s": "planned", "why": f"after {aft[0].replace('_', ' ')} is {aft[1]}"}
        if st.get("hold_for") == "vsl" and not has_vsl and (not st.get("hold_if") or st["hold_if"] == size):
            until = first_app + dt.timedelta(hours=st.get("hold_max_h") or 24) if first_app else None
            if until is None or now < until:
                return {"s": "waiting on VSL", "until": _iso(until)}
        return {"s": "planned"}
    out_people = []
    for slug, p in people.items():
        if slug in skip:
            continue
        per = {}
        for st in steps_cfg:
            if st.get("per", "person") != "person":
                continue
            if (st.get("kinds") and p["kind"] not in st["kinds"]) or p["kind"] in (st.get("not_kinds") or ()):
                continue   # a connection's referral ask is not a stranger's connect (campaign-steps.json kinds)
            per[st["id"]] = state(slug, st, per)
        hold_until = hold_until or next((v.get("until") for v in per.values() if v.get("until")), None)
        out_people.append({**p, "steps": per})
    comp = {}
    for st in steps_cfg:
        if st.get("per") == "company":
            comp[st["id"]] = state("", st, comp)
    labels = {st["id"]: st.get("label") or st["id"] for st in steps_cfg}
    touches = [(v["at"], f"{labels.get(sid, sid)} to {p['name']}") for p in out_people for sid, v in p["steps"].items()
               if v.get("s") in ("sent", "accepted", "replied") and v.get("at")]
    touches += [(e["at"], f"email to {e.get('name') or e.get('to') or 'someone'}") for e in x["emails"] if e.get("at")]
    touches += [(l["at"], f"LinkedIn {l.get('status') or 'touch'} with {l.get('name') or 'someone'}") for l in x["li"] if l.get("at")]
    last = max(touches, default=None)
    order = {"connection": -2, "contact": -1, "hiring_manager": 0, "decision_maker": 1, "engineer": 2, "recruiter": 3}
    out_people.sort(key=lambda p: (order.get(p["kind"], 9), p["name"]))
    return {"people": out_people, "skipped": [{"slug": s, "name": (people.get(s) or {}).get("name") or s, "why": w}
                                              for s, w in skip.items()],
            "vsl": slots, "size": size, "hold_until": hold_until, "company_steps": comp, "jobs": jobs,
            "referrers": x.get("referrers") or [],
            "last": {"at": last[0], "what": last[1]} if last else None}


def apps_feeds(now=None):
    """{person: feed} for every person with a store (KV `apps` = tyler, `apps/<person>` = the others)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out = {}
    for cid in PEOPLE:
        if cid == TYLER or probe(P(STATE, "sf/apply/candidates", cid, "applications.db")) == "ok":
            out[cid] = apps_feed(now, cid)
    return out


def hunts_24h(now):
    """{lane: {sent, answered, window, what}} over the last 24 hours, from the same stores feed.py's hunts read."""
    day = now - dt.timedelta(hours=24)
    inwin = lambda t: bool(t and day <= t <= now)  # noqa: E731
    out = {}
    up = list({json.dumps(r, sort_keys=True): r for r in jl(P(STATE, "net/upwork/ledger.jsonl"))}.values())
    out["upwork"] = {"sent": len({r.get("key") or r.get("job") for r in up if r.get("event") == "proposal_sent" and inwin(_row_time(r))}),
                     "answered": len({r.get("client") or r.get("job") for r in up if r.get("event") == "client_reply" and inwin(_row_time(r))}),
                     "what": "proposals sent · clients who wrote, last 24 h"}
    db = P(STATE, "sf/apply/applications.db")
    sent = None
    if probe(db) == "ok":
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        sent = c.execute("select count(*) from applications where " + SENT_SQL
                         + " and coalesce(submitted_at,started_at)>=?", (_iso(day),)).fetchone()[0]
        c.close()
    pipe = [r for r in jl(P(STATE, "sf/outreach/pipeline.jsonl")) if inwin(_t(r.get("stage_at")))]
    out["cold_apps"] = {"sent": sent, "answered": len({(r.get("key") or r.get("company")) for r in pipe}),
                        "what": "applications submitted · companies that answered (any stage), last 24 h"}
    li = []
    if probe(P(KB, "net/work/outreach/linkedin-log.csv")) == "ok":
        with open(P(KB, "net/work/outreach/linkedin-log.csv"), newline="") as f:
            li = [r for r in csv.DictReader(f) if (r.get("date") or "") >= day.strftime("%Y-%m-%d")]
    led = [r for r in jl(LINKEDIN) if inwin(_row_time(r))] if probe(LINKEDIN) == "ok" else []
    out["linkedin"] = {"sent": len(li) + sum(1 for r in led if r.get("stage") == "invite_sent"),
                       "answered": sum(1 for r in li if (r.get("status") or "") in ("accepted", "replied")) + sum(1 for r in led if r.get("stage") == "replied"),
                       "what": "requests / messages sent · accepted or replied, last 24 h"}
    em = [r for r in jl(P(STATE, "sf/outreach/emails.jsonl")) if r.get("direction") == "out" and r.get("status") == "sent"
          and r.get("kind") == "opener" and inwin(_t(r.get("sent_at") or r.get("ts")))]
    rp = {r.get("gmail_message_id") or r.get("id") for r in jl(P(STATE, "sf/outreach/replies.jsonl")) if inwin(_t(r.get("ts")))}
    out["cold_email"] = {"sent": len(em), "answered": len(rp), "what": "first-touch emails sent · replies received, last 24 h"}
    ev = jl(P(STATE, "sf/events.jsonl"))
    out["in_person"] = {"sent": sum(1 for r in ev if inwin(_t(r.get("detected_at")))), "answered": None,
                        "what": "events found in the last 24 h; attendance is not recorded yet", "labels": ["found", "attended"]}
    for v in out.values():
        v["window"] = "last 24 h"
    return out
