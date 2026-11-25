"""Tests for the rubric judge, reference match and corpus labels (#15166). The model is a stub keyed on the script text: no network.
Run: python3 -m unittest discover -s net/work/_tools/vsl/tests"""
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import vsl_judge  # noqa: E402
import vsl_labels  # noqa: E402
import vsl_script  # noqa: E402

G = HERE / "golden"


def rows(score):
    return [{"beat": n, **{c: score for c in vsl_judge.CRITERIA}} for n in ("a", "b")]


def stub(good_marker, bias_first=0):
    """A judge that scores the script containing the marker 8 and the other 5, plus a bias for whichever is shown first."""
    def model(p):
        a, b = re.search(r"SCRIPT A:\n(.*?)\n\nSCRIPT B:\n(.*?)\n\nBeats", p, re.S).groups()
        sa = 8 if good_marker in a else 5
        sb = 8 if good_marker in b else 5
        return json.dumps({"a": rows(sa + bias_first), "b": rows(sb), "why": "stub"})
    return model


class Judge(unittest.TestCase):
    def setUp(self):
        self.v14 = vsl_judge.beats((G / "v14_ai_automation.md").read_text())
        self.v12 = vsl_judge.beats((G / "v12_ai_automation.md").read_text())

    def test_beats_parse(self):
        self.assertEqual([b["name"] for b in self.v14][:2], ["The roadmap", "How it fits together"])
        self.assertNotIn("[horus]", " ".join(b["spoken"] for b in self.v14))

    def test_v14_beats_v12_in_both_orderings(self):
        ok, d = vsl_judge.wins_both(self.v14, self.v12, stub("hiring for"))
        self.assertTrue(ok, d)
        self.assertFalse(vsl_judge.wins_both(self.v12, self.v14, stub("hiring for"))[0])

    def test_position_bias_cancels(self):
        x, y, _ = vsl_judge.score_pair(self.v14, self.v12, stub("zzz-nothing", bias_first=3))
        self.assertEqual(x, y)

    def test_match_table_has_provenance_and_skips_self(self):
        rows_, hits = vsl_judge.match_table((G / "v14_ai_automation.md").read_text(), 2)
        self.assertTrue(rows_ and all(r["source"] and r["exemplar"] and r["status"] for r in rows_))
        self.assertNotIn("tests/golden/v14_ai_automation.md", [h["path"] for h in hits])

    def test_known_pairs_are_derived_from_labels(self):
        pairs = vsl_judge.known_pairs()
        self.assertIn(("_tools/vsl/tests/golden/v14_ai_automation.md", "_tools/vsl/tests/golden/v12_ai_automation.md"), pairs)

    def test_calibrate_bar(self):
        rate, res = vsl_judge.calibrate(stub("hiring for"))
        self.assertEqual(rate, 1.0)
        rate, _ = vsl_judge.calibrate(stub("zzz-nothing"))
        self.assertEqual(rate, 0.0)       # a judge that ties everything fails the bar

    def test_judge_stage_in_rewrite_loop(self):
        os.environ["VSL_JUDGE"] = "on"
        self.addCleanup(os.environ.__setitem__, "VSL_JUDGE", "off")
        findings = vsl_script.judge_findings((G / "v12_ai_automation.md").read_text(), stub("zzz-nothing"))
        self.assertTrue(findings and findings[0].startswith("judge:"), findings)
        # a draft that outscores its nearest exemplar in both orderings passes the stage
        self.assertEqual(vsl_script.judge_findings((G / "v14_ai_automation.md").read_text(), stub("Next.js app. A coordinator agent built on Claude")), [])


class Labels(unittest.TestCase):
    def test_db_outcomes_regenerate_labels(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "p.db"
            c = sqlite3.connect(db)
            c.execute("create table proposals(letter_file, hired_at, replied_at, interview_at, call_at, declined_at)")
            c.execute("insert into proposals values('net/work/upwork/letters/x.md', NULL, '2026-11-01', NULL, NULL, NULL)")
            c.commit()
            self.assertEqual(vsl_labels.from_db(db)["upwork/letters/x.md"][0], "accepted")
            c.execute("update proposals set hired_at='2026-11-02'")
            c.commit()
            self.assertEqual(vsl_labels.from_db(db)["upwork/letters/x.md"][0], "won")

    def test_curated_wins_and_gate_rejects(self):
        d = vsl_labels.derive(Path("/nonexistent.db"))
        self.assertNotIn("_tools/vsl/tests/golden/v12_ai_automation.md", d)     # curated row stands
        self.assertTrue(all(v[0] in ("rejected", "won", "accepted") for v in d.values()))



if __name__ == "__main__":
    unittest.main()
