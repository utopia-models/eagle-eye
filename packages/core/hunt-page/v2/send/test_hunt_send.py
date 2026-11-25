#!/usr/bin/env python3
"""hunt_send sequence tests: an in-memory Eagle Eye + fake Gmail/model/copygate (nothing leaves this process).

  python3 -m unittest -v send/test_hunt_send.py
"""
import datetime as dt, json, os, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["HUNT_SEND_STATE"] = tempfile.mkdtemp(prefix="hs-test-")
import hunt_send as H  # noqa: E402

H.VIEWER_DIR = tempfile.mkdtemp(prefix="hs-viewer-")


def fake_media(take, out):
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "thumb.gif"), "wb").write(b"GIF89a")
    return 60.0


class Fake:
    def __init__(self):
        self.items, self.touches, self.replies, self.sent, self.gated, self.n = {}, {}, [], [], [], 0

    def nid(self):
        self.n += 1
        return f"id{self.n}"

    def add_item(self, ht, **kw):
        i = self.nid()
        self.items[i] = {"id": i, "huntType": ht, "target": kw.get("target", "Acme"), "signal": "raised $2M seed", "stage": "one_shot",
                         "vslStage": "none", "replyStatus": "none", "details": kw.get("details", {}),
                         "person": kw.get("person", {"fullName": "Dana Lee", "email": "dana@acme.example", "linkedinUrl": "https://linkedin.com/in/dana"}),
                         "company": {"name": kw.get("target", "Acme")}, "oneShots": [{"id": "os-" + i, "status": "ready", "script": kw.get("script", "/nope/acme/script.md")}],
                         "extension": {}}
        return i

    # --- the helpers hunt_send uses
    def item_detail(self, ws, i):
        it = json.loads(json.dumps(self.items[i]))
        it["touches"] = [t for t in self.touches.values() if t["itemId"] == i]
        it["replies"] = [r for r in self.replies if r["itemId"] == i]
        return it

    def items_of(self, ws, ht):
        return [dict(v) for v in self.items.values() if v["huntType"] == ht]

    def touches_of(self, ws, i):
        return [dict(t) for t in self.touches.values() if t["itemId"] == i]

    def upsert_touch(self, ws, body):
        for t in self.touches.values():
            if t["channel"] == body["channel"] and t.get("providerId") == body.get("providerId"):
                return t
        t = dict(body, id=self.nid())
        self.touches[t["id"]] = t
        return t

    def patch_touch(self, ws, tid, **kv):
        self.touches[tid].update(kv)

    def due_touches(self, ws):
        now = H.iso()
        return [dict(t) for t in self.touches.values() if t.get("status") == "queued" and (t.get("dueAt") or "") <= now]

    def patch_item(self, ws, i, **kv):
        self.items[i].update(kv)

    def gmail_send(self, msg, thread_id=None, subject=None):
        self.sent.append({"to": msg["To"], "subject": msg["Subject"], "thread": thread_id, "in_reply_to": msg["In-Reply-To"],
                          "body": msg.get_body(("plain",)).get_content()})
        return {"id": f"g{len(self.sent)}", "threadId": thread_id or f"th{len(self.sent)}", "messageId": f"<gmail{len(self.sent)}@mail.gmail.example>"}

    def gate(self, text, channel, to, first, followup=False, audience="client"):
        self.gated.append({"text": text, "channel": channel, "audience": audience, "followup": followup})
        return True, []


class Base(unittest.TestCase):
    def setUp(self):
        self.f = Fake()
        for name in ("item_detail", "items_of", "touches_of", "upsert_touch", "patch_touch", "due_touches", "patch_item", "gmail_send", "gate"):
            p = mock.patch.object(H, name, getattr(self.f, name))
            p.start()
            self.addCleanup(p.stop)
        for fn in os.listdir(H.STATE):
            os.remove(os.path.join(H.STATE, fn))


class FundingOffer(Base):
    def test_sequence_has_every_step_on_its_day_and_is_idempotent(self):
        i = self.f.add_item("funding", person={"fullName": "Dana Lee", "email": "dana@acme.example", "linkedinUrl": "https://linkedin.com/in/dana",
                                                "handles": {"phone": "+15555550100"}})
        with mock.patch.object(H, "r2_env", lambda: None):
            self.assertEqual(H.start_offers("tyler"), 1)
            self.assertEqual(H.start_offers("tyler"), 0, "a row already in a campaign is not restarted")
        ts = sorted(self.f.touches.values(), key=lambda t: (t["details"]["day"], t["step"]))
        self.assertEqual([(t["step"], t["details"]["day"], t["channel"]) for t in ts],
                         [("offer", 0, "email"), ("li_visit", 1, "linkedin"), ("dial_1", 3, "call"), ("li_connect", 3, "linkedin"),
                          ("li_dm", 4, "linkedin"), ("x_reply", 7, "x"), ("dial_2", 10, "call")])
        self.assertTrue(all(t["status"] == "queued" for t in ts))
        d0 = dt.datetime.fromisoformat(ts[0]["dueAt"].replace("Z", "+00:00"))
        d10 = dt.datetime.fromisoformat(ts[-1]["dueAt"].replace("Z", "+00:00"))
        self.assertEqual((d10 - d0).days, 10)
        self.assertFalse([t for t in ts if t["channel"] == "email" and t["step"] != "offer"], "email follow-ups are pg-boss fu_1..3, not sequence steps")
        self.assertEqual(next(t for t in ts if t["step"] == "li_connect")["details"]["action"].split(" -> ")[-1][:19], "Send without a note")
        pend = [json.loads(l) for l in open(os.path.join(H.STATE, "pending.jsonl"))]
        self.assertEqual({p["runner"] for p in pend}, {"nova", "voice"}, "desk + dial steps are queued for novaserver / Tyler's dial block")

    def test_no_phone_cancels_the_dial_steps_with_a_reason(self):
        self.f.add_item("funding")
        H.start_offers("tyler")
        dial = [t for t in self.f.touches.values() if t["channel"] == "call"]
        self.assertEqual([t["status"] for t in dial], ["cancelled", "cancelled"])
        self.assertIn("no phone", dial[0]["details"]["reason"])

    def test_offer_holds_in_tyler_without_the_public_viewer(self):
        self.f.add_item("funding")
        H.start_offers("tyler")
        with mock.patch.object(H, "r2_env", lambda: None):
            H.run_due("tyler")
        self.assertEqual(self.f.sent, [], "no real send while the public viewer cannot exist")
        self.assertEqual(next(t for t in self.f.touches.values() if t["step"] == "offer")["status"], "queued")

    def test_offer_email_has_no_link_no_price_and_the_fixed_ask(self):
        self.f.add_item("funding", person={"fullName": "Dana Lee", "email": "dryrun@example.com"})
        H.start_offers("dryrun")
        with mock.patch.object(H, "claude_json", lambda p, s, model="sonnet": {"subject": "onboard the new hire",
                                                                                  "line1": "I walked acme.dev and found three things I'd fix first, starting with the missing iPhone link."}):
            H.run_due("dryrun")
        self.assertEqual(len(self.f.sent), 1)
        m = self.f.sent[0]
        self.assertEqual(m["to"], "dryrun@example.com")
        self.assertIn("Want the 90-second walkthrough?", m["body"])
        self.assertNotRegex(m["body"], r"https?://|\$\d")
        offer = next(t for t in self.f.touches.values() if t["step"] == "offer")
        self.assertEqual(offer["status"], "sent")
        self.assertTrue(offer["threadId"])
        self.assertEqual(offer["details"]["message_id"], "<gmail1@mail.gmail.example>", "the Message-Id Gmail stamped, not ours (Gmail rewrites it)")
        self.assertEqual(self.f.gated[-1]["audience"], "client", "touch 1 passed copygate")

    def test_offer_copy_with_a_link_or_price_is_refused(self):
        self.assertEqual(H.offer_problems("x", "Hi A,\n\nSee https://utopiamodels.ai/call for $3,200/mo\n\nBest"), ["touch 1 carries no link", "touch 1 names no price"])
        self.assertEqual(H.offer_problems("their words", H.email_body("Dana", "I walked acme.dev and found three things.", H.OFFER_LINE2)), [])
        self.assertEqual(H.offer_problems("s", H.email_body("Ilia", "Congrats on the $3M seed; I walked touchmark.ai and found three things.", H.OFFER_LINE2)), [],
                         "their own round amount is not a price (live dry run 11-21 refused 3 drafts on this)")

    def test_yes_cancels_the_rest_and_puts_the_package_on_the_vizier_bar(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "acme"))
        open(os.path.join(d, "acme", "acme.md"), "w").write("# acme\n## 1 · a (10 s)\nline\n")
        i = self.f.add_item("funding", script=os.path.join(d, "acme", "script.md"))
        H.start_offers("tyler")
        offer = next(t for t in self.f.touches.values() if t["step"] == "offer")
        self.f.touches[offer["id"]].update(status="sent", threadId="th1")
        calls = []
        with mock.patch.object(H.subprocess, "run", lambda *a, **k: calls.append(a[0]) or mock.Mock(returncode=0, stderr="")), \
             mock.patch.object(H.urllib.request, "urlopen", lambda req, timeout=10: mock.Mock(read=lambda: json.dumps([{"title": "1"}] if "scripts" in getattr(req, "full_url", req) else {"clients": 1}).encode())):
            res = H.on_reply("tyler", self.f.item_detail("tyler", i), offer, "positive")
        self.assertEqual(res["cancelled"], 4, "6 later steps; the 2 dial steps were already cancelled (no phone)")
        self.assertTrue(res["vizier"]["ok"])
        self.assertEqual(res["vizier"]["slug"], "acme")
        self.assertIn("tee", calls[0])
        self.assertTrue(all(t["status"] in ("sent", "cancelled") for t in self.f.touches.values()))

    def test_take_waits_for_the_yes_then_goes_out_in_the_offer_thread(self):
        i = self.f.add_item("funding", person={"fullName": "Dana Lee", "email": "dryrun@example.com"})
        H.start_offers("dryrun")
        offer = next(t for t in self.f.touches.values() if t["step"] == "offer")
        self.f.touches[offer["id"]].update(status="sent", threadId="th-offer", details={**offer["details"], "subject": "onboard the new hire", "message_id": "<m1@x>"})
        self.assertEqual(H.send("dryrun", i, "/tmp/take.mp4"), {"held": "waiting for a yes to the offer (or the day-7 follow-up)"})
        self.f.items[i]["replyStatus"] = "replied"
        self.f.replies.append({"itemId": i, "outcome": "positive"})
        api_calls = []
        fake_api = lambda ws, m, path, body=None, idem=None: api_calls.append((m, path, body)) or ({"data": {"viewers": []}} if m == "GET" else {"data": {}})
        with mock.patch.object(H, "api", fake_api), mock.patch.object(H, "build_media", fake_media), \
             mock.patch.object(H, "render_page", lambda *a: None), mock.patch.object(H, "url_ok", lambda *a, **k: True), \
             mock.patch.object(H, "forward", lambda *a, **k: {}):
            r = H.send("dryrun", i, "/tmp/take.mp4")
        self.assertTrue(r["in_thread"])
        m = self.f.sent[-1]
        self.assertEqual(m["thread"], "th-offer")
        self.assertEqual(m["in_reply_to"], "<m1@x>")
        self.assertEqual(m["subject"], "Re: onboard the new hire")
        self.assertIn("Here's the walkthrough of Acme I mentioned.", m["body"])
        t = [b for (meth, p, b) in api_calls if p.startswith("/rest/touches")][0]
        self.assertEqual((t["step"], t["details"]["video"], t["threadId"]), ("video", True, "th-offer"))


class JobsAndInvestors(Base):
    def _send(self, ht, person, copy):
        i = self.f.add_item(ht, person=person, target="ML Engineer" if ht == "job_post" else "OSS Capital")
        api_calls = []
        fake_api = lambda ws, m, path, body=None, idem=None: api_calls.append((m, path, body)) or ({"data": {"viewers": []}} if m == "GET" else {"data": {}})
        with mock.patch.object(H, "api", fake_api), mock.patch.object(H, "build_media", fake_media), \
             mock.patch.object(H, "render_page", lambda *a: None), mock.patch.object(H, "url_ok", lambda *a, **k: True), \
             mock.patch.object(H, "forward", lambda *a, **k: {}), mock.patch.object(H, "claude_json", lambda p, s, model="sonnet": copy):
            r = H.send("dryrun", i, "/tmp/take.mp4")
        return i, r, api_calls

    def test_job_one_shot_sends_the_hm_email_and_queues_ats_connect_referral(self):
        person = {"fullName": "Sam Park", "email": "dryrun@example.com", "linkedinUrl": "https://linkedin.com/in/sam"}
        self.f.items  # noqa
        i, r, calls = self._send("job_post", person, {"subject": "eval harness", "line1": "Applied for ML Engineer.", "line2": "Worth two minutes?",
                                                      "page_title": "Acme: eval demo", "pill": "Book an intro", "linkedin_note": "hi"})
        self.f.items[i]["details"] = {}
        self.assertEqual(r["queued"], ["ats", "li_connect"], "no referral candidate -> referral cancelled with a reason")
        steps = {t["step"]: t for t in self.f.touches.values()}
        self.assertEqual(steps["referral"]["status"], "cancelled")
        self.assertIn("ground-truth.yaml", steps["ats"]["details"]["answers"])
        self.assertIn("/v/", steps["ats"]["details"]["cover_first_line"])
        self.assertNotIn("hm_email", steps, "the HM email left with the take, it is not queued again")
        self.assertEqual(self.f.gated[0]["audience"], "hiring-manager")

    def test_job_referral_from_the_package_contact(self):
        i = self.f.add_item("job_post", person={}, details={"contact": {"name": "Sam Park", "email": "dryrun@example.com", "linkedin": "https://linkedin.com/in/sam",
                                                                         "referral": [{"name": "Ria Shah", "linkedin": "https://linkedin.com/in/ria"}],
                                                                         "ats": {"kind": "greenhouse", "url": "https://boards.greenhouse.io/acme/jobs/1"}}})
        H.start_sequence("dryrun", self.f.item_detail("dryrun", i), {"person": H.contact_of(self.f.item_detail("dryrun", i)), "first": "Sam", "page": "https://x/v/a/"},
                         sent_steps=("hm_email",))
        steps = {t["step"]: t for t in self.f.touches.values()}
        self.assertEqual(steps["referral"]["status"], "queued")
        self.assertIn("would you be up for referring me", steps["referral"]["details"]["text"].lower())
        self.assertEqual(steps["ats"]["details"]["ats"], "greenhouse")
        self.assertEqual(steps["ats"]["details"]["steps"], H.ATS_STEPS["greenhouse"])

    def test_investor_email_states_the_ask_and_queues_x(self):
        person = {"fullName": "Joseph Jacks", "email": "dryrun@example.com", "handles": {"x": "@JosephJacks_"}}
        copy = {"subject": "Plane-adjacent: open-source agent ops, solo founder + agent fleet, raising pre-seed",
                "line1": "You backed Plane as sole investor; open-source ops tooling is the layer I build.", "line2": "Utopia Models is one founder running an AI engineering company with a fleet of agents.",
                "line3": "Eagle Eye found 60 live signals today.", "line4": H.INVEST_ASK + ". I recorded a 90-second live demo for you:",
                "page_title": "OSS Capital: a live demo", "pill": "Reply by email", "linkedin_note": "hi"}
        self.assertEqual(self._send("investor", person, copy)[1]["held"][:24], "investor sends are held ", "Tyler 11-21: investors hold")
        self.assertEqual(self.f.sent, [])
        self.assertEqual(self.f.touches, {}, "no investor touch is even queued while held")
        H.INVESTOR_SENDS_HELD = False
        self.addCleanup(setattr, H, "INVESTOR_SENDS_HELD", True)
        i, r, calls = self._send("investor", person, copy)
        self.assertIn("$8M post-money", self.f.sent[-1]["body"])
        self.assertEqual(r["queued"], ["x_reply", "x_dm"], "no LinkedIn -> li_connect cancelled; email follow-ups are pg-boss fu_1..3")
        steps = {t["step"]: t for t in self.f.touches.values()}
        self.assertEqual(steps["x_reply"]["details"]["account"], "@JosephJacks_")
        self.assertEqual(self.f.gated[0]["audience"], "professional")


class InvestorHold(Base):
    def test_held_investor_due_step_never_sends(self):
        i = self.f.add_item("investor")
        self.f.upsert_touch("dryrun", {"itemId": i, "channel": "email", "status": "queued", "step": "inv_email", "dueAt": "2026-11-20T00:00:00Z",
                                       "providerId": "seq:x", "details": {"runner": "ra"}})
        H.run_due("dryrun")
        self.assertEqual(self.f.sent, [])
        self.assertEqual(H.start_sequence("dryrun", self.f.item_detail("dryrun", i), {"person": {}, "first": "J"}), [])


if __name__ == "__main__":
    unittest.main()
