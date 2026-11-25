#!/usr/bin/env python3
"""hunt-send: the SEND step of every hunt (DOMAINS.md domain 2: Q8 + BACKENDS card, 11-21).

After Tyler records a one-shot, it reaches the target the SAME DAY by email + LinkedIn + call, our own viewer page
reports watches, and the hunt's backend agent answers replies as Tyler toward a booked call (utopiamodels.ai/call).
No drafts, no approval, Tyler never in the loop. Stdlib only (Ra is RAM-tight).

  hunt_send.py cycle   [--ws tyler|dryrun] [--store /srv/vsl] [--settle 600]   detect takes -> Recorded -> send settled takes
  hunt_send.py loop    [--every 60]                                             cycle + replies forever (the systemd unit)
  hunt_send.py detect  [--ws ...] [--store ...]                                 take landed -> recording row + vsl_stage recorded
  hunt_send.py send    --ws W --item ID [--take PATH]                           build viewer, publish, email, queue LI/call
  hunt_send.py replies [--once]                                                 Gmail history on tyler@ -> answer in thread
  hunt_send.py dryrun-seed --from ITEM_ID                                       copy a tyler item into workspace dryrun
  hunt_send.py drain                                                            replay beacons the Worker parked in R2

Safety: workspace 'dryrun' only ever mails dryrun@example.com (two independent guards: the seeded person's email
AND the send-time override). Workspace 'tyler' sends only when the public viewer answers 200 at utopiamodels.ai/v/<slug>/
(never a link the target cannot open).
"""
import argparse, base64, datetime as dt, email.policy, glob, hashlib, html, json, os, re, secrets, shutil, struct, subprocess
import sys, tempfile, time, urllib.error, urllib.parse, urllib.request, zlib
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("HUNT_SEND_STATE", os.path.join(HERE, "state"))
API = os.environ.get("EAGLE_API", "http://100.127.249.81:8798")
TOKENS = os.path.expanduser(os.environ.get("HUNT_SEND_TOKENS", "~/.claude/private/hunt-send"))
STORE = os.environ.get("VSL_STORE", "/srv/vsl")
VIEWER_DIR = os.path.expanduser(os.environ.get("VIEWER_DIR", "~/.local/share/eagle-viewer"))
TAILNET_BASE = os.environ.get("VIEWER_TAILNET_BASE", "https://ra.tail4016d7.ts.net:8451")
PUBLIC_BASE = os.environ.get("VIEWER_PUBLIC_BASE", "https://utopiamodels.ai")
R2_BUCKET = os.environ.get("VIEWER_R2_BUCKET", "oneshot-viewer")
CACHE = os.path.expanduser("~/.claude/knowledge/_infra/scripts/infisical-cache.sh")
COPYGATE = os.path.expanduser("~/dev/utopia-models/knowledge/wi/work/_tools/copygate/copygate.py")
CLAUDE = shutil.which("claude") or "/usr/local/bin/claude"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import eeconf  # noqa: E402
SENDER, SENDER_NAME, SENDER_ROLE = (eeconf.get("sender_email", "sender@example.com"), eeconf.get("sender_name", "Sender Name"), eeconf.get("sender_role", "Founder"))
CTA = "https://utopiamodels.ai/call"
MAIL_DOMAIN = eeconf.get("mail_domain", "example.com")
DRY_TO = eeconf.get("dry_run_to", "dryrun@example.com")
VOICE_AGENT = os.environ.get("HUNT_SEND_VOICE_AGENT", "horus")  # the voice profile the gate grades against (Tyler-voice outreach)
MIN_TAKE_S = float(os.environ.get("HUNT_SEND_MIN_TAKE_S", "15"))
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
OFFER = ("a senior AI engineering team on their repo within 48 hours; the first two weeks they pay only if happy with the "
         "work; after that $3,200 a month; book at utopiamodels.ai/call")
# channels per hunt type (Q8: email + LinkedIn + call the same day; Upwork = the proposal in the Upwork desk)
CHANNELS = {"funding": ["email", "linkedin", "call"], "job_post": ["email", "linkedin"], "upwork": ["upwork"], "investor": ["email", "x"]}
VIZIER_DIR = "/home/eagle/.local/state/vizier-display/talk-scripts"
VIZIER = os.environ.get("VIZIER_DISPLAY", "http://127.0.0.1:18787")  # the laptop Vizier bar (scripts + /push cards)
# Tyler 11-21: "we can hold off on investors until this is clearer" -> the investor hunt builds rows + one-shots, but NO
# investor send ever fires from here (no email, no queued X/LinkedIn step); rows show status "Held". Flip only on his word.
INVESTOR_SENDS_HELD = True
INVEST_ASK = "Raising $250-500K on a SAFE at an $8M post-money cap"  # Tyler cards 11-21 (~5:55 PM raise, ~6:55 PM cap)

# Campaign sequences (Tyler cards 11-21 ~6:55 PM; campaign_channels_all_hunts.md §2 funding, §3 jobs, §5 investors).
# (step, day, channel, runner): runner "ra" = this process sends it when due; "nova" = queued with exact steps for a
# novaserver desk (LinkedIn = sekhmet's cold-apps desk, X = desk-social); "voice" = Tyler's live dial block on Vizier.
# Funding touch 1 OFFERS the walkthrough with no link (Cold Email Studio free-pilot opener + Gong interest CTA: 12% vs
# 5-7% reply); the video is recorded on "yes" and goes out in-thread. Any reply cancels the queued rest.
SEQUENCES = {
    "funding": [("offer", 0, "email", "ra"), ("li_visit", 1, "linkedin", "nova"), ("li_connect", 3, "linkedin", "nova"),
                ("dial_1", 3, "call", "voice"), ("li_dm", 4, "linkedin", "nova"),
                ("x_reply", 7, "x", "nova"), ("dial_2", 10, "call", "voice")],
    # one-shot = video + small demo; the HM email leaves with the take, the rest is queued (card: ATS + HM email + referral + connect)
    "job_post": [("ats", 0, "ats", "nova"), ("hm_email", 0, "email", "ra"), ("li_connect", 1, "linkedin", "nova"),
                 ("referral", 2, "linkedin", "nova")],
    # investor card: email from tyler@ + X reply/DM; then LinkedIn connect
    "investor": [("inv_email", 0, "email", "ra"), ("x_reply", 0, "x", "nova"), ("x_dm", 1, "x", "nova"),
                 ("li_connect", 3, "linkedin", "nova")],
    # email follow-ups for every hunt = fu_1/fu_2/fu_3 on days 3/7/14 after the first send, each adding something new
    # (card 11-21 ~8:50 PM; pg-boss in src/followups.ts schedules them, send/followups.py writes + sends them in-thread)
}
SEQ_STEP = {ht: {s[0]: s for s in seq} for ht, seq in SEQUENCES.items()}


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def log(*a):
    line = f"{iso()} " + " ".join(str(x) for x in a)
    print(line, flush=True)
    os.makedirs(STATE, exist_ok=True)
    with open(os.path.join(STATE, "send.log"), "a") as f:
        f.write(line + "\n")


def load(name, default):
    try:
        return json.load(open(os.path.join(STATE, name)))
    except Exception:
        return default


def save(name, d):
    os.makedirs(STATE, exist_ok=True)
    p = os.path.join(STATE, name)
    json.dump(d, open(p + ".tmp", "w"), indent=1, default=str)
    os.replace(p + ".tmp", p)


def slugify(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-") or "x"


# ---------------------------------------------------------------- Eagle Eye API (per-agent token per workspace)
def token(ws):
    t = os.environ.get(f"HUNT_SEND_TOKEN_{ws.upper()}")
    if t:
        return t
    p = os.path.join(TOKENS, f"{ws}.token")
    if not os.path.exists(p):
        raise SystemExit(f"no API token for workspace {ws} ({p}; mint: npm run key mint hunt-send -- --workspace {ws} ...)")
    return open(p).read().strip()


def api(ws, method, path, body=None, idem=None):
    h = {"Authorization": "Bearer " + token(ws), "Content-Type": "application/json"}
    if idem:
        h["Idempotency-Key"] = idem
    req = urllib.request.Request(API + path, method=method, headers=h, data=None if body is None else json.dumps(body).encode())
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}")


def item_detail(ws, item_id):
    return api(ws, "GET", f"/rest/huntItems/{item_id}?depth=1")["data"]["huntItem"]


def patch_item(ws, item_id, **kv):
    return api(ws, "PATCH", f"/rest/huntItems/{item_id}", kv)


def touches_of(ws, item_id):
    return api(ws, "GET", f"/rest/touches?filter=itemId[eq]:{item_id}&limit=200")["data"]["touches"]


def upsert_touch(ws, body):
    return api(ws, "POST", "/rest/touches?upsert=true", body)["data"]["createTouch"]


def patch_touch(ws, touch_id, **kv):
    return api(ws, "PATCH", f"/rest/touches/{touch_id}", kv)


def items_of(ws, hunt_type):
    return api(ws, "GET", f"/rest/huntItems?filter=huntType[eq]:{hunt_type}&limit=200")["data"]["huntItems"]


def due_touches(ws):
    return api(ws, "GET", f"/rest/touches?filter=status[eq]:queued,dueAt[lte]:{iso()}&limit=200")["data"]["touches"]


ORDER = {"vslStage":["none", "scripted", "recorded", "rendered", "sent", "watched"],
         "stage": ["new", "qualified", "one_shot", "sent", "replied"],
         "replyStatus": ["none", "opened", "watched", "replied", "booked", "won"]}


def forward(ws, it, **kv):
    """PATCH only the fields that move forward (a re-run never undoes 'watched' or 'replied')."""
    out = {k: v for k, v in kv.items() if k not in ORDER or v not in ORDER[k] or it.get(k) not in ORDER[k]
           or ORDER[k].index(v) > ORDER[k].index(it.get(k))}
    if out:
        patch_item(ws, it["id"], **out)
        it.update(out)
    return out


# ---------------------------------------------------------------- Google (DWD mint from Ra's encrypted cache; never printed)
_tok = {}


def gtoken(subject=SENDER, scope="https://www.googleapis.com/auth/gmail.modify"):
    k = (subject, scope)
    if k in _tok and _tok[k][1] > time.time():
        return _tok[k][0]
    p = subprocess.run(["bash", CACHE, "mint-google", scope, subject], capture_output=True, text=True, timeout=60)
    t = p.stdout.strip()
    if p.returncode or len(t) < 50:
        raise RuntimeError(f"google mint failed for {subject}: {p.stderr.strip()[:200]}")
    _tok[k] = (t, time.time() + 2400)
    return t


def gmail(method, path, body=None, subject=SENDER, query=None):
    url = GMAIL + path + ("?" + urllib.parse.urlencode(query, doseq=True) if query else "")
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + gtoken(subject), "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"gmail {method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}")


def gmail_send(msg: EmailMessage, thread_id=None, subject=SENDER):
    """Send; the result carries `messageId` = the Message-Id Gmail actually stamped (it replaces ours), which is what the
    recipient's reply references, so every In-Reply-To we write later must use it."""
    raw = base64.urlsafe_b64encode(msg.as_bytes(policy=email.policy.SMTP)).decode()
    r = gmail("POST", "/messages/send", {"raw": raw, **({"threadId": thread_id} if thread_id else {})}, subject=subject)
    try:
        m = gmail("GET", f"/messages/{r['id']}", query={"format": "metadata", "metadataHeaders": ["Message-Id"]}, subject=subject)
        r["messageId"] = header(m, "Message-Id") or msg["Message-ID"]
    except Exception:
        r["messageId"] = msg["Message-ID"]
    return r


# ---------------------------------------------------------------- media: web mp4, poster, Loom-style GIF thumbnail
def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    d = json.loads(p.stdout or "{}")
    codecs = {s["codec_type"]: s["codec_name"] for s in d.get("streams", [])}
    return codecs, float(d.get("format", {}).get("duration") or 0)


def play_png(path, size=96):
    """A Loom-like play badge (dark translucent circle, white triangle) as an RGBA PNG, pure Python."""
    r = size / 2
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx, dy = x - r + 0.5, y - r + 0.5
            d = (dx * dx + dy * dy) ** 0.5
            a = 0 if d > r else int(170 * min(1.0, r - d))
            px = (20, 20, 22, a)
            tx, ty = x - size * 0.40, y - size * 0.5  # triangle pointing right, centered optically
            if 0 <= tx <= size * 0.27 and abs(ty) <= (size * 0.27 - tx) * 0.62 + 0.0001 and d <= r:
                px = (255, 255, 255, 255)
            row += bytes(px)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)  # noqa: E731
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
                           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def build_media(take, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    codecs, dur = probe(take)
    video = os.path.join(out_dir, "video.mp4")
    if codecs.get("video") == "h264" and codecs.get("audio") in ("aac", None):
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", take, "-c", "copy", "-movflags", "+faststart", video]
    else:
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", take, "-vf", "scale='min(1920,iw)':-2",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", video]
    subprocess.run(cmd, check=True, timeout=1800)
    ss = "1" if dur > 3 else "0"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", ss, "-i", video, "-frames:v", "1", "-vf", "scale=1280:-2",
                    "-q:v", "3", os.path.join(out_dir, "poster.jpg")], check=True, timeout=120)
    badge = os.path.join(out_dir, ".play.png")
    play_png(badge)
    gif_len = str(min(3.0, max(dur - float(ss), 1.0)))
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", ss, "-t", gif_len, "-i", video, "-i", badge,
                    "-filter_complex", "[0:v]fps=10,scale=480:-2:flags=lanczos[v];[v][1:v]overlay=(W-w)/2:(H-h)/2,split[a][b];"
                    "[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer", "-loop", "0", os.path.join(out_dir, "thumb.gif")],
                   check=True, timeout=300)
    os.remove(badge)
    vc, vdur = probe(video)
    if vc.get("video") != "h264" or vdur <= 0:
        raise RuntimeError(f"web video check failed: {vc} {vdur}")
    return round(vdur, 2)


def render_page(out_dir, slug, title, pill, created_at, base_path):
    tpl = open(os.path.join(HERE, "viewer.html")).read()
    initials = "".join(w[0] for w in SENDER_NAME.split()[:2]).upper()
    rep = {"TITLE": html.escape(title), "SENDER": html.escape(SENDER_NAME), "SENDER_ROLE": html.escape(SENDER_ROLE),
           "INITIALS": initials, "CTA_URL": CTA, "PILL": html.escape(pill), "CREATED_AT": created_at,
           "CREATED_HUMAN": "today", "BASE": base_path, "BEACON": base_path + "e"}
    page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: rep[m.group(1)], tpl)
    open(os.path.join(out_dir, "index.html"), "w").write(page)


# ---------------------------------------------------------------- publish: tailnet copy always, R2 (public) when the key is on Ra
def cache_get(project, key):
    p = subprocess.run(["bash", CACHE, "get", project, key], capture_output=True, text=True, timeout=30)
    return p.stdout.strip() if p.returncode == 0 else ""


_r2 = {"at": 0.0, "env": None}


def r2_env():
    """R2 S3 env from Ra's cache; looked up at most every 10 min (each read is a sudo systemd-creds decrypt)."""
    if time.time() - _r2["at"] < 600:
        return _r2["env"]
    _r2["at"], _r2["env"] = time.time(), _r2_env()
    return _r2["env"]


def _r2_env():
    kid, sec, ep = (cache_get("fleet-infra", k) for k in ("R2_ACCESS_KEY_ID_UTOPIA", "R2_SECRET_ACCESS_KEY_UTOPIA", "R2_S3_ENDPOINT_UTOPIA"))
    if not (kid and sec and ep):
        return None
    return {**os.environ, "AWS_ACCESS_KEY_ID": kid, "AWS_SECRET_ACCESS_KEY": sec, "AWS_DEFAULT_REGION": "auto", "R2_EP": ep}


def publish_r2(slug, out_dir):
    env = r2_env()
    if not env:
        return False, "R2 secret not cached on Ra (fleet-infra/R2_SECRET_ACCESS_KEY_UTOPIA)"
    aws = shutil.which("aws") or os.path.expanduser("~/.local/bin/aws")
    for f in ("video.mp4", "poster.jpg", "thumb.gif", "index.html"):  # page last: it never points at a missing file
        ct = {"mp4": "video/mp4", "jpg": "image/jpeg", "gif": "image/gif", "html": "text/html; charset=utf-8"}[f.split(".")[-1]]
        p = subprocess.run([aws, "s3", "cp", os.path.join(out_dir, f), f"s3://{R2_BUCKET}/v/{slug}/{f}", "--endpoint-url", env["R2_EP"],
                            "--content-type", ct, "--only-show-errors"], env=env, capture_output=True, text=True, timeout=1800)
        if p.returncode:
            return False, f"R2 upload {f}: {p.stderr.strip()[:200]}"
    return True, "r2"


def url_ok(url, rng=False):
    try:
        req = urllib.request.Request(url, method="GET", headers={"Range": "bytes=0-99"} if rng else {})
        r = urllib.request.urlopen(req, timeout=20)
        return r.status in (200, 206)
    except Exception:
        return False


# ---------------------------------------------------------------- copy: written per person by the model, graded by copygate
EMAIL_SCHEMA = {"type": "object", "required": ["subject", "line1", "line2", "page_title", "pill", "linkedin_note"], "properties": {
    "subject": {"type": "string"}, "line1": {"type": "string"}, "line2": {"type": "string"}, "page_title": {"type": "string"},
    "pill": {"type": "string"}, "linkedin_note": {"type": "string"}}}
REPLY_SCHEMA = {"type": "object", "required": ["outcome", "should_reply", "body"], "properties": {
    "outcome": {"type": "string", "enum": ["positive", "neutral", "negative", "booked", "hired", "unsubscribe"]},
    "should_reply": {"type": "boolean"}, "body": {"type": "string"}}}


def claude_json(prompt, schema, model="sonnet"):
    cmd = [CLAUDE, "-p", "--model", model, "--output-format", "json", "--json-schema", json.dumps(schema),
           "--setting-sources", "project", "--dangerously-skip-permissions", "--max-turns", "3", "--tools", "Read", "--allowedTools", "Read"]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600, cwd=tempfile.gettempdir())
    try:
        d = json.loads(p.stdout)
    except Exception:
        raise RuntimeError(f"claude -p gave no JSON (rc {p.returncode}): {p.stderr.strip()[:200]}")
    so = d.get("structured_output")
    if so is None:
        so = json.loads(d.get("result") or "{}")
    return so


def gate(text, channel, to, first, followup=False, audience="client"):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text)
    try:
        cmd = ["python3", COPYGATE, "check", "--agent", VOICE_AGENT, "--channel", channel, "--to", to, "--name", first, "--json"]
        if channel == "email":
            cmd += ["--audience", audience]
        cmd += ["--followup" if followup else "--first", f.name]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        try:
            d = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            return False, [["block", "copygate", (p.stdout + p.stderr).strip()[-300:]]]
        return bool(d.get("ok")), [x for x in d.get("findings", []) if x[0] == "block"]
    finally:
        os.unlink(f.name)


def package_text(it):
    """The one-shot package the backend agent built (script + header with sources), for facts only."""
    out = []
    for os_ in it.get("oneShots", []):
        sp = os_.get("script") or ""
        d = os.path.dirname(sp)
        for f in sorted(glob.glob(os.path.join(d, "*.md"))):
            if os.path.basename(f) in ("script.md",) and len(glob.glob(os.path.join(d, "*.md"))) > 1:
                continue
            out.append(f"--- {os.path.basename(f)}\n" + open(f).read()[:6000])
    return "\n".join(out)[:12000]


def email_body(first, *lines):
    return f"Hi {first},\n\n" + "\n\n".join(l for l in lines if l) + f"\n\nBest,\n{SENDER_NAME}\n"


AUDIENCE = {"client": "client", "job": "hiring-manager", "investor": "professional"}
KIND_RULES = {
    "client": None,
    # campaign_channels_all_hunts.md §3 day 0 (Overloop hiring-signal opener): applied + built a small thing on their product
    "job": """KIND = a JOB APPLICATION to the hiring manager / founder. Tyler applied for the role and recorded a short video of a small
demo he built for ONE task the role does (from the package). line1 = "Applied for <role>." + one clause on what he built on their
product/stack (their words from the post). line2 = one short question inviting them to watch (e.g. "Worth two minutes?").
Under 80 words in all. page_title = "<company>: <task> demo for the <role> role" style, under 60 chars. pill = "Book an intro".""",
    # investor_hunt.md §4: Seibel (plain, no compliments, no meeting ask, let them escalate) + Kamps (hook = their own bet)
    "investor": f"""KIND = an INVESTOR email (Seibel: plain, no jargon, no compliments, no meeting ask; Kamps: the hook is THEIR OWN BET,
stated as a fact that ties it to our work, never praise). Exactly FOUR lines after the greeting; return line1..line4:
line1 = the fact tying their recent bet to ours ("You backed <deal company> in <month>; <why that is the layer we build>").
line2 = what Utopia Models is, plain: one founder running an AI engineering company with a fleet of agents, Eagle Eye (MIT) and Vizier (Apache-2.0) open source.
line3 = ONE real number from the package (quote it exactly as the package states it; never invent or round up).
line4 = "{INVEST_ASK}. I recorded a 90-second live demo for you:" (the video link is added after this line).
subject = "<deal company>-adjacent: open-source agent ops, solo founder + agent fleet, raising pre-seed" (the Crunchbase shape), under 90 chars.
page_title = "<their fund>: a live demo of the fleet" style, under 60 chars. pill = "Reply by email". linkedin_note: under 200 chars, no link.
About 120 words in all. No em dashes, no exclamation marks.""",
}


def write_email(it, first, to, kind="client"):
    person, company = contact_of(it), (it.get("company") or {}).get("name") or it["target"]
    base = f"""You write ONE cold email for ONE person, as Tyler Youk (founder of Utopia Models, an AI engineering team), in first person.
Tyler recorded a short screen-share video FOR this person: their own words, their live product, three specific things he'd
build next, then the offer. The email exists only to get them to watch it. Copy the strongest video cold-email shape:
subject = THEIR OWN WORDS (a short phrase they wrote in their launch/post, lowercase, 2-6 words, no "video", no emoji);
body = exactly two lines after "Hi {first},": line1 names something only true for them (quote or paraphrase their words or a
specific thing seen on their product, from the package below) and says Tyler recorded a short walkthrough of it; line2 is
one short low-friction question inviting them to watch (e.g. "Worth a look?"). Each line one sentence, under 30 words.
No pitch, no price, no claims that are not in the package, no em dashes, no exclamation marks, no "I hope this finds you".
Also return: page_title (the viewer page title, like a Loom title: "{company}: three things I'd build next" style, under 60
chars), pill (2-5 words shown beside the Book a call button, e.g. "Want this built?"), linkedin_note (a LinkedIn connection
note, under 280 characters, same voice, mentions the video, no link, no pitch).
Recipient: {person.get('fullName')} ({person.get('title') or ''}) at {company}. Signal: {it.get('signal')}.
=== package ===
{package_text(it)}"""
    if KIND_RULES.get(kind):
        base += "\n\nOVERRIDES (they win over everything above):\n" + KIND_RULES[kind]
    schema = EMAIL_SCHEMA if kind != "investor" else {**EMAIL_SCHEMA, "required": EMAIL_SCHEMA["required"] + ["line3", "line4"],
                                                      "properties": {**EMAIL_SCHEMA["properties"], "line3": {"type": "string"}, "line4": {"type": "string"}}}
    findings, prompt = [], base
    for attempt in range(3):
        d = claude_json(prompt, schema)
        lines = [d["line1"].strip(), d["line2"].strip()] + ([d["line3"].strip(), d["line4"].strip()] if kind == "investor" else [])
        body = email_body(first, *lines)
        if kind == "investor" and "$8M post-money" not in body:
            findings = [["block", "ask", "the investor email states the ask: " + INVEST_ASK]]
            prompt = base + "\n\nRefused: " + json.dumps(findings)
            continue
        ok, findings = gate(body, "email", to, first, audience=AUDIENCE[kind])
        if ok:
            d["body"] = body
            note_ok, note_f = gate(d["linkedin_note"].strip(), "linkedin", person.get("linkedinUrl") or to, first, audience=AUDIENCE[kind])
            d["linkedin_ok"] = note_ok
            d["linkedin_findings"] = note_f
            return d
        log("copy blocked, retry", attempt + 1, json.dumps(findings)[:300])
        prompt = base + "\n\nYour previous draft was refused by the copy gate. Fix every finding:\n" + json.dumps(findings) + \
            f"\nPrevious line1: {d['line1']}\nPrevious line2: {d['line2']}"
    raise RuntimeError(f"copy gate refused 3 drafts: {json.dumps(findings)[:300]}")


def write_thread_video(it, first, to):
    """The walkthrough they said yes to, in the offer's thread: one line + the embed (copied from the Loom reply shape)."""
    product = product_of(it)
    body = email_body(first, f"Here's the walkthrough of {product} I mentioned.")
    ok, findings = gate(body, "email", to, first, followup=True)
    if not ok:
        raise RuntimeError(f"copy gate refused the in-thread video note: {json.dumps(findings)[:300]}")
    return {"subject": "Re:", "body": body, "page_title": f"{product}: three things I'd build next", "pill": "Want this built?"}


def build_email(to, subject, body, page_url, title, gif_path, inline_gif):
    first_lines, sign = body.rsplit("\n\nBest,", 1)
    link = page_url + "?c=email"
    msg = EmailMessage()
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=MAIL_DOMAIN)
    msg.set_content(f"{first_lines}\n\n{title}: {link}\n\nBest,{sign}")
    cid = make_msgid(domain=MAIL_DOMAIN)[1:-1]
    src = f"cid:{cid}" if inline_gif else page_url + "thumb.gif"
    paras = "".join(f"<div>{html.escape(p)}</div><div><br></div>" for p in first_lines.split("\n\n"))
    embed = (f'<div><a href="{html.escape(link)}" style="color:#1868DB;font-weight:600;text-decoration:none">{html.escape(title)} - Watch Video</a></div>'
             f'<div><a href="{html.escape(link)}"><img src="{src}" width="480" alt="{html.escape(title)} - Watch Video" '
             f'style="display:block;max-width:100%;border-radius:8px;border:0"></a></div><div><br></div>')
    msg.add_alternative(f'<div dir="ltr" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">{paras}{embed}'
                        f'<div>Best,</div><div>{html.escape(SENDER_NAME)}</div></div>', subtype="html")
    if inline_gif:
        msg.get_payload()[1].add_related(open(gif_path, "rb").read(), "image", "gif", cid=f"<{cid}>", filename="thumb.gif")
    return msg


# ---------------------------------------------------------------- take detection
def norm_name(name):
    n = slugify(name, 80)
    while re.search(r"-take\d+$", n):
        n = re.sub(r"-take\d+$", "", n)
    return n


def slug_map(ws):
    """talk-script slug -> (item_id, one_shot_id), from the one-shots the backend agents registered."""
    out = {}
    r = api(ws, "GET", "/rest/oneShots?limit=200")["data"]["oneShots"]
    for o in r:
        keys = {a.get("file") for a in (o.get("assets") or []) if isinstance(a, dict) and a.get("file")}
        if o.get("script"):
            keys.add(os.path.basename(os.path.dirname(o["script"])))
        for k in keys:
            out[slugify(k, 80)] = (o["itemId"], o["id"])
    return out


def takes(store, days=3):
    """Complete takes in the vsl store: <store>/<day>/<name>-take<N>.mp4 whose sidecar .json carries "mp4" (written last)."""
    out = []
    today = dt.date.today()
    for i in range(days):
        day = (today - dt.timedelta(days=i)).isoformat()
        for j in glob.glob(os.path.join(store, day, "*.json")):
            try:
                m = json.load(open(j))
            except Exception:
                continue
            if not isinstance(m, dict) or not m.get("mp4") or not os.path.exists(m["mp4"]):
                continue
            out.append({"json": j, "mp4": m["mp4"], "name": m.get("name") or "", "slug": norm_name(m.get("name") or ""),
                        "duration_s": float(m.get("duration_s") or 0), "landed": os.path.getmtime(j),
                        "recorded_at": m.get("recorded_at")})
    return sorted(out, key=lambda t: t["landed"])


def detect(ws, store, settle):
    """Mark Recorded on landing; mark the newest take final once `settle` s pass with no newer take. Returns final takes."""
    st = load(f"takes-{ws}.json", {})
    smap = slug_map(ws)
    finals = []
    allt = takes(store)
    for t in allt:
        hit = smap.get(t["slug"])
        if not hit or t["duration_s"] < MIN_TAKE_S:
            continue
        item_id, os_id = hit
        rec = st.get(t["mp4"])
        if not rec:
            r = api(ws, "POST", "/rest/recordings", {"oneShotId": os_id, "takePath": t["mp4"], "durationS": t["duration_s"],
                                                      "isFinal": False, "recordedAt": t["recorded_at"] or iso()},
                    idem=f"rec:{hashlib.sha1(t['mp4'].encode()).hexdigest()}")
            rid = r["data"]["createRecording"]["id"]
            it = item_detail(ws, item_id)
            forward(ws, it, vslStage="recorded")
            rec = st[t["mp4"]] = {"item_id": item_id, "one_shot_id": os_id, "recording_id": rid, "slug": t["slug"], "landed": t["landed"]}
            save(f"takes-{ws}.json", st)
            log("RECORDED", ws, t["slug"], t["mp4"], f"{t['duration_s']}s", "item", item_id)
    # final = newest take per slug, settled
    newest = {}
    for path, rec in st.items():
        if rec.get("final_sent"):
            continue
        if rec["slug"] not in newest or rec["landed"] > newest[rec["slug"]][1]["landed"]:
            newest[rec["slug"]] = (path, rec)
    for slug, (path, rec) in newest.items():
        if time.time() - rec["landed"] >= settle and not rec.get("final"):
            # the recordings_one_final index allows one final per one-shot: clear older finals first
            olds = api(ws, "GET", f"/rest/recordings?filter=oneShotId[eq]:{rec['one_shot_id']},isFinal[eq]:true")["data"]["recordings"]
            for o in olds:
                if o["id"] != rec["recording_id"]:
                    api(ws, "PATCH", f"/rest/recordings/{o['id']}", {"isFinal": False})
            api(ws, "PATCH", f"/rest/recordings/{rec['recording_id']}", {"isFinal": True})
            rec["final"] = True
            save(f"takes-{ws}.json", st)
            log("FINAL", ws, slug, path)
        if rec.get("final"):
            finals.append((path, rec))
    return finals


# ---------------------------------------------------------------- send
VIDEO_STEPS = (None, "video", "hm_email", "inv_email")


def video_sent(touches):
    return [t for t in touches if t["channel"] in ("email", "upwork") and t.get("status") == "sent"
            and (t.get("step") in VIDEO_STEPS or (t.get("details") or {}).get("video"))]


def send(ws, item_id, take, recording_id=None, followup_touch=None):
    it = item_detail(ws, item_id)
    person, company = contact_of(it), it.get("company") or {}
    touches = it.get("touches", [])
    sent = video_sent(touches)
    if sent:
        log("SKIP already sent", ws, item_id, sent[0]["channel"], sent[0]["sentAt"])
        return {"skipped": "already sent"}
    ht = it["huntType"]
    if ht == "investor" and INVESTOR_SENDS_HELD:
        return {"held": "investor sends are held (Tyler 11-21: hold off on investors until the story is clearer)"}
    first = (person.get("fullName") or it["target"]).split()[0]
    to = person.get("email")
    if ws != "tyler":
        to = DRY_TO  # guard 2 (guard 1: the dryrun seed stored agent@ as the person's email)
    if ws != "tyler" and not to.endswith("@" + DRY_TO.split("@")[1]):
        raise SystemExit("refusing: a non-tyler workspace only mails the dry-run domain")
    offer = next((t for t in touches if t.get("step") == "offer"), None)
    thread = None
    if ht == "funding" and offer:
        # card 11-21: touch 1 offered the walkthrough; the video goes out IN THAT THREAD after a yes (or at the day-7 follow-up fu_2)
        yes = it.get("replyStatus") in ("replied", "booked") and any((r.get("outcome") in ("positive", "booked")) for r in it.get("replies") or [])
        if offer.get("status") != "sent":
            return {"held": "the offer (touch 1) has not gone out yet"}
        if not yes and followup_touch is None:
            return {"held": "waiting for a yes to the offer (or the day-7 follow-up)"}
        thread = offer
    channels = CHANNELS.get(ht, ["email"])
    one_shot = (it.get("oneShots") or [{}])[0]
    public = ws == "tyler"
    if public and not r2_env():
        # cheap check first: no ffmpeg, no model call, while the public viewer cannot exist (logged once per item)
        held = load("held.json", {})
        if item_id not in held:
            held[item_id] = iso()
            save("held.json", held)
            log("HOLD", ws, item_id, it["target"], "public viewer not publishable: R2 secret not cached on Ra")
        return {"held": "R2 secret not cached on Ra"}

    # 1 viewer: reuse the item's slug, else <company>-<random>
    vs = api(ws, "GET", f"/rest/viewers?filter=itemId[eq]:{item_id}")["data"]["viewers"]
    slug = vs[0]["slug"] if vs else f"{slugify(company.get('name') or it['target'], 24)}-{secrets.token_hex(3)}"
    out = os.path.join(VIEWER_DIR, slug)
    dur = build_media(take, out)
    base = (PUBLIC_BASE if public else TAILNET_BASE) + f"/v/{slug}/"

    # 2 copy (written for this one person, graded by copygate; refuses to send if it never passes)
    copies = load(f"copy-{ws}.json", {})
    copy = copies.get(item_id)
    if copy is None and "email" in channels:
        if thread:
            copy = write_thread_video(it, first, to)
        elif ht == "job_post":
            copy = write_email(it, first, to, kind="job")
        elif ht == "investor":
            copy = write_email(it, first, to, kind="investor")
        else:
            copy = write_email(it, first, to)
        copies[item_id] = copy  # drafted once per item; a held/retried send reuses it
        save(f"copy-{ws}.json", copies)
    title = (copy or {}).get("page_title") or f"{company.get('name') or it['target']}: a walkthrough for {first}"
    render_page(out, slug, title, (copy or {}).get("pill") or "Want this built?", iso(), f"/v/{slug}/")
    pub = {"tailnet": TAILNET_BASE + f"/v/{slug}/"}
    if public:
        ok, how = publish_r2(slug, out)
        pub["r2"] = how
        if not ok or not url_ok(base) or not url_ok(base + "video.mp4", rng=True):
            api(ws, "POST", "/rest/viewers?upsert=true", {"slug": slug, "itemId": item_id, "oneShotId": one_shot.get("id"),
                "recordingId": recording_id, "title": title, "senderName": SENDER_NAME, "videoUrl": base + "video.mp4", "pageUrl": base,
                "published": {**pub, "public": False}})
            log("HOLD", ws, slug, "public viewer not live:", how)
            return {"held": how, "slug": slug}
    api(ws, "POST", "/rest/viewers?upsert=true", {"slug": slug, "itemId": item_id, "oneShotId": one_shot.get("id"),
        "recordingId": recording_id, "title": title, "senderName": SENDER_NAME, "videoUrl": base + "video.mp4", "pageUrl": base,
        "published": {**pub, "public": public}})
    if not url_ok(base) or not url_ok(base + "video.mp4", rng=True):
        raise RuntimeError(f"viewer does not answer at {base}")
    result = {"slug": slug, "page": base, "duration_s": dur}

    # 3 email, from tyler@'s real mailbox (in the offer's thread when there is one)
    step = "video" if ht == "funding" else "hm_email" if ht == "job_post" else "inv_email" if ht == "investor" else None
    if "email" in channels and to:
        subj = copy["subject"].strip()
        msg = build_email(to, subj, copy["body"], base, title, os.path.join(out, "thumb.gif"), inline_gif=not public)
        if thread:
            td = thread.get("details") or {}
            del msg["Subject"]
            msg["Subject"] = "Re: " + (td.get("subject") or subj)
            if td.get("message_id"):
                msg["In-Reply-To"] = td["message_id"]
                msg["References"] = td["message_id"]
        r = gmail_send(msg, thread_id=thread.get("threadId") if thread else None)
        body = {"itemId": item_id, "oneShotId": one_shot.get("id"), "channel": "email", "status": "sent", "sentAt": iso(),
                "providerId": r["id"], "threadId": r["threadId"], "step": step, "dueAt": iso(),
                "details": {"to": to, "subject": msg["Subject"], "page": base, "message_id": r.get("messageId") or msg["Message-ID"], "dry_run": ws != "tyler", "video": True,
                            **({"in_thread_of": thread["id"]} if thread else {})}}
        if followup_touch:  # the day-7 follow-up (fu_2) carried the video: that touch IS this send
            patch_touch(ws, followup_touch["id"], status="sent", sentAt=iso(), threadId=r["threadId"],
                        details={**(followup_touch.get("details") or {}), **body["details"], "gmail_id": r["id"]})
        else:
            api(ws, "POST", "/rest/touches?upsert=true", body, idem=f"email:{r['id']}")
        result.update(email_id=r["id"], thread_id=r["threadId"], to=to, subject=msg["Subject"], in_thread=bool(thread))
        log("EMAIL", ws, slug, "->", to, "|", msg["Subject"], "| gmail", r["id"], "| in-thread" if thread else "")

    queued = []
    if ht in ("job_post", "investor"):
        # 4a the hunt's sequence: everything except the email that just left is queued with exact steps (ATS, LinkedIn, X)
        ts = start_sequence(ws, it, {"person": person, "first": first, "page": base}, sent_steps=(step,) if result.get("email_id") else ())
        queued = [t.get("step") for t in ts if t.get("status") == "queued"]
    elif not (ht == "funding" and thread):
        # 4b the channels novaserver runs (LinkedIn desk, dialer, Upwork desk): queued touches with exact steps
        for ch in channels:
            if ch == "email":
                continue
            steps = None
            if ch == "linkedin" and person.get("linkedinUrl"):
                steps = {"desk": "sekhmet web-desk (real Chrome, LinkedIn logged in)", "profile": person["linkedinUrl"],
                         "action": "Connect -> Add a note -> paste note -> Send", "note": (copy or {}).get("linkedin_note"),
                         "note_gate_ok": (copy or {}).get("linkedin_ok"), "after": "PATCH this touch status=sent, sentAt=now"}
            elif ch == "call":
                phone = (person.get("handles") or {}).get("phone")
                if phone:
                    steps = {"dialer": "dialer.salesblaster.ai (Telnyx number)", "phone": phone, "when": "same day, after the email",
                             "script": f"Hi {first}, it's Tyler from Utopia Models. I sent you a short video this morning about {company.get('name')}; "
                                       f"did it come through? ... The link to grab a time is utopiamodels.ai/call.",
                             "after": "PATCH this touch status=sent; a reply/booking goes to /rest/replies"}
            elif ch == "upwork":
                steps = {"desk": "upwork desk (Tyler's Upwork, write mode at power-on)", "job": (it.get("extension") or {}).get("jobUrl"),
                         "action": "Submit a proposal: the cover letter from the package's proposal.md with the viewer link "
                                   f"{base}?c=upwork in its first line; attach nothing else",
                         "after": "PATCH this touch status=sent, providerId=<proposal id>"}
            if steps:
                api(ws, "POST", "/rest/touches?upsert=true", {"itemId": item_id, "oneShotId": one_shot.get("id"), "channel": ch,
                    "status": "queued", "sentAt": iso(), "providerId": f"queued:{ch}:{item_id}", "details": steps})
                queued.append(ch)
                with open(os.path.join(STATE, "pending.jsonl"), "a") as f:
                    f.write(json.dumps({"at": iso(), "ws": ws, "item_id": item_id, "channel": ch, "slug": slug, **steps}) + "\n")
    result["queued"] = queued

    if result.get("email_id"):
        forward(ws, it, stage="sent", vslStage="sent")
        if one_shot.get("id"):
            api(ws, "PATCH", f"/rest/oneShots/{one_shot['id']}", {"status": "sent"})
    log("SENT", ws, json.dumps(result))
    return result


# ---------------------------------------------------------------- campaign sequences (dated touches; any reply stops them)
def real_sends_ok(ws):
    """Workspace 'tyler' reaches real people only once the public viewer can be published (R2 on Ra); dryrun always (agent@)."""
    return ws != "tyler" or bool(r2_env())


def contact_of(it):
    """The person the campaign goes to: the item's person row, else the package contact the backend agent found."""
    p = dict(it.get("person") or {})
    c = (it.get("details") or {}).get("contact") or {}
    p.setdefault("fullName", c.get("name"))
    for k_in, k_out in (("email", "email"), ("linkedin", "linkedinUrl"), ("role", "title")):
        if not p.get(k_out) and c.get(k_in):
            p[k_out] = c[k_in]
    p["handles"] = {**(c.get("handles") or {}), **(p.get("handles") or {}),
                    **({"x": c["x"]} if c.get("x") else {}), **({"phone": c["phone"]} if c.get("phone") else {})}
    p["referral"] = c.get("referral") or []
    p["ats"] = c.get("ats") or {}
    return p


def product_of(it):
    c = it.get("company") or {}
    return c.get("name") or it["target"]


def seq_start_at(touches):
    t = [x for x in touches if x.get("step") and x.get("dueAt")]
    if not t:
        return None
    return min(dt.datetime.fromisoformat(x["dueAt"].replace("Z", "+00:00")) for x in t)


ATS_STEPS = {
    "greenhouse": ["open the job URL", "Apply -> First name, Last name, Email, Phone from ground-truth.yaml", "Resume: upload the PDF ground-truth.yaml names",
                   "Cover letter: paste the cover text (first line = the demo link)", "answer every custom question from ground-truth.yaml (never invent)", "Submit, wait for the confirmation page, screenshot it"],
    "lever": ["open the job URL + /apply", "Full name, Email, Phone, Current company from ground-truth.yaml", "Resume upload",
              "Additional information: paste the cover text", "custom questions from ground-truth.yaml", "Submit application, screenshot the thank-you page"],
    "ashby": ["open the job URL -> Application tab", "Name, Email, Phone, LinkedIn from ground-truth.yaml", "Resume upload", "Cover letter / additional info: paste the cover text",
              "custom questions from ground-truth.yaml", "Submit, screenshot the confirmation"],
    "workday": ["open the job URL -> Apply -> Apply Manually", "sign in or create the account from Infisical jobs/WORKDAY_* for that tenant",
                "My Information / Experience: from ground-truth.yaml; Resume upload", "Application questions from ground-truth.yaml",
                "Voluntary disclosures as ground-truth.yaml says", "Review -> Submit, screenshot"],
}


def step_details(ws, it, step, ch, runner, ctx):
    """Exact steps for a queued touch (a novaserver desk or Tyler's dial block runs it, then PATCHes the touch)."""
    p, first, product, page = ctx["person"], ctx["first"], product_of(it), ctx.get("page")
    after = "PATCH /rest/touches/<this id> {status:'sent', sentAt:now} (or {status:'cancelled', details.reason} if the step cannot run)"
    li = p.get("linkedinUrl")
    if ch == "email":
        return {"by": "hunt-send on Ra", "when": "due_at, in the thread of the first email", "after": "hunt-send PATCHes it"}
    if step == "li_visit":
        return {"desk": "sekhmet cold-apps desk (real Chrome, LinkedIn logged in)", "profile": li, "action": "open the profile, scroll once, leave (a visit only)", "after": after} if li else None
    if step == "li_connect":
        return {"desk": "sekhmet cold-apps desk (real Chrome, LinkedIn logged in)", "profile": li,
                "action": "More -> Connect -> Send without a note (no acceptance gain from a note; free seats get 5 notes/month)", "after": after} if li else None
    if step == "li_dm":
        if not li:
            return None
        txt = f"Hi {first}, sent you a note about {product}. Happy to record that walkthrough, takes me a day."
        ok, f = gate(txt, "linkedin", li, first, followup=True)
        return {"desk": "sekhmet cold-apps desk", "profile": li, "only_if": "the day-3 connect was accepted; else PATCH status=cancelled",
                "action": "Message -> paste text -> Send", "text": txt, "gate_ok": ok, "gate_findings": f, "after": after}
    if step in ("dial_1", "dial_2"):
        phone = (p.get("handles") or {}).get("phone")
        if not phone:
            return None
        return {"block": "Tyler's 1-hour live dial block on Vizier (days 3 and 10), after caller ID (CNAM/STIR) is set on nova",
                "dialer": "dialer.salesblaster.ai (Telnyx number)", "phone": phone, "when": "8am-8pm their time",
                "opener": f"Hi {first}, it's Tyler from Utopia Models. I emailed you about {product} a few days ago, offering a short walkthrough. Did it reach you?",
                "voicemail": f"Hi {first}, Tyler from Utopia Models. I emailed you about a walkthrough of {product}; reply there if you want it. Thanks.",
                "after": after + "; a booked call -> PATCH huntItems reply_status=booked"}
    if step == "x_reply":
        x = (p.get("handles") or {}).get("x")
        what = ("their post announcing the deal named in this item (or their latest post about it)" if it["huntType"] == "investor"
                else "their post announcing the raise")
        return {"desk": "desk-social on Ra/nova (X as @pharaohbuilds), real input, <= 5 X actions/day, hard stop on any error",
                "account": x, "find": what, "action": ("one reply: a fact tying their bet to our work + the video link " + (page or "(viewer link)") + ", never praise")
                if it["huntType"] == "investor" else "one real reply or a like, no pitch, no link; skip if nothing posted in 14 days", "after": after}
    if step == "x_dm":
        return {"desk": "desk-social (X @pharaohbuilds)", "account": (p.get("handles") or {}).get("x"),
                "only_if": "their DMs are open or they followed back; else PATCH status=cancelled",
                "text": f"Hi {first}, sent you a short video on email about how we fit your thesis: {page or '(viewer link)'}", "after": after}
    if step == "ats":
        a = p.get("ats") or {}
        kind = (a.get("kind") or "").lower()
        url = a.get("url") or (it.get("extension") or {}).get("sourceUrl") or (it.get("details") or {}).get("link")
        return {"desk": "sekhmet cold-apps desk (real Chrome) or apply.py on Ra for a plain form", "ats": kind or "unknown", "url": url,
                "steps": ATS_STEPS.get(kind, ["open the URL", "fill every field from ground-truth.yaml (never invent)", "paste the cover text", "submit, screenshot the confirmation"]),
                "cover_first_line": f"A 2-minute video and a small demo of how I'd do this role: {page or '(viewer link)'}",
                "answers": "net/work/_tools/jobs/ground-truth.yaml (the facts apply.py uses)", "after": after}
    if step == "referral":
        r = (p.get("referral") or [None])[0]
        if not r or not r.get("linkedin"):
            return None
        rf = (r.get("name") or "").split()[0] or "there"
        txt = (f"Hi {rf}, I applied for the {it['target']} role at {product} and built a small demo for it: {page or '(viewer link)'}. "
               f"Would you be up for referring me if it looks good?")
        ok, f = gate(txt, "linkedin", r["linkedin"], rf)
        return {"desk": "sekhmet cold-apps desk", "employee": r, "action": "Connect -> Add a note -> paste text -> Send (or Message if already 1st degree)",
                "text": txt, "gate_ok": ok, "gate_findings": f, "after": after}
    return None


def start_sequence(ws, it, ctx, start=None, sent_steps=()):
    """Queue every step of the hunt's sequence as a dated touch (idempotent on provider_id seq:<item>:<step>)."""
    seq = SEQUENCES.get(it["huntType"])
    if it["huntType"] == "investor" and INVESTOR_SENDS_HELD:
        return []
    if not seq:
        return []
    have = {t.get("step") for t in touches_of(ws, it["id"])}
    start = start or now()
    out = []
    os_id = ((it.get("oneShots") or [{}])[0]).get("id")
    for step, day, ch, runner in seq:
        if step in have or step in sent_steps:
            continue
        det = step_details(ws, it, step, ch, runner, ctx)
        status, reason = "queued", None
        if det is None:
            status, reason = "cancelled", f"{step}: no {('LinkedIn profile' if ch == 'linkedin' else 'phone' if ch == 'call' else 'referral candidate' if step == 'referral' else 'target')} for this person"
            det = {"reason": reason}
        due = start + dt.timedelta(days=day)
        t = upsert_touch(ws, {"itemId": it["id"], "oneShotId": os_id, "channel": ch, "status": status, "step": step, "sentAt": iso(),
                              "dueAt": iso(due), "providerId": f"seq:{it['id']}:{step}", "details": {**det, "runner": runner, "day": day}})
        out.append(t)
        if status == "queued" and runner != "ra":
            with open(os.path.join(STATE, "pending.jsonl"), "a") as f:
                f.write(json.dumps({"at": iso(), "ws": ws, "item_id": it["id"], "touch_id": t.get("id"), "step": step, "channel": ch,
                                    "due_at": iso(due), "runner": runner, **det}, default=str) + "\n")
    log("SEQUENCE", ws, it["huntType"], it["target"], f"{len(out)} touches", ",".join(f"{t.get('step')}:{t.get('status')}" for t in out))
    return out


def cancel_rest(ws, item_id, why):
    n = 0
    for t in touches_of(ws, item_id):
        if t.get("status") == "queued":
            patch_touch(ws, t["id"], status="cancelled", details={**(t.get("details") or {}), "reason": why})
            n += 1
    return n


OFFER_LINE2 = "Want the 90-second walkthrough?"
OFFER_SCHEMA = {"type": "object", "required": ["subject", "line1"], "properties": {"subject": {"type": "string"}, "line1": {"type": "string"}}}


def offer_problems(subject, body):
    """Touch 1 has no link and no price (Gong interest CTA; campaign_channels §6 item 3) and stays under ~60 words."""
    p = []
    if re.search(r"https?://|www\.|\.ai/|\.com/|utopiamodels", body + " " + subject, re.I):
        p.append("touch 1 carries no link")
    # our price only: their own round ("congrats on the $3M seed") is not a price
    if re.search(r"\$\s?3,?200|\$\s?\d[\d,.]*\s*(?:/|a |per )\s*(?:mo|month|hour|h)\b|per month|a month|/mo\b|\bpric(?:e|es|ing)\b|\bretainer\b", body, re.I):
        p.append("touch 1 names no price")
    if len(body.split()) > 60:
        p.append(f"{len(body.split())} words, keep it under 60")
    return p


def write_offer(it, first, to):
    """Funding touch 1: one observation only true for them + the walkthrough offer (Cold Email Studio's free-pilot opener:
    "can I do a campaign of 100 people for free for you?" -> "I walked <product> and found three things. Want the
    90-second walkthrough?"), in Tyler's voice, through copygate."""
    product = product_of(it)
    base = f"""You write line 1 of ONE cold email, as Tyler Youk (founder, Utopia Models, a senior AI engineering team), first person.
The email copies the Cold Email Studio free-pilot opener (they wrote "We do cold email as a service, can I do a campaign of 100
people for free for you?" and got 2 meetings from the first 10 emails): it OFFERS a free thing made for them and asks if they
want it. Line 2 is fixed and you do not write it: "{OFFER_LINE2}"
line1 = ONE sentence, under 30 words: says Tyler walked {product} (their live product) and found three things he'd fix or build
first, and names the most concrete one from the package below (e.g. "I walked meetriver.com and found three things I'd fix
first, starting with the missing iPhone link."). Congratulating the round in a few words is fine; no other compliment.
subject = THEIR OWN WORDS (a short phrase from their launch/post in the package, lowercase, 2-6 words, no "video", no emoji).
No link, no URL, no price, no "free", no em dashes, no exclamation marks, nothing not in the package.
Recipient: {first} at {product}. Signal: {it.get('signal')}.
=== package ===
{package_text(it)}"""
    prompt, findings = base, []
    for attempt in range(3):
        d = claude_json(prompt, OFFER_SCHEMA)
        body = email_body(first, d["line1"].strip(), OFFER_LINE2)
        probs = offer_problems(d["subject"], body)
        ok, findings = (False, [["block", "offer", x] for x in probs]) if probs else gate(body, "email", to, first)
        if ok:
            return {"subject": d["subject"].strip(), "body": body}
        log("offer copy blocked, retry", attempt + 1, json.dumps(findings)[:300])
        prompt = base + "\n\nYour previous line was refused. Fix every finding:\n" + json.dumps(findings) + f"\nPrevious line1: {d['line1']}"
    raise RuntimeError(f"offer copy refused 3 times: {json.dumps(findings)[:300]}")


def text_email(to, subject, body, thread=None):
    m = EmailMessage()
    m["From"] = f"{SENDER_NAME} <{SENDER}>"
    m["To"] = to
    m["Subject"] = subject
    m["Message-ID"] = make_msgid(domain=MAIL_DOMAIN)
    if thread:
        m["In-Reply-To"] = thread["message_id"]
        m["References"] = thread["message_id"]
    m.set_content(body)
    return m


def first_email(touches):
    """The campaign's first sent email (the offer, the HM email, the investor email): its thread carries every follow-up."""
    for t in sorted(touches, key=lambda x: x.get("sentAt") or ""):
        if t["channel"] == "email" and t.get("status") == "sent" and t.get("threadId"):
            return t
    return None


def to_addr(ws, person):
    return person.get("email") if ws == "tyler" else DRY_TO


def send_offer(ws, it, touch):
    person = contact_of(it)
    first = (person.get("fullName") or it["target"]).split()[0]
    to = to_addr(ws, person)
    if not to:
        patch_touch(ws, touch["id"], status="cancelled", details={**(touch.get("details") or {}), "reason": "no email for this person"})
        log("OFFER no email", ws, it["target"])
        return None
    copies = load(f"copy-{ws}.json", {})
    key = it["id"] + ":offer"
    if key not in copies:
        copies[key] = write_offer(it, first, to)
        save(f"copy-{ws}.json", copies)
    c = copies[key]
    msg = text_email(to, c["subject"], c["body"])
    r = gmail_send(msg)
    patch_touch(ws, touch["id"], status="sent", sentAt=iso(), threadId=r["threadId"],
                details={**(touch.get("details") or {}), "to": to, "subject": c["subject"], "gmail_id": r["id"], "message_id": r.get("messageId") or msg["Message-ID"],
                         "dry_run": ws != "tyler"})
    log("OFFER", ws, it["target"], "->", to, "|", c["subject"], "| gmail", r["id"])
    return r


def final_take(ws, item_id):
    for path, rec in load(f"takes-{ws}.json", {}).items():
        if rec.get("item_id") == item_id and rec.get("final"):
            return path, rec
    return None, None


def start_offers(ws):
    """Funding rows whose one-shot package is ready and that have no campaign yet: queue the whole sequence (touch 1 = offer)."""
    n = 0
    for row in items_of(ws, "funding"):
        if row.get("stage") not in ("one_shot",) or row.get("replyStatus") not in ("none", None) or row.get("vslStage") in ("sent", "watched"):
            continue
        it = item_detail(ws, row["id"])
        if not any(o.get("status") == "ready" for o in it.get("oneShots") or []):
            continue
        ts = it.get("touches") or []
        if any(t.get("step") == "offer" for t in ts) or any(t["channel"] == "email" and t.get("status") == "sent" for t in ts):
            continue  # already in a campaign, or the pre-offer flow already sent the video
        person = contact_of(it)
        start_sequence(ws, it, {"person": person, "first": (person.get("fullName") or it["target"]).split()[0]})
        n += 1
    return n


def run_due(ws):
    """Ra steps whose due_at passed: the offer and the in-thread follow-ups. Desk/voice steps stay queued for their runner."""
    out = []
    for t in due_touches(ws):
        if (t.get("details") or {}).get("runner") != "ra" or t["channel"] != "email":
            continue
        if not real_sends_ok(ws):
            held = load("held.json", {})
            if t["id"] not in held:
                held[t["id"]] = iso()
                save("held.json", held)
                log("HOLD", ws, t.get("step"), t["itemId"], "real sends wait for the public viewer (R2 secret not cached on Ra)")
            continue
        it = item_detail(ws, t["itemId"])
        if it["huntType"] == "investor" and INVESTOR_SENDS_HELD:
            continue
        try:
            if t["step"] != "offer":
                continue  # follow-ups belong to pg-boss (send/followups.py)
            r = send_offer(ws, it, t)
            out.append((t["step"], it["target"], bool(r)))
        except Exception as e:
            log("DUE ERROR", ws, t.get("step"), it["target"], type(e).__name__, str(e)[:300])
    return out


def vizier_ready(ws, it):
    """A "yes" on the offer: the one-shot package goes onto the Vizier bar (talk-script + a suggestion card)."""
    o = next((o for o in it.get("oneShots") or [] if o.get("script")), None)
    if not o:
        return {"ok": False, "why": "no one-shot script"}
    d = os.path.dirname(o["script"])
    slug = os.path.basename(d)
    src = os.path.join(d, f"{slug}.md")
    if not os.path.isfile(src):
        return {"ok": False, "why": f"missing {src}"}
    if ws != "tyler":
        return {"ok": True, "dryrun": True, "slug": slug, "why": "dryrun: Tyler's bar untouched"}
    with open(src) as f:
        p = subprocess.run(["sudo", "-n", "-u", "eagle", "tee", f"{VIZIER_DIR}/{slug}.md"], stdin=f, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True, timeout=30)
    if p.returncode:
        return {"ok": False, "why": "vizier install: " + p.stderr.strip()[:200]}
    secs = json.loads(urllib.request.urlopen(VIZIER + "/prompter/scripts?file=" + slug, timeout=10).read())
    req = urllib.request.Request(VIZIER + "/push", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"text": f"Ready to record: {product_of(it)} said yes. Talk-script {slug} ({len(secs)} takes) is on the bar."}).encode())
    n = json.loads(urllib.request.urlopen(req, timeout=10).read()).get("clients")
    return {"ok": len(secs) > 0, "slug": slug, "takes": len(secs), "bar_clients": n}


def on_reply(ws, it, touch, outcome):
    """Any reply stops the queued rest; a yes to the funding offer puts the package on the Vizier bar (Ready to record)."""
    n = cancel_rest(ws, it["id"], f"reply received ({outcome})")
    res = {"cancelled": n}
    if it["huntType"] == "funding" and touch.get("step") == "offer" and outcome == "positive":
        res["vizier"] = vizier_ready(ws, it)
        log("READY TO RECORD", ws, it["target"], json.dumps(res))
    return res


# ---------------------------------------------------------------- replies: Gmail history on tyler@ -> answer in thread
def thread_index():
    idx = {}
    for ws in ("tyler", "dryrun"):
        try:
            rows = api(ws, "GET", "/rest/touches?filter=channel[eq]:email,status[eq]:sent&limit=200")["data"]["touches"]
        except Exception as e:
            log("thread index", ws, e)
            continue
        for t in rows:
            if t.get("threadId"):
                idx[t["threadId"]] = (ws, t)
    return idx


def header(msg, name):
    return next((h["value"] for h in msg.get("payload", {}).get("headers", []) if h["name"].lower() == name.lower()), "")


def plain(msg):
    def walk(p):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(p["body"]["data"] + "==").decode(errors="replace")
        for c in p.get("parts", []) or []:
            t = walk(c)
            if t:
                return t
        return ""
    t = walk(msg.get("payload", {}))
    # drop the quoted history ("On ... wrote:")
    return re.split(r"\n\s*On .{5,200}wrote:\s*\n", t, maxsplit=1)[0].strip()


def answer(ws, touch, thread_id, msg):
    it = item_detail(ws, touch["itemId"])
    first = ((it.get("person") or {}).get("fullName") or it["target"]).split()[0]
    frm = parseaddr(header(msg, "From"))[1]
    th = gmail("GET", f"/threads/{thread_id}", query={"format": "full"})
    convo = "\n\n".join(f"From: {header(m, 'From')}\nDate: {header(m, 'Date')}\n{plain(m)[:2500]}" for m in th.get("messages", []))
    body_in = plain(msg)
    rep = api(ws, "POST", "/rest/replies?upsert=true", {"itemId": it["id"], "touchId": touch["id"], "channel": "email", "body": body_in[:20000],
              "receivedAt": dt.datetime.fromtimestamp(int(msg["internalDate"]) / 1000, dt.timezone.utc).isoformat(), "providerId": msg["id"]})
    rid = rep["data"]["createReply"]["id"]
    if "mailer-daemon" in frm.lower() or "postmaster" in frm.lower():
        api(ws, "PATCH", f"/rest/touches/{touch['id']}", {"status": "failed"})
        api(ws, "PATCH", f"/rest/replies/{rid}", {"outcome": "bounce"})
        cancel_rest(ws, it["id"], "bounce")
        log("BOUNCE", ws, it["target"], frm)
        return
    forward(ws, it, stage="replied", replyStatus="replied")
    offer_rule = ""
    if touch.get("step") == "offer":
        offer_rule = ("\nThis thread is the OFFER: Tyler offered a free 90-second walkthrough of their product. If they accept "
                      "(\"yes\", \"send it\", \"sure\", \"go for it\"), outcome=positive and should_reply=false: the walkthrough itself "
                      "is the answer and goes out in this thread once Tyler records it. If they ask questions, answer them (positive).")
    prompt = f"""You are the hunt's backend agent answering an email reply AS Tyler Youk (founder, Utopia Models), first person.
Goal: a booked call at https://utopiamodels.ai/call (Cal.com, Utopia Models team page). Answer what they actually asked, from
the facts below only; anything not in the facts is "happy to go through that on a call". Offer, if relevant: {OFFER}.
Body: starts "Hi {first}," then 1-3 short sentences, then "Best,\\n{SENDER_NAME}". Under 80 words. No em dashes, no
exclamation marks, no price unless they asked, never claim to be human or an AI. Include the booking link when they show any
interest. outcome: positive (interested/questions), neutral, negative (not interested), unsubscribe (stop emailing),
booked (they say they booked), hired. should_reply=false for negative and unsubscribe (no reply goes out).{offer_rule}
=== thread (oldest first) ===
{convo[-9000:]}
=== package facts ===
{package_text(it)[:6000]}"""
    findings = []
    for attempt in range(3):
        d = claude_json(prompt, REPLY_SCHEMA)
        api(ws, "PATCH", f"/rest/replies/{rid}", {"outcome": d["outcome"]})
        if d["outcome"] == "booked":
            forward(ws, it, replyStatus="booked")
        if attempt == 0:
            on_reply(ws, it, touch, d["outcome"])
        if not d["should_reply"]:
            log("NO-REPLY", ws, it["target"], d["outcome"])
            return
        body = d["body"].strip() + "\n"
        to = frm if ws == "tyler" else DRY_TO
        ok, findings = gate(body, "email", to, first, followup=True)
        if ok:
            subj = header(msg, "Subject")
            m = EmailMessage()
            m["From"] = f"{SENDER_NAME} <{SENDER}>"
            m["To"] = to
            m["Subject"] = subj if subj.lower().startswith("re:") else "Re: " + subj
            mid = header(msg, "Message-ID")
            m["In-Reply-To"] = mid
            m["References"] = (header(msg, "References") + " " + mid).strip()
            m.set_content(body)
            r = gmail_send(m, thread_id=thread_id)
            log("REPLIED", ws, it["target"], d["outcome"], "->", to, "| gmail", r["id"])
            return r
        log("reply blocked, retry", attempt + 1, json.dumps(findings)[:300])
        prompt += "\n\nYour previous reply was refused by the copy gate. Fix every finding:\n" + json.dumps(findings) + "\nPrevious: " + d["body"]
    log("REPLY REFUSED x3", ws, it["target"], json.dumps(findings)[:300])


def replies():
    st = load("replies.json", {})
    hid = st.get("history_id")
    if not hid:
        st["history_id"] = gmail("GET", "/profile")["historyId"]
        save("replies.json", st)
        log("replies: history starts at", st["history_id"])
        return 0
    idx = thread_index()
    seen = set(st.get("seen", []))
    page, n, latest = None, 0, hid
    while True:
        q = {"startHistoryId": hid, "historyTypes": "messageAdded", "maxResults": 500, **({"pageToken": page} if page else {})}
        try:
            h = gmail("GET", "/history", query=q)
        except RuntimeError as e:
            if "404" in str(e):  # history expired: restart from now
                st["history_id"] = gmail("GET", "/profile")["historyId"]
                save("replies.json", st)
                return 0
            raise
        latest = h.get("historyId", latest)
        for rec in h.get("history", []):
            for ma in rec.get("messagesAdded", []):
                m = ma["message"]
                if m["id"] in seen or m.get("threadId") not in idx:
                    continue
                full = gmail("GET", f"/messages/{m['id']}", query={"format": "full"})
                frm = parseaddr(header(full, "From"))[1].lower()
                seen.add(m["id"])
                if frm == SENDER or "SENT" in full.get("labelIds", []):
                    continue
                ws, touch = idx[m["threadId"]]
                try:
                    answer(ws, touch, m["threadId"], full)
                    n += 1
                except Exception as e:
                    log("reply error", ws, m["id"], type(e).__name__, str(e)[:300])
        page = h.get("nextPageToken")
        if not page:
            break
    st["history_id"], st["seen"] = latest, sorted(seen)[-2000:]
    save("replies.json", st)
    return n


# ---------------------------------------------------------------- dry-run seed, drain, cycle
def dryrun_seed(src_id):
    it = item_detail("tyler", src_id)
    p, c, ext = it.get("person") or {}, it.get("company") or {}, it.get("extension") or {}
    body = {"huntType": it["huntType"], "externalId": "dryrun:" + it["externalId"], "target": it["target"], "signal": it["signal"],
            "signalAt": it["signalAt"], "stage": "one_shot", "vslStage": "scripted", "details": {**(it.get("details") or {}), "dryrun_of": src_id},
            "person": {"fullName": p.get("fullName") or it["target"], "email": DRY_TO, "title": p.get("title") or "",
                       **({"linkedinUrl": p["linkedinUrl"]} if p.get("linkedinUrl") else {})},
            "company": {"name": c.get("name") or it["target"], **({"domain": "dryrun." + c["domain"]} if c.get("domain") else {})}}
    if it["huntType"] == "funding" and ext:
        body["funding"] = {"kind": ext["kind"], "round": ext["round"], "amountUsd": float(ext["amountUsd"]) if ext.get("amountUsd") else None,
                           "announcedOn": str(ext["announcedOn"])[:10], "sourceUrl": ext["sourceUrl"]}
    r = api("dryrun", "POST", "/rest/huntItems?upsert=true", body)["data"]["createHuntItem"]
    for o in it.get("oneShots", []):
        api("dryrun", "POST", "/rest/oneShots?upsert=true", {"itemId": r["id"], "kind": o["kind"], "status": "ready",
            "script": o.get("script"), "assets": o.get("assets") or []})
    log("DRYRUN-SEED", src_id, "->", r["id"], it["target"])
    return r["id"]


def drain():
    """Replay beacons the Worker parked in R2 (beacons/<slug>/*.json) into the local API, then delete them."""
    env = r2_env()
    if not env:
        return "R2 secret not cached"
    aws = shutil.which("aws") or os.path.expanduser("~/.local/bin/aws")
    p = subprocess.run([aws, "s3api", "list-objects-v2", "--bucket", R2_BUCKET, "--prefix", "beacons/", "--endpoint-url", env["R2_EP"],
                        "--query", "Contents[].Key", "--output", "json"], env=env, capture_output=True, text=True, timeout=120)
    keys = json.loads(p.stdout or "null") or []
    for k in keys:
        slug = k.split("/")[1]
        g = subprocess.run([aws, "s3", "cp", f"s3://{R2_BUCKET}/{k}", "-", "--endpoint-url", env["R2_EP"]], env=env, capture_output=True, timeout=60)
        req = urllib.request.Request(f"{API}/v/{slug}/e", data=g.stdout, method="POST", headers={"content-type": "text/plain"})
        try:
            urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                continue
        subprocess.run([aws, "s3", "rm", f"s3://{R2_BUCKET}/{k}", "--endpoint-url", env["R2_EP"]], env=env, capture_output=True, timeout=60)
    return f"drained {len(keys)}"


def cycle(ws, store, settle):
    for step, fn in (("offers", lambda: start_offers(ws)), ("due", lambda: run_due(ws))):
        try:
            fn()
        except Exception as e:
            log(step, "error", type(e).__name__, str(e)[:300])
    for path, rec in detect(ws, store, settle):
        try:
            r = send(ws, rec["item_id"], path, rec["recording_id"])
            if r.get("held"):
                continue
            st = load(f"takes-{ws}.json", {})
            st[path]["final_sent"] = iso()
            save(f"takes-{ws}.json", st)
        except Exception as e:
            log("SEND ERROR", ws, rec.get("slug"), type(e).__name__, str(e)[:400])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cycle", "loop", "detect", "send", "replies", "dryrun-seed", "drain"])
    ap.add_argument("--ws", default="tyler")
    ap.add_argument("--store", default=STORE)
    ap.add_argument("--settle", type=float, default=600)
    ap.add_argument("--item")
    ap.add_argument("--take")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--every", type=float, default=60)
    a = ap.parse_args()
    if a.cmd == "detect":
        print(json.dumps(detect(a.ws, a.store, a.settle), indent=1, default=str))
    elif a.cmd == "cycle":
        cycle(a.ws, a.store, a.settle)
    elif a.cmd == "send":
        print(json.dumps(send(a.ws, a.item, a.take), indent=1))
    elif a.cmd == "replies":
        print("answered", replies())
    elif a.cmd == "dryrun-seed":
        print(dryrun_seed(a.src))
    elif a.cmd == "drain":
        print(drain())
    elif a.cmd == "loop":
        log("loop start", a.ws, a.store, f"settle={a.settle}s every={a.every}s")
        while True:
            t0 = time.time()
            for step, fn in (("cycle", lambda: cycle(a.ws, a.store, a.settle)), ("replies", replies), ("drain", drain)):
                try:
                    fn()
                except Exception as e:
                    log(step, "error", type(e).__name__, str(e)[:300])
            time.sleep(max(5, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
