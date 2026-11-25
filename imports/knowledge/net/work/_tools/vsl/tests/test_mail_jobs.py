"""The mail-sourced path (Architect 16665): Upwork job-match mail -> a job at needs_description -> queued once the post text is read by hand."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mail_jobs as M  # noqa: E402
import oneshot_auto as A  # noqa: E402

BODY = ("Job matched [automation] GoHighLevel (GHL) Expert for Ongoing, As-Needed Su... | Hourly: $12.00 - $30.00 · Est. time: More than 6 months | "
        "Payment verified · 4.99 stars · $20K spent · United States | upwork.com/jobs/~022124721370540504047 | mail 37s ago. WRITE THE PACKAGE, do not apply")


class Parse(unittest.TestCase):
    def test_real_mail_text(self):
        p = M.parse_match(BODY, "2026-11-23T04:28:44.5+00:00")
        self.assertEqual((p["job"], p["category"], p["title"]), ("~022124721370540504047", "automation", "GoHighLevel (GHL) Expert for Ongoing, As-Needed Su"))
        self.assertEqual(p["mail_at"], "2026-11-23T04:28:07Z")          # sent_at minus the 37 s the matcher printed
        self.assertIn("Hourly: $12.00 - $30.00", p["pay"])
        self.assertIn("$20K spent", p["client"])

    def test_not_a_match_line(self):
        self.assertIsNone(M.parse_match("Hello there", "2026-11-23T04:28:44+00:00"))
        self.assertIsNone(M.parse_match(BODY, "not a time"))

    def test_fetch_uses_only_upwork_sender_and_sorts_newest_first(self):
        msgs = [{"sender": "upwork", "body": BODY, "sent_at": "2026-11-23T04:28:44+00:00"},
                {"sender": "agent", "body": BODY, "sent_at": "2026-11-23T05:00:00+00:00"},
                {"sender": "upwork", "body": BODY.replace("04047", "09999"), "sent_at": "2026-11-23T03:00:00+00:00"}]

        class R:
            stdout = json.dumps(msgs)
        got = M.fetch_matches(runner=lambda *a, **k: R())
        self.assertEqual([g["job"][-5:] for g in got], ["04047", "09999"])
        self.assertEqual(M.fetch_matches(runner=lambda *a, **k: (_ for _ in ()).throw(OSError("no fleetmail"))), [])


class Flow(unittest.TestCase):
    def setUp(self):
        A.STATE = Path(tempfile.mkdtemp())
        self.hunts = Path(tempfile.mkdtemp())
        self.c = dict(A.cfg(), hunts_dir=str(self.hunts), mail={"max_age_min": 90})
        self.now = A.iso()
        self.m = {"job": "~022124721370540504047", "title": "GoHighLevel (GHL) Expert for Ongoing, As-Needed Su", "pay": "Hourly: $12.00 - $30.00",
                  "client": "Payment verified", "category": "automation", "mail_at": self.now}

    def test_mail_makes_a_job_that_waits_for_the_description(self):
        new = A.scan_mail(self.c, [self.m])
        self.assertEqual(len(new), 1)
        j = A.load_job(new[0]["slug"])
        self.assertEqual((j["state"], j["source"], j["t"]["targeted"]), ("needs_description", "mail", self.now))
        self.assertEqual(A.scan_mail(self.c, [self.m]), [], "deduped by job id")
        self.assertEqual(A.promote_described(self.c), [], "no post text yet: it keeps waiting")

    def test_post_text_read_by_hand_queues_it_and_the_timeline_measures_the_wait(self):
        j = A.scan_mail(self.c, [self.m])[0]
        d = self.hunts / j["slug"]
        d.mkdir()
        (d / "post.md").write_text("We need a GoHighLevel expert for ongoing work. " * 12)
        self.assertEqual(A.promote_described(self.c), [j["slug"]])
        j2 = A.load_job(j["slug"])
        self.assertEqual(j2["state"], "queued")
        self.assertTrue(j2["t"]["description_at"] and j2["mvp_type"] in ("copy", "terminal") and "GoHighLevel" in j2["text"])
        tl = A.timeline(j["slug"])
        self.assertEqual(tl["targeted_at"], self.now)
        self.assertIsNotNone(tl["targeted_to_description_min"])

    def test_too_old_a_role_and_a_short_post(self):
        old = dict(self.m, job="~022100000000000000001", mail_at="2026-11-23T00:00:00Z")
        role = dict(self.m, job="~022100000000000000002", title="Appointment Setter (Phone) for Coaching")
        self.assertEqual(A.scan_mail(self.c, [old, role]), [])
        sk = json.loads((A.STATE / "skipped.json").read_text())
        self.assertIn("min old", sk["~022100000000000000001"])
        self.assertIn("a role", sk["~022100000000000000002"])
        j = A.scan_mail(self.c, [self.m])[0]
        (self.hunts / j["slug"]).mkdir()
        (self.hunts / j["slug"] / "post.md").write_text("too short")
        self.assertEqual(A.promote_described(self.c), [])


if __name__ == "__main__":
    unittest.main()
