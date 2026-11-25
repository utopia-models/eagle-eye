import subprocess, sys, unittest
from pathlib import Path
T = Path(__file__).resolve().parents[1] / "vsl_take_analyze.py"


class TakeAnalyze(unittest.TestCase):
    def test_selftest_flags_section_3_manager(self):
        r = subprocess.run([sys.executable, str(T), "--selftest"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("section 3 flagged", r.stdout)


if __name__ == "__main__":
    unittest.main()
