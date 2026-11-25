"""Replay tests for Tyler's 2026-11-18 13:35 MT card answers (knowledge#16020).
Run: python3 -m unittest net/work/_tools/vsl/tests/test_vsl_16020_replay.py
 1. no claim gate: a script with an unproven claim and no facts ledger PASSES the gate
 2. length: a 3-minute script passes (the 90 s cap is gone); a 6-minute one still fails (the YouTube ceiling is 5)
 3. the structural rules he gave still fail a script before he records (replay of each broken rule)"""
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("VSL_JUDGE", "off")
import script_check  # noqa: E402

NEXT = "The next build is the invoice module behind this same approval gate, and I can start it the day you reply."


def script(secs=60, body="It reads the mail.", closing=NEXT):
    return (f"# video: x\n## Do not say\n- a price\n## 1 · Opener (5 s)\n[horus] Their post.\nHi, it's Tyler. I read your whole post.\n"
            f"I will show an architecture diagram, then a demo, then what I build next.\n## 2 · Your demo ({secs} s)\n"
            f"(Horus) Here's the demo I built for your post.\n{body}\n## 3 · Next step (10 s)\n{closing}\n")


class Replay(unittest.TestCase):
    def test_baseline_passes(self):
        self.assertEqual(script_check.check(script()), [])

    def test_unproven_claim_is_not_gated(self):
        s = script(body="We have run this for forty clients and it never failed once.")
        self.assertEqual(script_check.check(s, asset=True), [])

    def test_three_minute_upwork_script_passes(self):
        self.assertEqual(script_check.check(script(secs=170)), [])

    def test_six_minute_script_fails(self):
        self.assertTrue(any("length" in r for r in script_check.check(script(secs=340))))

    def test_rules_he_gave_still_fail(self):
        broken = {
            "question": script(body="Which inbox?"),
            "reply ask": script(closing="Reply here and I will send the next build."),
            "fleet talk": script(body="My agents read the mail."),
            "cue shows OCC": script().replace("Here's the demo I built for your post.", "Here's the OCC."),
        }
        for name, s in broken.items():
            self.assertNotEqual(script_check.check(s), [], name)


if __name__ == "__main__":
    unittest.main()
