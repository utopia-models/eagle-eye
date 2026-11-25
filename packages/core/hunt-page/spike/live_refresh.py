#!/usr/bin/env python3
"""THROWAWAY SPIKE. Live rows on top of Eagle Eye's frozen 11-20 copy, for Tyler only (Tyler 11-21).

  python3 live_refresh.py            one pass: merge live rows into public/people/tyler.json
  python3 live_refresh.py --loop 300 the same every 300 s (run under nohup; log in state/refresh.log)

Base: public/people/tyler.json as build_snapshot.py writes it (no `live_at` key) is saved to state/tyler.frozen.json;
every pass merges onto that saved base, so build_snapshot.py can be re-run at any time and is never edited here.

Live sources (Ra only, novaserver offline):
  funding  Launch YC (public JSON) · SEC EDGAR Form D (full-text search + primary_doc.xml) · TechCrunch RSS (venture, startups, main) ·
           Crunchbase News RSS. Last 48 h, tech/AI, seed-ish (Form D: tech industry group, offering <= $25M, no funds).
  jobs     dev@ inbox, ATS mail (greenhouse / ashby / workday / workable / lever): received / rejection / interview.
  upwork   dev@ inbox: "New job alert" (job_read) and "<client> sent you a message" (client_reply, also into Clients).
Every live row carries `src` (its source) and `live: true`; frozen rows carry `src: "11-20 copy"`.
No token or secret is printed or written: tokens live in this process's memory only.
"""
import datetime as dt, email.utils, html, json, os, re, subprocess, sys, time, traceback
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "public", "people", "tyler.json")
STATE = os.path.join(HERE, "state")
FROZEN = os.path.join(STATE, "tyler.frozen.json")
CACHE = os.path.join(STATE, "live-cache.json")
MINT = os.path.expanduser("~/.claude/knowledge/_infra/scripts/infisical-cache.sh")
UA = "utopia-models eagle-eye-spike dryrun@example.com"
DEV = "inbox@example.com"
WINDOW_H = 48
NOW = None


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, headers=None, timeout=25, raw=False):
    h = {"User-Agent": UA, "Accept-Encoding": "identity"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b)


def recent(ts):
    try:
        return (NOW - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() <= WINDOW_H * 3600
    except Exception:
        return False


AMT = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s?(million|billion|[MBK])\b", re.I)
ROUND = re.compile(r"\b(pre-seed|seed|series [a-h]\b|series [a-h]-?\d?)", re.I)
RAISE = re.compile(r"\b(raises?|raised|raising|funding|seed|series [a-h]|lands|secures|nabs|bags|closes|backs|backed|valuation|round)\b", re.I)


ROUNDUP = re.compile(r"\b(top \d+|top funding|biggest|this week|week'?s|weekly|funding rounds|mega-rounds|startups this week|debut fund|new fund|closes .*\bfund\b|\bfund (?:i|ii|iii|iv|\d)\b)", re.I)


def amount(text):
    m = AMT.search(text or "")
    if not m:
        return None
    u = m.group(2).lower()[0]
    return f"${m.group(1)}{'B' if u == 'b' else 'K' if u == 'k' else 'M'}"


def usd(text):
    m = AMT.search(text or "")
    if not m:
        return None
    u = m.group(2).lower()[0]
    return float(m.group(1)) * (1e9 if u == "b" else 1e3 if u == "k" else 1e6)


US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
AI = re.compile(r"\bA\.?I\b|\.ai\b|\bLLMs?\b|\bagent(?:s|ic)?\b|machine learning|\bML\b|inference|neural|\bGPT|intelligen|\bmodels?\b|computer vision|deep learning|generative|cognit", re.I)


def fit(r):
    """Tyler 11-21 funding fit: technical founders, AI product, $500K-$5M pre-seed/seed, US, raised within 48 h."""
    text = " ".join([r.get("co") or "", r.get("what") or ""] + (r.get("tags") or []))
    f = {"ai": bool(AI.search(text)), "amount": r.get("usd") is not None and 5e5 <= r["usd"] <= 5e6,
         "us": r.get("us"), "stage": r.get("stage_ok"), "48h": recent(r["ts"]),
         "technical_founder": None}  # not in any of these sources: checked by hand before outreach
    r["fit"] = f
    return f["ai"] and f["amount"] and f["us"] is not False and f["stage"] is not False and f["48h"]


def round_of(text):
    m = ROUND.search(text or "")
    return m.group(1).title().replace("Pre-Seed", "Pre-seed") if m else None


# ---------------------------------------------------------------- funding sources
def yc_launches():
    rows = []
    for page in range(0, 10):
        d = get(f"https://www.ycombinator.com/launches?page={page}", {"Accept": "application/json"})  # without it the URL serves HTML
        hits = d.get("hits") or []
        for h in hits:
            ts = (h.get("created_at") or "")[:19] + "Z"
            if not recent(ts):
                continue
            c = h.get("company") or {}
            rows.append({"ts": ts, "kind": "launch", "co": c.get("name") or h.get("title"),
                         "what": f"Launched on YC ({c.get('batch') or 'batch n/a'}): {h.get('title')}",
                         "round": "YC " + (c.get("batch") or ""), "amount": "YC standard $500K (not stated in the launch)",
                         "usd": 5e5, "us": True, "stage_ok": True,
                         "link": h.get("search_path") or ("https://www.ycombinator.com/launches/" + h.get("slug", "")),
                         "site": c.get("url"), "tags": c.get("tags") or [], "src": "Launch YC"})
        if not hits or not recent((hits[-1].get("created_at") or "")[:19] + "Z") or page + 1 >= d.get("nbPages", 1):
            break
    return rows


def rss(url, src, need_raise):
    root = ET.fromstring(get(url, raw=True))
    rows = []
    for it in root.iter("item"):
        title = html.unescape(it.findtext("title") or "").strip()
        pubr = None
        if src == "Google News RSS":  # "<headline> - <publisher>"
            title, _, pubr = title.rpartition(" - ") if " - " in title else (title, "", None)
        if ROUNDUP.search(title):
            continue
        desc = re.sub("<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        pub = it.findtext("pubDate")
        try:
            ts = iso(email.utils.parsedate_to_datetime(pub))
        except Exception:
            continue
        if not recent(ts) or (need_raise and not RAISE.search(title)):
            continue
        cats = [c.text or "" for c in it.findall("category")]
        if need_raise is False and not (RAISE.search(title) or any(re.search(r"venture|fundrais|seed", c, re.I) for c in cats)):
            continue
        m = re.match(r"^(.+?)\s+(?:raises|raised|lands|secures|nabs|bags|closes|gets|snags|scores|pulls in|hauls in|announces)\b", title, re.I)
        co = m.group(1) if m else title
        co = re.sub(r"^.*?(?:startup|company|maker|platform|developer|provider)\s+", "", co, flags=re.I) if m and len(co) > 40 else co
        rows.append({"ts": ts, "kind": "news", "co": co, "what": title, "round": round_of(title + " " + desc),
                     "amount": amount(title) or amount(desc), "usd": usd(title) or usd(desc),
                     "us": True if re.search(r"\b(U\.S\.|US-based|San Francisco|New York|Austin|Boston|Seattle|Los Angeles|Bay Area|Palo Alto)\b", title + " " + desc) else None,
                     "stage_ok": (bool(re.search(r"pre-seed|seed", title + " " + desc, re.I)) or None) if not re.search(r"series [b-h]\b", title, re.I) else False,
                     "link": (it.findtext("link") or "").strip(), "src": src, **({"publisher": pubr} if pubr else {})})
    return rows


def tc_feeds():
    """TechCrunch venture + startups + main feeds, funding headlines only, one row per link."""
    rows, seen = [], set()
    for u in ("https://techcrunch.com/category/venture/feed/", "https://techcrunch.com/category/startups/feed/", "https://techcrunch.com/feed/"):
        for r in rss(u, "TechCrunch RSS", True):
            if r["link"] not in seen:
                seen.add(r["link"]); rows.append(r)
    return rows


def gnews():
    """Google News search RSS, last 24 h: AI seed / pre-seed raises. The one source here that publishes on weekends."""
    rows, seen = [], set()
    for q in ("(AI) (raises OR raised OR lands OR secures) (seed OR pre-seed) when:1d",
              "(AI OR agents OR LLM) startup (\"seed round\" OR \"pre-seed\") when:1d"):
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        for r in rss(u, "Google News RSS", True):
            k = r["what"].lower()
            if k not in seen:
                seen.add(k); rows.append(r)
    return rows


TECH = {"Computers", "Telecommunications", "Other Technology"}


def form_d(cache):
    seen = cache.setdefault("formd", {})
    start = (NOW - dt.timedelta(hours=WINDOW_H)).date().isoformat()
    hits, frm = [], 0
    while True:
        d = get(f"https://efts.sec.gov/LATEST/search-index?forms=D&dateRange=custom&startdt={start}&enddt={NOW.date().isoformat()}&from={frm}")
        page = d["hits"]["hits"]
        hits += page
        frm += len(page)
        if not page or frm >= d["hits"]["total"]["value"] or frm >= 2000:
            break
        time.sleep(0.15)
    rows = []
    for h in hits:
        s = h["_source"]
        if s.get("form") != "D":  # D only; D/A amendments are not new rounds
            continue
        adsh, cik = s["adsh"], s["ciks"][0].lstrip("0")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}"
        if adsh not in seen:
            try:
                x = get(base + "/primary_doc.xml", raw=True).decode("utf-8", "replace")
                t = lambda tag: (re.search(f"<{tag}>([^<]*)<", x) or [None, None])[1]
                info = {"name": t("entityName"), "industry": t("industryGroupType"), "fund": t("investmentFundType"),
                        "offering": t("totalOfferingAmount"), "sold": t("totalAmountSold"), "first_sale": t("value"),
                        "state": (s.get("biz_locations") or [""])[0], "file_date": s.get("file_date")}
                if info["industry"] in TECH and not info["fund"]:
                    hdr = get(base + f"/{adsh}-index-headers.html", raw=True).decode("utf-8", "replace")
                    m = re.search(r"ACCEPTANCE-DATETIME>(\d{14})", hdr)
                    if m:
                        info["accepted"] = iso(dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("America/New_York")))
                seen[adsh] = info
            except Exception as e:
                seen[adsh] = {"error": str(e)[:120]}
            time.sleep(0.12)  # SEC fair access: < 10 req/s
        i = seen[adsh]
        if i.get("industry") not in TECH or i.get("fund"):
            continue
        off = i.get("offering")
        try:
            offn = float(off) if off and off.replace(".", "").isdigit() else None
        except ValueError:
            offn = None
        if offn is not None and offn > 25e6:
            continue
        ts = i.get("accepted") or (i["file_date"] + "T00:00:00Z")
        if not recent(ts):
            continue
        amt = (f"${offn / 1e6:.1f}M offering" if offn else ("indefinite offering" if off and "ndefinite" in off else None))
        sold = i.get("sold")
        what = f"Form D filed · {i['industry']}" + (f" · {amt}" if amt else "") + (f" · ${float(sold) / 1e6:.1f}M sold" if sold and sold.replace('.', '').isdigit() and float(sold) > 0 else "") + (f" · {i['state']}" if i.get("state") else "")
        rows.append({"ts": ts, "kind": "form_d", "co": (i.get("name") or "").strip(), "what": what,
                     "round": "Form D", "amount": amt, "link": base + "/", "src": "SEC EDGAR Form D",
                     "usd": (float(sold) if sold and sold.replace('.', '').isdigit() and float(sold) > 0 else offn),
                     "us": (i.get("state") or "").split(", ")[-1].strip() in US_STATES, "stage_ok": None})
    return rows


# ---------------------------------------------------------------- dev@ inbox
def mint(scope, subject):
    r = subprocess.run(["bash", MINT, "mint-google", scope, subject], capture_output=True, text=True, timeout=40)
    tok = r.stdout.strip()
    if r.returncode or not tok:
        raise RuntimeError("token mint failed: " + (r.stderr.strip().splitlines() or ["no output"])[-1])
    return tok


def gmail(cache, q):
    tok = mint("https://www.googleapis.com/auth/gmail.readonly", DEV)
    H = {"Authorization": "Bearer " + tok}
    B = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    ids, pt = [], None
    while True:
        p = {"q": q, "maxResults": 500}
        if pt:
            p["pageToken"] = pt
        d = get(B + "?" + urllib.parse.urlencode(p), H)
        ids += [m["id"] for m in d.get("messages", [])]
        pt = d.get("nextPageToken")
        if not pt or len(ids) > 1500:
            break
    mc = cache.setdefault("gmail", {})
    out = []
    for i in ids:
        if i not in mc:
            d = get(B + f"/{i}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date", H)
            hd = {x["name"]: x["value"] for x in d["payload"]["headers"]}
            mc[i] = {"ts": iso(dt.datetime.fromtimestamp(int(d["internalDate"]) / 1000, dt.timezone.utc)),
                     "date": hd.get("Date"), "from": hd.get("From", ""), "subject": hd.get("Subject", ""), "snippet": html.unescape(d.get("snippet", ""))[:300]}
        out.append(mc[i])
    return out


ATS = re.compile(r"greenhouse-mail\.io|ashbyhq\.com|myworkday\.com|workablemail\.com|lever\.co|smartrecruiters|icims|jobvite|rippling|bamboohr|workday", re.I)
REJ = re.compile(r"unfortunately|not (?:to )?mov(?:e|ing) forward|move forward with other|decided to (?:pursue|proceed with) other|other candidates|not be (?:moving|proceeding)|will not be (?:moving|proceeding)|position has been filled|no longer under consideration|not selected|regret to inform", re.I)
INT = re.compile(r"\binterview\b|schedule (?:a|time|your)|next steps?\b|your availability|phone screen|technical assessment|coding (?:challenge|assessment)|book a time", re.I)
SKIP = re.compile(r"security code|verification code|verify your email|confirm your email", re.I)


def ats_company(frm, subj):
    name = email.utils.parseaddr(frm)[0].strip().strip('"')
    m = re.match(r"^(.+?)\s+(?:Hiring|Talent|Careers|Recruiting|People|Workday|HR|Team)\b", name)
    if m and not re.search(r"greenhouse|workday notification|colleague zone", m.group(1), re.I):
        return m.group(1).strip("| ").replace("Talent | ", "")
    for pat in (r"application (?:to|at|with|for .+? at)\s+(.+?)(?:\s+for\b|!|$)", r"Update From\s+(.+)$", r"interest in (?:joining )?(.+?)(?:!|$)",
                r"Your (.+?) Application\b", r"on your .+ Application at\s+(.+)$", r"Recent (.+?) Job Application", r"Thank you from (.+)$",
                r"applying to (.+?)(?:!|$)", r" - (.+)$"):
        m = re.search(pat, subj, re.I)
        if m:
            return m.group(1).strip(" !.")
    addr = email.utils.parseaddr(frm)[1]
    loc = addr.split("@")[0]
    if "myworkday" in addr and loc not in ("no-reply", "noreply"):
        return loc.split("_")[0].capitalize()
    return name or addr


def jobs_rows(msgs):
    rows = []
    for m in msgs:
        if not ATS.search(m["from"]) or SKIP.search(m["subject"]):
            continue
        text = m["subject"] + " " + m["snippet"]
        kind = "rejection" if REJ.search(text) else "interview invite" if INT.search(text) and not re.search(r"thank you for (?:applying|your (?:application|interest))", m["subject"], re.I) else "application received"
        rows.append({"ts": m["ts"], "kind": kind, "co": ats_company(m["from"], m["subject"]),
                     "what": f"{kind}: {m['subject']}", "src": "dev@ inbox (ATS mail)"})
    return rows


def upwork_rows(msgs):
    jobs, replies = [], []
    for m in msgs:
        if not re.search(r"upwork\.com", m["from"], re.I):
            continue
        s = m["subject"]
        if s.lower().startswith("new job alert"):
            jobs.append({"ts": m["ts"], "kind": "job_read", "co": "Upwork", "what": s.split(":", 1)[-1].strip(), "src": "dev@ inbox (Upwork alert)"})
            continue
        mm = re.match(r"^(.+?) sent you a message", s)
        if mm:
            first = mm.group(1).split()[0]
            replies.append({"ts": m["ts"], "kind": "client_reply", "co": first, "what": m["snippet"] or s, "src": "dev@ inbox (Upwork message)"})
        elif re.search(r"offer|contract|proposal|interview|invit|payment|milestone", s, re.I) and not re.search(r"survey|research", s, re.I):
            replies.append({"ts": m["ts"], "kind": "upwork_notice", "co": "Upwork", "what": s, "src": "dev@ inbox (Upwork)"})
    return jobs, replies


def mail_at(m):
    """The email's Date header as ISO UTC (the sender's clock), else Gmail's receive time."""
    try:
        return iso(email.utils.parsedate_to_datetime(m["date"]))
    except Exception:
        return m["ts"]


# ---------------------------------------------------------------- job posts (AI / ML engineer roles) + Upwork posts
# DOMAINS.md domain 2: JOB POSTS = AI/ML engineer roles, contract or full-time, remote/US; one-shot = video + small demo.
# UPWORK = the wired one-shot system: product/UI -> live demo, system/integration -> architecture page, script/data -> terminal run.
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
JOB_AI = re.compile(r"\b(?:A\.?I|ML|MLOps|LLMs?|GenAI|Gen AI|generative|machine learning|deep learning|NLP|computer vision|agent(?:s|ic)?|applied scientist|inference|RAG)\b", re.I)
JOB_ENG = re.compile(r"engineer|developer|architect|\bSWE\b", re.I)
JOB_NOT = re.compile(r"\b(?:sales|account executive|recruiter|marketing|designer|manager, (?:sales|marketing)|intern(?:ship)?)\b", re.I)


def ai_role(title):
    return bool(JOB_AI.search(title or "") and JOB_ENG.search(title or "") and not JOB_NOT.search(title or ""))


def level_of(title):
    m = re.search(r"\b(founding|principal|staff|lead|senior|sr\.?|junior|jr\.?|mid-level|new grad|head of)\b", title or "", re.I)
    return {"sr": "Senior", "sr.": "Senior", "jr": "Junior", "jr.": "Junior"}.get(m.group(1).lower(), m.group(1).title()) if m else None


def ago_to_ts(text):
    """'13 minutes ago' / 'about 5 hours' / '1 day ago' / 'yesterday' -> ISO UTC; None when older or unparseable."""
    t = (text or "").lower()
    if re.search(r"just now|moments? ago|recently", t):
        return iso(NOW)
    m = re.search(r"(\d+|an?|one)\s*(second|minute|min|hour|hr|day|week|month|year)s?", t)
    if not m:
        return iso(NOW - dt.timedelta(days=1)) if "yesterday" in t else None
    n = 1 if m.group(1) in ("a", "an", "one") else int(m.group(1))
    unit = {"second": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600, "day": 86400, "week": 604800, "month": 2592000, "year": 31536000}[m.group(2)]
    return iso(NOW - dt.timedelta(seconds=n * unit))


def ttl(cache, name, secs, fn):
    """Rate-limited sources: re-poll at most every `secs`; rows are re-filtered to the 48 h window every pass."""
    c = cache.setdefault("ttl", {}).get(name)
    if c and time.time() - c["at"] < secs:
        rows = c["rows"]
    else:
        try:
            rows = fn()
        except Exception:
            if not c:
                raise
            c["at"] = time.time() - secs + 300  # keep the last read rows, retry in 5 min
            rows = c["rows"]
        else:
            cache["ttl"][name] = {"at": time.time(), "rows": rows}
    return [r for r in rows if recent(r["signal_at"])]


def post(src, board, co, title, link, signal_at, **kw):
    r = {"post": True, "src": src, "board": board, "co": (co or "").strip(), "what": re.sub(r"\s+", " ", title or "").strip(),
         "link": link, "signal_at": signal_at, "ts": signal_at, "kind": "post", "status": "Found"}
    r.update({k: v for k, v in kw.items() if v not in (None, "", [])})
    return r


def linkedin_jobs():
    rows, seen = [], set()
    for kw in ('"AI engineer" OR "machine learning engineer" OR "ML engineer"', '"LLM" OR "AI agent" OR "applied AI" engineer'):
        for jt, emp in (("F", "Full-time"), ("C", "Contract")):
            q = {"keywords": kw, "location": "United States", "f_WT": "2", "f_TPR": "r172800", "f_JT": jt, "start": "0"}
            try:
                t = get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + urllib.parse.urlencode(q),
                        {"User-Agent": BROWSER_UA, "Accept": "text/html"}, raw=True).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 429 and rows:  # rate limited mid-pass: keep what this pass read
                    return rows
                raise
            time.sleep(4)  # guest endpoint rate limit (429 at ~10 req in a minute)
            for c in re.findall(r"<li>(.*?)</li>", t, re.S):
                txt = lambda cls: html.unescape(re.sub(r"<[^>]+>|\s+", " ", (re.search(f'class="[^"]*{cls}[^"]*"[^>]*>(.*?)</(?:h3|h4|span|a|div)>', c, re.S) or [None, ""])[1])).strip()
                jid = (re.search(r"jobPosting:(\d+)", c) or [None, None])[1]
                title, co = txt("base-search-card__title"), txt("base-search-card__subtitle")
                if not jid or jid in seen or not ai_role(title):
                    continue
                seen.add(jid)
                when = txt("job-search-card__listdate")
                ts = ago_to_ts(when) or ((re.search(r'datetime="([\d-]+)"', c) or [None, None])[1] or "") + "T12:00:00Z"
                rows.append(post("LinkedIn jobs (guest)", "LinkedIn", co, title, f"https://www.linkedin.com/jobs/view/{jid}/", ts,
                                 location=txt("job-search-card__location") + " · remote", employment=emp, level=level_of(title),
                                 comp=txt("job-search-card__salary-info") or None))
    return rows


def wellfound_jobs():
    rows, seen = [], set()
    for slug in ("machine-learning-engineer", "artificial-intelligence-engineer", "ai-engineer"):
        t = get(f"https://wellfound.com/role/r/{slug}", {"User-Agent": BROWSER_UA, "Accept": "text/html"}, raw=True).decode("utf-8", "replace")
        a = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S).group(1))["props"]["pageProps"]["apolloState"]["data"]
        owner = {}
        for v in a.values():
            if v.get("__typename") == "StartupResult":
                for ref in v.get("highlightedJobListings") or []:
                    owner[ref["__ref"]] = v
        for k, v in a.items():
            if not k.startswith("JobListing") or v["id"] in seen:
                continue
            seen.add(v["id"])
            comp = v.get("compensation") or ""
            if not v.get("remote") or re.search(r"CAD|₹|€|£", comp) or not ai_role(v.get("title")):
                continue
            s = owner.get(k) or {}
            ts = iso(dt.datetime.fromtimestamp(v["liveStartAt"], dt.timezone.utc)) if v.get("liveStartAt") else None
            if not ts:
                continue
            rows.append(post("Wellfound (public)", "Wellfound", s.get("name"), v["title"], f"https://wellfound.com/jobs/{v['id']}-{v.get('slug') or ''}", ts,
                             location=", ".join(v.get("locationNames") or []) + " · remote", employment=(v.get("jobType") or "").title(),
                             level=level_of(v["title"]), comp=comp.split(" • ")[0] or None, logo=s.get("logoUrl"), about=s.get("highConcept")))
    return rows


def yc_jobs():
    rows, seen = [], set()
    for path in ("software-engineer/machine-learning", "software-engineer"):
        t = get(f"https://www.ycombinator.com/jobs/role/{path}", {"User-Agent": BROWSER_UA, "Accept": "text/html"}, raw=True).decode("utf-8", "replace")
        for j in json.loads(html.unescape(re.search(r'data-page="([^"]+)"', t).group(1)))["props"].get("jobPostings") or []:
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            ts = ago_to_ts(j.get("createdAt"))
            loc = j.get("location") or ""
            if not ts or not ai_role(j.get("title")) or not re.search(r"remote|\bUS\b", loc, re.I):
                continue
            rows.append(post("YC jobs (public)", "YC", j.get("companyName"), j["title"], "https://www.ycombinator.com" + j["url"], ts,
                             location=loc, employment=j.get("type"), level=level_of(j["title"]) or j.get("minExperience"),
                             comp=j.get("salaryRange") or None, logo=j.get("companyLogoUrl"), about=j.get("companyOneLiner"), batch=j.get("companyBatchName")))
    return rows


def hn_jobs():
    st = get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=5")["hits"]
    story = next(h for h in st if h["title"].startswith("Ask HN: Who is hiring?"))
    since = int((NOW - dt.timedelta(hours=WINDOW_H)).timestamp())
    d = get(f"https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{story['objectID']}&numericFilters=created_at_i>{since}&hitsPerPage=500")
    rows = []
    for h in d["hits"]:
        if str(h.get("parent_id")) != story["objectID"]:
            continue
        text = html.unescape(re.sub(r"<p>", "\n", h.get("comment_text") or ""))
        text = re.sub(r"<[^>]+>", "", text)
        head = text.split("\n")[0]
        parts = [p.strip() for p in head.split("|")]
        role = next((p for p in parts[1:] if ai_role(p)), None) or (head if ai_role(head) else None)
        if not role or not re.search(r"remote|\bUS\b|USA|United States|SF|NYC|San Francisco|New York", head, re.I):
            continue
        rows.append(post(f"HN Who is hiring ({story['title'].split('(')[-1].rstrip(')')})", "HN", parts[0], role,
                         f"https://news.ycombinator.com/item?id={h['objectID']}", h["created_at"][:19] + "Z",
                         location=next((p for p in parts if re.search(r"remote|onsite|hybrid", p, re.I)), None),
                         employment=next((p for p in parts if re.search(r"full.?time|contract|part.?time", p, re.I)), None),
                         level=level_of(role), comp=next((p for p in parts if "$" in p), None)))
    return rows


UP_FIT = re.compile(r"\bA\.?I\b|\bLLMs?\b|\bGPT|OpenAI|Claude|Anthropic|\bagent(?:s|ic)?\b|automat|\bn8n\b|zapier|make\.com|machine learning|\bML\b|"
                    r"data engineer|\bETL\b|data pipeline|pipeline|scrap|data extraction|crawl|chatbot|\bRAG\b|vector|langchain|"
                    r"\bsoftware (?:engineer|developer)\b|back-?end|front-?end|full[- ]?stack|\bAPI\b|\bREST(?:ful)?\b|GraphQL|FastAPI|Django|Flask|\bNode(?:\.js)?\b|\bReact\b|Next\.js|TypeScript|\bPython\b|\bGolang\b|\bJava\b|\bRust\b|web app|\bSaaS\b|microservices?|\bSQL\b|Postgres|data warehouse|\bdbt\b|Airflow|\bSpark\b|Kafka|DevOps|\bSRE\b|Kubernetes|Docker|Terraform|\bAWS\b|\bGCP\b|\bAzure\b|CI/CD", re.I)
UP_NOT = re.compile(r"captcha|\bPHP\b|wordpress|email sender|proxy|logo|virtual assistant|data entry|lead gen|cold call|appointment setter|video edit|content writ|instructor|trainer|tutor|hackerrank|take a .{0,20}assessment|email address extraction|email extraction|talent pool", re.I)


def oneshot_type(title, desc=""):
    for t in (title, desc):
        if re.search(r"scrap|crawl|\bETL\b|script|data engineer", t, re.I):
            return "terminal run"
        if re.search(r"dashboard|web ?app|website|front-?end|\bUI\b|\bUX\b|landing page|mobile app|\bMVP\b|\bSaaS\b|portal|chatbot|assistant|\bapp\b", t, re.I):
            return "live demo"
        if re.search(r"integrat|\bAPI\b|architect|system|n8n|zapier|make\.com|\bCRM\b|workflow|automat|pipeline|agent|infrastructure|backend", t, re.I):
            return "architecture page"
        if re.search(r"\bdata\b|csv|extract|spreadsheet|excel", t, re.I):
            return "terminal run"
    return "architecture page"


def up_fields(text):
    """Budget / level / client facts from an Upwork tile or alert body (plain text)."""
    g = lambda p: (re.search(p, text, re.I) or [None, None])[1]
    budget = g(r"(Hourly:\s*\$[\d,.]+(?:\s*-\s*\$[\d,.]+)?)") or g(r"(Fixed[- ]price[^\n•]*?\$[\d,.]+[KkMm]?)") or g(r"(Est\.? budget:\s*\$[\d,.]+[KkMm]?)") or g(r"(Budget:\s*\$[\d,.]+[KkMm]?)")
    return {"budget": re.sub(r"\s+", " ", budget).replace("Hourly:", "hourly").strip() if budget else None,
            "level": g(r"\b(Entry level|Intermediate|Expert)\b"),
            "verified": bool(re.search(r"Payment verified", text)),
            "rating": g(r"Payment (?:un)?verified\s*[•\n ]*\s*(\d\.\d+)"),
            "spent": g(r"(\$[\d.,]+[KkMm]?\+?)\s*spent"),
            "country": g(r"spent\s*[•\n ]*\s*([A-Z][A-Za-z .]+?)(?:\s{2,}|\n|$)"),
            "proposals": g(r"Proposals:\s*([^\n•]+?)\s*(?:\n|$)")}


def up_row(src, jid, title, link, ts, desc, skills, f):
    chips = [c for c in (["budget", f["budget"]] if f["budget"] else None, ["level", f["level"]] if f["level"] else None,
                         ["client spent", f["spent"]] if f["spent"] else None, ["rating", "★ " + f["rating"]] if f["rating"] else None,
                         ["proposals", f["proposals"]] if f["proposals"] else None) if c]
    return post(src, "Upwork", "Upwork client" + (" · " + f["country"] if f.get("country") else ""), title, link, ts,
                job=jid, oneshot_type=oneshot_type(title, desc), verified=f["verified"], chips=chips, desc=(desc or "")[:400], skills=skills[:8],
                location=f.get("country"), level=f.get("level"), comp=f.get("budget"))


def gmail_body(H, mid):
    import base64
    x = get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full", H)
    def walk(p):
        if p.get("parts"):
            for c in p["parts"]:
                yield from walk(c)
        elif (p.get("body") or {}).get("data") and p.get("mimeType") == "text/html":
            yield base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace")
    return "".join(walk(x["payload"]))


def upwork_alerts(cache):
    """dev@ 'New job alert' mail (Upwork saved searches), body parsed; the job link resolved from the email's tracking redirect."""
    tok = mint("https://www.googleapis.com/auth/gmail.readonly", DEV)
    H = {"Authorization": "Bearer " + tok}
    d = get("https://gmail.googleapis.com/gmail/v1/users/me/messages?" + urllib.parse.urlencode({"q": f'from:upwork.com subject:"New job alert" newer_than:{WINDOW_H // 24}d', "maxResults": 200}), H)
    uc = cache.setdefault("up_alert", {})
    rows = []
    for m in d.get("messages", []):
        if m["id"] not in uc:
            h = gmail_body(H, m["id"])
            h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
            href = (re.search(r'href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*View job details', h) or [None, None])[1]
            text = html.unescape(re.sub(r"[ \t͏­‌]+", " ", re.sub(r"<[^>]+>", "\n", h)))
            text = re.sub(r"\n\s*\n+", "\n", text)
            title = (re.search(r"submit a proposal when you.re ready\.\s*\n?\s*(.+?)\n", text) or [None, None])[1]
            body = text.split(title, 1)[-1] if title else text
            desc = (re.search(r"^\s*(.+?)(?:\.\.\. more|\n(?:Hourly|Fixed))", body, re.S) or [None, ""])[1]
            skills_line = (re.search(r"(?:USA|spent[^\n]*)\n(.+?)Posted", body, re.S) or [None, ""])[1]
            jid, link = None, None
            if href:
                try:
                    class NoRedir(urllib.request.HTTPRedirectHandler):
                        def redirect_request(self, *a, **k):
                            return None
                    op = urllib.request.build_opener(NoRedir)
                    try:
                        op.open(urllib.request.Request(href.replace("&amp;", "&"), headers={"User-Agent": BROWSER_UA}), timeout=15)
                    except urllib.error.HTTPError as e:
                        link = e.headers.get("Location")
                    m2 = re.search(r"(~0[0-9a-z]{10,})", link or "")
                    jid = m2.group(1) if m2 else None
                    link = f"https://www.upwork.com/jobs/{jid}" if jid else link
                except Exception:
                    pass
            hd = get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}?format=metadata&metadataHeaders=Date&metadataHeaders=Subject", H)
            hh = {x["name"]: x["value"] for x in hd["payload"]["headers"]}
            uc[m["id"]] = {"ts": iso(email.utils.parsedate_to_datetime(hh["Date"])), "subject": hh.get("Subject", ""),
                           "title": (title or hh.get("Subject", "").split(":", 1)[-1]).strip(), "desc": re.sub(r"\s+", " ", desc).strip(),
                           "skills": [s.strip() for s in re.split(r"\n|\s{2,}", skills_line) if s.strip() and not s.strip().startswith("+")][:8],
                           "fields": up_fields(body), "jid": jid, "link": link}
        a = uc[m["id"]]
        rows.append(up_row("dev@ inbox (Upwork alert)", a["jid"], a["title"], a["link"], a["ts"], a["desc"], a["skills"], a["fields"]))
    return rows


UPWORK_CDP = 9402  # /etc/desks/upwork.env DESK_CDP


def upwork_desk():
    """Read-only: open a background tab in the Upwork desk's Chrome, read Best matches + Most recent tiles, close the tab.
    Never clicks, never applies."""
    import itertools
    import websocket
    V = get(f"http://127.0.0.1:{UPWORK_CDP}/json/version", timeout=5)
    ws = websocket.create_connection(V["webSocketDebuggerUrl"], timeout=40, suppress_origin=True)
    ids = itertools.count(1)

    def call(method, params=None, sid=None):
        i = next(ids)
        ws.send(json.dumps({"id": i, "method": method, "params": params or {}, **({"sessionId": sid} if sid else {})}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == i:
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error'].get('message')}")
                return r["result"]
    JS = r"""(() => [...document.querySelectorAll('section[data-ev-sublocation="job_feed_tile"], article[data-test="JobTile"]')].map(s => {
        const a = s.querySelector('a[href*="/jobs/"]'); const q = sel => (s.querySelector(sel) || {}).innerText || "";
        return {uid: s.getAttribute('data-ev-opening_uid') || s.getAttribute('data-ev-job-uid'), href: a && a.getAttribute('href'), title: a && a.innerText.trim(),
                posted: q('[data-test="posted-on"], [data-test="job-pubilshed-date"]'), desc: q('[data-test="job-description-text"], [data-test="UpCLineClamp JobDescription"]'),
                skills: [...s.querySelectorAll('[data-test="token"], .air3-token')].map(x => x.innerText.trim()).filter(Boolean), text: s.innerText}; }))()"""
    rows, seen = [], set()
    tid = call("Target.createTarget", {"url": "about:blank", "background": True})["targetId"]
    try:
        sid = call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        for feed in ("best-matches", "most-recent"):
            call("Page.navigate", {"url": f"https://www.upwork.com/nx/find-work/{feed}"}, sid)
            time.sleep(8)
            for _ in range(4):  # the feed renders 2-10 tiles; "Load More Jobs" is a feed-pagination button (no apply / proposal action)
                call("Runtime.evaluate", {"expression": "(() => { window.scrollTo(0, document.body.scrollHeight); const b = [...document.querySelectorAll('button')].find(b => /^load more jobs$/i.test(b.innerText.trim())); if (b) b.click(); })()"}, sid)
                time.sleep(3)
            tiles = call("Runtime.evaluate", {"expression": JS, "returnByValue": True}, sid)["result"].get("value") or []
            if not tiles:
                u = call("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}, sid)["result"]["value"]
                raise RuntimeError(f"no job tiles on {feed} (page {u})")
            for t in tiles:
                m = re.search(r"(~0[0-9a-z]{10,})", t.get("href") or "")
                jid = m.group(1) if m else ("~02" + t["uid"] if t.get("uid") else None)
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                ts = ago_to_ts(t.get("posted"))
                if not ts:
                    continue
                text = t.get("text") or ""
                desc = t.get("desc") or (re.search(r"hrs/week\n(?:[^\n]*only\n)?(.+?)\nSkills", text, re.S) or [None, ""])[1]
                skills = t.get("skills") or [s for s in ((re.search(r"\nSkills\n(.+?)\n(?:Actively|Verified|Payment)", text, re.S) or [None, ""])[1]).split("\n") if s.strip()]
                rows.append(up_row(f"Upwork desk ({feed})", jid, t.get("title"), f"https://www.upwork.com/jobs/{jid}", ts, desc, skills, up_fields(text)))
    finally:
        try:
            call("Target.closeTarget", {"targetId": tid})
        finally:
            ws.close()
    return rows


def up_fit(r):
    text = " ".join([r["what"], r.get("desc") or "", " ".join(r.get("skills") or [])])
    return bool(UP_FIT.search(text)) and not UP_NOT.search(r["what"] + " " + " ".join(r.get("skills") or []))


# ---------------------------------------------------------------- merge
def merge(old, new, n=None):
    key = lambda e: (e.get("ts"), e.get("kind"), (e.get("co") or "").lower(), (e.get("what") or "")[:60])
    seen, out = set(), []
    for e in sorted(new + [dict(e, src=e.get("src") or "11-20 copy") for e in old], key=lambda e: str(e.get("ts") or ""), reverse=True):
        if key(e) in seen:
            continue
        seen.add(key(e))
        out.append(e)
    return out[:n] if n else out


def base():
    os.makedirs(STATE, exist_ok=True)
    cur = json.load(open(OUT))
    if "live_at" not in cur:  # a fresh build_snapshot.py output: that is the frozen base
        json.dump(cur, open(FROZEN, "w"), indent=1)
        return cur
    return json.load(open(FROZEN))


LIVE_ROWS = os.path.join(STATE, "live-rows.json")
HUNTS_LIVE = os.path.join(HERE, "public", "people", "hunts-live.json")


def fetch_live():
    """Poll every live source once; save the rows (with signal_at / found_at) to state/live-rows.json."""
    global NOW
    NOW = dt.datetime.now(dt.timezone.utc)
    os.makedirs(STATE, exist_ok=True)
    try:
        cache = json.load(open(CACHE))
    except Exception:
        cache = {}
    status = {}

    def src(name, fn):
        t0 = time.time()
        try:
            rows = fn()
            status[name] = {"ok": True, "rows": len(rows), "checked": iso(NOW), "secs": round(time.time() - t0, 1)}
            return rows
        except Exception as e:
            status[name] = {"ok": False, "rows": 0, "checked": iso(NOW), "error": f"{type(e).__name__}: {str(e)[:200]}"}
            return []

    funding = (src("Launch YC", yc_launches) + src("SEC EDGAR Form D", lambda: form_d(cache))
               + src("TechCrunch RSS", lambda: tc_feeds())
               + src("Crunchbase News RSS", lambda: rss("https://news.crunchbase.com/feed/", "Crunchbase News RSS", False))
               + src("Google News RSS", gnews))
    msgs = src("dev@ inbox (Gmail)", lambda: gmail(cache, f"newer_than:{WINDOW_H // 24}d"))
    for m in msgs:
        m["signal_at"] = mail_at(m)
    jobs = jobs_rows(msgs)
    up_jobs, up_replies = upwork_rows(msgs)
    posts = (src("LinkedIn jobs (guest)", lambda: ttl(cache, "linkedin", 1800, linkedin_jobs))
             + src("Wellfound (public)", lambda: ttl(cache, "wellfound", 900, wellfound_jobs))
             + src("YC jobs (public)", lambda: ttl(cache, "ycjobs", 900, yc_jobs))
             + src("HN Who is hiring", lambda: ttl(cache, "hn", 300, hn_jobs)))
    status["dev@ inbox (job alerts)"] = {"ok": True, "rows": 0, "checked": iso(NOW),
                                         "note": "no LinkedIn / Indeed / Wellfound alert mail in dev@ in 48 h (no alert subscriptions on dev@)"}
    up_posts = src("dev@ inbox (Upwork alert)", lambda: upwork_alerts(cache)) + src("Upwork desk (CDP)", lambda: ttl(cache, "updesk", 600, upwork_desk))
    seen_post = set()
    posts = [r for r in sorted(posts, key=lambda r: r["signal_at"], reverse=True)
             if not ((r["co"].lower(), r["what"].lower()) in seen_post or seen_post.add((r["co"].lower(), r["what"].lower())))]
    by_job = {}
    for r in sorted(up_posts, key=lambda r: r["src"].startswith("dev@")):  # desk rows (exact posted time, proposals) win over the alert copy
        k = r.get("job") or r["what"].lower()
        if k not in by_job:
            by_job[k] = r
        elif r.get("signal_at") < by_job[k]["signal_at"]:
            by_job[k]["signal_at"] = by_job[k]["ts"] = r["signal_at"]
    up_posts = list(by_job.values())
    for r in up_posts:
        r["fit_ok"] = up_fit(r)
    for r in posts:
        r["fit_ok"] = True  # already filtered: AI/ML engineer title, remote or US, last 48 h
    by_ts = {m["ts"] + m["subject"][:40]: m["signal_at"] for m in msgs}
    found = cache.setdefault("found", {})
    for r in funding + jobs + up_jobs + up_replies + posts + up_posts:
        r["live"] = True
        r["signal_at"] = r.get("signal_at") or by_ts.get(r["ts"] + (r.get("what") or "").split(": ", 1)[-1][:40]) or r["ts"]
        if r.get("post") and r.get("link"):  # posts: keyed on the job link; the first posted-time estimate sticks ("3 hours ago" drifts)
            k = "post|" + r["link"]
            first = cache.setdefault("post_at", {}).setdefault(r["link"], r["signal_at"])
            r["signal_at"] = r["ts"] = min(first, r["signal_at"])
        else:
            k = "|".join([r["src"], r["ts"], (r.get("co") or "")[:40], (r.get("what") or "")[:40]])
        found.setdefault(k, iso(NOW))
        r["found_at"] = found[k]
    for r in funding:
        r["fit_ok"] = fit(r)

    cut = iso(NOW - dt.timedelta(hours=WINDOW_H + 24))
    cache["gmail"] = {k: v for k, v in cache.get("gmail", {}).items() if v.get("ts", "") >= cut}
    cache["formd"] = {k: v for k, v in cache.get("formd", {}).items() if "error" not in v and (v.get("file_date") or "") >= cut[:10]}  # errors retry next pass
    cache["found"] = {k: v for k, v in found.items() if v >= cut}
    cache["post_at"] = {k: v for k, v in cache.get("post_at", {}).items() if v >= cut}
    cache["up_alert"] = {k: v for k, v in cache.get("up_alert", {}).items() if v.get("ts", "") >= cut}
    json.dump(cache, open(CACHE + ".tmp", "w"))
    os.replace(CACHE + ".tmp", CACHE)
    out = {"at": iso(NOW), "status": status, "funding": funding, "jobs": jobs, "up_jobs": up_jobs, "up_replies": up_replies, "posts": posts, "up_posts": up_posts}
    json.dump(out, open(LIVE_ROWS + ".tmp", "w"))
    os.replace(LIVE_ROWS + ".tmp", LIVE_ROWS)
    return status


def hunts_live():
    """The real hunt's ready-to-record rows (public/people/hunts-live.json), as funding feed rows.
    Accepts a list, or {"rows": [...]}; a row in the UI's built shape (target/title/url/source) is mapped too."""
    try:
        d = json.load(open(HUNTS_LIVE))
    except FileNotFoundError:
        return [], "not written yet"
    except Exception as e:
        return [], f"unreadable: {type(e).__name__}: {e}"
    rows = d if isinstance(d, list) else d.get("rows") or d.get("feed") or d.get("hunts") or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        e = dict(r)
        e.setdefault("co", r.get("target") or r.get("company"))
        e.setdefault("what", r.get("title") or r.get("signal") or r.get("what"))
        e.setdefault("link", r.get("url"))
        e.setdefault("ts", r.get("signal_at") or r.get("found_at"))
        e.setdefault("signal_at", e.get("ts"))
        e["src"] = r.get("src") or r.get("source") or "hunts-live.json"
        e["live"] = True
        e["hunt"] = True
        out.append(e)
    return out, f"{len(out)} rows"


def compose():
    """tyler.json = roosts from the copy (current clients) + hunt rows from live data ONLY (Tyler 11-21:
    no mock, no stale rows): hunts-live.json, live funding rows that fit, live dev@ mail."""
    now = dt.datetime.now(dt.timezone.utc)
    d = base()
    try:
        L = json.load(open(LIVE_ROWS))
    except Exception:
        L = {"at": None, "status": {}, "funding": [], "jobs": [], "up_jobs": [], "up_replies": []}
    hl, hl_note = hunts_live()
    status = dict(L["status"], **{"hunts-live.json": {"ok": not hl_note.startswith("unreadable"), "rows": len(hl), "note": hl_note, "checked": iso(now)}})
    lane = lambda i: next(h for h in d["hunts"] if h["id"] == i)

    f = lane("funding")
    fsrc = ["Launch YC", "SEC EDGAR Form D", "TechCrunch RSS", "Crunchbase News RSS", "Google News RSS"]
    ok = [s for s in fsrc if (status.get(s) or {}).get("ok")]
    f["backend"] = dict(f.get("backend") or {}, agent="funding")  # the funding-hunt agent's role name
    fitting = [r for r in L["funding"] if r.get("fit_ok")]
    hunt_fund = [r for r in hl if (r.get("type") or r.get("lane") or "funding") in ("funding",)]
    hunt_cos = {(r.get("co") or "").strip().lower() for r in hunt_fund}
    f["feed"] = merge([], hunt_fund + [r for r in fitting if (r.get("co") or "").strip().lower() not in hunt_cos])  # the hunt's row wins
    f["state"] = "running" if ok or hunt_fund else "failed"
    f.pop("empty", None)
    if not f["feed"]:
        f["empty"] = {"title": "No funded founders in the last 48 h", "why": "Searched " + ", ".join(ok) + f": {len(L['funding'])} raises in 48 h, none fit AI / $500K-$5M / US.", "next": "Next search in 2 min"}
    f["searched"] = {"rows_48h": len(L["funding"]), "fit": len(fitting), "hunt_rows": len(hunt_fund),
                     "rule": "technical founders (not checked yet), AI product, $500K-$5M pre-seed/seed, US, last 48 h"}
    f["funnel"] = ([{"k": "ready to record", "v": len(hunt_fund), "note": "the hunt"}, {"k": "raises seen", "v": len(L["funding"]), "note": "last 48 h"},
                    {"k": "fit", "v": len(fitting), "note": "AI · $500K-$5M · US"}])
    f["checked"] = L["at"]
    f["source"] = "hunts-live.json · " + " · ".join(fsrc) + " (live from Ra)"
    for r in f["feed"]:
        r.setdefault("found_at", iso(now))

    j = lane("jobs")
    cnt = lambda k: sum(1 for r in L["jobs"] if r["kind"] == k)
    j["legacy"] = {"funnel": j.get("funnel"), "extra": j.get("extra"), "feed": j.get("feed")} if "legacy" not in j else j["legacy"]
    posts = [dict(r, agent="sekhmet", front="eagle", type="job", subtype=r["board"], oneshot_type="video + demo")
             for r in L.get("posts", []) if r.get("fit_ok") and recent(r["signal_at"])]
    j["backend"] = dict(j.get("backend") or {}, agent="sekhmet")
    # the one-shot builder's rows (hunts/oneshots/agent, "Ready to record") replace the live row with the same link
    hl_jobs = [r for r in hl if (r.get("type") or r.get("lane")) in ("job", "jobs")]
    built = {r.get("link") for r in hl_jobs}
    j["feed"] = merge([], hl_jobs + [r for r in posts if r.get("link") not in built])  # AI/ML engineer posts only (Tyler 11-21: legacy letter applications are not hunt rows)
    j["funnel"] = [{"k": "AI/ML posts found", "v": len(posts), "note": "last 48 h"}, {"k": "AI/ML posts answered", "v": 0, "note": "video + demo"}]
    j["searched"] = {"rule": "AI / ML engineer roles (AI, ML, LLM/agent, applied AI), contract or full-time, remote/US, posted in the last 48 h",
                     "sources": ["LinkedIn jobs (guest)", "Wellfound (public)", "YC jobs (public)", "HN Who is hiring", "dev@ inbox (job alerts)"]}
    j["source"] = "LinkedIn jobs (guest) · Wellfound · YC jobs · HN Who is hiring (live from Ra)"
    j["state"] = "running" if any((status.get(x) or {}).get("ok") for x in j["searched"]["sources"]) else "failed"
    j.pop("empty", None)
    if not j["feed"]:
        j["empty"] = {"title": "No AI/ML engineer posts in the last 48 h", "why": "Searched " + ", ".join(j["searched"]["sources"]), "next": "Next search in 2 min"}
    j.pop("extra", None)
    j["live_extra"] = f"dev@ last 48 h (letter applications): {cnt('application received')} received · {cnt('rejection')} rejections · {cnt('interview invite')} interview invites"
    j["kicker"] = "AI / ML engineer roles, answered with video + demo"
    j["oneshot"] = "Video + build-first demo of the posted need"
    j["checked"] = L["at"]
    if isinstance(d.get("enrich"), dict):
        d["enrich"]["jobs"] = []  # built job one-shots ride in the feed (above), not as a second copy here

    u = lane("upwork")
    u["legacy"] = {"queue": u.get("queue"), "feed": u.get("feed"), "note": "11-19/11-20 sources: stage.json, studio.json, Upwork ledger"}
    u["queue"] = {"ready": [], "recorded": [], "sent": []}  # built one-shots ride in the feed (below)
    ups = [dict(r, agent="upwork", front="eagle", type="upwork", subtype=r["oneshot_type"])
           for r in L.get("up_posts", []) if r.get("fit_ok") and recent(r["signal_at"])]
    hl_up = [dict(r, subtype=r.get("oneshot_type")) for r in hl if (r.get("type") or r.get("lane")) == "upwork"]
    built = {r.get("link") for r in hl_up}
    u["backend"] = dict(u.get("backend") or {}, agent="upwork")
    u["feed"] = merge([], hl_up + [r for r in ups if r.get("link") not in built])  # AI / agent / automation / data-engineering posts only, last 48 h
    u["searched"] = {"rows_48h": len(L.get("up_posts", [])), "fit": len(ups),
                     "rule": "AI/ML, automation, software engineering, data, DevOps/cloud jobs, posted in the last 48 h (drops PHP, proxy / email-sender apps, captcha, VA work)"}
    u["source"] = "dev@ inbox (Upwork alert) · Upwork desk Best matches + Most recent (CDP, read-only)"
    u["state"] = "running" if any((status.get(x) or {}).get("ok") for x in ("dev@ inbox (Upwork alert)", "Upwork desk (CDP)")) else "failed"
    u["live_extra"] = f"dev@ last 48 h: {len(L['up_jobs'])} job alerts · {sum(1 for r in L['up_replies'] if r['kind'] == 'client_reply')} client messages"
    u["checked"] = L["at"]

    nw = next((r for r in d["roosts"] if r["id"] == "network"), None)
    if nw is not None:  # Tyler 11-21: interview invites from letter applications go to the roost thread, never the hunt feed
        nw["feed"] = merge([e for e in (nw.get("feed") or []) if e.get("kind") != "interview invite"],
                           [r for r in L["jobs"] if r["kind"] == "interview invite"])
    cl = next((r for r in d["roosts"] if r["id"] == "clients"), None)
    if cl is not None:
        names = {c["name"].lower() for c in cl.get("rows", [])}
        cl["feed"] = merge(cl.get("feed") or [], [r for r in L["up_replies"] if r["kind"] == "client_reply" and r["co"].lower() in names])

    d["built"] = iso(now)
    d["live_at"] = L["at"]
    d["live_sources"] = status
    d["live_note"] = ("Hunt rows are live only: hunts-live.json, funding (Launch YC, SEC Form D, TechCrunch, Crunchbase News, Google News; polled every 2 min) "
                      "job posts (LinkedIn guest, Wellfound, YC jobs, HN Who is hiring), Upwork (dev@ alerts + the Upwork desk feed) and the dev@ inbox. Roosts (clients, network) are from the 11-20 copy (copy_at) plus live client messages.")
    tmp = OUT + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1, default=str)
    os.replace(tmp, OUT)
    return status


if __name__ == "__main__":
    loop = int(sys.argv[sys.argv.index("--loop") + 1]) if "--loop" in sys.argv else 0
    last_fetch, last_hl = 0, None
    while True:
        try:
            if time.time() - last_fetch >= (loop or 0):
                st = fetch_live()
                last_fetch = time.time()
                print(iso(dt.datetime.now(dt.timezone.utc)), "fetch", json.dumps({k: (v["rows"] if v["ok"] else "ERR " + v["error"]) for k, v in st.items()}), flush=True)
                compose()
            else:
                m = os.path.getmtime(HUNTS_LIVE) if os.path.exists(HUNTS_LIVE) else None
                if m != last_hl:
                    last_hl = m
                    st = compose()
                    print(iso(dt.datetime.now(dt.timezone.utc)), "compose hunts-live", st["hunts-live.json"]["note"], flush=True)
        except Exception:
            traceback.print_exc()
        if not loop:
            break
        time.sleep(10)
