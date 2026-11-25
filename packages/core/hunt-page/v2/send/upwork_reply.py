#!/usr/bin/env python3
"""upwork_reply.py: answer an Upwork client message within 5 minutes, in Tyler's voice, toward a booked call
(Tyler card 11-21 ~8:50 PM: "Upwork client message -> agent answers in under 5 min as Tyler toward a Cal.com call").

The seat rule stands (net/work/upwork/RULES.md, fleet-doctrine:upwork SKILL): Upwork is never driven by a script. This loop
never opens upwork.com. Its pieces:

  1 WATCH   (this process, Ra, every 30 s): inbox@example.com's Upwork notification mail ("<Name> sent you a message",
            Gmail API, the same signal mail_watch.py uses). Each new mail = one client message: a reply row on that
            client's roost in Eagle Eye (so ROOSTS shows "Reply · due in 5 min · upwork"), a next step Reply due at
            received + 5 min, and a READ request to the upwork agent (fleetmail, thread upwork-desk): the mail carries no
            text, so the seat holder looks at the room and runs step 2 with the client's words.
  2 DRAFT   `upwork_reply.py draft --client "<Name>" --message-file F`: the backend agent writes the answer as Tyler
            (first person, signed "Tyler Youk, Utopia Models, Inc."), from the client record + thread, toward a call:
            an active contract -> the booking page utopiamodels.ai/call (Cal.com; utopiamodels.ai is on
            active-contract-links.txt); before a contract the Upwork pre-send gate refuses booking links (circumvention
            ticket #55841136), so the call is proposed through Upwork's own meeting tool with the 3 soonest free slots.
            Gates: copygate (one writer pipeline, channel upwork) + presend_check.py --contract active|none. 3 tries.
  3 SEND    live: fleetmail to the upwork agent with the exact text and the deadline (received + 5 min); it types it into
            the room by the human seat and PATCHes the touch to sent. dry-run (the default): the draft goes to
            dryrun@example.com by email, nothing reaches the seat or the client, the touch stays `drafted`.

  upwork_reply.py watch [--once] [--live]
  upwork_reply.py draft --client "Mohamed T." --message-file msg.txt [--contract active|none] [--received ISO] [--live]

Live = `--live` or UPWORK_REPLY_LIVE=1 (queued for power-on: the Upwork seat on novaserver must be signed in).
"""
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("HUNT_SEND_TOKENS", os.path.expanduser("~/.claude/private/upwork-reply"))  # its own key: people/roosts/nextSteps
import hunt_send as H  # noqa: E402

BOX = os.environ.get("UPWORK_REPLY_BOX") or H.eeconf.get("upwork_reply_box", "inbox@example.com")
QUERY = 'from:upwork.com subject:"sent you a message" newer_than:1d'
KB = os.path.expanduser("~/dev/utopia-models/knowledge")
PRESEND = os.path.join(KB, "net/work/_tools/upwork/presend_check.py")
CRM = os.path.join(KB, "net/work/upwork/crm")
CAL = os.path.expanduser("~/.claude/knowledge/_infra/scripts/fleet_calendar.py")
WS = os.environ.get("UPWORK_REPLY_WS", "tyler")
AGENT = "upwork"           # the seat holder (knowledge#13160)
SLA_S = 300                # the 5-minute clock
BOOK = "utopiamodels.ai/call"
SIGN = "Tyler Youk, Utopia Models, Inc."
ACTIVE_STAGES = ("contract", "hourly")
SCHEMA = {"type": "object", "required": ["reply", "outcome"], "properties": {
    "reply": {"type": "string"}, "outcome": {"type": "string", "enum": ["positive", "neutral", "negative", "booked", "hired"]}}}


def live_mode(flag):
    return bool(flag) or os.environ.get("UPWORK_REPLY_LIVE") == "1"


def first_name(client):
    return (client or "").split()[0].strip(".,") or "there"


def slugify(client):
    return re.sub(r"[^a-z0-9]+", "-", first_name(client).lower()).strip("-")


# ---------------------------------------------------------------- Eagle Eye records
def roost_for(ws, client):
    """The client's roost (person = first name, the CRM/ingest convention); a new client gets one (origin upwork)."""
    first = first_name(client)
    ppl = H.api(ws, "GET", f"/rest/people?filter=fullName[ilike]:{first}%25&limit=20")["data"]["people"]
    person = next((p for p in ppl if first_name(p["fullName"]).lower() == first.lower()), None)
    if not person:
        person = H.api(ws, "POST", "/rest/people?upsert=true", {"fullName": first})["data"]["createPerson"]
    rs = H.api(ws, "GET", f"/rest/roosts?filter=personId[eq]:{person['id']}&limit=5")["data"]["roosts"]
    if rs:
        return rs[0]
    return H.api(ws, "POST", "/rest/roosts?upsert=true", {"personId": person["id"], "kind": "client", "origin": "upwork",
                                                         "stage": "prospect: replied on Upwork"})["data"]["createRoost"]


def contract_of(roost):
    return "active" if str(roost.get("stage") or "").split(":")[0] in ACTIVE_STAGES else "none"


def record_message(ws, roost, client, received, provider, body="View your message and send a reply."):
    rep = H.api(ws, "POST", "/rest/replies?upsert=true", {"roostId": roost["id"], "channel": "upwork", "body": body[:20000],
                                                          "receivedAt": received, "providerId": provider})["data"]["createReply"]
    due = H.iso(dt.datetime.fromisoformat(received.replace("Z", "+00:00")) + dt.timedelta(seconds=SLA_S))
    H.api(ws, "POST", "/rest/nextSteps?upsert=true", {"roostId": roost["id"], "what": "Reply", "dueAt": due, "owner": AGENT,
                                                       "sourceKey": f"upwork:reply:{provider}"})
    return rep, due


def crm_text(client):
    f = os.path.join(CRM, slugify(client) + ".jsonl")
    if not os.path.isfile(f):
        return ""
    return "\n".join(l.strip() for l in open(f) if l.strip())[-4000:]


def slots(n=3):
    """The n soonest free 30-min slots >= 3 h out (fleet_calendar gaps), as text; [] when the calendar cannot be read."""
    try:
        start = (H.now() + dt.timedelta(hours=3)).strftime("%Y-%m-%d")
        end = (H.now() + dt.timedelta(days=4)).strftime("%Y-%m-%d")
        p = subprocess.run(["python3", CAL, "gaps", start, end, "--minutes", "30"], capture_output=True, text=True, timeout=60)
        lines = [l.strip() for l in p.stdout.splitlines() if re.search(r"\d{1,2}:\d{2}", l)]
        return lines[:n]
    except Exception:
        return []


# ---------------------------------------------------------------- gates (copygate = the one writer pipeline + Upwork pre-send)
def gates(text, client, contract):
    ok, findings = H.gate(text, "upwork", client, first_name(client), followup=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text)
    try:
        p = subprocess.run(["python3", PRESEND, "--contract", contract, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if p.returncode != 0:
        ok = False
        findings = findings + [["block", "presend", l] for l in p.stdout.strip().splitlines()[:6]]
    return ok, findings


def write_reply(client, message, contract, thread="", record=""):
    first = first_name(client)
    if contract == "active":
        call = f"If a call helps, the link is https://{BOOK} (Cal.com, Utopia Models). Offer it when a call moves things forward."
    else:
        free = slots()
        call = ("There is NO contract yet, so no links of any kind and no booking tools: propose a short call through Upwork's own "
                "meeting tool" + (f", offering these times (Tyler's, MT): {'; '.join(free)}" if free else ", asking which time works") + ".")
    base = f"""You answer ONE Upwork message from a client, AS Tyler Youk, first person, within minutes. Goal: move toward a booked call.
Answer what {first} actually asked first, from the facts below only; anything not in the facts -> "happy to go through that on a call".
{call}
Rules: start "Hi {first},", then 1-3 short sentences, then sign exactly "{SIGN}". Under 80 words. No em dashes, no exclamation marks,
no caveats ("I can't", "not sure", "unfortunately"), no price or terms not already in the thread, never move the conversation off
Upwork, never ask for or give an email, phone or chat handle. outcome: positive | neutral | negative | booked | hired.
=== their message ===
{message[:4000]}
=== thread / client record (oldest first) ===
{(thread + chr(10) + record)[-6000:]}"""
    prompt, findings = base, []
    for attempt in range(3):
        d = H.claude_json(prompt, SCHEMA)
        text = d["reply"].strip()
        if SIGN not in text:
            text = text.rstrip() + "\n\n" + SIGN
        ok, findings = gates(text, client, contract)
        if ok:
            return {**d, "reply": text}
        H.log("upwork reply blocked, retry", attempt + 1, json.dumps(findings)[:300])
        prompt = base + "\n\nYour previous draft was refused by the gates. Fix every finding:\n" + json.dumps(findings) + "\nPrevious:\n" + text
    raise RuntimeError(f"gates refused 3 Upwork drafts: {json.dumps(findings)[:300]}")


# ---------------------------------------------------------------- the two steps
def fleetmail(text, deadline):
    p = subprocess.run(["fleetmail", "send", AGENT, text, "--thread", "upwork-desk", "--deadline", deadline, "--class", "urgent"],
                       capture_output=True, text=True, timeout=60)
    return p.stdout.strip() or p.stderr.strip()[:200]


def draft(client, message, contract=None, received=None, live=False, ws=WS, provider=None):
    t0 = time.time()
    received = received or H.iso()
    roost = roost_for(ws, client)
    contract = contract or contract_of(roost)
    provider = provider or "draft:" + hashlib.sha1(f"{client}|{received}|{message}".encode()).hexdigest()[:16]
    rep, due = record_message(ws, roost, client, received, "msg:" + provider.split(":", 1)[-1], body=message)
    thread = "\n".join(f"[{r.get('receivedAt')}] {r.get('body', '')[:500]}" for r in
                       H.api(ws, "GET", f"/rest/replies?filter=roostId[eq]:{roost['id']}&limit=20")["data"]["replies"]
                       if not str(r.get("body", "")).startswith("View your message"))
    d = write_reply(client, message, contract, thread, crm_text(client))
    drafted = H.iso()
    lat = (dt.datetime.fromisoformat(drafted.replace("Z", "+00:00")) - dt.datetime.fromisoformat(received.replace("Z", "+00:00"))).total_seconds()
    touch = H.api(ws, "POST", "/rest/touches?upsert=true", {"roostId": roost["id"], "channel": "upwork", "status": "drafted", "sentAt": drafted,
        "providerId": provider, "details": {"text": d["reply"], "client": client, "received_at": received, "drafted_at": drafted,
        "latency_s": round(lat), "draft_s": round(time.time() - t0), "contract": contract, "outcome": d["outcome"],
        "live": bool(live), "deadline": due}})["data"]["createTouch"]
    if d["outcome"] in ("positive", "neutral", "negative", "booked", "hired"):
        H.api(ws, "PATCH", f"/rest/replies/{rep['id']}", {"outcome": d["outcome"]})
    if live:
        sent = fleetmail(f"SEND in {client}'s Upwork room by {due} (5-min clock). Type exactly, by the human seat:\n\n{d['reply']}\n\n"
                         f"Then: ledger.py add message_sent --client {slugify(client)}; PATCH /rest/touches/{touch['id']} status=sent.", due)
        H.log("UPWORK DRAFT live", client, contract, f"{round(lat)}s", "fleetmail", sent)
    else:
        m = H.text_email(H.DRY_TO, f"[dry-run] Upwork reply to {client} ({contract} contract, drafted {round(lat)} s after the message)",
                         f"Their message:\n{message}\n\n--- reply (gated: copygate upwork + presend_check --contract {contract}) ---\n{d['reply']}\n")
        r = H.gmail_send(m)
        H.log("UPWORK DRAFT dry-run", client, contract, f"{round(lat)}s", "-> agent@ gmail", r["id"])
    return {"touch": touch["id"], "roost": roost["id"], "contract": contract, "latency_s": round(lat), "reply": d["reply"], "live": bool(live)}


def watch_once(live=False, ws=WS):
    st = H.load("upwork-reply.json", {})
    seen = set(st.get("seen", []))
    r = H.gmail("GET", "/messages", subject=BOX, query={"q": QUERY, "maxResults": 20})
    ids = [m["id"] for m in r.get("messages", [])]
    if "seen" not in st:  # first run: no backlog, only messages from now on
        st["seen"] = ids
        H.save("upwork-reply.json", st)
        H.log("upwork-reply: watching", BOX, f"({len(ids)} earlier notifications skipped)")
        return []
    out = []
    for mid in reversed(ids):
        if mid in seen:
            continue
        g = H.gmail("GET", f"/messages/{mid}", subject=BOX, query={"format": "metadata", "metadataHeaders": ["Subject"]})
        m = re.match(r"(.+?) sent you a message", H.header(g, "Subject"))
        seen.add(mid)
        if not m:
            continue
        client = m.group(1).strip()
        received = H.iso(dt.datetime.fromtimestamp(int(g["internalDate"]) / 1000, dt.timezone.utc))
        roost = roost_for(ws, client)
        rep, due = record_message(ws, roost, client, received, f"mail:{mid}")
        cmd = f"python3 {os.path.abspath(__file__)} draft --client '{client}' --message-file <their words> --received {received}" + (" --live" if live else "")
        if live:
            res = fleetmail(f"{client} wrote on Upwork at {received}; answer by {due} (5-min clock). LOOK at the room, save their message, run:\n{cmd}", due)
        else:
            res = "dry-run: read request not sent"
        H.log("UPWORK MESSAGE", client, received, "due", due, "|", res)
        out.append({"client": client, "received": received, "due": due, "roost": roost["id"]})
    st["seen"] = sorted(seen)[-500:]
    H.save("upwork-reply.json", st)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--once", action="store_true")
    w.add_argument("--live", action="store_true")
    w.add_argument("--every", type=float, default=30)
    d = sub.add_parser("draft")
    d.add_argument("--client", required=True)
    d.add_argument("--message-file", required=True)
    d.add_argument("--contract", choices=["active", "none"])
    d.add_argument("--received")
    d.add_argument("--live", action="store_true")
    d.add_argument("--ws", default=WS)
    a = ap.parse_args()
    if a.cmd == "draft":
        print(json.dumps(draft(a.client, open(a.message_file).read().strip(), a.contract, a.received, live_mode(a.live), a.ws), indent=1))
        return
    while True:
        try:
            watch_once(live_mode(a.live))
        except Exception as e:
            H.log("upwork-reply watch error", type(e).__name__, str(e)[:300])
        if a.once:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
