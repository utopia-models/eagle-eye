#!/usr/bin/env python3
"""upwork_reply.py tests: fake Eagle Eye API, Gmail, model and gates (nothing leaves this process; the seat is never touched).

  python3 -m unittest -v send/test_upwork_reply.py
"""
import os, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("HUNT_SEND_STATE", tempfile.mkdtemp(prefix="ur-test-"))
import upwork_reply as U  # noqa: E402

H = U.H


class Api:
    def __init__(self):
        self.calls, self.people, self.roosts = [], [], []

    def __call__(self, ws, method, path, body=None, idem=None):
        self.calls.append((method, path, body))
        if path.startswith("/rest/people?filter"):
            return {"data": {"people": self.people}}
        if path.startswith("/rest/people"):
            p = {"id": "p1", **body}
            self.people.append(p)
            return {"data": {"createPerson": p}}
        if path.startswith("/rest/roosts?filter"):
            return {"data": {"roosts": self.roosts}}
        if path.startswith("/rest/roosts"):
            r = {"id": "r1", **body}
            self.roosts.append(r)
            return {"data": {"createRoost": r}}
        if path.startswith("/rest/replies?filter"):
            return {"data": {"replies": []}}
        if path.startswith("/rest/replies"):
            return {"data": {"createReply": {"id": "rep1"}}}
        if path.startswith("/rest/touches"):
            return {"data": {"createTouch": {"id": "t1", **body}}}
        return {"data": {}}


class UpworkReply(unittest.TestCase):
    def setUp(self):
        self.api = Api()
        self.sent, self.fm, self.prompts = [], [], []
        for target, name, fn in ((H, "api", self.api), (H, "gmail_send", lambda m, thread_id=None, subject=None: self.sent.append(m) or {"id": "g1", "threadId": "th"}),
                                 (U, "fleetmail", lambda text, deadline: self.fm.append((text, deadline)) or "m1"),
                                 (U, "slots", lambda n=3: ["Sun Nov 22 9:00-10:00"])):
            p = mock.patch.object(target, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def model(self, reply):
        def fake(prompt, schema, model="sonnet"):
            self.prompts.append(prompt)
            return {"reply": reply, "outcome": "positive"}
        p = mock.patch.object(H, "claude_json", fake)
        p.start()
        self.addCleanup(p.stop)

    def gates_ok(self, ok=True):
        p = mock.patch.object(U, "gates", lambda text, client, contract: (ok, [] if ok else [["block", "presend", "URL: cal.com"]]))
        p.start()
        self.addCleanup(p.stop)

    def test_contract_from_roost_stage(self):
        self.assertEqual(U.contract_of({"stage": "contract"}), "active")
        self.assertEqual(U.contract_of({"stage": "hourly"}), "active")
        self.assertEqual(U.contract_of({"stage": "prospect: replied on Upwork"}), "none")

    def test_dry_run_mails_agent_only_and_records_a_drafted_touch_with_the_5_min_deadline(self):
        self.model("Hi Dana,\n\nYes, Shopify works. Want to set up a meeting through Upwork?")
        self.gates_ok()
        r = U.draft("Dana R.", "Can you do Shopify?", received="2026-11-22T01:00:00Z", live=False, ws="dryrun")
        self.assertEqual(self.fm, [], "dry-run never reaches the upwork agent or the seat")
        self.assertEqual(self.sent[0]["To"], "dryrun@example.com")
        self.assertIn(U.SIGN, r["reply"], "signed as the agency (per-hunt identity)")
        touch = next(b for m, p, b in self.api.calls if p.startswith("/rest/touches"))
        self.assertEqual((touch["channel"], touch["status"], touch["details"]["deadline"]), ("upwork", "drafted", "2026-11-22T01:05:00Z"))
        step = next(b for m, p, b in self.api.calls if p.startswith("/rest/nextSteps"))
        self.assertEqual((step["what"], step["owner"], step["dueAt"]), ("Reply", "upwork", "2026-11-22T01:05:00Z"))
        self.assertIn("NO contract yet", self.prompts[0], "pre-contract: the call goes through Upwork's meeting tool")
        self.assertIn("Sun Nov 22 9:00-10:00", self.prompts[0])

    def test_active_contract_offers_the_cal_com_booking_page(self):
        self.model("Hi Mo,\n\nHappy to talk it through: https://utopiamodels.ai/call")
        self.gates_ok()
        U.draft("Mo T.", "Can we talk?", contract="active", live=True, ws="dryrun")
        self.assertIn("https://utopiamodels.ai/call", self.prompts[0])
        self.assertEqual(self.sent, [])
        self.assertIn("SEND in Mo T.'s Upwork room", self.fm[0][0], "live: the seat holder types it, by hand")

    def test_three_refusals_raise_and_nothing_is_sent(self):
        self.model("Hi Dana, book here: cal.com/x")
        self.gates_ok(False)
        with self.assertRaises(RuntimeError):
            U.draft("Dana R.", "hi", live=False, ws="dryrun")
        self.assertEqual((self.sent, self.fm), ([], []))

    def test_gates_run_copygate_and_the_upwork_presend_check(self):
        with mock.patch.object(H, "gate", lambda *a, **k: (True, [])):
            ok, f = U.gates("Hi Dana,\n\nBook at https://cal.com/tyler\n\nTyler Youk, Utopia Models, Inc.", "Dana R.", "none")
        self.assertFalse(ok)
        self.assertTrue(any(x[1] == "presend" for x in f), f)


if __name__ == "__main__":
    unittest.main()
