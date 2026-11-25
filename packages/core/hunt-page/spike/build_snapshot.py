#!/usr/bin/env python3
"""THROWAWAY SPIKE. Builds public/snapshot.json from the real copies on Ra.

Sources (read, never written):
  ~eagle/dev/eagle-eye/data.json, cold-apps.json, lanes.put.json, studio.json  (Eagle Eye's last copy, 2026-11-20 17:48Z)
  ~upwork/.claude/state/net/upwork/ledger.jsonl                                  (Upwork ledger)
  knowledge/net/work/vsl/*/stage.json                                            (one-shot packages)
"""
import glob, json, os, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
VSL = os.path.expanduser("~/dev/utopia-models/knowledge/net/work/vsl")


def sudo_read(user, path):
    return subprocess.run(["sudo", "-n", "-u", user, "cat", path], capture_output=True, text=True, check=True).stdout


def latest(events, n=5):
    return sorted(events, key=lambda e: str(e.get("ts") or ""), reverse=True)[:n]


data = json.loads(sudo_read("eagle", "/home/eagle/dev/eagle-eye/data.json"))
cold = json.loads(sudo_read("eagle", "/home/eagle/dev/eagle-eye/cold-apps.json"))
lanes = json.loads(sudo_read("eagle", "/home/eagle/dev/eagle-eye/lanes.put.json"))["lanes"]
studio = json.loads(sudo_read("eagle", "/home/eagle/dev/eagle-eye/studio.json"))
ledger = []
for line in sudo_read("upwork", "/home/upwork/.claude/state/net/upwork/ledger.jsonl").splitlines():
    try:
        ledger.append(json.loads(line))
    except Exception:
        pass

H = data["hunts"]

# ---------- Upwork one-shot queue ----------
packages = {}
for f in glob.glob(f"{VSL}/*/stage.json"):
    slug = os.path.basename(os.path.dirname(f))
    packages[slug] = json.load(open(f))
ready, recorded, sent = [], [], []
for slug, p in packages.items():
    if p.get("sent"):
        continue  # sent rows come from the ledger's vsl_sent events
    rec = (p.get("vsl") or {}).get("recorded")
    demo = p.get("demo_ready") or {}
    pend = p.get("demo_pending") or {}
    item = {"slug": slug, "job": p.get("job") or p.get("job_key"),
            "demo": demo.get("url") or pend.get("url"), "demo_ok": bool(demo.get("url")),
            "note": p.get("note") or (("demo ready " + demo["ts"]) if demo.get("ts") else (pend.get("note") or "")),
            "source": f"net/work/vsl/{slug}/stage.json"}
    (recorded if rec else ready).append(item)
for c in studio.get("clients", []):
    for v in c.get("videos", []):
        takes = [t for t in v.get("takes", []) if t.get("status") == "ready"]
        if takes:
            t = takes[-1]
            recorded.append({"slug": c["client"], "note": f"{len(takes)} takes ready, last {t['at'][:16]}Z, {round(t['duration'])} s (studio.json)",
                             "source": "studio.json"})
            ready[:] = [r for r in ready if r["slug"] != c["client"]]
for e in ledger:
    if e.get("event") == "vsl_sent":
        sent.append({"slug": e.get("client"), "ts": e.get("ts"), "note": e.get("note", ""), "file": e.get("file"), "source": "Upwork ledger vsl_sent"})
sent.sort(key=lambda r: r["ts"] or "", reverse=True)

up_feed = latest([e for e in lanes["upwork"]["events"]], 5)

hunts = [
    {
        "id": "funding", "name": "Funding + launch events", "kicker": "Founders funded or launched in the last 48 h",
        "state": "not_started",
        "empty": {"title": "Hunt not running yet",
                  "why": "Form D + Launch YC adapters are in the build. Nothing has been searched, so there is no number to show.",
                  "next": "Adapters: SEC Form D, Launch YC, TechCrunch venture RSS, Crunchbase News RSS"},
        "backend": {"agent": None, "does": "finds funded founders, preps the repo walkthrough"},
        "frontend": {"agent": "eagle", "does": "records the one-shot with Tyler"},
        "funnel": None, "feed": [], "queue": None, "checked": None,
        "oneshot": "Walkthrough of the founder's live product: 3 verified improvements; built demo for the top ~10%",
    },
    {
        "id": "jobs", "name": "Job posts", "kicker": "Cold applications merged in: a posted need, answered with a one-shot",
        "state": "running",
        "backend": {"agent": "sekhmet", "does": "applies, reads replies (applications.db + inbox)"},
        "frontend": {"agent": "eagle", "does": "records the one-shot with Tyler"},
        "funnel": [
            {"k": "applied", "v": cold["applications_submitted"], "note": "last 28 days"},
            {"k": "answered", "v": cold["replies"], "note": "rejections included"},
            {"k": "interviews", "v": cold["interviews"]},
            {"k": "one-shots", "v": None, "note": "not measured: no video yet"},
        ],
        "extra": f"{cold['last_24h']} in 24 h · {cold['last_7d']} in 7 d · {cold['applications_submitted_total']:,} all time · cold email {H['cold_email']['sent']}→{H['cold_email']['answered']} · LinkedIn {H['linkedin']['sent']}→{H['linkedin']['answered']}",
        "feed": latest(lanes["cold_apps"]["events"] + lanes["cold_email"]["events"] + lanes["linkedin"]["events"], 5),
        "queue": {"empty": {"title": "No one-shots in this queue",
                            "why": f"Job posts are answered by letter today: {cold['applications_submitted']:,} letters, 0 videos. The one-shot builder for job posts is part of the rehaul build.",
                            "next": "Builder: pick the top-fit posts each day, stage a package, hand to Eagle"}},
        "checked": cold["updated"],
        "source": H["cold_apps"]["source"],
        "oneshot": "Build-first demo of the posted need",
    },
    {
        "id": "upwork", "name": "Upwork", "kicker": "Multiple one-shot types: live demo, architecture page, terminal run",
        "state": "running",
        "backend": {"agent": "upwork", "does": "reads jobs, stages packages, sends proposals"},
        "frontend": {"agent": "eagle", "does": "records the one-shot with Tyler"},
        "funnel": [
            {"k": "proposals", "v": H["upwork"]["sent"], "note": "all time"},
            {"k": "answered", "v": H["upwork"]["answered"]},
            {"k": "videos sent", "v": data["videos_sent"]},
            {"k": "contracts", "v": data["contracts"]},
            {"k": "paid", "v": "$100", "note": "+ $100 pending"},
        ],
        "extra": "Video proposals 1 of 5 won · letters 0 of ~50",
        "feed": up_feed,
        "queue": {"ready": ready, "recorded": recorded, "sent": sent},
        "checked": H["upwork"]["last_row"]["ts"],
        "source": H["upwork"]["source"],
        "oneshot": "Build-first demo of the posted need, recorded as a 60-120 s VSL",
    },
]

R = data["roosts"]
net = R["network"]
roosts = [
    {"id": "clients", "name": "Clients", "agent": "purser", "headline": {"v": len(R["clients"]["rows"]), "k": "clients"},
     "rows": R["clients"]["rows"], "feed": latest(lanes["clients"]["events"], 5), "checked": R["clients"]["at"],
     "source": R["clients"]["source"], "paid_total": data.get("paid_total")},
    {"id": "network", "name": "Network", "agent": "atlas", "headline": {"v": net["people"], "k": "people"},
     "channels": net["channels"], "in_contacts": net["in_contacts"],
     "feed": latest(lanes["network"]["events"] + ([{"ts": net["latest"]["ts"], "kind": net["latest"]["kind"], "what": net["latest"]["what"], "co": net["latest"]["co"]}]), 5),
     "rows": [r for r in net["rows"] if r.get("what")][:12], "checked": net["at"], "source": net["source"],
     "reason": net.get("reason")},
]

# ---------- opt-a v2 enrichment: real per-row fields (Tyler 11-21: "fill the row") ----------
# Job posts: the 11-20 novaserver backup of sekhmet's apply store on Ra (postings.jsonl: board, level, location, role class).
# Upwork: the Upwork ledger (title, fit, proposals, bid, connects, type, demo format, client replies, closed).
# Logos: the company's own logo, read from its job board page (Ashby square logo, else its website's icon), cached in public/logos/.
import re, urllib.request, urllib.parse, html as _html
POSTINGS = os.path.expanduser("~/ra-backups/novaserver-2026-11-20/state-sekhmet/state/sf/apply/postings.jsonl")
LOGOS = f"{HERE}/public/logos"
os.makedirs(LOGOS, exist_ok=True)
companies = json.loads(sudo_read("eagle", "/home/eagle/dev/eagle-eye/lanes.json")).get("companies", {})


def http(url, n=600000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read(n), r.headers.get("Content-Type", ""), r.geturl()


def site_icon(site):
    """Largest icon the company's own homepage declares (apple-touch-icon first), else /favicon.ico."""
    try:
        body, _, final = http(site)
        page = body.decode("utf-8", "ignore")
        links = re.findall(r"<link[^>]+>", page, re.I)
        best = None
        for l in links:
            rel = (re.search(r'rel=["\']([^"\']+)', l, re.I) or [None, ""])[1].lower()
            href = (re.search(r'href=["\']([^"\']+)', l, re.I) or [None, ""])[1]
            if not href or "icon" not in rel or "mask" in rel:
                continue
            size = int((re.search(r'sizes=["\'](\d+)', l, re.I) or [None, "0"])[1])
            score = (2 if "apple" in rel else 1) * 1000 + size
            if not best or score > best[0]:
                best = (score, urllib.parse.urljoin(final, _html.unescape(href)))
        return best[1] if best else urllib.parse.urljoin(final, "/favicon.ico")
    except Exception:
        return None


def board_logo(posting_url):
    """(logo_url, website) from the company's job board page."""
    try:
        host = urllib.parse.urlparse(posting_url).netloc
        if "ashbyhq.com" in host:
            org = urllib.parse.urlparse(posting_url).path.strip("/").split("/")[0]
            page = http(f"https://jobs.ashbyhq.com/{org}")[0].decode("utf-8", "ignore")
            sq = re.search(r'"logoSquareImageUrl":"([^"]+)"', page)
            web = re.search(r'"publicWebsite":"([^"]+)"', page)
            web = web.group(1) if web else None
            return (sq.group(1) if sq else (site_icon(web) if web else None)), web
        if "greenhouse.io" in host:
            org = urllib.parse.urlparse(posting_url).path.strip("/").split("/")[0]
            page = http(f"https://job-boards.greenhouse.io/{org}")[0].decode("utf-8", "ignore")
            img = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="logo"', page) or re.search(r'class="logo"[^>]*src="([^"]+)"', page)
            return (_html.unescape(img.group(1)) if img else None), None
        site = f"https://{host.replace('jobs.', '').replace('careers.', '')}/"
        return site_icon(site), site
    except Exception:
        return None, None


def cache_logo(key, url):
    if not url:
        return None
    for ext in ("png", "jpg", "svg", "ico", "webp"):
        if os.path.exists(f"{LOGOS}/{key}.{ext}"):
            return f"/logos/{key}.{ext}"
    if url == "cached-only":
        return None
    try:
        body, ctype, _ = http(url, 2_000_000)
        if len(body) < 100:
            return None
        ext = "svg" if "svg" in ctype else "jpg" if "jpeg" in ctype else "ico" if "icon" in ctype or url.split("?")[0].endswith(".ico") else "webp" if "webp" in ctype else "png"
        open(f"{LOGOS}/{key}.{ext}", "wb").write(body)
        return f"/logos/{key}.{ext}"
    except Exception:
        return None


BOARD = {"ashby": "Ashby", "greenhouse": "Greenhouse", "lever": "Lever", "workable": "Workable", "linkedin": "LinkedIn", "hn": "HN"}
LEVEL = {"senior": "Senior", "early": "Early career", "mid": "Mid", "staff": "Staff", "principal": "Principal", "lead": "Lead"}
ROLE_CLASS = {"on-target": "On-target", "adjacent": "Adjacent"}
posts = {}
if os.path.exists(POSTINGS):
    for line in open(POSTINGS):
        try:
            p = json.loads(line)
        except Exception:
            continue
        if p.get("outcome") == "submitted" and p.get("submitted_at"):
            posts[(p["submitted_at"][:19], (p.get("role") or "").strip())] = p
job_rows = []
for e in latest([x for x in lanes["cold_apps"]["events"] if x.get("kind") == "application"], 10):
    p = posts.get((e["ts"][:19], (e.get("what") or "").strip()), {})
    co_key = next((k for k, v in companies.items() if v.get("name") == e.get("co")), None)
    co = companies.get(co_key) or {}
    src = (p.get("source") or "").split("-")[0]
    slug = re.sub(r"[^a-z0-9]+", "-", (e.get("co") or "").lower()).strip("-")
    have = cache_logo(slug, "cached-only")
    logo_url, web = (None, None) if have or not p.get("posting_url") else board_logo(p["posting_url"])
    job_rows.append({
        "ts": e["ts"], "co": e["co"], "role": e["what"],
        "board": BOARD.get(src), "level": LEVEL.get(p.get("level")), "role_class": ROLE_CLASS.get(p.get("role_class")),
        "location": (p.get("location") or "").split(";")[0].strip() or None,
        "url": p.get("posting_url"), "website": web,
        "apps": co.get("apps"), "replies": co.get("replies"), "tier": co.get("tier"), "stage": co.get("stage"),
        "logo": have or cache_logo(slug, logo_url),
        "source": "postings.jsonl (11-20 backup) + lanes.json companies" if p else "lanes.put.json cold_apps",
    })

FORMAT = {"web": "Live demo", "terminal": "Terminal run", "diagram": "Architecture page"}
TYPE_L = {"ai-agent": "AI agent", "workflow-automation": "Workflow automation"}


def up_meta(slug, jobs=(), names=()):
    jobs = set(j for j in jobs if j and j.startswith("~"))
    names_l = [n.lower() for n in names if n]
    for e in ledger:  # jobs reached through the slug or the client's name
        cl = str(e.get("client") or "").lower()
        if (slug and e.get("slug") == slug) or (names_l and any(n in cl for n in names_l)):
            if e.get("job"):
                jobs.add(e["job"])
            if "(" in cl:
                names_l.append(cl.split("(")[0].strip())
    for e in ledger:
        cl = str(e.get("client") or "").lower()
        if names_l and any(n and n in cl for n in names_l) and e.get("job"):
            jobs.add(e["job"])
    m = {"jobs": sorted(jobs), "formats": [], "replies": [], "fit": None, "proposals": None, "title": None, "bid": None,
         "connects": None, "kind": None, "closed": False, "budget": None, "spent": None, "rating": None, "client": None}
    for e in ledger:
        j = e.get("job") or e.get("key")
        if j in jobs:
            m["title"] = m["title"] or e.get("title") or (e.get("client") if e.get("event") == "vsl_pick" and ":" in str(e.get("client")) else None)
            if e.get("fit") is not None:
                m["fit"] = max(m["fit"] or 0, e["fit"])
            if e.get("proposals") is not None:
                m["proposals"] = e["proposals"]
            if e.get("event") == "proposal_sent":
                m["bid"] = e.get("bid_usd"); m["connects"] = e.get("connects"); m["kind"] = TYPE_L.get(e.get("type"), m["kind"])
            if e.get("event") == "job_private":
                m["closed"] = True
            if e.get("event") == "demo_ready" and e.get("url") and "Live demo" not in m["formats"]:
                m["formats"].append("Live demo")
            note = str(e.get("note") or "")
            f = re.search(r"demo format: ([a-z+]+)", note)
            if f:
                for k in f.group(1).split("+"):
                    if FORMAT.get(k) and FORMAT[k] not in m["formats"]:
                        m["formats"].append(FORMAT[k])
            b = re.search(r"hourly \$(\d+)-(\d+)", note)
            if b:
                m["budget"] = f"${b.group(1)}–{b.group(2)}/h"
            pr = re.search(r"(\d+\+?) proposals", note)
            if pr and m["proposals"] is None:
                m["proposals"] = pr.group(1)
            cn = re.search(r"(\d+) Connects", note)
            if cn and m["connects"] is None:
                m["connects"] = int(cn.group(1))
            s = re.search(r"\$([\d.]+K) spent", note)
            if s:
                m["spent"] = "$" + s.group(1)
            rt = re.search(r"client [A-Z]{2} (\d\.\d+)", note)
            if rt:
                m["rating"] = rt.group(1)
            c = e.get("client")
            if c and not str(c).startswith("~") and e.get("event") in ("vsl_sent", "message_sent"):
                m["client"] = m["client"] or c
    for e in ledger:
        cl = str(e.get("client") or "").lower()
        if e.get("event") in ("client_reply", "replied") and names_l and (any(n in cl for n in names_l) or cl in [n.split()[0] for n in names_l]):
            m["replies"].append({"ts": e.get("ts"), "what": e.get("note") or e.get("what") or ""})
    return m


upwork_meta = {}
for r in ready + recorded:
    p = packages.get(r["slug"], {})
    m = up_meta(r["slug"], [p.get("job"), p.get("job_key")] + [x for x in str(p.get("job") or "").split(" + ")])
    for k in str(p.get("demo_format") or "").split("+"):
        if FORMAT.get(k) and FORMAT[k] not in m["formats"]:
            m["formats"].append(FORMAT[k])
    upwork_meta[r["slug"]] = m
for r in sent:
    note = str(r.get("note") or "")
    pid = re.search(r"proposal (\d+)", note)
    jobs = [r["slug"]] if str(r["slug"]).startswith("~") else []
    if pid:
        jobs += [e.get("job") for e in ledger if e.get("event") == "proposal_sent" and str(e.get("proposal_id")) == pid.group(1)]
    names = [] if str(r["slug"]).startswith("~") else [r["slug"]]
    m = up_meta(None, jobs, names)
    if pid and re.search(r"\$[\d,]+ fixed", note):
        m["bid_unit"] = "fixed"
    elif pid and "/h" in note:
        m["bid_unit"] = "/h"
    upwork_meta[r["slug"]] = m
enrich = {"jobs": job_rows, "upwork": upwork_meta}

out = {"person": "tyler", "display": "Tyler", "enrich": enrich, "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "copy_at": data["updated"], "copy_where": "Ra · ~eagle/dev/eagle-eye (Eagle Eye's last copy)",
       "hunts": hunts, "roosts": roosts}
os.makedirs(f"{HERE}/public/people", exist_ok=True)
json.dump(out, open(f"{HERE}/public/people/tyler.json", "w"), indent=1, default=str)

# ---------- the other people: only what exists on Ra, else the true reason ----------
PF = "packages/core/person_feed.py"
def try_feed(person):
    r = subprocess.run(["python3", os.path.expanduser(f"~/dev/eagle-eye/{PF}"), person], capture_output=True, text=True, timeout=90)
    return (json.loads(r.stdout), None) if r.returncode == 0 and r.stdout.strip() else (None, (r.stderr or "").strip().splitlines()[-1:] or ["no output"])
others = {
    "claire": ("Sam", "Her numbers come from her own ledger Sheet (Applications — <person>), read by person_feed.py. From Ra the read failed: {err}. The token mint needs Infisical, which lives on novaserver, offline since 11-20."),
    "osman": ("Pat", "person_feed.py found {err} on Ra. Their apply store (candidates/osman/applications.db) lives on novaserver, offline since 11-20; the 11-20 backup on Ra holds an empty folder for him."),
    "yusuf": ("Yusuf", "person_feed.py found {err} on Ra."),
}
for person, (name, why) in others.items():
    feed, err = try_feed(person)
    o = {"person": person, "display": name, "built": out["built"], "copy_at": None, "copy_where": "Ra", "hunts": [], "roosts": []}
    if feed:
        o["raw"] = feed; o["copy_at"] = feed.get("updated")
    else:
        o["empty"] = {"title": "No data on Ra for " + name, "why": why.format(err=err[0]), "next": "Re-run person_feed.py " + person + " when novaserver is back"}
    if person == "yusuf":
        y = json.load(open(os.path.expanduser("~/dev/eagle-eye/packages/core/person/yusuf-empty.json")))
        m = y["hunts"]["messages"]
        o["copy_at"] = y["updated"]; o["copy_where"] = "packages/core/person/yusuf-empty.json"
        o["hunts"] = [{"id": "messages", "name": "Messages", "kicker": m["what"], "state": "not_started",
                       "empty": {"title": "Hunt not running yet", "why": m["reason"] + " (his last feed, " + y["updated"][:10] + ").", "next": "Link WhatsApp for temp-6a"},
                       "backend": {"agent": "temp-6a", "does": "sends and answers messages for him"}, "frontend": {"agent": None, "does": ""},
                       "funnel": None, "feed": [], "queue": None, "checked": y["updated"], "source": m["source"]}]
        o["roosts"] = [{"id": "network", "name": "Network", "agent": None, "headline": {"v": len(y["roosts"]["network"]["rows"]), "k": "people"},
                        "rows": [], "feed": [], "checked": y["updated"], "source": "yusuf-empty.json", "reason": y["roosts"]["network"]["reason"] + ": none recorded yet"}]
    json.dump(o, open(f"{HERE}/public/people/{person}.json", "w"), indent=1)
json.dump([{"id": "tyler", "name": "Tyler"}] + [{"id": k, "name": v[0]} for k, v in others.items()], open(f"{HERE}/public/people/index.json", "w"))
print("ok", len(json.dumps(out)), "bytes; upwork queue", len(ready), len(recorded), len(sent))

# layout gate (README): new data can bring longer labels, so every snapshot build re-checks the UI for overlaps
_lc = subprocess.run([os.path.expanduser("~/.local/share/fleet-playwright/bin/python"), os.path.join(HERE, "tools", "layout-check.py")], capture_output=True, text=True)
print((_lc.stdout.strip().splitlines() or ["layout-check: no output " + _lc.stderr[-300:]])[-1])
