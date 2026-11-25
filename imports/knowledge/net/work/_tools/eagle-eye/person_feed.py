#!/usr/bin/env python3
"""person_feed.py: one person's Eagle Eye feed, read from their own job-hunt ledger (knowledge#13617).

KV `p/<person>` adds a person's extra hunts and Network reason to their Eagle Eye home (handler-dev.js personData;
/p/claire and /p/osman now redirect there, knowledge#14303). Claire's search is her own. Her numbers come from her ledger Sheet
(net/work/_tools/client-desk/client_desk.py: one row per application or status change), never from Tyler's stores.
The output is the same shape the Eagle Eye UI reads (`hunts`, `roosts`, top-level stage totals), so the page is the
same UI with a per-person config (`/p/<person>` in the Worker; the open-source repo's `config.js` documents it).

    python3 person_feed.py claire              # print the feed JSON (measures the Sheet)
    python3 person_feed.py claire --push       # measure, then PUT it into KV eagle-eye-data key `p/claire`
    python3 person_feed.py osman --push        # a person with no ledger Sheet: their desk's apply store (below)
    python3 person_feed.py --self-test         # offline: the counting rules on a fixture ledger

A person with no `ledger_sheet` in client-desk/clients.json (Osman, knowledge#14129) is measured from their desk's apply
store instead, <apply root>/candidates/<person>/applications.db, the same store feed.py's `candidates` block reads:
  found = postings the desk worked · sent = outcome submitted or submitted_unconfirmed (feed.py SENT_SQL)
  came back = postings with a row in the store's `interviews` table (employer email replies are not in this store)
The store is horus's (mode 0660 + ACL): when this user cannot open it, the count runs as horus via `sudo -n -u eagle`.

Counting (per application = org + role + kind; its status is the newest row's):
  found      every application in the ledger (queued included)
  sent       applications that reached submitted or later (submitted, interview, offer, rejected; withdrawn only
             after a submitted row)
  replied    applications the employer answered: interview, offer or rejected
  interviews applications that reached interview or offer
  offers     applications with an offer
A failed read prints nothing and exits 1, so the pusher never overwrites a good feed with an empty one.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.environ.get("CLIENT_DESK_DIR") or os.path.join(HERE, "../client-desk")
KV_NS = "d97b9be8758d4ede805c0bf9c6d2e68c"   # eagle-eye-data (the Worker's DATA binding)
SENT = {"submitted", "interview", "offer", "rejected"}
REPLIED = {"interview", "offer", "rejected"}
INTERVIEW = {"interview", "offer"}
# a person's lanes: ledger `kind` -> the hunt key the page config names
APPLY_ROOT = os.environ.get("EAGLE_CANDIDATES_ROOT") or "/home/eagle/.claude/state/sf/apply/candidates"
AGENTS = {"claire": "claire-scout", "osman": "milli-scout"}   # the agent that works each person's roosts
SENT_SQL = "outcome in ('submitted','submitted_unconfirmed')"   # feed.py SENT_SQL
#: The "sent" a person's page shows (knowledge#14302): CONFIRMED submits, once per job URL, the same number
#: candidate-apply.py status prints and milli-scout / claire-scout read. /p/osman showed 34 (31 confirmed + 4
#: unconfirmed rows) beside milli-scout's 26; one definition ends that.
CONFIRMED_SQL = ("select count(distinct coalesce(nullif(posting_url, ''), posting_id)) from applications "
                 "where outcome = 'submitted'")
CAMP_ROOT = os.environ.get("NET_CAMPAIGN_ROOT") or "/home/sekhmet/.local/state/net-campaigns"   # campaign.py --person ledgers


def read_lines(path: str, owner: str) -> list | None:
    """The file's non-empty lines: read directly, else as the store's owner (`sudo -n -u <owner> cat`). None = unreadable
    (a missing file is [] only when we could tell), so the caller names the gap instead of showing a false empty."""
    try:
        with open(path) as f:
            return [x for x in f.read().splitlines() if x.strip()]
    except FileNotFoundError:
        return []
    except OSError:
        r = subprocess.run(["sudo", "-n", "-u", owner, "cat", path], capture_output=True, text=True, timeout=60, cwd="/")
        return [x for x in r.stdout.splitlines() if x.strip()] if r.returncode == 0 else None


def jl(lines: list) -> list:
    out = []
    for x in lines:
        try:
            out.append(json.loads(x))
        except ValueError:
            pass
    return out


def in_person(person: str, now: str | None = None) -> dict:
    """The In Person hunt + lane from candidates/<id>/in_person.jsonl (in_person_find.py writes it)."""
    lines = read_lines(os.path.join(APPLY_ROOT, person, "in_person.jsonl"), "horus")
    if lines is None:
        return {"hunt": {"sent": None, "answered": None, "status": "empty", "reason": "the in-person file is not readable by the feed"},
                "events": []}
    ev = sorted(jl(lines), key=lambda r: r.get("start") or "")
    now = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    up = [e for e in ev if (e.get("start") or "9") >= now]
    if not up:
        return {"hunt": {"sent": None, "answered": None, "status": "empty",
                         "reason": "no upcoming event near you found yet" if not ev else "no upcoming event left; the finder runs daily"},
                "events": []}
    rows = [{"ts": e.get("start"), "kind": "event", "what": " · ".join(x for x in (e.get("name"), e.get("city") or e.get("place")) if x),
             "co": e.get("name") or "", "url": e.get("url")} for e in up]
    h = {"sent": len(up), "answered": 0, "status": "live", "found": len(ev), "window": "upcoming events near you",
         "what": "meetups and career fairs near you that fit your search; attended = events you went to",
         "source": "Luma place pages (in_person_find.py)", "last_action": {"ts": up[0]["start"], "event": "next event"},
         "labels": {"sent": "found", "answered": "attended"}}
    return {"hunt": h, "events": rows}


def facts_to_ask(person: str) -> dict:
    """What the desk could not fill in, with how many postings it blocked (candidate-apply.py status's list, read from
    the worker log: a posting's newest attempt, against the newest ground-truth fingerprint)."""
    lines = read_lines(os.path.join(APPLY_ROOT, person, "worker.jsonl"), "horus")
    if lines is None:
        return {"rows": [], "reason": "the desk's log is not readable by the feed"}
    rows = jl(lines)
    gt = next((r["gt"] for r in reversed(rows) if r.get("gt")), None)
    last = {}
    for r in rows:
        if r.get("url"):
            last[r["url"]] = r
    n: dict = {}
    for r in last.values():
        if r.get("outcome") == "blocked_missing_fact" and r.get("gt") == gt:
            for m in r.get("missing_facts") or [{"fact": None, "label": "?"}]:
                k = m.get("fact") or f"(no profile field) {str(m.get('label', ''))[:60]}"
                n[k] = n.get(k, 0) + 1
    return {"rows": [{"fact": k, "blocked": v} for k, v in sorted(n.items(), key=lambda kv: -kv[1])],
            "reason": None if n else "nothing is waiting on you"}


def campaign_people(person: str) -> dict:
    """Network roost: the people the agent works at the companies you applied to, from your campaign ledger."""
    lines = read_lines(os.path.join(CAMP_ROOT, person, "ledger.jsonl"), "sekhmet")
    if lines is None:
        return {"rows": [], "reason": "your campaign ledger is not readable by the feed yet"}
    rows = jl(lines)
    steps: dict = {}
    for r in rows:
        if r.get("type") == "step":
            steps.setdefault(r.get("slug"), {})[r.get("step")] = r.get("state")
    out = []
    for r in rows:
        if r.get("type") != "person":
            continue
        st = steps.get(r.get("slug"), {})
        stage = ("replied" if "replied" in st.values() else "DM sent" if st.get("li_dm") == "sent" else
                 "connected" if st.get("li_connect") == "accepted" else "connect sent" if st.get("li_connect") == "sent" else "found")
        out.append({"name": r.get("name") or r.get("slug"), "hunt": "cold_apps", "stage": stage, "contracts": 0, "paid": 0,
                    "kind": " · ".join(x for x in (r.get("title"), r.get("co")) if x) or "contact", "at": r.get("at")})
    return {"rows": out, "reason": None if out else "the agent has not addressed anyone at your companies yet"}


KINDS = {"internship": ("internships", "Internships"), "server": ("server", "Server jobs"), "job": ("jobs", "Jobs")}


def count(rows: list) -> dict:
    apps: dict = {}
    for r in rows:   # the ledger is append-only and in time order: the last row per application is its status
        k = (r.get("org", "").strip().lower(), r.get("role", "").strip().lower(), r.get("kind", "").strip())
        a = apps.setdefault(k, {"kind": k[2], "seen": set(), "status": "", "ts": ""})
        st = r.get("status", "").strip()
        a["seen"].add(st)
        a["status"], a["ts"] = st, r.get("logged_utc", "")
    hunts, tot = {}, {"found": 0, "sent": 0, "replied": 0, "interviews": 0, "offers": 0}
    for kind, (key, name) in KINDS.items():
        mine = [a for a in apps.values() if a["kind"] == kind]
        if not mine and kind == "job":
            continue
        n = {
            "found": len(mine),
            "sent": sum(1 for a in mine if a["seen"] & SENT),
            "replied": sum(1 for a in mine if a["seen"] & REPLIED),
            "interviews": sum(1 for a in mine if a["seen"] & INTERVIEW),
            "offers": sum(1 for a in mine if "offer" in a["seen"]),
        }
        for x in tot:
            tot[x] += n[x]
        last = max((a for a in mine), key=lambda a: a["ts"], default=None)
        h = {"sent": n["sent"], "answered": n["replied"], "status": "live", "found": n["found"],
             "interviews": n["interviews"], "offers": n["offers"],
             "window": f"all time · {n['found']} found, {n['sent']} sent",
             "what": "sent = applications submitted; came back = an interview, an offer or a rejection",
             "source": "her ledger Sheet (client_desk.py)"}
        if last and last["ts"]:
            h["last_action"] = {"ts": last["ts"].replace(" ", "T") + ":00Z", "event": last["status"]}
        if not mine:
            h.update(sent=None, answered=None, status="empty", reason=f"no {name.lower()} in her ledger yet")
        elif n["sent"] == 0:
            h["reason"] = f"{n['found']} found and queued, none submitted yet"
        hunts[key] = h
    return {"hunts": hunts, **tot}


def apply_counts(db: str) -> dict:
    """The raw numbers of one apply store, opened read-only."""
    import sqlite3  # noqa: PLC0415
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        one = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        return {"found": one("select count(*) from applications"),
                "sent": one(CONFIRMED_SQL),
                "interviews": one("select count(distinct coalesce(posting_id, company)) from interviews"),
                "offers": one("select count(*) from interviews where lower(coalesce(outcome,'')) = 'offer'"),
                "last": one("select max(submitted_at) from applications where " + SENT_SQL) or "",
                # knowledge#14295: the Network roost's people = employers that answered with an interview
                "contacts": [list(r) for r in c.execute(
                    "select company, max(coalesce(stage,'')), max(coalesce(status,'')), max(coalesce(start_utc,'')) "
                    "from interviews where coalesce(company,'') <> '' group by company order by max(start_utc) desc limit 60")]}
    finally:
        c.close()


def apply_feed(person: str) -> dict:
    db = os.path.join(APPLY_ROOT, person, "applications.db")
    if not os.path.exists(db) and not os.path.exists(os.path.dirname(db)):
        raise SystemExit(f"no ledger Sheet and no apply store for {person}")
    try:
        n = apply_counts(db)
    except Exception:  # noqa: BLE001 — not readable as this user: count as the store's owner
        import inspect  # noqa: PLC0415 — horus cannot read this file (it sits in our home), so the code goes inline
        src = (f"import json, sys\nSENT_SQL = {SENT_SQL!r}\nCONFIRMED_SQL = {CONFIRMED_SQL!r}\n" + inspect.getsource(apply_counts)
               + "print(json.dumps(apply_counts(sys.argv[1])))\n")
        r = subprocess.run(["sudo", "-n", "-u", "eagle", "python3", "-c", src, db],
                           capture_output=True, text=True, timeout=60, cwd="/")
        if r.returncode != 0:
            raise SystemExit(f"apply store unreadable: {r.stderr.strip()[:200]}")
        n = json.loads(r.stdout)
    h = {"sent": n["sent"], "answered": n["interviews"], "status": "live", "found": n["found"],
         "interviews": n["interviews"], "offers": n["offers"],
         "window": f"all time · {n['found']} worked, {n['sent']} sent",
         "what": "sent = applications submitted in your name; came back = an interview recorded by your desk",
         "source": "your desk's apply store"}
    if n["last"]:
        h["last_action"] = {"ts": n["last"], "event": "submitted"}
    if n["sent"] == 0:
        h["reason"] = f"{n['found']} worked, none submitted yet"
    rows = [{"name": co, "hunt": "cold_apps", "stage": " · ".join(x for x in (st, sg) if x) or "interview",
             "contracts": 0, "paid": 0, "kind": "recruiter / hiring team", "at": at or None}
            for co, sg, st, at in n.get("contacts") or []]
    return {"network_rows": rows, "hunts": {"applications": h}, "found": n["found"], "sent": n["sent"], "replied": n["interviews"],
            "interviews": n["interviews"], "offers": n["offers"]}


def feed(person: str) -> dict:
    sys.path.insert(0, DESK)
    import client_desk  # noqa: PLC0415
    with open(os.path.join(DESK, "clients.json")) as f:
        sheet = (json.load(f).get(person) or {}).get("ledger_sheet")
    if sheet:
        lr = client_desk.rows(person)
        out = count(lr)
        newest = {}
        for r in sorted(lr, key=lambda r: r.get("logged_utc", "")):   # newest row per employer wins
            newest[r.get("org", "")] = r
        out["network_rows"] = [{"name": o, "hunt": "cold_apps", "stage": r.get("status", ""), "contracts": 0, "paid": 0,
                                "kind": "recruiter / hiring team", "at": (r.get("logged_utc") or "").replace(" ", "T") + "Z"}
                               for o, r in newest.items() if o and r.get("status") in REPLIED]
        net = "her network shows here once her LinkedIn is connected"
    else:
        out = apply_feed(person)
        net = "your network shows here once your LinkedIn is connected"
    rows = out.pop("network_rows", [])   # the employers that answered: the Clients roost (knowledge#14303)
    cp = campaign_people(person)
    out["roosts"] = {
        "clients": {"rows": rows, "people": len(rows), "reason": None if rows else "no employer has answered you yet",
                    "agent": AGENTS[person],
                    "source": "your own search: employers that answered (interview, offer or rejection), from your ledger or apply store"},
        "network": {"rows": cp["rows"], "people": len(cp["rows"]), "reason": cp["reason"] or None, "agent": AGENTS[person],
                    "source": "the people your agent works at the companies you applied to (campaign ledger: LinkedIn connect, DM, reply)"}}
    ip = in_person(person)
    out["hunts"]["in_person"] = ip["hunt"]
    out["lanes"] = {"in_person": {"events": ip["events"], "companies": [], "source": ip["hunt"].get("source") or "no event found yet"}}
    out["facts"] = facts_to_ask(person)
    out["person"] = person
    out["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def push(person: str, body: str) -> None:
    get = os.path.expanduser("~/.claude/scripts/infisical-get.sh")
    rd = lambda k: subprocess.run(["bash", get, "fleet-infra", k], capture_output=True, text=True).stdout.strip()  # noqa: E731
    tok, acct = rd("CF_API_TOKEN_UTOPIA"), rd("CF_ACCOUNT_ID_UTOPIA")
    if not tok or not acct:
        raise SystemExit("CF_API_TOKEN_UTOPIA / CF_ACCOUNT_ID_UTOPIA unreadable from Infisical")
    url = (f"https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces/{KV_NS}/values/"
           f"p%2F{person}")
    req = urllib.request.Request(url, data=body.encode(), method="PUT",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if not r.get("success"):
        raise SystemExit(f"KV put failed: {r.get('errors')}")


def self_test() -> int:
    L = lambda ts, org, role, kind, st: {"logged_utc": ts, "org": org, "role": role, "kind": kind, "status": st}  # noqa: E731
    rows = [L("2026-11-01 10:00", "A", "intern", "internship", "queued"),
            L("2026-11-02 10:00", "A", "intern", "internship", "submitted"),
            L("2026-11-03 10:00", "A", "intern", "internship", "interview"),
            L("2026-11-01 10:00", "B", "intern", "internship", "submitted"),
            L("2026-11-04 10:00", "B", "intern", "internship", "rejected"),
            L("2026-11-01 10:00", "C", "intern", "internship", "queued"),
            L("2026-11-01 10:00", "D", "server", "server", "queued"),
            L("2026-11-05 10:00", "E", "intern", "internship", "withdrawn")]
    c = count(rows)
    i, s = c["hunts"]["internships"], c["hunts"]["server"]
    want = [(i["found"], 4), (i["sent"], 2), (i["answered"], 2), (i["interviews"], 1), (i["offers"], 0),
            (s["found"], 1), (s["sent"], 0), (c["sent"], 2), (c["found"], 5),
            (i["last_action"]["event"], "withdrawn"), ("jobs" in c["hunts"], False)]
    # knowledge#14302: the apply store's sent = confirmed submits once per job URL (a retry row and an unconfirmed one
    # are not sent), the number candidate-apply.py status and the person's own agent read.
    import sqlite3, tempfile  # noqa: PLC0415, E401
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "applications.db")
        k = sqlite3.connect(db)
        k.execute("create table applications (posting_id text, posting_url text, outcome text, submitted_at text)")
        k.execute("create table interviews (posting_id text, company text, outcome text, stage text, status text, start_utc text)")
        k.execute("insert into interviews values ('1','Acme','', 'phone','scheduled','2026-11-20T10:00Z')")
        k.executemany("insert into applications values (?,?,?,?)", [
            ("1", "u1", "submitted", "2026-11-15"), ("1b", "u1", "submitted", "2026-11-15"),
            ("2", "u2", "submitted_unconfirmed", "2026-11-15"), ("3", "u3", "submitted", "2026-11-16"),
            ("4", "u4", "blocked_missing_fact", None)])
        k.commit(); k.close()
        want.append((apply_counts(db)["sent"], 2))
        want.append((apply_counts(db)["contacts"], [["Acme", "phone", "scheduled", "2026-11-20T10:00Z"]]))
    want.append((jl(['{"a":1}', "oops"]), [{"a": 1}]))
    with tempfile.TemporaryDirectory() as td:   # the In Person hunt and the facts panel, offline
        global APPLY_ROOT
        old, APPLY_ROOT = APPLY_ROOT, td
        os.makedirs(os.path.join(td, "p"))
        open(os.path.join(td, "p", "in_person.jsonl"), "w").write(
            json.dumps({"id": "e1", "name": "Data Night", "start": "2026-11-20T23:00:00Z", "url": "u", "city": "Arlington, VA"}) + "\n"
            + json.dumps({"id": "e0", "name": "Old", "start": "2026-11-01T23:00:00Z"}) + "\n")
        open(os.path.join(td, "p", "worker.jsonl"), "w").write(
            json.dumps({"url": "c", "outcome": "blocked_missing_fact", "gt": "g1", "missing_facts": [{"fact": "old"}]}) + "\n"
            + json.dumps({"url": "a", "outcome": "blocked_missing_fact", "gt": "g2", "missing_facts": [{"fact": "work_auth"}]}) + "\n"
            + json.dumps({"url": "b", "outcome": "blocked_missing_fact", "gt": "g2", "missing_facts": [{"fact": "work_auth"}, {"fact": "salary"}]}) + "\n")
        ip = in_person("p", "2026-11-18T00:00:00Z")
        want += [(ip["hunt"]["sent"], 1), (ip["hunt"]["found"], 2), (ip["events"][0]["what"], "Data Night · Arlington, VA"),
                 (in_person("nobody")["hunt"]["status"], "empty"),
                 (facts_to_ask("p")["rows"], [{"fact": "work_auth", "blocked": 2}, {"fact": "salary", "blocked": 1}])]
        APPLY_ROOT = old
    bad = [(g, w) for g, w in want if g != w]
    print("self-test", "PASS" if not bad else f"FAIL {bad}")
    return 1 if bad else 0


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--self-test":
        return self_test()
    person = argv[0]
    try:
        body = json.dumps(feed(person), separators=(",", ":"))
    except Exception as e:  # noqa: BLE001
        print(f"person_feed: {person}: {e}", file=sys.stderr)
        return 1
    if "--push" in argv:
        push(person, body)
        print(f"pushed p/{person}: {len(body)} bytes")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
