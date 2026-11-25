"""oneshot_delay.py: every minute after READY is exactly one tag (recording > revision > waiting), build time is untouched, test revisions are
excluded, the weekly report feeds the gate that would have caught each revision back (Tyler 2026-11-22 6:55 AM ET). The self-test holds the cases."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


class OneshotDelay(unittest.TestCase):
    def test_self_test(self):
        r = subprocess.run([sys.executable, str(HERE / "oneshot_delay.py"), "--self-test"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("self-test PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
