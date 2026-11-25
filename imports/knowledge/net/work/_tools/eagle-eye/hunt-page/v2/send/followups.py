#!/usr/bin/env python3
"""followups.py: one follow-up, in-thread from tyler@, each adding something NEW (Tyler card 11-21 ~8:50 PM).

pg-boss (src/followups.ts) schedules the three touches (fu_1 day 3, fu_2 day 7, fu_3 day 14 after the first send) and runs
`followups.py send --ws <slug> --touch <id>` when one is due. The structure is copied from lemlist's "added value" sequence
(https://www.lemlist.com/blog/cold-email-follow-up): "Email 1: Mention you noticed your lead's pain points ... Email 2: Include
a quick video explaining how you'd deal with it ... Email 4: Send a case study of how you solved it for a similar company",
with "Add new value with each email" (https://www.lemlist.com/blog/how-many-cold-email-follow-ups) and the last step as the
break-up (https://www.lemlist.com/blog/cold-email-sequence, step 14). lemlist: "Two identical 'just bumping this' emails in the
same week read as automated, because they are", so a step with nothing new and real is CANCELLED, never sent as a bump.

  fu_1 (day 3)  adds "fix":    one more fix on their live product, from the one-shot package, not named in any earlier email
  fu_2 (day 7)  adds "clip":   the recorded walkthrough (hunt_send.send in the thread) when a final take exists and no video went
                               out yet; else the package's demo link if never sent; else cancelled
  fu_3 (day 14) adds "result": one real result for a similar company (client roster records only), as the last note; none -> cancelled

The backend agent (the model) writes it; copygate grades it in Tyler's voice (followup mode); 3 tries, then the touch fails.
Workspace dryrun mails agent@ only (hunt_send.to_addr + the guard below).

  followups.py send --ws dryrun --touch <touch id> [--print]   # --print: write + gate, print, send nothing, touch unchanged
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hunt_send as H  # noqa: E402

CLIENTS = os.environ.get("EAGLE_CLIENTS_FILE", os.path.expanduser("~/.claude/knowledge/_infra/occ-feeds/clients.json"))
SCHEMA = {"type": "object", "required": ["has_new", "new_thing", "line1", "line2"], "properties": {
    "has_new": {"type": "boolean"}, "new_thing": {"type": "string"}, "line1": {"type": "string"}, "line2": {"type": "string"}}}

ANGLE = {
    "fix": """ADD = ONE MORE FIX on their live product (lemlist step: the pain point you noticed). Pick ONE concrete thing from the
package that NO earlier email in this thread named. line1 = what you found + what you'd change, one or two short sentences
("Also noticed your pricing page loads the old plan names; I'd swap them for the three in your launch post."). line2 = one
short low-friction question ("Want me to add it to the walkthrough?"). If every fix in the package was already named,
has_new=false.""",
    "clip": """ADD = A NEW DEMO CLIP (lemlist step: "a quick video explaining how you'd deal with it"). The only clip you may point to is
the demo link given below under DEMO (never invent one). line1 = one sentence on what the clip shows for THEM ("Recorded a
short clip of the iPhone handoff on your downloads page:") and end line1 with the link exactly as given. line2 = one short
question. If DEMO is empty, has_new=false.""",
    "result": """ADD = A RESULT FOR A SIMILAR COMPANY (lemlist step: "a case study of how you solved it for a similar company"), and this
is the LAST note (lemlist's break-up). Use ONLY a record under RESULTS below that is genuinely similar to their product or
problem; say it plainly, no client names, no numbers that are not in the record. line1 = the result in one or two short
sentences. line2 = the last-note close, one short sentence that leaves the door open with the booking link
https://utopiamodels.ai/call. If no record is similar, has_new=false.""",
}


def earlier_emails(touches):
    out = []
    for t in sorted(touches, key=lambda x: x.get("sentAt") or ""):
        if t["channel"] == "email" and t.get("status") == "sent":
            d = t.get("details") or {}
            out.append(f"[{t.get('step') or 'first'}] subject: {d.get('subject', '')}\n{d.get('body') or ''}")
    return "\n\n".join(out)[-6000:]


def head_email(touches):
    return H.first_email([t for t in touches if not str(t.get("step") or "").startswith("fu_")])


def results_text():
    try:
        d = json.load(open(CLIENTS))
    except Exception:
        return ""
    rows = []
    for c in d.get("clients", []):
        paid = [i["label"] for i in c.get("items", []) if i.get("state") == "paid"]
        rows.append(f"- {c.get('what')} ({c.get('kind')}, via {c.get('source')}); delivered and paid: {', '.join(paid) or 'nothing yet'}")
    return "\n".join(rows)


def demo_link(it, touches):
    """The package's demo URL when no earlier email linked it."""
    sent = earlier_emails(touches)
    for o in it.get("oneShots") or []:
        u = o.get("demoUrl")
        if u and u not in sent:
            return u
    return ""


def cancel(ws, touch, why):
    H.patch_touch(ws, touch["id"], status="cancelled", details={**(touch.get("details") or {}), "reason": why})
    H.log("FOLLOWUP cancelled", ws, touch.get("step"), touch["itemId"], why)
    return {"cancelled": why}


def write(it, first, to, adds, touches, extra):
    base = f"""You write ONE short follow-up email, as Tyler Youk (founder, Utopia Models, a senior AI engineering team), first person,
in the thread of an email he already sent this person (they have not replied). It must add something NEW; never "just
checking in", "bumping this", "following up", "circling back" or a restatement of the earlier email.
{ANGLE[adds]}
Rules: only facts from the package / records below; no em dashes, no exclamation marks, no price, under 60 words in all.
Return has_new, new_thing (a few words naming the new thing), line1, line2.
Recipient: {first} at {H.product_of(it)}. Signal: {it.get('signal')}.
=== earlier emails in this thread (do not repeat them) ===
{earlier_emails(touches) or '(the first email only)'}
=== package ===
{H.package_text(it)[:8000]}
{extra}"""
    prompt, findings = base, []
    for attempt in range(3):
        d = H.claude_json(prompt, SCHEMA)
        if not d.get("has_new"):
            return None, []
        body = H.email_body(first, d["line1"].strip(), d["line2"].strip())
        ok, findings = H.gate(body, "email", to, first, followup=True)
        if ok:
            return {**d, "body": body}, findings
        H.log("followup copy blocked, retry", attempt + 1, json.dumps(findings)[:300])
        prompt = base + "\n\nYour previous draft was refused by the copy gate. Fix every finding:\n" + json.dumps(findings) + \
            f"\nPrevious: {d['line1']} {d['line2']}"
    raise RuntimeError(f"copy gate refused 3 follow-up drafts: {json.dumps(findings)[:300]}")


def send(ws, touch_id, dry_print=False):
    touch = H.api(ws, "GET", f"/rest/touches/{touch_id}")["data"]["touch"]
    if touch.get("status") != "queued":
        return {"skipped": f"touch is {touch.get('status')}"}
    it = H.item_detail(ws, touch["itemId"])
    if it["huntType"] == "investor" and H.INVESTOR_SENDS_HELD:
        return cancel(ws, touch, "investor sends are held (Tyler 11-21)")
    touches = it.get("touches") or []
    if it.get("replies") or any(t["channel"] == "email" and t.get("status") == "failed" for t in touches):
        return cancel(ws, touch, "reply or bounce on this prospect")
    head = head_email(touches)
    if not head:
        return cancel(ws, touch, "the first email never went out")
    adds = (touch.get("details") or {}).get("adds") or {"fu_1": "fix", "fu_2": "clip", "fu_3": "result"}[touch["step"]]
    person = H.contact_of(it)
    first = (person.get("fullName") or it["target"]).split()[0]
    to = H.to_addr(ws, person)
    if ws != "tyler" and not (to or "").endswith("@utopiamodels.ai"):
        raise SystemExit("refusing: a non-tyler workspace only mails @utopiamodels.ai")
    if not to:
        return cancel(ws, touch, "no email for this person")

    extra = ""
    if adds == "clip":
        path, rec = H.final_take(ws, it["id"])
        if path and not H.video_sent(touches) and not dry_print:
            r = H.send(ws, it["id"], path, rec.get("recording_id"), followup_touch=touch)  # the walkthrough, in the thread
            if r.get("email_id"):
                return {"sent": "video", **r}
        demo = demo_link(it, touches)
        extra = f"=== DEMO ===\n{demo}"
    elif adds == "result":
        extra = f"=== RESULTS (real client records; use only if similar) ===\n{results_text()}"

    copy, _ = write(it, first, to, adds, touches, extra)
    if copy is None:
        return cancel(ws, touch, f"nothing new and real to add ({adds}); never a filler bump")
    if dry_print:
        return {"print": copy["body"], "new_thing": copy["new_thing"], "to": to}
    d = head.get("details") or {}
    subj = d.get("subject") or it["target"]
    msg = H.text_email(to, subj if subj.lower().startswith("re:") else "Re: " + subj, copy["body"],
                       thread={"message_id": d.get("message_id")} if d.get("message_id") else None)
    r = H.gmail_send(msg, thread_id=head["threadId"])
    H.patch_touch(ws, touch["id"], status="sent", sentAt=H.iso(), threadId=r["threadId"],
                  details={**(touch.get("details") or {}), "gmail_id": r["id"], "message_id": r.get("messageId"), "to": to,
                           "subject": msg["Subject"], "body": copy["body"], "new_thing": copy["new_thing"], "dry_run": ws != "tyler"})
    H.log("FOLLOWUP", ws, it["target"], touch["step"], adds, "->", to, "|", copy["new_thing"], "| gmail", r["id"])
    return {"sent": touch["step"], "to": to, "gmail_id": r["id"], "new_thing": copy["new_thing"]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("--ws", required=True)
    s.add_argument("--touch", required=True)
    s.add_argument("--print", action="store_true", dest="dry_print")
    a = ap.parse_args()
    print(json.dumps(send(a.ws, a.touch, a.dry_print), default=str))


if __name__ == "__main__":
    main()
