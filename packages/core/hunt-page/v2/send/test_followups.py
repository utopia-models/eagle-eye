#!/usr/bin/env python3
"""followups.py tests: in-memory Eagle Eye + fake Gmail/model/copygate from test_hunt_send (nothing leaves this process).

  python3 -m unittest -v send/test_followups.py
"""
import os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_hunt_send import Base, H  # noqa: E402
import followups as FU  # noqa: E402


class Followups(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(H, "api", self.api)
        p.start()
        self.addCleanup(p.stop)
        self.prompts = []

    def api(self, ws, method, path, body=None, idem=None):
        assert method == "GET" and path.startswith("/rest/touches/"), path
        return {"data": {"touch": dict(self.f.touches[path.rsplit("/", 1)[1]])}}

    def model(self, *outs):
        it = iter(outs)

        def fake(prompt, schema, model="sonnet"):
            self.prompts.append(prompt)
            return next(it)
        p = mock.patch.object(H, "claude_json", fake)
        p.start()
        self.addCleanup(p.stop)

    def head(self, i, ws="dryrun"):
        self.f.upsert_touch(ws, {"itemId": i, "channel": "email", "status": "sent", "step": "offer", "threadId": "th-1", "sentAt": "2026-11-18T00:00:00Z",
                                 "providerId": "g0", "details": {"subject": "hard to switch from", "message_id": "<gmail0@mail.gmail.example>",
                                                                 "body": "Hi Ilia,\n\nI walked touchmark.ai and found three things, starting with one discount number.\n"}})

    def fu(self, i, step, adds):
        return self.f.upsert_touch("dryrun", {"itemId": i, "channel": "email", "status": "queued", "step": step, "providerId": f"fu:{i}:{step}",
                                              "dueAt": "2026-11-21T00:00:00Z", "details": {"runner": "boss", "adds": adds}})["id"]

    def test_fix_goes_in_thread_to_agent_only_with_something_new(self):
        i = self.f.add_item("funding", target="Touchmark", person={"fullName": "Ilia K", "email": "ilia@touchmark.example"})
        self.head(i)
        t = self.fu(i, "fu_1", "fix")
        self.model({"has_new": True, "new_thing": "pricing page plan names", "line1": "Also noticed the pricing page still shows the old plan names.",
                    "line2": "Want it in the walkthrough?"})
        r = FU.send("dryrun", t)
        self.assertEqual(r["sent"], "fu_1")
        s = self.f.sent[-1]
        self.assertEqual(s["to"], "dryrun@example.com", "dry run reaches agent@ only, never the prospect")
        self.assertEqual((s["thread"], s["in_reply_to"], s["subject"]), ("th-1", "<gmail0@mail.gmail.example>", "Re: hard to switch from"))
        self.assertTrue(self.f.gated[-1]["followup"], "graded by copygate in follow-up mode")
        self.assertIn("one discount number", self.prompts[0], "the model sees earlier emails so it never repeats them")
        self.assertEqual(self.f.touches[t]["status"], "sent")
        self.assertEqual(self.f.touches[t]["details"]["new_thing"], "pricing page plan names")

    def test_nothing_new_cancels_never_a_bump(self):
        i = self.f.add_item("funding")
        self.head(i)
        t = self.fu(i, "fu_2", "clip")
        self.model({"has_new": False, "new_thing": "", "line1": "", "line2": ""})
        r = FU.send("dryrun", t)
        self.assertIn("never a filler bump", r["cancelled"])
        self.assertEqual(self.f.sent, [])
        self.assertEqual(self.f.touches[t]["status"], "cancelled")

    def test_any_reply_or_bounce_stops_it(self):
        i = self.f.add_item("funding")
        self.head(i)
        t = self.fu(i, "fu_1", "fix")
        self.f.replies.append({"itemId": i, "body": "unsubscribe", "outcome": "unsubscribe"})
        self.assertIn("reply or bounce", FU.send("dryrun", t)["cancelled"])
        j = self.f.add_item("funding")
        self.head(j)
        self.f.upsert_touch("dryrun", {"itemId": j, "channel": "email", "status": "failed", "providerId": "gb"})
        self.assertIn("reply or bounce", FU.send("dryrun", self.fu(j, "fu_1", "fix"))["cancelled"])
        self.assertEqual(self.f.sent, [])

    def test_investor_followups_stay_held(self):
        i = self.f.add_item("investor")
        self.head(i)
        self.assertIn("held", FU.send("dryrun", self.fu(i, "fu_1", "fix"))["cancelled"])
        self.assertEqual(self.f.sent, [])

    def test_clip_sends_the_recorded_walkthrough_when_a_final_take_exists(self):
        i = self.f.add_item("funding")
        self.head(i)
        t = self.fu(i, "fu_2", "clip")
        calls = []
        with mock.patch.object(H, "final_take", lambda ws, item: ("/srv/vsl/take.mp4", {"recording_id": "rec1"})), \
             mock.patch.object(H, "send", lambda *a, **k: calls.append((a, k)) or {"email_id": "g9"}):
            r = FU.send("dryrun", t)
        self.assertEqual(r["sent"], "video")
        self.assertEqual(calls[0][1]["followup_touch"]["id"], t, "the video IS the day-7 follow-up, in the offer's thread")

    def test_result_uses_only_real_records(self):
        i = self.f.add_item("funding")
        self.head(i)
        t = self.fu(i, "fu_3", "result")
        self.model({"has_new": False, "new_thing": "", "line1": "", "line2": ""})
        with mock.patch.object(FU, "results_text", lambda: "- Polymarket market-maker bot (contract, via upwork); delivered and paid: M1"):
            FU.send("dryrun", t)
        self.assertIn("Polymarket market-maker bot", self.prompts[0])
        self.assertEqual(self.f.touches[t]["status"], "cancelled", "no similar record -> no email")


if __name__ == "__main__":
    unittest.main()
