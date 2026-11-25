"""knowledge#17487: the three package integrity gates and the 9263 regression (the old 521-char text, the old RLY-1050 title)."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import post_integrity as P  # noqa: E402
import script_authoring as A  # noqa: E402

SCRIPTS = HERE.parents[1] / "vsl" / "scripts"
CUES = (SCRIPTS / "9263-v5.cues.md").read_text()
FIX_POST = " ".join(re.findall(r'"([^"]+)"', CUES)) + "\n"   # the verbatim quotes the fixed package cites
FULL = ("Project Overview. We run a property company and built Relay, which includes an AI assistant. " * 14) + FIX_POST + " That is all.\n"


class Gate1(unittest.TestCase):
    def test_old_521_char_text_fails(self):
        old = (SCRIPTS / "9263-v3.package" / "job-post.txt").read_text()
        self.assertTrue(P.post_complete(old))
        self.assertTrue(P.post_complete("# Title ## Project Overview We operate a company. The ass"))

    def test_whole_post_passes_and_package_check_refuses_truncated(self):
        self.assertEqual(P.post_complete(FULL), [])
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "post.md").write_text("A short cut. The ass")
            fails = A.check_package(d, "A short cut. The ass")
            self.assertTrue([f for f in fails if f["file"] == "post.md"])


class Gate2(unittest.TestCase):
    def test_rly_1050_title_fails(self):
        self.assertTrue(P.seeded_reasons([{"title": "RLY-1050 Cancel vs Submit"}], FULL))
        self.assertTrue(P.seeded_reasons([{"title": "RLY-1050 Cancel vs Submit", "source": "Prevent skipped steps"}], FULL))

    def test_quoted_seed_passes(self):
        self.assertEqual(P.seeded_reasons([{"title": "Prevent skipped steps", "source": "Prevent skipped steps, incorrect actions, and incomplete tasks."}], FULL), [])


class Gate3(unittest.TestCase):
    def test_v5_passes_and_v4_fails_by_row(self):
        v5 = (SCRIPTS / "9263-v5.md").read_text()
        self.assertEqual(P.claims_reasons(v5, CUES, FULL), [])
        v4 = (SCRIPTS / "9263-v4.md").read_text()
        rs = P.claims_reasons(v4, (SCRIPTS / "9263-v4.cues.md").read_text(), FULL)
        self.assertTrue(any(r.startswith("row 3") for r in rs), rs)

    def test_self_test(self):
        r = subprocess.run([sys.executable, str(HERE / "post_integrity.py"), "--self-test"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
