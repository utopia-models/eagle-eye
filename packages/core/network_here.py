#!/usr/bin/env python3
"""network_here.py: who in Tyler's network works at a company, or knows someone who does (knowledge#14278).

Tyler, 2026-11-16 12:30 PM MT, on the Cold Apps company panel: "For each cold app company, I would like to see who in
my network map either works there, or knows someone that works there." The panel's YOUR NETWORK HERE section
(apps.html) renders `companies[k].net` from apps_feed.py, which calls `network_at()` here.

How it runs: APPENDED to feed.py's source together with apps_feed.py (apps-push.py), as horus on novaserver, so it
reuses feed.py's `_norm`, `_clean`, `js`, `P`, `STATE`. Stdlib only. Nothing here touches linkedin.com: the LinkedIn
part is read from the files the human seat writes (net/work/_tools/linkedin/li_people.py, as sekhmet).

Sources, each read live, each named in `sources.network_here`:
  1. the network roster (the Network roost, ~380 people from phone, WhatsApp and LinkedIn) `sf/network/roster.json`:
     each person's `company` + `title`, and the domain of a work email.
  2. the CRM (Twenty on novaserver): People owned by tyler or atlas (people Tyler has a relationship with, not the
     ~15k hiring contacts horus found), with their Company and its domain. Snapshot `crm.json`, refreshed daily.
  3. LinkedIn, per company, from li_people.py's lookup file `li/<key>.json`: the 1st-degree search ("works there",
     via LinkedIn) and the 2nd-degree search, whose cards carry the mutual connections ("knows someone there").
     A card counts only when its headline names the company: a keyword search also returns people who only
     mention it.
  4. WhatsApp and phone contacts reach this only through the roster (atlas's readers build it); they carry no employer
     of their own.

A company is ONE key set: `_norm(name)` plus the stem of its domain or ATS board slug (`company_keys`), so "Spotnana",
"Spotnana Inc." and spotnana.wd1.myworkdayjobs.com are one company. A person matches when their key set meets it.

Cache: `at/<key>.json` per company, rebuilt when older than a day or when its LinkedIn file is newer.
Queue: `queue.json` = the cold-app companies, newest application first, for li_people.py to look up.
    python3 network_here.py --self-test    # offline (via test_network_here.py)
"""
# ── appended part: everything below runs after feed.py's definitions ──────────────────────────────────────────────
NET_DIR = os.environ.get("EAGLE_NET_DIR") or "/var/lib/net-network"
NET_ROSTER = os.environ.get("EAGLE_NET_ROSTER") or P(STATE, "sf/network/roster.json")
NET_CRM_KEY = os.path.expanduser(os.environ.get("TWENTY_API_KEY_FILE", "~/.claude/state/crm/api-key"))
NET_CRM_URL = os.environ.get("TWENTY_URL", "http://127.0.0.1:3020").rstrip("/") + "/rest"
NET_TTL_S = 86400            # a company's cache and the CRM snapshot are rebuilt daily
NET_KEEP = 50                # people kept per group in the feed; the panel shows 5 and "+N more" (the rest)
NET_CRM_OWNERS = ("TYLER", "ATLAS")
NET_VERSION = 4              # bump when the join changes: every cached company is rebuilt on its next read

FREEMAIL = {"gmail", "googlemail", "yahoo", "ymail", "hotmail", "outlook", "live", "msn", "icloud", "me", "mac", "aol",
            "proton", "protonmail", "pm", "gmx", "mail", "zoho", "yandex", "comcast", "verizon", "att", "sbcglobal",
            "cox", "charter", "fastmail", "hey", "duck", "qq", "163", "126", "edu", "students"}
#: hosts whose first path segment is the company's board slug
SLUG_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com", "jobvite.com",
              "gem.com", "rippling.com", "dover.com", "teamtailor.com", "pinpointhq.com", "recruitee.com")
#: hosts whose first label is the company's tenant
TENANT_HOSTS = ("myworkdayjobs.com", "bamboohr.com", "icims.com", "breezy.hr", "applytojob.com", "recruitee.com",
                "teamtailor.com", "jobs.personio.de", "personio.de", "workday.com", "taleo.net", "paylocity.com",
                "ultipro.com", "adp.com", "freshteam.com", "zohorecruit.com", "catsone.com", "eightfold.ai")
#: job boards and aggregators: their host names nobody's employer
AGGREGATORS = {"linkedin", "indeed", "glassdoor", "ziprecruiter", "builtin", "builtinnyc", "wellfound", "angel",
               "ycombinator", "workatastartup", "dice", "simplyhired", "monster", "google", "careerbuilder", "hiring",
               "jobs", "careers", "apply", "boards", "job", "otta", "welcometothejungle", "remoteok", "weworkremotely",
               "lensa", "talent", "jooble", "adzuna", "clearancejobs", "usajobs", "handshake", "joinhandshake"}
#: CRM / roster company values that are buckets, not employers
NOT_EMPLOYER = {"personalnetwork", "testfixtures", "fixture", "youkfamily", "upworkleads", "photographer", "contact",
                "nonprofitorganization", "selfemployed", "freelance", "student", "unemployed", "retired"}
_PAST = re.compile(r"(?i)\((?:previous|prev|former|formerly|past|ex)\)|^\s*(?:ex|former|formerly)[\s:-]")
_TLD = re.compile(r"\.(?:com|co|io|ai|net|org|dev|app|tech|us|xyz|gov|edu|mil|inc|so|sh|me|cc|tv|info|biz|ly)$")


def domain_stem(v):
    """The company stem of an email address, a domain or a URL: 'max@salesblaster.example' -> 'salesblaster',
    'https://careers.spotnana.com/x' -> 'spotnana', 'spotnana.wd1.myworkdayjobs.com' -> 'spotnana',
    'boards.greenhouse.io/spotnana/jobs/1' -> 'spotnana'. None for a free-mail address, an aggregator or junk."""
    s = (v or "").strip().lower()
    if not s:
        return None
    if "@" in s and "/" not in s:
        s = s.rsplit("@", 1)[1]
    s = re.sub(r"^[a-z]+://", "", s)
    host, _, path = s.partition("/")
    host = host.split(":")[0].strip(".")
    if not host or "." not in host:
        return None
    seg = [p for p in path.split("/") if p and p not in ("embed", "job_app", "jobs", "j", "en-us", "en", "us", "o")]
    for h in SLUG_HOSTS:
        if host == h or host.endswith("." + h):
            if host.split(".")[0] not in ("boards", "job-boards", "jobs", "apply", "app", "www", "careers", "ats") \
                    and host != h and h not in ("greenhouse.io", "lever.co", "ashbyhq.com"):
                return _stem_word(host.split(".")[0])
            return _stem_word(seg[0]) if seg else None
    for h in TENANT_HOSTS:
        if host.endswith("." + h):
            t = host[: -len(h) - 1].split(".")[0]
            t = re.sub(r"^(?:careers|jobs|recruiting)-", "", t)
            return _stem_word(t)
    labels = host.split(".")
    while len(labels) > 2 and labels[0] in ("www", "careers", "jobs", "apply", "boards", "job", "hire", "work", "talent", "mail", "en"):
        labels = labels[1:]
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in ("co", "com", "ac", "org", "gov", "net"):
        stem = labels[-3]   # example.co.uk
    else:
        stem = labels[-2] if len(labels) >= 2 else labels[0]
    if stem in FREEMAIL or stem in AGGREGATORS:
        return None
    return _stem_word(stem)


def _stem_word(w):
    w = re.sub(r"[^a-z0-9-]", "", (w or "").lower())
    if not w or w in FREEMAIL or w in AGGREGATORS or len(w.replace("-", "")) < 3:
        return None
    k = _norm(w.replace("-", " "))
    return k if k and len(k) >= 3 else None


#: words a company name may carry after its brand: "Kratos Defense & Security Solutions" is also "Kratos"
_NET_GENERIC = {"industries", "industry", "holdings", "corporation", "corp", "company", "solutions", "systems",
                "technologies", "technology", "tech", "group", "labs", "defense", "security", "software", "services",
                "international", "global", "partners", "enterprises", "platforms", "and", "inc", "llc", "ltd", "co", "ai"}


def company_keys(name, *urls):
    """The key set of one company: its `_norm` name, the brand without generic trailing words (when 4+ letters
    remain), plus the stem of each domain / URL / board slug given."""
    out = set()
    k = _norm(name) if name else ""
    if k and k not in NOT_EMPLOYER:
        out.add(k)
        words = re.sub(r"[^a-z0-9 ]", " ", (_clean(name) or "").lower().replace("&", " and ")).split()
        if words and words[0] == "the":
            words = words[1:]
        while len(words) > 1 and words[-1] in _NET_GENERIC:
            words.pop()
        if words and len(words) < len(re.sub(r"[^a-z0-9 ]", " ", (_clean(name) or "").lower()).split()):
            alias = "".join(words)
            if len(alias) >= 4:
                out.add(alias)
    for u in urls:
        s = domain_stem(u)
        if s:
            out.add(s)
    return out


def split_company(raw):
    """A stored company string -> (clean name, past?). 'PNC (previous)' -> ('PNC', True); 'Kratos' -> ('Kratos', False)."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return None, False
    past = bool(_PAST.search(s))
    s = re.sub(r"(?i)\s*\((?:previous|prev|former|formerly|past|ex)\)\s*", " ", s)
    s = re.sub(r"(?i)^\s*(?:ex|former|formerly)[\s:-]+", "", s).strip()
    return (s or None), past


def headline_names(headline, name, keys):
    """-> 'current' | 'past' | None: does a LinkedIn headline name the company? Matched on the folded headline against
    every company key (a key under 4 letters must be a whole word), so '@Spotnana', 'SWE at Spotnana Inc.' and
    'Spotnana | Columbia' all count, and 'Ex-Spotnana' or 'formerly at Spotnana' is past."""
    h = (headline or "").lower()
    if not h:
        return None
    flat = re.sub(r"[^a-z0-9]", "", h)
    words = re.sub(r"[^a-z0-9]+", " ", h).split()
    hit = None
    for k in keys:
        if not k:
            continue
        if len(k) >= 4 and k in flat:
            hit = k
            break
        if k in words:
            hit = k
            break
    if not hit:
        nm = re.sub(r"[^a-z0-9]", "", (name or "").lower())
        if len(nm) >= 4 and nm in flat:
            hit = nm
    if not hit:
        return None
    first = (name or hit).split()[0].lower() if name else hit
    if re.search(r"(?:\bex[\s-]*@?|\bformer(?:ly)?\b[^|,;]{0,30}|\bpreviously\b[^|,;]{0,30}|\bprev(?:ious)?\.?\s*@?)"
                 + re.escape(first[:6]), h):
        return "past"
    return "current"


def _age(path):
    try:
        return dt.datetime.now().timestamp() - os.path.getmtime(path)
    except OSError:
        return None


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def crm_snapshot(force=False):
    """Tyler's and atlas's CRM People with their Company (+domain): the daily snapshot `crm.json`, refreshed from Twenty
    when older than a day. -> (people, status)."""
    snap = P(NET_DIR, "crm.json")
    age = _age(snap)
    if not force and age is not None and age < NET_TTL_S:
        d = js(snap) or {}
        return d.get("people") or [], f"crm.json ({len(d.get('people') or [])} people, {int(age // 3600)} h old)"
    try:
        key = open(NET_CRM_KEY).read().strip()
    except OSError:
        key = os.environ.get("TWENTY_API_KEY", "")
    if not key:
        d = js(snap) or {}
        return d.get("people") or [], "no CRM key for this user" + (" (stale crm.json)" if d else "")
    import urllib.parse  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    people = []
    try:
        for owner in NET_CRM_OWNERS:
            cursor = None
            for _ in range(20):
                q = {"limit": "200", "depth": "1", "filter": f"ownerAgent[eq]:{owner}"}
                if cursor:
                    q["starting_after"] = cursor
                req = urllib.request.Request(NET_CRM_URL + "/people?" + urllib.parse.urlencode(q),
                                             headers={"Authorization": f"Bearer {key}"})
                d = json.loads(urllib.request.urlopen(req, timeout=20).read())
                for p in (d.get("data") or {}).get("people") or []:
                    nm = p.get("name") or {}
                    co_ = p.get("company") or {}
                    em = p.get("emails") or {}
                    people.append({"name": f"{nm.get('firstName') or ''} {nm.get('lastName') or ''}".strip(),
                                   "title": p.get("jobTitle") or "", "company": co_.get("name") or "",
                                   "domain": ((co_.get("domainName") or {}).get("primaryLinkUrl") or ""),
                                   "emails": [e for e in [em.get("primaryEmail")] + (em.get("additionalEmails") or []) if e],
                                   "owner": owner.lower()})
                pi = d.get("pageInfo") or {}
                if not pi.get("hasNextPage"):
                    break
                cursor = pi.get("endCursor")
    except Exception as e:  # noqa: BLE001
        d = js(snap) or {}
        return d.get("people") or [], f"CRM unreachable ({type(e).__name__}); " + ("stale crm.json" if d else "no snapshot")
    _write_json(snap, {"at": _iso(dt.datetime.now(dt.timezone.utc)), "people": people})
    return people, f"Twenty ({len(people)} people owned by tyler or atlas, refreshed now)"


def _title_ok(t):
    t = (t or "").strip()
    return "" if re.match(r"(?i)^(contact|test fixture|upwork lead|dmv research contact)\b", t) else t[:120]


def network_people(roster=None, crm=None):
    """Everyone Tyler knows who carries an employer: [{name, title, company, keys, past, via}] from the roster + CRM,
    one row per person (a person in both is one row, via 'CRM')."""
    out, by_name = [], {}

    def add(name, title, company_raw, urls, via):
        name = re.sub(r"\s+", " ", (name or "").strip())
        if not name or "@" in name or re.fullmatch(r"[\d+ ()-]+", name):
            return
        company, past = split_company(company_raw)
        keys = company_keys(company, *urls) if company else {s for s in (domain_stem(u) for u in urls) if s}
        if not keys:
            return
        nk = re.sub(r"[^a-z]", "", name.lower())
        row = by_name.get(nk)
        if row:   # the same person in both stores: one row, the richer title, every key
            row["keys"] |= keys
            row["title"] = row["title"] or _title_ok(title)
            row["company"] = row["company"] or company
            row["past"] = row["past"] and past
            return
        row = {"name": name[:60], "title": _title_ok(title), "company": company or "", "keys": keys, "past": past, "via": via}
        by_name[nk] = row
        out.append(row)
    for r in (roster or []):
        add(r.get("name"), r.get("title"), r.get("company"), list(r.get("emails") or []), "CRM")
    for r in (crm or []):
        add(r.get("name"), r.get("title"), r.get("company"), [r.get("domain")] + list(r.get("emails") or []), "CRM")
    return out


def li_lookup(keys):
    """li_people.py's newest lookup file for any of the company's keys, or None."""
    best = None
    for k in keys:
        d = js(P(NET_DIR, "li", f"{k}.json"))
        if isinstance(d, dict) and (best is None or (d.get("at") or "") > (best.get("at") or "")):
            best = d
    return best


def li_title(headline):
    """A LinkedIn headline's job part: the text before its first '|' or '•' ('Backend Engineer at Spotnana | Columbia
    University | Machine Learning' -> 'Backend Engineer at Spotnana')."""
    return re.split(r"\s*[|•·]\s*", (headline or "").strip())[0][:120]


def li_card(c, name, keys):
    """-> (how, title) for one LinkedIn card: how = 'current' | 'past' | None from its headline, else from LinkedIn's
    summary line ('Software Engineer at Spotnana since June 2025, ...'); title = the headline's job part when the
    headline names the company, else the summary's role clause."""
    how = headline_names(c.get("headline"), name, keys)
    if how:
        return how, li_title(c.get("headline"))
    sm = c.get("summary") or ""
    how = headline_names(sm, name, keys)
    if not how:
        return None, ""
    return how, re.split(r"\s+(?:since|for the last|for over|for nearly|from)\b|,", sm)[0].strip()[:120]


def _person(name):
    """A LinkedIn card's name as read, without OCR'd badge glyphs ('Mark T. Nelson [fi' -> 'Mark T. Nelson')."""
    toks = (name or "").split()
    while len(toks) > 2 and (len(toks[-1]) == 1 or re.search(r"[^A-Za-z.'’-]", toks[-1])):
        toks.pop()
    return " ".join(toks)[:60]


def _short(names):
    return [re.sub(r"\s+", " ", n).strip()[:40] for n in names if n and n.strip()]


def match_people(name, keys, people, li=None):
    """The pure join: -> {works: [...], knows: [...], wn, kn, li}. `works` rows: {n, t, via, past?};
    `knows` rows: {c: [connector names], cm: N more connectors, n, t}."""
    works, seen = [], {}
    for p in people:
        if p["keys"] & keys:
            w = {"n": p["name"], "t": p["title"] or "", "via": p["via"]}
            if p["past"]:
                w["past"] = 1
            seen[re.sub(r"[^a-z]", "", p["name"].lower())] = w
            works.append(w)
    knows, li_state = [], None
    if li:
        li_state = {"at": li.get("at"), "state": li.get("state")}
        for c in li.get("first") or []:
            how, title = li_card(c, name, keys)
            if not how:
                continue
            nk = re.sub(r"[^a-z]", "", _person(c.get("name")).lower())
            if nk in seen:   # in the CRM too: one row, both ways Tyler knows them
                if "LinkedIn" not in seen[nk]["via"]:
                    seen[nk]["via"] += " · LinkedIn"
                seen[nk]["t"] = seen[nk]["t"] or title
                continue
            w = {"n": _person(c.get("name")), "t": title, "via": "LinkedIn"}
            if how == "past":
                w["past"] = 1
            seen[nk] = w
            works.append(w)
        for c in li.get("second") or []:
            how, title = li_card(c, name, keys)
            if how != "current":
                continue
            con = _short(c.get("mutual") or [])
            if not con and not int(c.get("mutual_more") or 0):
                continue   # no mutual connection read at all: not someone Tyler reaches through his network
            knows.append({"c": con[:2], "cm": int(c.get("mutual_more") or 0) + max(0, len(con) - 2),
                          "n": _person(c.get("name")), "t": title})
    works.sort(key=lambda w: (bool(w.get("past")), "LinkedIn" in w["via"] and "CRM" not in w["via"], w["n"]))
    return {"works": works[:NET_KEEP], "wn": len(works), "knows": knows[:NET_KEEP], "kn": len(knows), "li": li_state}


_NET_INDEX = {}


def network_index():
    """The people index, built once per process (the feed runs once per 30 s cycle)."""
    if "people" not in _NET_INDEX:
        roster = (js(NET_ROSTER) or {}).get("people_rows") or []
        crm, crm_st = crm_snapshot()
        _NET_INDEX["people"] = network_people(roster, crm)
        _NET_INDEX["status"] = (f"roster.json ({len(roster)} people, {probe(NET_ROSTER)}) + {crm_st} + LinkedIn lookups "
                                f"{NET_DIR}/li ({len(glob.glob(P(NET_DIR, 'li', '*.json')))} companies)")
    return _NET_INDEX["people"], _NET_INDEX["status"]


def network_at(company, *urls, now=None):
    """Who in Tyler's network works at `company` or knows someone there. Cached per company in `at/<key>.json` for a
    day (rebuilt sooner when its LinkedIn lookup is newer). -> {works, wn, knows, kn, li, at}."""
    keys = company_keys(company, *urls)
    if not keys:
        return {"works": [], "wn": 0, "knows": [], "kn": 0, "li": None, "at": None}
    main = _norm(company) or sorted(keys)[0]
    cache = P(NET_DIR, "at", f"{main}.json")
    li = li_lookup(keys)
    age = _age(cache)
    d = js(cache) if age is not None and age < NET_TTL_S else None
    if d and d.get("v") == NET_VERSION and (not li or (d.get("li") or {}).get("at") == li.get("at")) \
            and sorted(d.get("keys") or []) == sorted(keys):
        return d
    people, _ = network_index()
    d = match_people(company, keys, people, li)
    d["at"] = _iso(now or dt.datetime.now(dt.timezone.utc))
    d["keys"] = sorted(keys)
    d["v"] = NET_VERSION
    _write_json(cache, d)
    return d


def write_queue(companies):
    """`queue.json` for li_people.py: [{co, k, keys, last}] newest application first. `companies` = [(name, key, last
    application ISO, [urls])]. Returns the path written, or None."""
    rows = []
    for name, k, last, urls in sorted(companies, key=lambda c: c[2] or "", reverse=True):
        if not k or not name or re.fullmatch(r"(?i)company|unknown|confidential|n/?a", name):
            continue
        rows.append({"co": name, "k": k, "keys": sorted(company_keys(name, *urls)), "last": last})
    p = P(NET_DIR, "queue.json")
    return p if _write_json(p, {"at": _iso(dt.datetime.now(dt.timezone.utc)), "companies": rows}) else None
