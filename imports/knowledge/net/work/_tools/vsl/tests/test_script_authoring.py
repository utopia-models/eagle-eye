"""script_authoring.py + takeflow/rehearsal.py (knowledge#17210): the floor, specificity, agent-talk and contraction rules; the writer loop is
capped at 2 and returns the failing rows; rehearsal.json names the failing row."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "vsl" / "takeflow"))
import rehearsal  # noqa: E402
import script_authoring as SA  # noqa: E402

POST = "We need a Zendesk ticket triage system that routes refund requests to Stripe and escalates chargebacks to the finance lead."
GOOD_ROWS = ["Hi, I'm Tyler Youk, I read your Zendesk triage post."]
BODY = ["Here's the Zendesk queue, refund requests sorted by Stripe status.",
        "A chargeback lands in the escalation lane, the finance lead gets the Stripe charge."] * 8


def pkg(entire_rows, intro_rows=None, extra=""):
    d = Path(tempfile.mkdtemp())
    (d / "entire-script.md").write_text("## [Tyler] Intro (5 s)\n[browser] none\n" + "\n".join(GOOD_ROWS) + "\n\n## [Tyler] The app (60 s)\n[browser] tab 1\n" + "\n".join(entire_rows) + "\n" + extra)
    (d / "intro-script.md").write_text("## [Tyler] Intro (5 s)\n[browser] none\n" + "\n".join(GOOD_ROWS + ["My voice agent will walk you through it."]) + "\n\n## [AI voice] The app (60 s)\n[browser] tab 1\n" + "\n".join(intro_rows or entire_rows) + "\n")
    return d


class Authoring(unittest.TestCase):
    def test_golden_passes(self):
        self.assertEqual(SA.check_package(pkg(BODY), POST), [])

    def test_short_script_fails_floor(self):
        f = SA.check_package(pkg(BODY[:2]), POST)
        self.assertTrue(any("floor" in x["why"] for x in f))

    def test_no_contraction_fails(self):
        rows = [r.replace("Here's", "Here is") for r in BODY]
        d = pkg(rows)
        (d / "entire-script.md").write_text((d / "entire-script.md").read_text().replace("I'm", "I am"))
        self.assertTrue(any("no contraction" in x["why"] for x in SA.check_package(d, POST)))

    def test_generic_row_fails(self):
        f = SA.check_package(pkg(BODY + ["This workflow saves your team time and cost."]), POST)
        self.assertTrue(any("another job" in x["why"] for x in f))

    def test_agent_talk_and_contraction(self):
        f = SA.check_package(pkg(BODY + ["Agent Chief runs the Zendesk queue.", "This Zendesk row is far too long because it keeps adding clauses about the Stripe refund lane and more."]), POST)
        why = " ".join(x["why"] for x in f)
        self.assertIn("agent talk", why)
        self.assertIn("max 14", why)

    def test_loop_returns_failing_rows_max_loops(self):
        p, calls = pkg(BODY[:2]), []
        doc = SA.run_loop(p, POST, lambda _: None, steps={"write": lambda p, t, f: calls.append(f), "review": lambda p, t: []})
        self.assertFalse(doc["pass"])
        self.assertEqual(doc["loops"], SA.MAX_LOOPS)
        self.assertEqual(len(calls), SA.MAX_LOOPS)
        self.assertIn("floor", calls[0][0]["why"])
        self.assertEqual(json.loads((p / "script-check.json").read_text())["pass"], False)

    def test_loop_fixes_then_passes(self):
        p = pkg(BODY[:2])
        def fix(p, t, f):
            (p / "entire-script.md").write_text(pkg(BODY, None, "")  .joinpath("entire-script.md").read_text())
            (p / "intro-script.md").write_text(pkg(BODY).joinpath("intro-script.md").read_text())
        doc = SA.run_loop(p, POST, lambda _: None, steps={"write": fix, "review": lambda p, t: []})
        self.assertTrue(doc["pass"])
        self.assertEqual(doc["loops"], 1)

    def test_reviewer_rows_fail_the_package(self):
        doc = SA.run_loop(pkg(BODY), POST, lambda _: None, steps={"write": lambda *a: None, "review": lambda p, t: [{"file": "entire-script.md", "row": "x", "why": "generic"}]})
        self.assertFalse(doc["pass"])


def actor(row):
    return {"ev": "actor", "row": row}


FX = Path(__file__).resolve().parents[3] / "vsl" / "takeflow" / "tests" / "fixtures"


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.log = [{"ev": "rehearse"}, actor("0.0|start|1000"), actor("0.0|end|2000"), actor("1.0|start|3000"), actor("1.0|end|4000"),
                    actor("1.1|start|5000"), actor("1.1|end|6000"), actor("1.1|tab|diagram|focused|")]

    def test_pass(self):
        r = rehearsal.check(self.d, 3, 80.0, self.log)
        self.assertTrue(r["pass"], r)

    def test_no_motion_fails(self):
        r = rehearsal.check(self.d, 1, 80.0, self.log)
        self.assertFalse(r["checks"]["motion"]["pass"])

    def test_missing_row_named_from_actions_json(self):
        (self.d / "actions.json").write_text(json.dumps({"lines": [{"id": "0.0", "steps": [1]}, {"id": "1.0", "steps": [1]}, {"id": "1.2", "steps": [1]}, {"id": "1.3", "hold": True}]}))
        r = rehearsal.check(self.d, 3, 80.0, self.log)
        self.assertEqual(r["failing_row"]["row"], "1.2")

    def test_black_last_frame_and_no_tab2(self):
        r = rehearsal.check(self.d, 3, 16.0, self.log[:-1])
        self.assertFalse(r["checks"]["last_frame"]["pass"])
        self.assertFalse(r["checks"]["tab2"]["pass"])

    def test_only_last_rehearsal_counts(self):
        r = rehearsal.check(self.d, 3, 80.0, [actor("0.0|start|1"), actor("0.0|end|900"), actor("0.0|tab|diagram|focused|")] + [{"ev": "rehearse"}] + self.log[1:4])
        self.assertFalse(r["checks"]["tab2"]["pass"])

    def test_no_recording_is_pending_not_pass(self):
        r = rehearsal.run(self.d)
        self.assertFalse(r["pass"])
        self.assertIn("pending", r)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg")
    def test_eagles_real_take_9263_passes(self):
        """Eagle's real rehearsal of take 9263 (fleetmail #16265): 3 page changes, a diagram tab row, a log of `id|start|ms` actor rows. The old checker said motion=1, acting 6/7, no tab 2."""
        rec, log = FX / "eagle-9263-r3.mkv", rehearsal.read_log(FX / "eagle-9263-s3-take.jsonl")
        r = rehearsal.check(self.d, rehearsal.scene_count(rec), rehearsal.last_frame_luma(rec), log)
        self.assertTrue(r["pass"], r)
        self.assertEqual(r["checks"]["tab2"]["why"], "tab 2 (diagram) focused at row 2.0")


if __name__ == "__main__":
    unittest.main()
