"""oneshot_revise.py: classify to one artifact, the worker may change only that file, only the affected gates re-run, a failed gate restores the
files, evidence and a reload request are written (Tyler 2026-11-22 6:50 AM ET). The self-test holds the cases; this runs it under the suite."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


class OneshotRevise(unittest.TestCase):
    def test_self_test(self):
        r = subprocess.run([sys.executable, str(HERE / "oneshot_revise.py"), "--self-test"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
